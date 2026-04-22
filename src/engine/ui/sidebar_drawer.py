"""Right-side icon drawer for graphical in-game UI."""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QEvent, QEasingCurve, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from .desktop_icon_button import DesktopIconButton


class _SidebarHandle(QWidget):
    clicked = Signal()

    CORNER_RADIUS_PX = 12

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

        self._expanded = False
        self._hovered = False
        self._pressed = False

    def set_expanded(self, expanded: bool) -> None:
        next_value = bool(expanded)
        if next_value == self._expanded:
            return
        self._expanded = next_value
        self.update()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._hovered = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._pressed = True
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(event)

        should_click = self._pressed and self.rect().contains(event.position().toPoint())
        self._pressed = False
        self.update()
        if should_click:
            self.clicked.emit()
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        rect = self.rect().adjusted(1, 1, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        fill_color = QColor(16, 24, 39, 184)
        border_color = QColor(122, 184, 255, 168)
        glyph_color = QColor("#D8EEFF")
        if self._pressed:
            fill_color = QColor(72, 118, 194, 216)
            border_color = QColor(166, 214, 255, 228)
        elif self._hovered:
            fill_color = QColor(30, 41, 62, 210)
            border_color = QColor(148, 202, 255, 204)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(
            float(rect.x()),
            float(rect.y()),
            float(rect.width()),
            float(rect.height()),
            float(self.CORNER_RADIUS_PX),
            float(self.CORNER_RADIUS_PX),
        )
        painter.fillPath(path, fill_color)
        painter.setPen(QPen(border_color, 1.2))
        painter.drawPath(path)

        chevron = QPainterPath()
        inset_x = max(7.0, rect.width() * 0.28)
        inset_y = max(18.0, rect.height() * 0.34)
        top_y = float(rect.top()) + inset_y
        mid_y = float(rect.center().y())
        bottom_y = float(rect.bottom()) - inset_y
        if self._expanded:
            x0 = float(rect.left()) + inset_x
            x1 = float(rect.right()) - inset_x
        else:
            x0 = float(rect.right()) - inset_x
            x1 = float(rect.left()) + inset_x
        chevron.moveTo(x0, top_y)
        chevron.lineTo(x1, mid_y)
        chevron.lineTo(x0, bottom_y)

        painter.setPen(QPen(glyph_color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(chevron)


class SidebarDrawer(QWidget):
    """Animated right-side drawer with vertically stacked desktop icon buttons."""

    itemTriggered = Signal(str)
    expandedChanged = Signal(bool)

    PANEL_WIDTH_PX = 176
    HANDLE_WIDTH_PX = 28
    HANDLE_HEIGHT_PX = 96
    TOP_MARGIN_PX = 48
    BOTTOM_MARGIN_PX = 320
    RIGHT_MARGIN_PX = 14
    PANEL_RADIUS_PX = 20
    PANEL_LAYOUT_MARGIN_PX = 14
    PANEL_LAYOUT_SPACING_PX = 10
    PANEL_BG_COLOR = QColor(10, 16, 28, 176)
    PANEL_BORDER_COLOR = QColor(120, 178, 255, 134)
    PANEL_HILITE_COLOR = QColor(216, 238, 255, 34)
    ANIMATION_DURATION_MS = 220

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)

        self._panel_width = self.PANEL_WIDTH_PX
        self._handle_width = self.HANDLE_WIDTH_PX
        self._handle_height = self.HANDLE_HEIGHT_PX
        self._top_margin = self.TOP_MARGIN_PX
        self._bottom_margin = self.BOTTOM_MARGIN_PX
        self._right_margin = self.RIGHT_MARGIN_PX
        self._expanded = False
        self._buttons: list[DesktopIconButton] = []
        self._anim_from_x = 0
        self._anim_to_x = 0
        self._anim_started_at = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_curve = QEasingCurve(QEasingCurve.Type.OutCubic)

        self._panel = QWidget(self)
        self._panel.setAttribute(Qt.WA_TranslucentBackground, True)
        self._panel.installEventFilter(self)

        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(
            self.PANEL_LAYOUT_MARGIN_PX,
            self.PANEL_LAYOUT_MARGIN_PX,
            self.PANEL_LAYOUT_MARGIN_PX,
            self.PANEL_LAYOUT_MARGIN_PX,
        )
        self._panel_layout.setSpacing(self.PANEL_LAYOUT_SPACING_PX)
        self._panel_layout.addStretch(1)

        self._handle = _SidebarHandle(self)
        self._handle.clicked.connect(self.toggle)
        self._handle.set_expanded(self._expanded)

        self.show()
        self._apply_host_geometry(self._target_x_for_state(self._expanded))

    def eventFilter(self, watched, event) -> bool:
        if watched is self._panel and event.type() in {
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.MouseButtonDblClick,
            QEvent.MouseMove,
        }:
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool, *, animated: bool = True) -> None:
        next_value = bool(expanded)
        current_x = self.x()
        target_x = self._target_x_for_state(next_value)
        if next_value == self._expanded and not self._anim_timer.isActive():
            self._apply_host_geometry(target_x)
            return

        self._expanded = next_value
        self._handle.set_expanded(next_value)
        self.expandedChanged.emit(next_value)

        if not animated:
            self._anim_timer.stop()
            self._apply_host_geometry(target_x)
            return

        self._anim_from_x = current_x
        self._anim_to_x = target_x
        self._anim_started_at = time.monotonic()
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def set_sidebar_metrics(
        self,
        *,
        panel_width: int | None = None,
        handle_width: int | None = None,
        handle_height: int | None = None,
        top_margin: int | None = None,
        bottom_margin: int | None = None,
        right_margin: int | None = None,
    ) -> None:
        if panel_width is not None:
            self._panel_width = max(96, int(panel_width))
        if handle_width is not None:
            self._handle_width = max(18, int(handle_width))
        if handle_height is not None:
            self._handle_height = max(42, int(handle_height))
        if top_margin is not None:
            self._top_margin = max(0, int(top_margin))
        if bottom_margin is not None:
            self._bottom_margin = max(0, int(bottom_margin))
        if right_margin is not None:
            self._right_margin = max(0, int(right_margin))

        self._anim_timer.stop()
        self._apply_host_geometry(self._target_x_for_state(self._expanded))

    def set_items(self, items: list[dict[str, Any]]) -> None:
        for button in self._buttons:
            button.deleteLater()
        self._buttons.clear()

        while self._panel_layout.count() > 0:
            item = self._panel_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for raw_item in items:
            key = str(raw_item.get("id", "")).strip()
            if not key:
                continue

            label = str(raw_item.get("label", key))
            button = DesktopIconButton(label, self._panel)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.set_icon_size((72, 72))
            button.set_text_font_size(12)

            accent = raw_item.get("accent")
            if accent is not None:
                button.set_accent_color(str(accent))

            icon_asset = raw_item.get("icon_asset")
            if isinstance(icon_asset, (list, tuple)) and icon_asset:
                button.set_icon_asset(*[str(part) for part in icon_asset])
            elif raw_item.get("icon") is not None:
                button.set_icon(raw_item.get("icon"))

            tooltip = raw_item.get("tooltip")
            if tooltip is not None:
                button.setToolTip(str(tooltip))

            button.clicked.connect(
                lambda item_key=key: self.itemTriggered.emit(item_key)
            )
            self._panel_layout.addWidget(button)
            self._buttons.append(button)

        self._panel_layout.addStretch(1)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_children()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        panel_rect = self._panel.geometry().adjusted(0, 0, -1, -1)
        if panel_rect.width() <= 0 or panel_rect.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        path = QPainterPath()
        path.addRoundedRect(
            float(panel_rect.x()),
            float(panel_rect.y()),
            float(panel_rect.width()),
            float(panel_rect.height()),
            float(self.PANEL_RADIUS_PX),
            float(self.PANEL_RADIUS_PX),
        )
        painter.fillPath(path, self.PANEL_BG_COLOR)
        painter.setPen(QPen(self.PANEL_BORDER_COLOR, 1.4))
        painter.drawPath(path)

        hilite_rect = panel_rect.adjusted(1, 1, -1, -1)
        if hilite_rect.height() > 12:
            hilite = QPainterPath()
            hilite.addRoundedRect(
                float(hilite_rect.x()),
                float(hilite_rect.y()),
                float(hilite_rect.width()),
                float(max(20, int(hilite_rect.height() * 0.22))),
                float(self.PANEL_RADIUS_PX - 2),
                float(self.PANEL_RADIUS_PX - 2),
            )
            painter.fillPath(hilite, self.PANEL_HILITE_COLOR)

    def _on_anim_tick(self) -> None:
        elapsed_ms = (time.monotonic() - self._anim_started_at) * 1000.0
        progress = min(1.0, max(0.0, elapsed_ms / float(self.ANIMATION_DURATION_MS)))
        eased = float(self._anim_curve.valueForProgress(progress))
        next_x = int(round(self._anim_from_x + (self._anim_to_x - self._anim_from_x) * eased))
        self._apply_host_geometry(next_x)
        if progress >= 1.0:
            self._anim_timer.stop()
            self._apply_host_geometry(self._anim_to_x)

    def _layout_children(self) -> None:
        self._panel.setGeometry(
            self._handle_width,
            0,
            max(1, self.width() - self._handle_width),
            max(1, self.height()),
        )
        handle_height = min(self.height(), self._handle_height)
        handle_y = max(0, (self.height() - handle_height) // 2)
        self._handle.setGeometry(0, handle_y, self._handle_width, handle_height)
        self._handle.raise_()
        self._panel.raise_()

    def _target_x_for_state(self, expanded: bool) -> int:
        parent = self.parentWidget()
        if parent is None:
            return 0

        if expanded:
            return max(
                0,
                parent.width() - self._right_margin - self._panel_width - self._handle_width,
            )
        return max(0, parent.width() - self._right_margin - self._handle_width)

    def _apply_host_geometry(self, x: int) -> None:
        parent = self.parentWidget()
        if parent is None:
            return

        total_width = self._panel_width + self._handle_width
        total_height = max(
            self._handle_height,
            parent.height() - self._top_margin - self._bottom_margin,
        )
        y = max(0, self._top_margin)
        self.setGeometry(int(x), y, total_width, max(1, total_height))
        self._layout_children()
        self.update()
