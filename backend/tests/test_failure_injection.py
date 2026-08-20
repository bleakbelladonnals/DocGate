from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.errors import DocGateError
from app.models import (
    AgentOutcome,
    AnnotationImport,
    GenericAnnotation,
    HunkDecisionInput,
    TaskDecisionInput,
)

from .conftest import import_five, make_receipt, replace_lines


def rules(evidence, rule_id, subject_id=None):
    return [c for c in evidence.checks if c.rule_id == rule_id and (subject_id is None or c.subject_id == subject_id)]


def test_fi_01_addressed_without_file_change_fails(svc):
    session, bundle = import_five(svc)
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle))
    evidence = svc.verify(session.session_id)
    assert not evidence.hunks
    assert rules(evidence, "DG-DIFF-001")[0].status == "fail"
    assert all(c.status in {"fail", "uncertain"} for c in rules(evidence, "DG-TASK-002"))


def test_fi_02_only_four_of_five_tasks_modified(svc):
    session, bundle = import_five(svc)
    replace_lines(svc.root / "simple.md", {t.locator.exact_quote: t.locator.exact_quote + " Updated." for t in bundle.tasks[:4]})
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    assert rules(evidence, "DG-TASK-002", bundle.tasks[4].task_id)[0].status == "fail"


def test_fi_03_wrong_duplicate_occurrence_is_not_certain(svc):
    session = svc.create_session("duplicate-paragraphs.md")
    payload = AnnotationImport(adapter="generic", annotations=[GenericAnnotation(id="dup", instruction="Change the second copy.", exact_quote="This paragraph is deliberately repeated.", occurrence=2)])
    bundle = svc.import_annotations(session.session_id, payload)
    path = svc.root / "duplicate-paragraphs.md"; text = path.read_text("utf-8"); path.write_text(text.replace("This paragraph is deliberately repeated.", "Wrong first paragraph changed.", 1), "utf-8")
    receipt = make_receipt(svc, session, bundle, claimed_lines={bundle.tasks[0].task_id:[(3,3)]})
    svc.submit_receipt(session.session_id, receipt); evidence = svc.verify(session.session_id)
    assert not any(a.confidence == "certain" for h in evidence.hunks for a in h.associated_tasks)
    assert any(h.unattributed for h in evidence.hunks)


def test_fi_04_partial_semantics_remains_human_decision(svc):
    session, bundle = import_five(svc); task = bundle.tasks[0]
    replace_lines(svc.root / "simple.md", {task.locator.exact_quote: task.locator.exact_quote + " Part one only."})
    outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}; outcomes[task.task_id] = AgentOutcome.ADDRESSED
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes)); evidence = svc.verify(session.session_id)
    assert rules(evidence, "DG-TASK-002", task.task_id)[0].status == "pass"
    assert not any(c.rule_id.startswith("DG-SEM") for c in evidence.checks)


def test_fi_05_forged_result_hash_is_rejected_with_rule_evidence(svc):
    session, bundle = import_five(svc)
    forged = make_receipt(svc, session, bundle, result_hash="0" * 64)
    with pytest.raises(DocGateError) as caught: svc.submit_receipt(session.session_id, forged)
    assert caught.value.code == "RESULT_HASH_MISMATCH"


def test_fi_06_unrelated_rewrite_is_unattributed(svc):
    session, bundle = import_five(svc); task = bundle.tasks[0]
    replace_lines(svc.root / "simple.md", {task.locator.exact_quote: task.locator.exact_quote + " Updated.", "# DocGate Smoke Document":"# An unrelated rewritten title"})
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    assert any(h.unattributed and "unrelated" in h.after for h in evidence.hunks)
    assert rules(evidence, "DG-SCOPE-001")[0].status == "warning"


def test_fi_07_section_deletion_is_shown_not_auto_accepted(svc):
    session, bundle = import_five(svc); task = bundle.tasks[0]
    replace_lines(svc.root / "simple.md", {task.locator.exact_quote:""})
    outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}; outcomes[task.task_id] = AgentOutcome.ADDRESSED
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes)); evidence = svc.verify(session.session_id)
    assert any(h.before == task.locator.exact_quote and h.after == "" for h in evidence.hunks)
    assert svc.get_detail(session.session_id)["decisions"].decisions == []


def test_fi_08_stale_round_base_is_rejected(svc):
    session, bundle = import_five(svc)
    stale = make_receipt(svc, session, bundle, base_hash="f" * 64)
    with pytest.raises(DocGateError) as caught: svc.submit_receipt(session.session_id, stale)
    assert caught.value.code == "STALE_BASELINE"


def test_fi_09_one_task_can_map_to_multiple_hunks(svc):
    session, bundle = import_five(svc); task = bundle.tasks[0]
    path = svc.root / "simple.md"; text = path.read_text("utf-8").replace("## Reliability", "## Proven Reliability").replace(task.locator.exact_quote, task.locator.exact_quote + " Updated."); path.write_text(text, "utf-8")
    outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}; outcomes[task.task_id] = AgentOutcome.ADDRESSED
    receipt = make_receipt(svc, session, bundle, outcomes=outcomes, claimed_lines={task.task_id:[(3,5)]})
    svc.submit_receipt(session.session_id, receipt); evidence = svc.verify(session.session_id)
    assert sum(any(a.task_id == task.task_id for a in h.associated_tasks) for h in evidence.hunks) >= 2


