from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app
from app.models import AgentOutcome

from .conftest import import_five, make_receipt, replace_lines


def client(workspace):
    return TestClient(create_app(workspace), base_url="http://127.0.0.1:8765")


def test_health_and_empty_sessions(workspace):
    with client(workspace) as api:
        assert api.get("/api/v1/health").json() == {"status":"ok","version":"0.1.0","schema_version":1}
        assert api.get("/api/v1/sessions").json() == {"sessions":[]}


def test_mutation_requires_custom_header_and_loopback_origin(workspace):
    with client(workspace) as api:
        assert api.post("/api/v1/sessions", json={"source_path":"simple.md"}).json()["error"]["code"] == "CSRF_REJECTED"
        response = api.post("/api/v1/sessions", headers={"x-docgate-request":"1","origin":"https://evil.example"}, json={"source_path":"simple.md"})
        assert response.status_code == 403 and response.json()["error"]["code"] == "ORIGIN_REJECTED"
    hostile = TestClient(create_app(workspace), base_url="http://evil.example")
    assert hostile.get("/api/v1/health").json()["error"]["code"] == "HOST_REJECTED"


def test_validation_and_not_found_use_uniform_safe_errors(workspace):
    with client(workspace) as api:
        response = api.post("/api/v1/sessions", headers={"x-docgate-request":"1"}, json={"wrong":"/private/secret.md"})
        assert response.status_code == 422 and set(response.json()["error"]) == {"code","message"}
        response = api.get("/api/v1/sessions/ses_missing")
        body = response.json(); assert response.status_code == 404 and body["error"]["code"] == "SESSION_NOT_FOUND"
        assert str(workspace) not in response.text and "Traceback" not in response.text


def test_api_complete_acceptance_flow_and_idempotent_decision(workspace):
    app = create_app(workspace); svc = app.state.service
    session, bundle = import_five(svc)
    replace_lines(workspace / "simple.md", {task.locator.exact_quote:task.locator.exact_quote + " API update." for task in bundle.tasks})
    receipt = make_receipt(svc, session, bundle)
    headers = {"x-docgate-request":"1"}
    with TestClient(app, base_url="http://127.0.0.1:8765") as api:
        assert api.post(f"/api/v1/sessions/{session.session_id}/receipt", headers=headers, json=receipt.model_dump(mode="json")).status_code == 200
        evidence = api.post(f"/api/v1/sessions/{session.session_id}/verify", headers=headers).json()
        blocked = api.post(f"/api/v1/sessions/{session.session_id}/accept", headers=headers)
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "ACCEPTANCE_BLOCKED"
        decision_ids = []
        for task in bundle.tasks:
            url = f"/api/v1/sessions/{session.session_id}/tasks/{task.task_id}/decision"
            first = api.put(url, headers=headers, json={"decision":"accepted","reason":"checked"}).json()
            second = api.put(url, headers=headers, json={"decision":"accepted","reason":"checked"}).json()
            assert first["decision_id"] == second["decision_id"]
            decision_ids.append(first["decision_id"])
        for hunk in evidence["hunks"]:
            if hunk["unattributed"]:
                api.put(f"/api/v1/sessions/{session.session_id}/hunks/{hunk['hunk_id']}/decision", headers=headers, json={"decision":"accepted"}).raise_for_status()
        accepted = api.post(f"/api/v1/sessions/{session.session_id}/accept", headers=headers)
        assert accepted.status_code == 200 and accepted.json()["session"]["state"] == "accepted"
        refused = api.put(f"/api/v1/sessions/{session.session_id}/tasks/{bundle.tasks[0].task_id}/decision", headers=headers, json={"decision":"rework_requested"})
        assert refused.status_code == 409


def test_verify_is_deterministic(workspace):
    app = create_app(workspace); svc = app.state.service
    session, bundle = import_five(svc); replace_lines(workspace / "simple.md", {bundle.tasks[0].locator.exact_quote:bundle.tasks[0].locator.exact_quote + " deterministic"})
    outcomes = {task.task_id: AgentOutcome.CLARIFICATION for task in bundle.tasks}; outcomes[bundle.tasks[0].task_id] = AgentOutcome.ADDRESSED
    svc.submit_receipt(session.session_id, make_receipt(svc, session, bundle, outcomes=outcomes))
    first = svc.verify(session.session_id); second = svc.verify(session.session_id)
    assert [h.hunk_id for h in first.hunks] == [h.hunk_id for h in second.hunks]
