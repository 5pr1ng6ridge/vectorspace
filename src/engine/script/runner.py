"""脚本执行器。"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from PySide6.QtCore import QTimer

from ..ui.dialogue_text import (
    DialogueSegment,
    count_reveal_units,
    parse_dialogue_segments,
)
from ..ui.game_view import GameView


class ScriptRunner:
    """按 ``flow`` 顺序驱动场景节点。"""

    def __init__(
        self,
        view: GameView,
        script_data: dict[str, Any],
        on_jump: Callable[[str], None] | None = None,
    ) -> None:
        self.view = view
        self.script_data = script_data
        self._on_jump = on_jump
        self._disposed = False
        self.flow: list[str] = script_data.get("flow", [])
        self.nodes: dict[str, dict[str, Any]] = script_data.get("nodes", {})

        self.index = 0
        self.waiting_for_click = False
        self.typing = False
        self.waiting_for_node_animation = False
        self.waiting_for_node_wait = False

        # 打字机状态
        self.current_segments: list[DialogueSegment] = []
        self.current_total_units = 0
        self.current_index = 0
        self.current_pause_points: list[tuple[int, int]] = []
        self.current_pause_cursor = 0
        self.current_speed_points: list[tuple[int, int]] = []
        self.current_speed_cursor = 0
        self.current_unit_boundaries: list[int] = []
        self.current_interval_ms_effective = 30
        self.current_step_by_unit = False
        self.waiting_for_pause = False
        self.type_interval_ms = 30

        self.type_timer = QTimer(view)
        self.type_timer.timeout.connect(self._on_typewriter_tick)

        self.pause_timer = QTimer(view)
        self.pause_timer.setSingleShot(True)
        self.pause_timer.timeout.connect(self._on_pause_timeout)

        self.node_wait_timer = QTimer(view)
        self.node_wait_timer.setSingleShot(True)
        self.node_wait_timer.timeout.connect(self._on_node_wait_timeout)

        self.view.advanceRequested.connect(self._on_advance_requested)
        self._apply_defaults()

    def start(self) -> None:
        if self._disposed:
            return
        self.index = 0
        self.waiting_for_click = False
        self.typing = False
        self.waiting_for_node_animation = False
        self.waiting_for_node_wait = False
        self.waiting_for_pause = False
        self.node_wait_timer.stop()
        self._show_current_node()

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self.type_timer.stop()
        self.pause_timer.stop()
        self.node_wait_timer.stop()
        try:
            self.view.advanceRequested.disconnect(self._on_advance_requested)
        except (TypeError, RuntimeError):
            pass

    def jump(self, scene_name: str) -> bool:
        if self._disposed:
            return False
        target = str(scene_name).strip()
        if not target or self._on_jump is None:
            return False

        self.type_timer.stop()
        self.pause_timer.stop()
        self.node_wait_timer.stop()
        self.waiting_for_click = False
        self.typing = False
        self.waiting_for_node_animation = False
        self.waiting_for_node_wait = False
        self.waiting_for_pause = False

        try:
            self._on_jump(target)
        except Exception as exc:
            print(f"[ScriptRunner] jump failed: {target} ({exc})")
            return False
        return True

    def _show_current_node(self) -> None:
        """显示当前节点；必要时自动跳转到下一个节点。"""
        if self._disposed:
            return

        if self.index >= len(self.flow):
            self.view.set_name("")
            self.view.show_text("(没有了喵，再点也不会有反应的喵)")
            self.waiting_for_click = False
            self.typing = False
            self.waiting_for_node_animation = False
            self.waiting_for_node_wait = False
            self.waiting_for_pause = False
            self.type_timer.stop()
            self.pause_timer.stop()
            self.node_wait_timer.stop()
            return

        node_id = self.flow[self.index]
        node = self.nodes.get(node_id, {})
        node_type = node.get("type")

        if node_type == "say":
            self._start_typewriter(node.get("text", ""))
            self.view.set_name(node.get("speaker", ""))
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

        if node_type in {"wait", "delay", "sleep"}:
            if self._run_wait_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"wait_click", "click_wait", "gap", "interval", "beat"}:
            self._run_wait_click_node()
            return

        if node_type in {"dialogue_ui_show", "ui_show"}:
            if self._run_dialogue_ui_show_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"dialogue_ui_hide", "ui_hide"}:
            if self._run_dialogue_ui_hide_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_register", "extra_textbox_register"}:
            self._run_textbox_register_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_set_text", "textbox_text", "extra_textbox_set_text"}:
            self._run_textbox_set_text_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_show", "extra_textbox_show"}:
            if self._run_textbox_show_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_hide", "extra_textbox_hide"}:
            if self._run_textbox_hide_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_transform", "extra_textbox_transform"}:
            if self._run_textbox_transform_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_remove", "extra_textbox_remove"}:
            self._run_textbox_remove_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type in {"textbox_clear", "extra_textbox_clear"}:
            self.view.clear_extra_textboxes()
            self.index += 1
            self._show_current_node()
            return

        if node_type == "call":
            self._run_call_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_register":
            self._run_image_register_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_show":
            if self._run_image_show_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_hide":
            if self._run_image_hide_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_transform":
            if self._run_image_transform_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_remove":
            self._run_image_remove_node(node)
            self.index += 1
            self._show_current_node()
            return

        if node_type == "image_clear":
            self.view.clear_images()
            self.index += 1
            self._show_current_node()
            return

        if node_type == "jump":
            if self._run_jump_node(node):
                return
            self.index += 1
            self._show_current_node()
            return

        # 未知节点直接跳过，避免流程卡住。
        self.index += 1
        self._show_current_node()

    def _run_call_node(self, node: dict[str, Any]) -> None:
        """执行 Python 回调节点。"""
        callback = node.get("fn") or node.get("callable") or node.get("function")
        if not callable(callback):
            return

        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            callback(self)
            return

        positional_count = 0
        has_varargs = False
        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
                has_varargs = True
                continue
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                positional_count += 1

        if has_varargs or positional_count >= 2:
            callback(self, node)
            return
        if positional_count == 1:
            callback(self)
            return
        callback()

    # ======================对话 UI 动画====================== 

    def _run_wait_node(self, node: dict[str, Any]) -> bool:
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            seconds = self._read_float(node, "seconds", "second", "sec", "s")
            if seconds is not None:
                duration_ms = int(round(float(seconds) * 1000.0))

        if duration_ms is None:
            duration_ms = 0
        duration_ms = max(0, int(duration_ms))

        self.type_timer.stop()
        self.pause_timer.stop()
        self.node_wait_timer.stop()
        self.typing = False
        self.waiting_for_pause = False
        self.waiting_for_click = False
        self.waiting_for_node_animation = False
        self.waiting_for_node_wait = False

        if duration_ms <= 0:
            return False

        self.waiting_for_node_wait = True
        self.node_wait_timer.start(duration_ms)
        return True

    def _run_wait_click_node(self) -> None:
        self.type_timer.stop()
        self.pause_timer.stop()
        self.node_wait_timer.stop()
        self.typing = False
        self.waiting_for_pause = False
        self.waiting_for_node_animation = False
        self.waiting_for_node_wait = False
        self.waiting_for_click = True

    def _run_dialogue_ui_show_node(self, node: dict[str, Any]) -> bool:
        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 220

        pending = self.view.show_dialogue_ui(
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "out_quad",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_dialogue_ui_hide_node(self, node: dict[str, Any]) -> bool:
        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 220

        pending = self.view.hide_dialogue_ui(
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "in_quad",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    # ======================额外文本框======================

    def _run_textbox_register_node(self, node: dict[str, Any]) -> None:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return

        rect_x = self._read_float(node, "rect_x", "x")
        rect_y = self._read_float(node, "rect_y", "y")
        rect_w = self._read_float(node, "rect_w", "width", "w")
        rect_h = self._read_float(node, "rect_h", "height", "h")

        rect_list = node.get("rect")
        if isinstance(rect_list, (list, tuple)) and len(rect_list) >= 4:
            if rect_x is None:
                rect_x = self._to_float(rect_list[0])
            if rect_y is None:
                rect_y = self._to_float(rect_list[1])
            if rect_w is None:
                rect_w = self._to_float(rect_list[2])
            if rect_h is None:
                rect_h = self._to_float(rect_list[3])

        if None in {rect_x, rect_y, rect_w, rect_h}:
            return

        text = node.get("text")
        if text is not None and not isinstance(text, str):
            text = str(text)

        self.view.register_extra_textbox(
            textbox_id=textbox_id,
            rect_x=float(rect_x),
            rect_y=float(rect_y),
            rect_w=float(rect_w),
            rect_h=float(rect_h),
            x=self._read_float(node, "pos_x", "start_x"),
            y=self._read_float(node, "pos_y", "start_y"),
            scale=self._read_float(node, "scale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            z=self._read_int(node, "z"),
            text=text if isinstance(text, str) else None,
            font_size=self._read_int(node, "font_size", "text_size"),
            color=self._read_str(node, "color", "text_color"),
            visible=self._read_bool(node, "visible", "show", default=False),
        )

    def _run_textbox_set_text_node(self, node: dict[str, Any]) -> None:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return

        text_value = node.get("text", "")
        text = text_value if isinstance(text_value, str) else str(text_value)
        visible: bool | None = None
        if any(k in node for k in ("visible", "show")):
            visible = self._read_bool(node, "visible", "show", default=False)
        self.view.set_extra_textbox_text(textbox_id, text, visible=visible)

    def _run_textbox_show_node(self, node: dict[str, Any]) -> bool:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        text = node.get("text")
        if text is not None and not isinstance(text, str):
            text = str(text)

        pending = self.view.show_extra_textbox(
            textbox_id=textbox_id,
            text=text if isinstance(text, str) else None,
            font_size=self._read_int(node, "font_size", "text_size"),
            color=self._read_str(node, "color", "text_color"),
            x=self._read_float(node, "x"),
            y=self._read_float(node, "y"),
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            scale=self._read_float(node, "scale"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            dopacity=self._read_float(node, "dopacity", "dalpha"),
            z=self._read_int(node, "z"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_textbox_hide_node(self, node: dict[str, Any]) -> bool:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        pending = self.view.hide_extra_textbox(
            textbox_id=textbox_id,
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            remove=self._read_bool(node, "remove", "delete", default=False),
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_textbox_transform_node(self, node: dict[str, Any]) -> bool:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        pending = self.view.transform_extra_textbox(
            textbox_id=textbox_id,
            x=self._read_float(node, "x"),
            y=self._read_float(node, "y"),
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            scale=self._read_float(node, "scale"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            dopacity=self._read_float(node, "dopacity", "dalpha"),
            z=self._read_int(node, "z"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_textbox_remove_node(self, node: dict[str, Any]) -> None:
        textbox_id = self._read_str(node, "id", "textbox_id", "name", "key")
        if textbox_id is None:
            return
        self.view.remove_extra_textbox(textbox_id)

    # ======================图像节点====================== 

    def _run_image_register_node(self, node: dict[str, Any]) -> None:
        image_id = self._read_str(node, "id", "image_id", "sprite_id", "name", "key")
        file = self._read_str(node, "file", "path", "src")
        if image_id is None or file is None:
            return

        self.view.register_image(
            image_id=image_id,
            file=file,
            folder=self._read_str(node, "folder", "dir"),
            x=self._read_float(node, "x"),
            y=self._read_float(node, "y"),
            scale=self._read_float(node, "scale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            z=self._read_int(node, "z"),
            anchor_x=self._read_float(node, "anchor_x"),
            anchor_y=self._read_float(node, "anchor_y"),
            visible=self._read_bool(node, "visible", "show", default=False),
        )

    def _run_image_show_node(self, node: dict[str, Any]) -> bool:
        image_id = self._read_str(node, "id", "image_id", "sprite_id", "name", "key")
        if image_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        pending = self.view.show_image(
            image_id=image_id,
            file=self._read_str(node, "file", "path", "src"),
            folder=self._read_str(node, "folder", "dir"),
            x=self._read_float(node, "x"),
            y=self._read_float(node, "y"),
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            scale=self._read_float(node, "scale"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            dopacity=self._read_float(node, "dopacity", "dalpha"),
            z=self._read_int(node, "z"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_image_hide_node(self, node: dict[str, Any]) -> bool:
        image_id = self._read_str(node, "id", "image_id", "sprite_id", "name", "key")
        if image_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        pending = self.view.hide_image(
            image_id=image_id,
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            remove=self._read_bool(node, "remove", "delete", default=False),
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_image_transform_node(self, node: dict[str, Any]) -> bool:
        image_id = self._read_str(node, "id", "image_id", "sprite_id", "name", "key")
        if image_id is None:
            return False

        wait = self._read_bool(node, "wait", "blocking", "block", default=False)
        duration_ms = self._read_int(
            node, "duration_ms", "duration", "time_ms", "time", "ms"
        )
        if duration_ms is None:
            duration_ms = 0

        pending = self.view.transform_image(
            image_id=image_id,
            x=self._read_float(node, "x"),
            y=self._read_float(node, "y"),
            dx=self._read_float(node, "dx"),
            dy=self._read_float(node, "dy"),
            scale=self._read_float(node, "scale"),
            dscale=self._read_float(node, "dscale"),
            opacity=self._read_float(node, "opacity", "alpha"),
            dopacity=self._read_float(node, "dopacity", "dalpha"),
            z=self._read_int(node, "z"),
            duration_ms=max(0, int(duration_ms)),
            easing=self._read_str(node, "easing", "ease") or "linear",
            on_finished=self._resume_after_node_animation if wait else None,
        )

        if wait and pending:
            self.waiting_for_node_animation = True
            return True
        return False

    def _run_image_remove_node(self, node: dict[str, Any]) -> None:
        image_id = self._read_str(node, "id", "image_id", "sprite_id", "name", "key")
        if image_id is None:
            return
        self.view.remove_image(image_id)

    # ======================scene切换====================== 
    
    def _run_jump_node(self, node: dict[str, Any]) -> bool:
        scene_name = self._read_str(
            node,
            "scene",
            "scene_id",
            "scene_name",
            "target",
            "to",
            "ref",
            "file",
        )
        if scene_name is None:
            return False
        return self.jump(scene_name)

    #==========================================================

    def _resume_after_node_animation(self) -> None:
        if self._disposed:
            return
        if not self.waiting_for_node_animation:
            return
        self.waiting_for_node_animation = False
        self.index += 1
        self._show_current_node()

    def _on_node_wait_timeout(self) -> None:
        if self._disposed:
            return
        if not self.waiting_for_node_wait:
            return
        self.waiting_for_node_wait = False
        self.index += 1
        self._show_current_node()

    def _start_typewriter(self, text: str) -> None:
        self.current_segments = parse_dialogue_segments(text)
        self.current_total_units = count_reveal_units(self.current_segments)
        self.current_index = 0
        self.current_pause_points = self._collect_pause_points(self.current_segments)
        self.current_pause_cursor = 0
        self.current_speed_points = self._collect_speed_points(self.current_segments)
        self.current_speed_cursor = 0
        self.current_unit_boundaries = self._collect_unit_boundaries(self.current_segments)
        self.current_interval_ms_effective = max(1, int(self.type_interval_ms))
        self.current_step_by_unit = False
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

        # 启动时立即显示首个单位，让 name 和首字同帧出现。
        self.current_index = self._advance_reveal_progress(self.current_index)
        self.view.show_text_segments(self.current_segments, self.current_index)
        self._apply_speed_changes_up_to_current_index()

        if self._try_pause_at_current_index():
            return

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        self.type_timer.start(self.current_interval_ms_effective)

    def _on_typewriter_tick(self) -> None:
        if self._disposed:
            self.type_timer.stop()
            return
        if not self.typing:
            self.type_timer.stop()
            return

        if self.waiting_for_pause:
            self.type_timer.stop()
            return

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        self.current_index = self._advance_reveal_progress(self.current_index)
        self.view.show_text_segments(self.current_segments, self.current_index)
        self._apply_speed_changes_up_to_current_index()

        if self._try_pause_at_current_index():
            return

        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()

    def _on_pause_timeout(self) -> None:
        if self._disposed:
            return
        if not self.typing:
            return

        self.waiting_for_pause = False
        self._apply_speed_changes_up_to_current_index()
        if self.current_index >= self.current_total_units:
            self._finish_current_typewriter()
            return

        self.type_timer.start(self.current_interval_ms_effective)

    def _try_pause_at_current_index(self) -> bool:
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

    def _advance_reveal_progress(self, current_index: int) -> int:
        if self.current_step_by_unit:
            return self._next_unit_boundary_after(current_index)
        return min(self.current_total_units, current_index + 1)

    def _next_unit_boundary_after(self, current_index: int) -> int:
        for boundary in self.current_unit_boundaries:
            if boundary > current_index:
                return boundary
        return self.current_total_units

    def _apply_speed_changes_up_to_current_index(self) -> None:
        changed = False
        while self.current_speed_cursor < len(self.current_speed_points):
            unit_index, interval_ms = self.current_speed_points[self.current_speed_cursor]
            if unit_index > self.current_index:
                break
            if int(interval_ms) == -1:
                self.current_step_by_unit = True
            else:
                self.current_step_by_unit = False
                self.current_interval_ms_effective = max(1, int(interval_ms))
            self.current_speed_cursor += 1
            changed = True

        if changed and self.type_timer.isActive():
            self.type_timer.setInterval(self.current_interval_ms_effective)

    @staticmethod
    def _collect_pause_points(segments: list[DialogueSegment]) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        unit_index = 0

        for segment in segments:
            if segment.kind == "text":
                unit_index += len(segment.content)
                continue

            if segment.kind in {"formula", "formula_display"}:
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
        points: list[tuple[int, int]] = []
        unit_index = 0

        for segment in segments:
            if segment.kind == "text":
                unit_index += len(segment.content)
                continue

            if segment.kind in {"formula", "formula_display"}:
                unit_index += 1
                continue

            if segment.kind != "speed":
                continue

            try:
                parsed_interval = int(segment.content)
            except ValueError:
                continue

            if parsed_interval != -1:
                parsed_interval = max(1, parsed_interval)

            if points and points[-1][0] == unit_index:
                points[-1] = (unit_index, parsed_interval)
            else:
                points.append((unit_index, parsed_interval))

        return points

    @staticmethod
    def _collect_unit_boundaries(segments: list[DialogueSegment]) -> list[int]:
        boundaries: list[int] = []
        unit_index = 0

        for segment in segments:
            if segment.kind == "text":
                if segment.content:
                    unit_index += len(segment.content)
                    boundaries.append(unit_index)
                continue

            if segment.kind in {"formula", "formula_display"}:
                unit_index += 1
                boundaries.append(unit_index)

        return boundaries

    def _on_advance_requested(self) -> None:
        if self._disposed:
            return
        if self.typing:
            self._jump_to_next_pause_or_finish()
            return

        if self.waiting_for_node_wait:
            return

        if self.waiting_for_node_animation:
            return

        if self.waiting_for_click:
            self.waiting_for_click = False
            self.index += 1
            self._show_current_node()

    def _apply_defaults(self) -> None:
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

    @staticmethod
    def _read_bool(node: dict[str, Any], *keys: str, default: bool = False) -> bool:
        for key in keys:
            value = node.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
        return default

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return float(stripped)
            except ValueError:
                return None
        return None