def test_fi_10_one_hunk_can_map_to_multiple_tasks(svc):
    session = svc.create_session("simple.md")
    quote = "The current workflow keeps every baseline immutable for later review."
    payload = AnnotationImport(adapter="generic", annotations=[GenericAnnotation(id="one", instruction="Add detail.", exact_quote=quote), GenericAnnotation(id="two", instruction="Add metric.", exact_quote=quote)])
    bundle = svc.import_annotations(session.session_id, payload); replace_lines(svc.root / "simple.md", {quote:quote + " Updated once for both tasks."})
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    assert any(len([a for a in h.associated_tasks if a.confidence == "certain"]) == 2 for h in evidence.hunks)


def test_fi_11_move_and_edit_exposes_low_confidence(svc):
    session, bundle = import_five(svc); path = svc.root / "simple.md"; text = path.read_text("utf-8")
    section = "## Acceptance\n\nA session is accepted only after every task and stray change has a decision.\n"
    path.write_text(text.replace(section, "").replace("# DocGate Smoke Document\n", "# DocGate Smoke Document\n\n" + section.replace("decision.", "explicit decision.")), "utf-8")
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    assert any(h.unattributed or any(a.confidence != "certain" for a in h.associated_tasks) for h in evidence.hunks)


def test_fi_12_clarification_without_change_is_valid(svc):
    session, bundle = import_five(svc); outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes)); evidence = svc.verify(session.session_id)
    assert rules(evidence, "DG-DIFF-001")[0].status == "pass"
    assert all(c.status == "pass" for c in rules(evidence, "DG-TASK-002"))


def test_fi_13_source_change_after_verify_blocks_acceptance(svc):
    session, bundle = import_five(svc); replace_lines(svc.root / "simple.md", {t.locator.exact_quote:t.locator.exact_quote + " Updated." for t in bundle.tasks})
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle)); evidence = svc.verify(session.session_id)
    for task in bundle.tasks: svc.decide_task(session.session_id, task.task_id, TaskDecisionInput(decision="accepted"))
    for hunk in evidence.hunks:
        if hunk.unattributed: svc.decide_hunk(session.session_id, hunk.hunk_id, HunkDecisionInput(decision="accepted"))
    (svc.root / "simple.md").write_text((svc.root / "simple.md").read_text("utf-8") + "\nmanual drift\n", "utf-8")
    with pytest.raises(DocGateError) as caught: svc.accept(session.session_id)
    assert caught.value.code == "ACCEPTANCE_BLOCKED" and "DG-BASE-001" in caught.value.details["pending"]


def test_fi_14_rework_reverting_protected_content_is_unattributed(svc):
    session, bundle = import_five(svc); first, second = bundle.tasks[:2]
    replace_lines(svc.root / "simple.md", {first.locator.exact_quote:first.locator.exact_quote + " Accepted change.", second.locator.exact_quote:second.locator.exact_quote + " Needs rework."})
    outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}; outcomes[first.task_id] = outcomes[second.task_id] = AgentOutcome.ADDRESSED
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes)); evidence = svc.verify(session.session_id)
    svc.decide_task(session.session_id, first.task_id, TaskDecisionInput(decision="accepted")); svc.decide_task(session.session_id, second.task_id, TaskDecisionInput(decision="rework_requested"))
    for task in bundle.tasks[2:]: svc.decide_task(session.session_id, task.task_id, TaskDecisionInput(decision="accepted"))
    for h in evidence.hunks:
        if h.unattributed: svc.decide_hunk(session.session_id, h.hunk_id, HunkDecisionInput(decision="accepted"))
    svc.rework(session.session_id); detail = svc.get_detail(session.session_id); active = detail["tasks"]
    replace_lines(svc.root / "simple.md", {first.locator.exact_quote + " Accepted change.": first.locator.exact_quote, second.locator.exact_quote + " Needs rework.": second.locator.exact_quote + " Fixed now."})
    svc.submit_receipt(session.session_id, make_receipt(svc, detail["session"], active)); new_evidence = svc.verify(session.session_id)
    assert any(h.unattributed and "Accepted change" in h.before for h in new_evidence.hunks)


def test_fi_15_decision_atomicity_on_interruption(svc, monkeypatch):
    session, bundle = import_five(svc); outcomes = {t.task_id: AgentOutcome.CLARIFICATION for t in bundle.tasks}
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes)); svc.verify(session.session_id)
    first = svc.decide_task(session.session_id, bundle.tasks[0].task_id, TaskDecisionInput(decision="accepted"))
    from app import storage
    original = storage.os.replace
    monkeypatch.setattr(storage.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("FI-15")))
    with pytest.raises(OSError): svc.decide_task(session.session_id, bundle.tasks[0].task_id, TaskDecisionInput(decision="rework_requested"))
    monkeypatch.setattr(storage.os, "replace", original)
    restored = svc.get_detail(session.session_id)["decisions"].decisions[0]
    assert restored.decision == "accepted" and restored.decision_id == first.decision_id
