# src/engine/script/loader.py
import json
from pathlib import Path
from typing import Any

def load_scene_script(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)