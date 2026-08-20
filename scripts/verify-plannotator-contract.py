from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from app.adapters.plannotator import parse_stdout
from app.service import DocGateService

ROOT = Path(__file__).parents[1]

with tempfile.TemporaryDirectory(prefix="docgate-plannotator-") as temporary:
    workspace = Path(temporary)
    shutil.copy(ROOT / "fixtures/simple.md", workspace / "simple.md")
    raw = (ROOT / "fixtures/plannotator/v0.24.2-output.json").read_text("utf-8")
    imported = parse_stdout(raw)
    service = DocGateService(workspace)
    session = service.create_session("simple.md")
    bundle = service.import_annotations(session.session_id, imported)
    assert len(bundle.tasks) == 5
    assert all(task.locator.start_line and task.locator.heading_path for task in bundle.tasks)
    print(json.dumps({"version":"v0.24.2","decision":"annotated","tasks":len(bundle.tasks),"locators":[task.locator.locator_status for task in bundle.tasks]}))
