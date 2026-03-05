from typing import Any

from PySide6.QtCore import QTimer

from ..latex.renderer import render_latex_block
from ..ui.dialogue_text import (
    DialogueSegment,
    count_reveal_units,
    parse_dialogue_segments,
)
from ..ui.game_view import GameView


class ScriptRunner:
    def __init__(self, view: GameView, script_data: dict[str, Any]) -> None:
        self.view = view
        self.script_data = script_data
        self.flow: list[str] = script_data.get("flow", [])
        self.nodes: dict[str, dict[str, Any]] = script_data.get("nodes", {})

        self.index = 0
        self.waiting_for_click = False
        self.typing = False

        self.current_segments: list[DialogueSegment] = []
        self.current_total_units = 0
        self.current_index = 0
        self.type_interval_ms = 30

        self.type_timer = QTimer(view)
        self.type_timer.timeout.connect(self._on_typewriter_tick)

        self.view.advanceRequested.connect(self._on_advance_requested)

    def start(self) -> None:
        self.index = 0
        self._show_current_node()

    def _show_current_node(self) -> None:
        if self.index >= len(self.flow):
            self.view.set_name("")
            self.view.show_text("(没有了喵、再点也不会有反应的喵)")
            self.waiting_for_click = False
            self.typing = False
            self.type_timer.stop()
            return

        node_id = self.flow[self.index]
        node = self.nodes.get(node_id, {})
        node_type = node.get("type")

        if node_type == "say":
            self.view.set_name(node.get("speaker", ""))
            self._start_typewriter(node.get("text", ""))
            return

        if node_type == "formula":
            self.view.set_name("")
            expr = node.get("latex", "")
            if not expr:
                self.view.show_text("(空公式节点)")
            else:
                self.view.show_formula(render_latex_block(expr))

            self.typing = False
            self.waiting_for_click = True
            return

        if node_type == "bg":
            filename = node.get("file", "")
            if filename:
                self.view.set_background(filename)

            self.index += 1
            self._show_current_node()
            return

        self.index += 1
        self._show_current_node()

    def _start_typewriter(self, text: str) -> None:
        self.current_segments = parse_dialogue_segments(text)
        self.current_total_units = count_reveal_units(self.current_segments)
        self.current_index = 0

        self.typing = True
        self.waiting_for_click = False

        self.view.show_text_segments(self.current_segments, 0)

        self.type_timer.stop()
        if self.current_total_units == 0:
            self.typing = False
            self.waiting_for_click = True
            return

        self.type_timer.start(self.type_interval_ms)

    def _on_typewriter_tick(self) -> None:
        if not self.typing:
            self.type_timer.stop()
            return

        if self.current_index >= self.current_total_units:
            self.type_timer.stop()
            self.typing = False
            self.waiting_for_click = True
            self.view.show_text_segments(self.current_segments)
            return

        self.current_index += 1
        self.view.show_text_segments(self.current_segments, self.current_index)

    def _on_advance_requested(self) -> None:
        if self.typing:
            self.type_timer.stop()
            self.typing = False
            self.waiting_for_click = True
            self.view.show_text_segments(self.current_segments)
            return

        if self.waiting_for_click:
            self.waiting_for_click = False
            self.index += 1
            self._show_current_node()
