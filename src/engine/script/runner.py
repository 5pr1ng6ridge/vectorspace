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
        self.current_pause_points: list[tuple[int, int]] = []
        self.current_pause_cursor = 0
        self.current_speed_points: list[tuple[int, int]] = []
        self.current_speed_cursor = 0
        self.current_interval_ms_effective = 30
        self.waiting_for_pause = False
        self.type_interval_ms = 30

        self.type_timer = QTimer(view)
        self.type_timer.timeout.connect(self._on_typewriter_tick)

        self.pause_timer = QTimer(view)
        self.pause_timer.setSingleShot(True)
        self.pause_timer.timeout.connect(self._on_pause_timeout)

        self.view.advanceRequested.connect(self._on_advance_requested)
        self._apply_defaults()

    def start(self) -> None:
        self.index = 0
        self._show_current_node()

    def _show_current_node(self) -> None:
        """显示当前节点；必要时自动跳转到下一个节点。"""
        if self.index >= len(self.flow):
            self.view.set_name("")
            self.view.show_text("(没有了喵，再点也不会有反应的喵)")
            self.waiting_for_click = False
            self.typing = False
            self.waiting_for_pause = False
            self.type_timer.stop()
            self.pause_timer.stop()
            return

        node_id = self.flow[self.index]
        node = self.nodes.get(node_id, {})
        node_type = node.get("type")

        if node_type == "say":
            self.view.set_name(node.get("speaker", ""))
            self._start_typewriter(node.get("text", ""))
            return

        if node_type == "formula":
            self.type_timer.stop()
            self.pause_timer.stop()
            self.waiting_for_pause = False
            self.typing = False

            self.view.set_name("")
            expr = node.get("latex", "")
            if not expr:
                self.view.show_text("(空公式节点)")
            else:
                self.view.show_formula(expr)

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
        self.current_pause_points = self._collect_pause_points(self.current_segments)
        self.current_pause_cursor = 0
        self.current_speed_points = self._collect_speed_points(self.current_segments)
        self.current_speed_cursor = 0
        self.current_interval_ms_effective = max(1, int(self.type_interval_ms))
        self.waiting_for_pause = False

        self.typing = True
        self.waiting_for_click = False
        self.view.show_text_segments(self.current_segments, 0)

        self.type_timer.stop()
        self.pause_timer.stop()
        self._apply_speed_changes_up_to_current_index()

        if self._try_pause_at_current_index():
            return

        if self.current_total_units == 0:
            self._finish_current_typewriter()
            return

        self.type_timer.start(self.current_interval_ms_effective)

    def _on_typewriter_tick(self) -> None:
        if not self.typing:
            self.type_timer.stop()
            return

        if self.waiting_for_pause:
            self.type_timer.stop()
            return

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        self.current_index += 1
        self.view.show_text_segments(self.current_segments, self.current_index)
        self._apply_speed_changes_up_to_current_index()

        if self._try_pause_at_current_index():
            return

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()

    def _on_pause_timeout(self) -> None:
        if not self.typing:
            return

        self.waiting_for_pause = False
        self._apply_speed_changes_up_to_current_index()
        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        self.type_timer.start(self.current_interval_ms_effective)

    def _try_pause_at_current_index(self) -> bool:
        """若当前位置命中 pause 点，则停下并等待一段时间。"""
        if self.current_pause_cursor >= len(self.current_pause_points):
            return False

        pause_unit, pause_ms = self.current_pause_points[self.current_pause_cursor]
        if pause_unit != self.current_index:
            return False

        self.current_pause_cursor += 1
        self.waiting_for_pause = True
        self.type_timer.stop()
        self.pause_timer.start(max(0, int(pause_ms)))
        return True

    def _jump_to_next_pause_or_finish(self) -> None:
        """点击时：跳到同节点下一个 pause；若不存在则直接补全本句。"""
        self.pause_timer.stop()
        self.waiting_for_pause = False

        if self.current_pause_cursor >= len(self.current_pause_points):
            self._finish_current_typewriter()
            return

        target_unit, _ = self.current_pause_points[self.current_pause_cursor]
        self.current_index = max(
            self.current_index,
            min(target_unit, self.current_total_units),
        )
        self.view.show_text_segments(self.current_segments, self.current_index)
        self._apply_speed_changes_up_to_current_index()

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        if self._try_pause_at_current_index():
            return

        self.type_timer.start(self.current_interval_ms_effective)

    def _finish_current_typewriter(self) -> None:
        self.type_timer.stop()
        self.pause_timer.stop()
        self.waiting_for_pause = False
        self.typing = False
        self.waiting_for_click = True
        self.current_index = self.current_total_units
        self.view.show_text_segments(self.current_segments)

    def _apply_speed_changes_up_to_current_index(self) -> None:
        """将当前位置之前（含当前位置）的 speed 指令应用到当前打字间隔。"""
        changed = False
        while self.current_speed_cursor < len(self.current_speed_points):
            unit_index, interval_ms = self.current_speed_points[self.current_speed_cursor]
            if unit_index > self.current_index:
                break
            self.current_interval_ms_effective = max(1, int(interval_ms))
            self.current_speed_cursor += 1
            changed = True

        if changed and self.type_timer.isActive():
            self.type_timer.setInterval(self.current_interval_ms_effective)

    @staticmethod
    def _collect_pause_points(segments: list[DialogueSegment]) -> list[tuple[int, int]]:
        """收集当前 say 中的 pause 点，格式为 (reveal_unit_index, duration_ms)。"""
        points: list[tuple[int, int]] = []
        unit_index = 0

        for segment in segments:
            if segment.kind == "text":
                unit_index += len(segment.content)
                continue

            if segment.kind == "formula":
                unit_index += 1
                continue

            if segment.kind != "pause":
                continue

            try:
                duration_ms = max(0, int(segment.content))
            except ValueError:
                continue

            if points and points[-1][0] == unit_index:
                prev_unit, prev_ms = points[-1]
                points[-1] = (prev_unit, prev_ms + duration_ms)
            else:
                points.append((unit_index, duration_ms))

        return points

    @staticmethod
    def _collect_speed_points(segments: list[DialogueSegment]) -> list[tuple[int, int]]:
        """收集当前 say 中的 speed 点，格式为 (reveal_unit_index, interval_ms)。"""
        points: list[tuple[int, int]] = []
        unit_index = 0

        for segment in segments:
            if segment.kind == "text":
                unit_index += len(segment.content)
                continue

            if segment.kind == "formula":
                unit_index += 1
                continue

            if segment.kind != "speed":
                continue

            try:
                interval_ms = max(1, int(segment.content))
            except ValueError:
                continue

            if points and points[-1][0] == unit_index:
                points[-1] = (unit_index, interval_ms)
            else:
                points.append((unit_index, interval_ms))

        return points

    def _on_advance_requested(self) -> None:
        """点击推进。

        1. 正在打字 -> 跳到本节点下一个停顿；若无停顿则直接补全本句
        2. 已显示完成 -> 前进到下一个节点
        """
        if self.typing:
            self._jump_to_next_pause_or_finish()
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
        if self.typing:
            self.current_interval_ms_effective = self.type_interval_ms
            self._apply_speed_changes_up_to_current_index()
        if self.type_timer.isActive():
            self.type_timer.setInterval(self.current_interval_ms_effective)

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
