from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


class SaveSystem:
    SLOT_COUNT = 30

    def __init__(self, save_dir: str | Path | None = None) -> None:
        if save_dir is None:
            save_dir = Path(__file__).resolve().parents[2] / "game" / "saves"
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def list_slots(self) -> list[dict[str, Any]]:
        slots: list[dict[str, Any]] = []
        for slot_index in range(self.SLOT_COUNT):
            payload = self.load_slot(slot_index)
            if payload is None:
                slots.append(self._build_empty_slot(slot_index))
                continue

            slots.append(
                {
                    "slot_index": slot_index,
                    "title": str(
                        payload.get("title") or self._default_title(slot_index)
                    ),
                    "scene_name": str(payload.get("scene_name") or "-"),
                    "saved_at": str(payload.get("saved_at") or "-"),
                    "empty": False,
                }
            )
        return slots

    def save_slot(self, slot_index: int, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_slot = self._normalize_slot_index(slot_index)
        stored_payload = self._json_safe(deepcopy(payload))
        stored_payload["slot_index"] = normalized_slot
        stored_payload["title"] = str(
            stored_payload.get("title") or self._default_title(normalized_slot)
        )
        stored_payload["saved_at"] = datetime.now().isoformat(
            sep=" ",
            timespec="seconds",
        )

        path = self._slot_path(normalized_slot)
        path.write_text(
            json.dumps(stored_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return stored_payload

    def load_slot(self, slot_index: int) -> dict[str, Any] | None:
        path = self._slot_path(slot_index)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return payload if isinstance(payload, dict) else None

    def _slot_path(self, slot_index: int) -> Path:
        normalized_slot = self._normalize_slot_index(slot_index)
        return self._save_dir / f"slot_{normalized_slot + 1:02d}.json"

    def _normalize_slot_index(self, slot_index: int) -> int:
        value = int(slot_index)
        if value < 0 or value >= self.SLOT_COUNT:
            raise ValueError(f"invalid save slot: {slot_index}")
        return value

    def _build_empty_slot(self, slot_index: int) -> dict[str, Any]:
        return {
            "slot_index": slot_index,
            "title": self._default_title(slot_index),
            "scene_name": "-",
            "saved_at": "-",
            "empty": True,
        }

    @staticmethod
    def _default_title(slot_index: int) -> str:
        return f"Archive Slot {slot_index + 1:02d}"

    def _json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        return str(value)
