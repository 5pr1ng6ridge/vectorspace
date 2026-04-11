"""Python scene authoring helpers."""

from __future__ import annotations

from typing import Any, Callable

SceneNode = dict[str, Any]
SceneCallable = Callable[..., Any]


class SceneBuilder:
    """Build a scene using a linear Python DSL.

    The result is a dict with ``id``, ``defaults`` and ``script``.
    Loader will normalize ``script`` into runner-compatible ``nodes/flow``.
    """

    def __init__(
        self,
        scene_id: str,
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self._scene_id = scene_id
        self._defaults = dict(defaults or {})
        self._script: list[SceneNode | SceneCallable] = []

    def add(self, node: SceneNode | SceneCallable) -> "SceneBuilder":
        self._script.append(node)
        return self

    def bg(self, file: str) -> "SceneBuilder":
        return self.add({"type": "bg", "file": file})

    def say(self, speaker: str, text: str) -> "SceneBuilder":
        return self.add({"type": "say", "speaker": speaker, "text": text})

    def formula(self, latex: str) -> "SceneBuilder":
        return self.add({"type": "formula", "latex": latex})

    def style(
        self,
        *,
        font_size: int | None = None,
        color: str | None = None,
        name_font_size: int | None = None,
        name_color: str | None = None,
    ) -> "SceneBuilder":
        node: SceneNode = {"type": "style"}
        if font_size is not None:
            node["font_size"] = int(font_size)
        if color is not None:
            node["color"] = color
        if name_font_size is not None:
            node["name_font_size"] = int(name_font_size)
        if name_color is not None:
            node["name_color"] = name_color
        return self.add(node)

    def typing(
        self,
        *,
        speed_ms: int | None = None,
        cps: float | None = None,
    ) -> "SceneBuilder":
        node: SceneNode = {"type": "typing"}
        if speed_ms is not None:
            node["speed_ms"] = int(speed_ms)
        if cps is not None:
            node["cps"] = float(cps)
        return self.add(node)

    def call(self, fn: SceneCallable) -> "SceneBuilder":
        return self.add({"type": "call", "fn": fn})

    def build(self) -> dict[str, Any]:
        return {
            "id": self._scene_id,
            "defaults": dict(self._defaults),
            "script": list(self._script),
        }
