from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import typer

from .adapters.plannotator import PLANNOTATOR_VERSION, run as run_plannotator
from .errors import DocGateError
from .models import AnnotationImport, HunkDecisionInput, Receipt, TaskDecisionInput
from .service import DocGateService

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def service() -> DocGateService:
    return DocGateService(Path(os.environ.get("DOCGATE_WORKSPACE_ROOT", os.getcwd())))


def emit(value) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def fail(exc: DocGateError) -> None:
    typer.echo(json.dumps({"error": {"code": exc.code, "message": exc.message, "details": exc.details}}, ensure_ascii=False), err=True)
    raise typer.Exit(1)


@app.command()
def doctor(port: int = 8765) -> None:
    """Check runtimes, pinned Plannotator, port and workspace access without reading documents."""
    command = os.environ.get("DOCGATE_PLANNOTATOR_COMMAND", ".tools/plannotator")
    command_path = command if Path(command).exists() else shutil.which(command)
    plannotator_actual = subprocess.run([command_path, "--version"], capture_output=True, text=True).stdout.strip() if command_path else None
    sock = socket.socket()
    port_free = sock.connect_ex(("127.0.0.1", port)) != 0
    sock.close()
    report = {
        "python": sys.version.split()[0],
        "node": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip() if shutil.which("node") else None,
        "npm": subprocess.run(["npm", "--version"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else None,
        "plannotator": {"expected": PLANNOTATOR_VERSION, "actual": plannotator_actual, "path": command, "available": command_path is not None},
        "port": {"number": port, "free": port_free},
        "workspace": {"writable": os.access(service().root, os.W_OK)},
    }
    emit(report)
    if not (sys.version_info[:2] == (3, 11) and report["node"].startswith("v22") and report["npm"] and report["plannotator"]["available"] and "0.24.2" in (plannotator_actual or "") and port_free):
        raise typer.Exit(1)


@app.command()
def review(document: str, launch_plannotator: bool = typer.Option(True, "--plannotator/--no-plannotator")) -> None:
    """Create an immutable baseline and optionally launch pinned Plannotator."""
    try:
        svc = service(); session = svc.create_session(document)
        if launch_plannotator:
            command = os.environ.get("DOCGATE_PLANNOTATOR_COMMAND", ".tools/plannotator")
            imported = run_plannotator(command, svc.root / session.source_path)
            svc.import_annotations(session.session_id, imported)
        emit(svc.get_detail(session.session_id))
    except DocGateError as exc: fail(exc)


@app.command("import-annotations")
def import_annotations(session_id: str, annotations: Path) -> None:
    try: emit(service().import_annotations(session_id, AnnotationImport.model_validate_json(annotations.read_bytes())))
    except DocGateError as exc: fail(exc)


@app.command()
def brief(session_id: str) -> None:
    try:
        svc = service(); session = svc._load_session(session_id)
        typer.echo(str(svc._round_dir(session) / "agent-brief.md"))
    except DocGateError as exc: fail(exc)


@app.command()
def submit(session_id: str, receipt: Path = typer.Option(..., "--receipt")) -> None:
    try: emit(service().submit_receipt(session_id, Receipt.model_validate_json(receipt.read_bytes())))
    except DocGateError as exc: fail(exc)


@app.command()
def verify(session_id: str) -> None:
    try: emit(service().verify(session_id))
    except DocGateError as exc: fail(exc)


@app.command()
def inspect(session_id: str, frontend_url: str = "http://127.0.0.1:3000") -> None:
    try:
        svc = service(); svc.get_detail(session_id)
        def port_ready(port: int) -> bool:
            with socket.socket() as probe:
                return probe.connect_ex(("127.0.0.1", port)) == 0
        root = Path(__file__).parents[2]
        if not port_ready(8765):
            env = {**os.environ, "DOCGATE_WORKSPACE_ROOT": str(svc.root)}
            subprocess.Popen(
                [str(root / ".venv/bin/uvicorn"), "app.main:app", "--app-dir", str(root / "backend"), "--host", "127.0.0.1", "--port", "8765"],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
            )
        if not port_ready(3000):
            subprocess.Popen(
                ["npm", "run", "dev"], cwd=root / "frontend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
            )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (port_ready(8765) and port_ready(3000)):
            time.sleep(0.1)
        if not (port_ready(8765) and port_ready(3000)):
            raise DocGateError("SERVICE_START_FAILED", "本地 API 或验收页未能在 15 秒内启动。", status=500)
        url = f"{frontend_url}/sessions/{session_id}"
        webbrowser.open(url); typer.echo(url)
    except DocGateError as exc: fail(exc)


@app.command()
def rework(session_id: str) -> None:
    try: emit(service().rework(session_id))
    except DocGateError as exc: fail(exc)


@app.command()
def accept(session_id: str) -> None:
    try: emit(service().accept(session_id))
    except DocGateError as exc: fail(exc)


if __name__ == "__main__":
    app()
