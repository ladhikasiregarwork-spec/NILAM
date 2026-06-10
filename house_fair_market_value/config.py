from __future__ import annotations

import json
from pathlib import Path


def load_config(base_dir: Path) -> dict:
    """Load model_config.json located next to the package."""
    path = Path(base_dir) / "model_config.json"
    return json.loads(path.read_text(encoding="utf-8"))
