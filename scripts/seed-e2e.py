from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.models import AnnotationImport, AgentInfo, ClaimedChange, Receipt, ReceiptTask, now_utc
from app.service import DocGateService
from app.storage import sha256_bytes

ROOT = Path(__file__).parents[1]
WORKSPACE = ROOT / "test-results" / "e2e-workspace"


def seed(name: str, service: DocGateService, payload: AnnotationImport) -> str:
    source = WORKSPACE / name
    shutil.copy(ROOT / "fixtures" / "simple.md", source)
    session = service.create_session(name)
    bundle = service.import_annotations(session.session_id, payload)
    text = source.read_text("utf-8")
    for task in bundle.tasks:
        text = text.replace(task.locator.exact_quote, task.locator.exact_quote + " Verified update.")
    text = text.replace("# DocGate Smoke Document", "# DocGate Smoke Document — unrelated title edit")
    source.write_text(text, "utf-8")
    receipt = Receipt(
        session_id=session.session_id,
        round_id=session.active_round_id,
        base_hash=bundle.base_hash,
        result_hash=sha256_bytes(source.read_bytes()),
        agent=AgentInfo(name="e2e-seeder"),
        tasks=[ReceiptTask(
            task_id=task.task_id,
            outcome="addressed",
            summary="Seeded deterministic update.",
            claimed_changes=[ClaimedChange(path=name, start_line=task.locator.start_line or 1, end_line=task.locator.end_line or 1)],
        ) for task in bundle.tasks],
        submitted_at=now_utc(),
    )
    service.submit_receipt(session.session_id, receipt)
    service.verify(session.session_id)
    return session.session_id


if WORKSPACE.exists():
    shutil.rmtree(WORKSPACE)
WORKSPACE.mkdir(parents=True)
service = DocGateService(WORKSPACE)
payload = AnnotationImport.model_validate_json((ROOT / "fixtures" / "annotations" / "simple.json").read_bytes())
ids = {"accept": seed("accept.md", service, payload), "rework": seed("rework.md", service, payload)}
(ROOT / "test-results" / "e2e-sessions.json").write_text(json.dumps(ids), "utf-8")

