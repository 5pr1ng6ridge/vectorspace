"""Prologue scene (Python entry).

Current strategy:
- Keep reading `prologue.json` to preserve existing content.
- Allow adding Python logic here incrementally (call nodes, dynamic branching, etc).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_scene() -> dict[str, Any]:
    json_path = Path(__file__).with_suffix(".json")
    with json_path.open("r", encoding="utf-8") as f:
        scene_data: dict[str, Any] = json.load(f)

    # Example: inject Python callable node into existing flow.
    #
    # def on_enter(runner) -> None:
    #     runner.view.set_name("System")
    #
    # scene_data["nodes"]["py_hook"] = {"type": "call", "fn": on_enter}
    # scene_data["flow"].insert(0, "py_hook")

    return scene_data
