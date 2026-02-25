from __future__ import annotations

import sys
from pathlib import Path

# Ensure test collection can import top-level packages like `core`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root = str(PROJECT_ROOT)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
