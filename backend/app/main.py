from __future__ import annotations

import os
from pathlib import Path

from .api import create_app

workspace = Path(os.environ.get("DOCGATE_WORKSPACE_ROOT", os.getcwd()))
app = create_app(workspace)

