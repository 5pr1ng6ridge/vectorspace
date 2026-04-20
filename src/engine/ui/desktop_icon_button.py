"""Desktop-style icon button widget for future graphical UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..resources.fonts import load_font_family
from ..resources.paths import asset_path


class DesktopIconButton(QWidget):
    """A reusable desktop icon style button with image, label and single-click."""

    clicked = Signal()
    pressed = Signal()
    released = Signal()

    DEFAULT_ICON_SIZE = QSize(96, 96)
    CONTENT_MARGIN_LEFT = 12
    CONTENT_MARGIN_TOP = 12
    CONTENT_MARGIN_RIGHT = 12
    CONTENT_MARGIN_BOTTOM = 10
    TEXT_GAP_PX = 10
    CORNER_RADIUS_PX = 14
    MIN_TEXT_WIDTH_PX = 112
    DEFAULT_TEXT_COLOR = QColor("#F4F7FF")
    DISABLED_TEXT_COLOR = QColor("#9198A2")
    HOVER_FILL_COLOR = QColor(255, 255, 255, 28)
    HOVER_BORDER_COLOR = QColor(255, 255, 255, 46)
    DISABLED_FILL_COLOR = QColor(255, 255, 255, 10)
    DISABLED_BORDER_COLOR = QColor(255, 255, 255, 18)

    def __init__(
        self,
        text: str = "",
        parent=None,
        *,
        icon: QPixmap | str | Path | None = None,
        icon_size: QSize | tuple[int, int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        self._hovered = False
        self._pressed = False
        self._pointer_down = False
        self._keyboard_pressed = False
        self._selected = False
        self._text = ""
        self._icon_size = self._normalize_size(icon_size or self.DEFAULT_ICON_SIZE)
        self._icon_pixmap = QPixmap()
        self._accent_color = QColor("#5CA6FF")
        self._text_color = QColor(self.DEFAULT_TEXT_COLOR)

        self._icon_label = QLabel(self)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._icon_label.setFixedSize(self._icon_size)

        self._text_label = QLabel(self)
        self._text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self._text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(Qt.NoTextInteraction)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.CONTENT_MARGIN_LEFT,
            self.CONTENT_MARGIN_TOP,
            self.CONTENT_MARGIN_RIGHT,
            self.CONTENT_MARGIN_BOTTOM,
        )
        layout.setSpacing(self.TEXT_GAP_PX)
        layout.addWidget(self._icon_label, alignment=Qt.AlignHCenter)
        layout.addWidget(self._text_label)

        self._apply_text_font()
        self._refresh_text_color()
        self.set_text(text)
        self.set_icon(icon)

    @staticmethod
    def _normalize_size(value: QSize | tuple[int, int]) -> QSize:
        if isinstance(value, QSize):
            return QSize(max(1, value.width()), max(1, value.height()))
        width, height = value
        return QSize(max(1, int(width)), max(1, int(height)))

    @staticmethod
    def _load_ui_font(size: int) -> QFont:
        primary_family = load_font_family("fonts", "FSEX302.ttf")
        fallback_family = load_font_family(
            "fonts",
            "fusion-pixel-12px-monospaced-zh_hans.ttf",
        )

        families: list[str] = []
        if primary_family:
            families.append(primary_family)
        if fallback_family and fallback_family not in families:
            families.append(fallback_family)

        font = QFont()
        font.setPointSize(size)
        if families:
            font.setFamilies(families)
        else:
            font.setFamily("sans-serif")
        return font

    @staticmethod
    def _color_from_value(value: QColor | str) -> QColor:
        if isinstance(value, QColor):
            return QColor(value)
        return QColor(str(value))

    def _accent_with_alpha(self, alpha: int) -> QColor:
        color = QColor(self._accent_color)
        color.setAlpha(max(0, min(255, int(alpha))))
        return color

    def _refresh_icon_pixmap(self) -> None:
        if self._icon_pixmap.isNull():
            self._icon_label.clear()
            return

        scaled = self._icon_pixmap.scaled(
            self._icon_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._icon_label.setPixmap(scaled)

    def _refresh_text_color(self) -> None:
        color = self._text_color if self.isEnabled() else self.DISABLED_TEXT_COLOR
        self._text_label.setStyleSheet(
            f"color: {color.name(QColor.HexArgb)}; background: transparent;"
        )

    def _apply_text_font(self) -> None:
        self._text_label.setFont(self._load_ui_font(14))

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = str(text)
        self._text_label.setText(self._text)
        self.updateGeometry()
        self.update()

    def icon_size(self) -> QSize:
        return QSize(self._icon_size)

    def set_icon_size(self, icon_size: QSize | tuple[int, int]) -> None:
        self._icon_size = self._normalize_size(icon_size)
        self._icon_label.setFixedSize(self._icon_size)
        self._refresh_icon_pixmap()
        self.updateGeometry()
        self.update()

    def set_text_color(self, color: QColor | str) -> None:
        self._text_color = self._color_from_value(color)
        self._refresh_text_color()

    def set_accent_color(self, color: QColor | str) -> None:
        self._accent_color = self._color_from_value(color)
        self.update()

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        next_value = bool(selected)
        if next_value == self._selected:
            return
        self._selected = next_value
        self.update()

    def set_icon(self, icon: QPixmap | str | Path | None) -> None:
        if icon is None:
            self._icon_pixmap = QPixmap()
        elif isinstance(icon, QPixmap):
            self._icon_pixmap = QPixmap(icon)
        else:
            self._icon_pixmap = QPixmap(str(icon))
        self._refresh_icon_pixmap()
        self.update()

    def set_icon_path(self, path: str | Path) -> None:
        self.set_icon(Path(path))

    def set_icon_asset(self, *parts: str) -> None:
        self.set_icon(asset_path(*parts))

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt naming
        super().setEnabled(enabled)
        self._refresh_text_color()
        if enabled:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
            self._pressed = False
            self._pointer_down = False
            self._keyboard_pressed = False
        self.update()

    def sizeHint(self) -> QSize:
        margins_width = self.CONTENT_MARGIN_LEFT + self.CONTENT_MARGIN_RIGHT
        margins_height = self.CONTENT_MARGIN_TOP + self.CONTENT_MARGIN_BOTTOM
        text_width = max(self.MIN_TEXT_WIDTH_PX, self._icon_size.width())
        metrics = self._text_label.fontMetrics()
        text_rect = metrics.boundingRect(
            0,
            0,
            text_width,
            1000,
            Qt.TextWordWrap | Qt.AlignHCenter,
            self._text or " ",
        )
        width = max(self._icon_size.width(), text_rect.width()) + margins_width
        height = (
            self._icon_size.height()
            + self.TEXT_GAP_PX
            + text_rect.height()
            + margins_height
        )
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if not self.isEnabled():
            return
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._hovered = False
        if not self._pointer_down:
            self._pressed = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.isEnabled() or event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        self._pointer_down = True
        self._pressed = True
        self.pressed.emit()
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pointer_down and self.isEnabled():
            next_pressed = self.rect().contains(event.position().toPoint())
            if next_pressed != self._pressed:
                self._pressed = next_pressed
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._pointer_down or event.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(event)

        should_click = self.isEnabled() and self.rect().contains(event.position().toPoint())
        self._pointer_down = False
        self._pressed = False
        self.released.emit()
        self.update()
        if should_click:
            self.clicked.emit()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            self.isEnabled()
            and not event.isAutoRepeat()
            and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)
        ):
            if not self._keyboard_pressed:
                self._keyboard_pressed = True
                self._pressed = True
                self.pressed.emit()
                self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if (
            self._keyboard_pressed
            and not event.isAutoRepeat()
            and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)
        ):
            self._keyboard_pressed = False
            self._pressed = False
            self.released.emit()
            self.clicked.emit()
            self.update()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._keyboard_pressed = False
        if not self._pointer_down:
            self._pressed = False
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_icon_pixmap()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        rect = self.rect().adjusted(1, 1, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        fill_color = QColor(0, 0, 0, 0)
        border_color = QColor(0, 0, 0, 0)
        if not self.isEnabled():
            fill_color = QColor(self.DISABLED_FILL_COLOR)
            border_color = QColor(self.DISABLED_BORDER_COLOR)
        elif self._pressed:
            fill_color = self._accent_with_alpha(128)
            border_color = self._accent_with_alpha(220)
        elif self._selected:
            fill_color = self._accent_with_alpha(92)
            border_color = self._accent_with_alpha(176)
        elif self._hovered:
            fill_color = QColor(self.HOVER_FILL_COLOR)
            border_color = QColor(self.HOVER_BORDER_COLOR)

        if self.hasFocus() and self.isEnabled():
            focus_border = self._accent_with_alpha(228)
            if focus_border.alpha() > border_color.alpha():
                border_color = focus_border

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
        if fill_color.alpha() > 0:
            painter.fillPath(path, fill_color)
        if border_color.alpha() > 0:
            painter.setPen(QPen(border_color, 1.5))
            painter.drawPath(path)
