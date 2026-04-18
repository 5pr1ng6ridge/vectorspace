from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextOption
from PySide6.QtWidgets import QPlainTextEdit

from .crt_text_edit import CrtTextEdit


class SaveSlotView(CrtTextEdit):
    closeRequested = Signal()
    saveRequested = Signal(int)
    loadRequested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._slots: list[dict[str, Any]] = []
        self._selected_slot = 0

        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setCursorWidth(0)

        self._apply_style()
        self._render()

    def set_slots(self, slots: list[dict[str, Any]]) -> None:
        self._slots = list(slots)
        if not self._slots:
            self._selected_slot = 0
        else:
            self._selected_slot = max(0, min(self._selected_slot, len(self._slots) - 1))
        self._render()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._move_cursor_to_top()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() != Qt.NoModifier:
            event.accept()
            return

        key = event.key()
        if key == Qt.Key_Escape:
            self.closeRequested.emit()
            return
        if key == Qt.Key_Up:
            self._move_selection(-1)
            return
        if key == Qt.Key_Down:
            self._move_selection(1)
            return
        if key == Qt.Key_S:
            self.saveRequested.emit(self._selected_slot)
            return
        if key == Qt.Key_L:
            self.loadRequested.emit(self._selected_slot)
            return

        event.accept()

    def _move_selection(self, delta: int) -> None:
        if not self._slots:
            return
        self._selected_slot = (self._selected_slot + delta) % len(self._slots)
        self._render()

    def _render(self) -> None:
        header_lines = [
            "[ SAVE / LOAD ]",
            "",
            "UP/DOWN: SELECT SLOT    S: SAVE    L: LOAD    ESC: BACK",
            "",
        ]

        slot_lines: list[str] = []
        slot_count = max(len(self._slots), 30)
        for slot_index in range(slot_count):
            slot = (
                self._slots[slot_index]
                if slot_index < len(self._slots)
                else {
                    "slot_index": slot_index,
                    "title": f"Archive Slot {slot_index + 1:02d}",
                    "scene_name": "-",
                    "saved_at": "-",
                    "empty": True,
                }
            )
            prefix = ">" if slot_index == self._selected_slot else " "
            scene_name = str(slot.get("scene_name") or "-")
            saved_at = str(slot.get("saved_at") or "-")
            if slot.get("empty", False):
                status = "EMPTY"
            else:
                status = saved_at
            title = str(slot.get("title") or f"Archive Slot {slot_index + 1:02d}")
            slot_lines.append(
                f"{prefix} [{slot_index + 1:02d}] {title:<20} | scene: {scene_name:<18} | {status}"
            )

        self.setPlainText("\n".join(header_lines + slot_lines))
        self._move_cursor_to_top()

    def _move_cursor_to_top(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _apply_style(self) -> None:
        self.apply_crt_style(22)
