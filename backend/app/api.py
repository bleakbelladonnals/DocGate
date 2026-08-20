from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .errors import DocGateError, error_body
from .models import (
    ActionResponse,
    AnnotationImport,
    Decision,
    Evidence,
    HealthResponse,
    HunkDecisionInput,
    Receipt,
    Round,
    Session,
    SessionCreateInput,
    SessionDetailResponse,
    SessionListResponse,
    TaskBundle,
    TaskDecisionInput,
)
from .service import DocGateService

LOOPBACK_HOST = re.compile(r"^(localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?$")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(workspace_root: Path) -> FastAPI:
    app = FastAPI(title="DocGate", version=__version__, docs_url="/api/docs", redoc_url=None)
    service = DocGateService(workspace_root)
    app.state.service = service

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        host = request.headers.get("host", "")
        if not LOOPBACK_HOST.fullmatch(host):
            return JSONResponse({"error": {"code": "HOST_REJECTED", "message": "DocGate 只接受本机访问。"}}, status_code=400)
        if request.method in MUTATING:
            origin = request.headers.get("origin")
            if origin:
                origin_host = origin.split("://", 1)[-1].rstrip("/")
                if not LOOPBACK_HOST.fullmatch(origin_host):
                    return JSONResponse({"error": {"code": "ORIGIN_REJECTED", "message": "状态修改只允许来自本机页面。"}}, status_code=403)
            if request.headers.get("x-docgate-request") != "1":
                return JSONResponse({"error": {"code": "CSRF_REJECTED", "message": "缺少本地状态修改防护头。"}}, status_code=403)
        return await call_next(request)

    @app.exception_handler(DocGateError)
    async def docgate_error(_: Request, exc: DocGateError):
        return JSONResponse(error_body(exc), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError):
        return JSONResponse({"error": {"code": "VALIDATION_ERROR", "message": "请求字段缺失或格式错误。"}}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "本地服务发生内部错误，请查看不含正文的服务日志。"}}, status_code=500)

    router = APIRouter(prefix="/api/v1")

    def get_service() -> DocGateService:
        return app.state.service

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(version=__version__)

    @router.get("/sessions", response_model=SessionListResponse)
    def sessions(svc: DocGateService = Depends(get_service)) -> SessionListResponse:
        return SessionListResponse(sessions=svc.list_session_summaries())

    @router.post("/sessions", response_model=Session, status_code=201)
    def create_session(value: SessionCreateInput, svc: DocGateService = Depends(get_service)) -> Session:
        return svc.create_session(value.source_path)

    @router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
    def detail(session_id: str, svc: DocGateService = Depends(get_service)) -> SessionDetailResponse:
        return SessionDetailResponse.model_validate(svc.get_detail(session_id))

    @router.post("/sessions/{session_id}/annotations/import", response_model=TaskBundle)
    def import_annotations(session_id: str, value: AnnotationImport, svc: DocGateService = Depends(get_service)) -> TaskBundle:
        return svc.import_annotations(session_id, value)

    @router.get("/sessions/{session_id}/tasks", response_model=TaskBundle)
    def tasks(session_id: str, svc: DocGateService = Depends(get_service)) -> TaskBundle:
        detail = svc.get_detail(session_id)
        if detail["tasks"] is None:
            raise DocGateError("TASKS_NOT_READY", "该会话尚未生成任务。", status=409)
        return detail["tasks"]

    @router.post("/sessions/{session_id}/receipt", response_model=Round)
    def receipt(session_id: str, value: Receipt, svc: DocGateService = Depends(get_service)) -> Round:
        return svc.submit_receipt(session_id, value)

    @router.post("/sessions/{session_id}/verify", response_model=Evidence)
    def verify(session_id: str, svc: DocGateService = Depends(get_service)) -> Evidence:
        return svc.verify(session_id)

    @router.get("/sessions/{session_id}/evidence", response_model=Evidence)
    def evidence(session_id: str, svc: DocGateService = Depends(get_service)) -> Evidence:
        value = svc.get_detail(session_id)["evidence"]
        if value is None:
            raise DocGateError("EVIDENCE_NOT_READY", "该会话尚未生成证据。", status=409)
        return value

    @router.put("/sessions/{session_id}/tasks/{task_id}/decision", response_model=Decision)
    def decide_task(session_id: str, task_id: str, value: TaskDecisionInput, svc: DocGateService = Depends(get_service)) -> Decision:
        return svc.decide_task(session_id, task_id, value)

    @router.put("/sessions/{session_id}/hunks/{hunk_id}/decision", response_model=Decision)
    def decide_hunk(session_id: str, hunk_id: str, value: HunkDecisionInput, svc: DocGateService = Depends(get_service)) -> Decision:
        return svc.decide_hunk(session_id, hunk_id, value)

    @router.post("/sessions/{session_id}/rework", response_model=ActionResponse)
    def rework(session_id: str, svc: DocGateService = Depends(get_service)) -> ActionResponse:
        return ActionResponse(session=svc.rework(session_id))

    @router.post("/sessions/{session_id}/accept", response_model=ActionResponse)
    def accept(session_id: str, svc: DocGateService = Depends(get_service)) -> ActionResponse:
        return ActionResponse(session=svc.accept(session_id))

    app.include_router(router)
    return app
