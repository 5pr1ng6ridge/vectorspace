from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextOption
from PySide6.QtWidgets import QPlainTextEdit

from .crt_text_edit import CrtTextEdit


class SettingsView(CrtTextEdit):
    closeRequested = Signal()
    settingChanged = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []
        self._selected_item = 0

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

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self._items = [self._normalize_item(item) for item in items]
        if not self._items:
            self._selected_item = 0
        else:
            self._selected_item = max(0, min(self._selected_item, len(self._items) - 1))
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
        if key == Qt.Key_Left:
            self._shift_current_value(-1)
            return
        if key == Qt.Key_Right:
            self._shift_current_value(1)
            return

        event.accept()

    def _move_selection(self, delta: int) -> None:
        if not self._items:
            return
        self._selected_item = (self._selected_item + delta) % len(self._items)
        self._render()

    def _shift_current_value(self, delta: int) -> None:
        if not self._items:
            return

        item = self._items[self._selected_item]
        options = item["options"]
        if not options:
            return

        current_index = int(item.get("selected_index", 0))
        next_index = (current_index + delta) % len(options)
        item["selected_index"] = next_index
        selected_value = str(options[next_index])
        self.settingChanged.emit(str(item["key"]), selected_value)
        self._render()

    def _render(self) -> None:
        header_lines = [
            "[ SETTINGS ]",
            "",
            "UP/DOWN: SELECT ITEM    LEFT/RIGHT: CHANGE VALUE    ESC: BACK",
            "",
        ]

        item_lines: list[str] = []
        for item_index, item in enumerate(self._items):
            prefix = ">" if item_index == self._selected_item else " "
            label = str(item["label"])
            options = item["options"]
            selected_index = int(item.get("selected_index", 0))
            current_value = str(options[selected_index]) if options else "-"
            item_lines.append(f"{prefix} {label:<18} : {current_value}")

        self.setPlainText("\n".join(header_lines + item_lines))
        self._move_cursor_to_top()

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        options = [str(option) for option in item.get("options", [])]
        selected_index = int(item.get("selected_index", 0))
        if options:
            selected_index = max(0, min(selected_index, len(options) - 1))
        else:
            selected_index = 0

        return {
            "key": str(item.get("key", "")),
            "label": str(item.get("label", "")),
            "options": options,
            "selected_index": selected_index,
        }

    def _move_cursor_to_top(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _apply_style(self) -> None:
        self.apply_crt_style(22)
