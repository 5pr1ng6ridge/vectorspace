"""Right-side icon drawer backed by sidebar_box.png."""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QEasingCurve, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..resources.paths import asset_path
from .desktop_icon_button import DesktopIconButton


class _SidebarHandle(QWidget):
    clicked = Signal()

    GLYPH_COLOR = QColor("#E4F4FF")
    GLYPH_HOVER_COLOR = QColor("#FFFFFF")
    GLYPH_PRESSED_COLOR = QColor("#9CCAFF")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.PointingHandCursor)
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

        glyph = ">" if self._expanded else "<"
        color = QColor(self.GLYPH_COLOR)
        if self._pressed:
            color = QColor(self.GLYPH_PRESSED_COLOR)
        elif self._hovered:
            color = QColor(self.GLYPH_HOVER_COLOR)

        font = QFont(self.font())
        font.setPixelSize(max(18, int(round(rect.height() * 0.42))))
        font.setBold(True)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setPen(color)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, glyph)


class SidebarDrawer(QWidget):
    """Animated right-side drawer using the provided sidebar box artwork."""

    itemTriggered = Signal(str)
    expandedChanged = Signal(bool)

    DESIGN_WIDTH = 214
    DESIGN_HEIGHT = 584
    DESIGN_PANEL_START_X = 30
    DESIGN_CONTENT_LEFT = 58
    DESIGN_CONTENT_RIGHT = 205
    DESIGN_CONTENT_TOP = 26
    DESIGN_CONTENT_BOTTOM = 24
    DESIGN_HANDLE_RECT = QRect(4, 220, 40, 116)
    TOP_MARGIN_PX = 48
    BOTTOM_MARGIN_PX = 320
    RIGHT_MARGIN_PX = 14
    ANIMATION_DURATION_MS = 440

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)

        self._background_pixmap = QPixmap(str(asset_path("ui", "sidebar_box.png")))
        self._background_scaled = QPixmap()
        self._background_scaled_size: tuple[int, int] | None = None
        self._buttons: list[DesktopIconButton] = []
        self._top_margin = self.TOP_MARGIN_PX
        self._bottom_margin = self.BOTTOM_MARGIN_PX
        self._right_margin = self.RIGHT_MARGIN_PX
        self._expanded = False
        self._collapsed_visible_width = self.DESIGN_PANEL_START_X
        self._anim_from_x = 0
        self._anim_to_x = 0
        self._anim_started_at = 0.0
        self._anim_curve = QEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        self._handle = _SidebarHandle(self)
        self._handle.clicked.connect(self.toggle)
        self._handle.set_expanded(self._expanded)

        self.show()
        self._apply_host_geometry(self._target_x_for_state(self._expanded))

    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def expand(self, *, animated: bool = True) -> None:
        self.set_expanded(True, animated=animated)

    def collapse(self, *, animated: bool = True) -> None:
        self.set_expanded(False, animated=animated)

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
        top_margin: int | None = None,
        bottom_margin: int | None = None,
        right_margin: int | None = None,
    ) -> None:
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

        for raw_item in items:
            key = str(raw_item.get("id", "")).strip()
            if not key:
                continue

            label = str(raw_item.get("label", key))
            button = DesktopIconButton(label, self)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

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
            self._buttons.append(button)

        self._layout_children()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_children()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        self._ensure_scaled_background()
        if self._background_scaled.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(0, 0, self._background_scaled)

    def _on_anim_tick(self) -> None:
        elapsed_ms = (time.monotonic() - self._anim_started_at) * 1000.0
        progress = min(1.0, max(0.0, elapsed_ms / float(self.ANIMATION_DURATION_MS)))
        eased = float(self._anim_curve.valueForProgress(progress))
        next_x = int(round(self._anim_from_x + (self._anim_to_x - self._anim_from_x) * eased))
        self._apply_host_geometry(next_x)
        if progress >= 1.0:
            self._anim_timer.stop()
            self._apply_host_geometry(self._anim_to_x)

    def _ensure_scaled_background(self) -> None:
        target_size = (max(1, self.width()), max(1, self.height()))
        if self._background_scaled_size == target_size and not self._background_scaled.isNull():
            return

        if self._background_pixmap.isNull():
            self._background_scaled = QPixmap()
            self.clearMask()
            self._background_scaled_size = target_size
            return

        self._background_scaled = self._background_pixmap.scaled(
            target_size[0],
            target_size[1],
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        self._background_scaled_size = target_size
        self.setMask(self._background_scaled.mask())

    def _content_rect(self) -> QRect:
        width = max(1, self.width())
        height = max(1, self.height())
        left = int(round(self.DESIGN_CONTENT_LEFT * width / float(self.DESIGN_WIDTH)))
        right = int(round(self.DESIGN_CONTENT_RIGHT * width / float(self.DESIGN_WIDTH)))
        top = int(round(self.DESIGN_CONTENT_TOP * height / float(self.DESIGN_HEIGHT)))
        bottom = int(round(self.DESIGN_CONTENT_BOTTOM * height / float(self.DESIGN_HEIGHT)))
        return QRect(
            left,
            top,
            max(1, right - left),
            max(1, height - top - bottom),
        )

    def _handle_rect(self) -> QRect:
        width = max(1, self.width())
        height = max(1, self.height())
        design_rect = self.DESIGN_HANDLE_RECT
        return QRect(
            int(round(design_rect.x() * width / float(self.DESIGN_WIDTH))),
            int(round(design_rect.y() * height / float(self.DESIGN_HEIGHT))),
            max(1, int(round(design_rect.width() * width / float(self.DESIGN_WIDTH)))),
            max(1, int(round(design_rect.height() * height / float(self.DESIGN_HEIGHT)))),
        )

    def _layout_children(self) -> None:
        self._ensure_scaled_background()
        self._handle.setGeometry(self._handle_rect())
        self._handle.raise_()

        if not self._buttons:
            return

        content_rect = self._content_rect()
        button_count = len(self._buttons)
        slot_height = content_rect.height() / float(button_count)
        button_width = max(72, content_rect.width())
        button_height = max(92, int(round(slot_height)))
        icon_size = max(42, min(button_width - 24, int(round(button_height * 0.7))))
        text_size = max(10, min(18, int(round(slot_height * 0.3))))

        for index, button in enumerate(self._buttons):
            button.set_icon_size((icon_size, icon_size))
            button.set_text_font_size(text_size)
            target_width = button_width
            target_height = button_height
            slot_center_y = content_rect.top() + int(round((index + 0.5) * slot_height))
            x = content_rect.left() + max(0, (content_rect.width() - target_width) // 2)
            y = slot_center_y - target_height // 2
            button.setGeometry(x, y, target_width, target_height)
            button.raise_()

    def _scaled_width_for_height(self, height: int) -> int:
        return max(
            1,
            int(round(height * self.DESIGN_WIDTH / float(self.DESIGN_HEIGHT))),
        )

    def _target_x_for_state(self, expanded: bool) -> int:
        parent = self.parentWidget()
        if parent is None:
            return 0

        total_height = max(1, parent.height() - self._top_margin - self._bottom_margin)
        total_width = self._scaled_width_for_height(total_height)
        collapsed_visible_width = int(
            round(total_width * self.DESIGN_PANEL_START_X / float(self.DESIGN_WIDTH))
        )
        self._collapsed_visible_width = max(1, collapsed_visible_width)
        if expanded:
            return max(0, parent.width() - total_width + 10)
        return max(0, parent.width() - self._right_margin - self._collapsed_visible_width)

    def _apply_host_geometry(self, x: int) -> None:
        parent = self.parentWidget()
        if parent is None:
            return

        total_height = max(1, parent.height() - self._top_margin - self._bottom_margin)
        total_width = self._scaled_width_for_height(total_height)
        y = max(0, self._top_margin)
        next_geometry = QRect(int(x), y, total_width, total_height)
        if self.geometry() == next_geometry:
            return

        previous_size = self.size()
        self.setGeometry(next_geometry)
        if previous_size == next_geometry.size():
            self.update()
