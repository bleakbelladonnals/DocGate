from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.adapters.plannotator import parse_stdout
from app.errors import DocGateError
from app.models import AnnotationImport, AgentOutcome, ChangeTask, HunkDecisionInput, ReceiptTask, SessionState, TaskDecisionInput
from app.storage import atomic_json, read_model, safe_markdown_path, session_lock

from .conftest import import_five, make_receipt, replace_lines


def test_plannotator_v0242_contract_parses_selected_text_and_comment():
    raw = json.dumps({"decision":"annotated", "feedback":"# File Feedback\n\nI've reviewed this file and have 1 piece of feedback:\n\n## 1. Feedback on: \"selected text\"\n> Make it measurable.\n\n---"})
    result = parse_stdout(raw)
    assert result.adapter == "plannotator"
    assert result.annotations[0].exact_quote == "selected text"
    assert result.annotations[0].instruction == "Make it measurable."


def test_real_plannotator_v0242_five_annotation_fixture():
    raw = (Path(__file__).parents[2] / "fixtures/plannotator/v0.24.2-output.json").read_text("utf-8")
    result = parse_stdout(raw)
    assert len(result.annotations) == 5
    assert len({item.exact_quote for item in result.annotations}) == 5
    assert all(item.instruction for item in result.annotations)


@pytest.mark.parametrize("raw", ["not json", '{"decision":"wat"}', '{"decision":"approved"}'])
def test_plannotator_contract_rejects_incompatible_output(raw):
    with pytest.raises(DocGateError): parse_stdout(raw)


def test_baseline_tasks_brief_and_ids_survive_reload(svc):
    session, bundle = import_five(svc)
    assert len(bundle.tasks) == 5 and len({t.task_id for t in bundle.tasks}) == 5
    round_dir = svc._round_dir(svc._load_session(session.session_id))
    assert (round_dir / "baseline.md").read_bytes() == (svc.root / "simple.md").read_bytes()
    assert (round_dir / "agent-brief.md").exists() and (round_dir / "receipt.schema.json").exists()
    assert svc.get_detail(session.session_id)["tasks"].tasks[0].task_id == bundle.tasks[0].task_id


def test_path_security_and_limits(workspace):
    with pytest.raises(DocGateError, match="工作区"): safe_markdown_path(workspace, "../outside.md", 100)
    outside = workspace.parent / "outside.md"; outside.write_text("outside", "utf-8")
    link = workspace / "link.md"; link.symlink_to(outside)
    with pytest.raises(DocGateError): safe_markdown_path(workspace, "link.md", 100)
    (workspace / "bad.txt").write_text("x", "utf-8")
    with pytest.raises(DocGateError): safe_markdown_path(workspace, "bad.txt", 100)
    (workspace / "bad.md").write_bytes(b"\xff")
    with pytest.raises(DocGateError): safe_markdown_path(workspace, "bad.md", 100)
    (workspace / "large.md").write_text("x" * 101, "utf-8")
    with pytest.raises(DocGateError): safe_markdown_path(workspace, "large.md", 100)


def test_corrupt_json_is_not_overwritten(svc):
    session = svc.create_session("simple.md")
    path = svc._session_dir(session.session_id) / "session.json"
    path.write_text("{broken", "utf-8")
    before = path.read_bytes()
    with pytest.raises(DocGateError) as caught: svc.get_detail(session.session_id)
    assert caught.value.code == "DATA_CORRUPTED" and path.read_bytes() == before


def test_atomic_write_failure_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "value.json"; atomic_json(path, {"schema_version": 1, "value": "old"})
    before = path.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(OSError): atomic_json(path, {"schema_version": 1, "value": "new"})
    assert path.read_bytes() == before


def test_session_lock_conflict(tmp_path):
    with session_lock(tmp_path):
        with pytest.raises(DocGateError) as caught:
            with session_lock(tmp_path): pass
    assert caught.value.code == "SESSION_BUSY"


def test_schema_rejects_unknown_and_missing_notes():
    with pytest.raises(ValidationError):
        AnnotationImport.model_validate({"schema_version":1,"adapter":"generic","annotations":[],"unknown":1})
    with pytest.raises(ValidationError):
        ReceiptTask(task_id="tsk_a", outcome=AgentOutcome.BLOCKED, summary="", claimed_changes=[])
    with pytest.raises(ValidationError):
        ChangeTask.model_validate({"task_id":"tsk_a","instruction":"x","annotation_source":{"adapter":"generic","external_id":"a"},"locator":{"exact_quote":"x","locator_status":"unique"},"created_at":"not-a-time"})
    with pytest.raises(ValidationError):
        ChangeTask.model_validate({"task_id":"tsk_a","instruction":"x","annotation_source":{"adapter":"generic","external_id":"a"},"locator":{"exact_quote":"x","locator_status":"unique"},"created_at":"2026-99-20T08:30:00Z"})


def test_accepted_session_is_immutable(svc):
    session, bundle = import_five(svc)
    replacements = {t.locator.exact_quote: t.locator.exact_quote + " Updated." for t in bundle.tasks}
    replace_lines(svc.root / "simple.md", replacements)
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    for task in bundle.tasks: svc.decide_task(session.session_id, task.task_id, TaskDecisionInput(decision="accepted"))
    for hunk in evidence.hunks:
        if hunk.unattributed: svc.decide_hunk(session.session_id, hunk.hunk_id, HunkDecisionInput(decision="accepted"))
    accepted = svc.accept(session.session_id)
    assert accepted.state == SessionState.ACCEPTED
    with pytest.raises(DocGateError): svc.verify(session.session_id)
