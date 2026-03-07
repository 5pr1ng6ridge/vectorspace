"""脚本执行器。

支持节点类型:
- ``say``: 对话文本（打字机效果 + 支持内联公式/标签）
- ``formula``: 独立公式块
- ``bg``: 背景切换（立即生效，不等待点击）
- ``style``: 动态修改字号/颜色
- ``typing``: 动态修改打字速度
"""

from typing import Any

from PySide6.QtCore import QTimer

from ..ui.dialogue_text import (
    DialogueSegment,
    count_reveal_units,
    parse_dialogue_segments,
)
from ..ui.game_view import GameView


class ScriptRunner:
    """按 ``flow`` 顺序驱动场景节点。"""

    def __init__(self, view: GameView, script_data: dict[str, Any]) -> None:
        self.view = view
        self.script_data = script_data
        self.flow: list[str] = script_data.get("flow", [])
        self.nodes: dict[str, dict[str, Any]] = script_data.get("nodes", {})

        self.index = 0
        self.waiting_for_click = False
        self.typing = False

        # 打字机状态
        self.current_segments: list[DialogueSegment] = []
        self.current_total_units = 0
        self.current_index = 0
        self.type_interval_ms = 30

        self.type_timer = QTimer(view)
        self.type_timer.timeout.connect(self._on_typewriter_tick)

        self.view.advanceRequested.connect(self._on_advance_requested)
        self._apply_defaults()

    def start(self) -> None:
        self.index = 0
        self._show_current_node()

    def _show_current_node(self) -> None:
        """显示当前节点；必要时自动跳转到下一个节点。"""
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
                self.view.show_text("(滚木公式节点)")
            else:
                self.view.show_formula(expr)

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

        if node_type == "style":
            self._apply_style_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type == "typing":
            self._apply_typing_node(node)
            self.index += 1
            self._show_current_node()
            return

        # 未知节点直接跳过，避免卡死流程。
        self.index += 1
        self._show_current_node()

    def _start_typewriter(self, text: str) -> None:
        """开始一段 ``say`` 文本的逐字显示。"""
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
        """点击推进:
        1. 正在打字 -> 直接补全本句
        2. 已显示完成 -> 前进到下一个节点
        """
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

    def _apply_defaults(self) -> None:
        """应用场景级默认配置 ``defaults``。"""
        defaults = self.script_data.get("defaults", {})
        if not isinstance(defaults, dict):
            return

        style_defaults = defaults.get("style")
        if isinstance(style_defaults, dict):
            self._apply_style_node(style_defaults)

        typing_defaults = defaults.get("typing")
        if isinstance(typing_defaults, dict):
            self._apply_typing_node(typing_defaults)

    def _apply_style_node(self, node: dict[str, Any]) -> None:
        """应用样式节点。

        支持字段:
        - ``font_size`` / ``text_size``
        - ``color`` / ``text_color``
        - ``name_font_size`` / ``name_size``
        - ``name_color``
        """
        font_size = self._read_int(node, "font_size", "text_size")
        color = self._read_str(node, "color", "text_color")
        name_font_size = self._read_int(node, "name_font_size", "name_size")
        name_color = self._read_str(node, "name_color")

        self.view.set_dialogue_style(
            font_size=font_size,
            color=color,
            name_font_size=name_font_size,
            name_color=name_color,
        )

    def _apply_typing_node(self, node: dict[str, Any]) -> None:
        """应用打字速度节点。

        支持字段:
        - ``speed_ms`` / ``type_interval_ms`` / ``interval_ms``
        - ``cps`` / ``chars_per_second``（优先转换为 ms）
        """
        interval_ms = self._read_int(
            node, "speed_ms", "type_interval_ms", "interval_ms"
        )
        cps = self._read_float(node, "cps", "chars_per_second")

        if cps is not None and cps > 0:
            interval_ms = max(1, int(round(1000.0 / cps)))

        if interval_ms is None:
            return

        self.type_interval_ms = max(1, int(interval_ms))
        if self.type_timer.isActive():
            self.type_timer.setInterval(self.type_interval_ms)

    @staticmethod
    def _read_str(node: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _read_int(node: dict[str, Any], *keys: str) -> int | None:
        for key in keys:
            value = node.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                try:
                    return int(float(stripped))
                except ValueError:
                    continue
        return None

    @staticmethod
    def _read_float(node: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = node.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                try:
                    return float(stripped)
                except ValueError:
                    continue
        return None
