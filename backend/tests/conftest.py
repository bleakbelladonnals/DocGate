from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.models import AnnotationImport, AgentInfo, AgentOutcome, ClaimedChange, Receipt, ReceiptTask, now_utc
from app.service import DocGateService
from app.storage import sha256_bytes

ROOT = Path(__file__).parents[2]


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    shutil.copy(ROOT / "fixtures/simple.md", tmp_path / "simple.md")
    shutil.copy(ROOT / "fixtures/duplicate-paragraphs.md", tmp_path / "duplicate-paragraphs.md")
    shutil.copy(ROOT / "fixtures/frontmatter.md", tmp_path / "frontmatter.md")
    return tmp_path


@pytest.fixture()
def svc(workspace: Path) -> DocGateService:
    return DocGateService(workspace)


def import_five(svc: DocGateService):
    session = svc.create_session("simple.md")
    payload = AnnotationImport.model_validate_json((ROOT / "fixtures/annotations/simple.json").read_bytes())
    bundle = svc.import_annotations(session.session_id, payload)
    return session, bundle


def make_receipt(svc: DocGateService, session, bundle, *, outcomes: dict[str, AgentOutcome] | None = None, claimed_lines: dict[str, list[tuple[int, int]]] | None = None, base_hash: str | None = None, result_hash: str | None = None) -> Receipt:
    content = (svc.root / session.source_path).read_bytes()
    tasks = []
    for index, task in enumerate(bundle.tasks, 1):
        outcome = (outcomes or {}).get(task.task_id, AgentOutcome.ADDRESSED)
        ranges = (claimed_lines or {}).get(task.task_id, [(task.locator.start_line or index, task.locator.end_line or index)]) if outcome == AgentOutcome.ADDRESSED else []
        tasks.append(ReceiptTask(
            task_id=task.task_id,
            outcome=outcome,
            summary="fixture claim",
            claimed_changes=[ClaimedChange(path=session.source_path, start_line=a, end_line=b) for a, b in ranges],
            notes=None if outcome == AgentOutcome.ADDRESSED else "Needs human clarification.",
        ))
    detail = svc.get_detail(session.session_id)
    return Receipt(
        session_id=session.session_id,
        round_id=detail["session"].active_round_id,
        base_hash=base_hash or bundle.base_hash,
        result_hash=result_hash or sha256_bytes(content),
        agent=AgentInfo(name="pytest"),
        tasks=tasks,
        submitted_at=now_utc(),
    )


def replace_lines(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text("utf-8")
    for before, after in replacements.items():
        text = text.replace(before, after)
    path.write_text(text, "utf-8")

