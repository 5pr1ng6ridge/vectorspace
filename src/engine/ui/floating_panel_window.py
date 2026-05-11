"""Window-like draggable panel used by in-game graphical UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPaintEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QToolButton, QWidget

from ..resources.fonts import load_font_family
from ..resources.paths import asset_path


class FloatingPanelWindow(QWidget):
    """A lightweight draggable panel that behaves like an in-game window."""

    activated = Signal()
    closed = Signal()
    positionChanged = Signal(QPoint)

    WINDOW_RADIUS_PX = 16
    WINDOW_PADDING_PX = 14
    TITLE_BAR_HEIGHT_PX = 46
    CONTENT_INSET_PX = 16
    CLOSE_BUTTON_SIZE_PX = 28

    FRAME_COLOR = QColor("#0A1921")
    BODY_COLOR = QColor("#0F2029")
    CONTENT_BG_COLOR = QColor("#071015")
    TITLE_TEXT_COLOR = QColor("#E4F4FF")

    def __init__(
        self,
        title: str = "",
        parent=None,
        *,
        accent: QColor | str = "#6AA9FF",
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)

        self._accent_color = self._color_from_value(accent)
        self._content_pixmap = QPixmap()
        self._scaled_content_pixmap = QPixmap()
        self._scaled_content_size: tuple[int, int] | None = None
        self._drag_active = False
        self._drag_offset_global = QPoint()

        self._title_label = QLabel(self)
        self._title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._content_label = QLabel(self)
        self._content_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._content_label.setAlignment(Qt.AlignCenter)

        self._close_button = QToolButton(self)
        self._close_button.setAutoRaise(True)
        self._close_button.setCursor(Qt.PointingHandCursor)
        self._close_button.setText("x")
        self._close_button.clicked.connect(self._close_panel)

        self._apply_fonts()
        self.set_title(title)
        self.set_accent_color(accent)

    @staticmethod
    def _color_from_value(value: QColor | str) -> QColor:
        if isinstance(value, QColor):
            return QColor(value)
        return QColor(str(value))

    @staticmethod
    def _ui_font(pixel_size: int) -> QFont:
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
        font.setPixelSize(max(1, int(pixel_size)))
        if families:
            font.setFamilies(families)
        else:
            font.setFamily("sans-serif")
        return font

    def _accent_with_alpha(self, alpha: int) -> QColor:
        color = QColor(self._accent_color)
        color.setAlpha(max(0, min(255, int(alpha))))
        return color

    def _apply_fonts(self) -> None:
        title_font = self._ui_font(18)
        title_font.setBold(True)
        self._title_label.setFont(title_font)

    def _apply_close_button_style(self) -> None:
        accent = self._accent_with_alpha(116).name(QColor.HexArgb)
        accent_hover = self._accent_with_alpha(164).name(QColor.HexArgb)
        accent_pressed = self._accent_with_alpha(210).name(QColor.HexArgb)
        self._close_button.setStyleSheet(
            f"""
            QToolButton {{
                color: {self.TITLE_TEXT_COLOR.name()};
                background-color: {accent};
                border: 1px solid {self._accent_with_alpha(200).name(QColor.HexArgb)};
                border-radius: 6px;
                font-size: 15px;
                font-weight: 700;
                padding-bottom: 1px;
            }}
            QToolButton:hover {{
                background-color: {accent_hover};
            }}
            QToolButton:pressed {{
                background-color: {accent_pressed};
            }}
            """
        )

    def set_title(self, title: str) -> None:
        self._title_label.setText(str(title))

    def set_accent_color(self, accent: QColor | str) -> None:
        self._accent_color = self._color_from_value(accent)
        self._title_label.setStyleSheet(
            f"color: {self.TITLE_TEXT_COLOR.name()}; background: transparent;"
        )
        self._apply_close_button_style()
        self.update()

    def set_content_pixmap(self, pixmap: QPixmap | str | Path | None) -> None:
        if pixmap is None:
            self._content_pixmap = QPixmap()
        elif isinstance(pixmap, QPixmap):
            self._content_pixmap = QPixmap(pixmap)
        else:
            self._content_pixmap = QPixmap(str(pixmap))
        self._scaled_content_size = None
        self._refresh_scaled_content()

    def set_content_asset(self, *parts: str) -> None:
        self.set_content_pixmap(asset_path(*parts))

    def _outer_rect(self) -> QRect:
        return self.rect().adjusted(1, 1, -1, -1)

    def _title_bar_rect(self) -> QRect:
        outer = self._outer_rect()
        return QRect(
            outer.x() + self.WINDOW_PADDING_PX,
            outer.y() + self.WINDOW_PADDING_PX,
            max(1, outer.width() - self.WINDOW_PADDING_PX * 2),
            self.TITLE_BAR_HEIGHT_PX,
        )

    def _content_box_rect(self) -> QRect:
        title_rect = self._title_bar_rect()
        return QRect(
            title_rect.x(),
            title_rect.bottom() + 10,
            title_rect.width(),
            max(1, self.height() - title_rect.bottom() - self.WINDOW_PADDING_PX - 11),
        )

    def _content_rect(self) -> QRect:
        return self._content_box_rect().adjusted(
            self.CONTENT_INSET_PX,
            self.CONTENT_INSET_PX,
            -self.CONTENT_INSET_PX,
            -self.CONTENT_INSET_PX,
        )

    def _refresh_scaled_content(self) -> None:
        target_rect = self._content_rect()
        if target_rect.width() <= 0 or target_rect.height() <= 0:
            self._content_label.clear()
            return
        if self._content_pixmap.isNull():
            self._content_label.clear()
            return

        target_size = (target_rect.width(), target_rect.height())
        if self._scaled_content_size != target_size:
            self._scaled_content_pixmap = self._content_pixmap.scaled(
                target_size[0],
                target_size[1],
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._scaled_content_size = target_size
        self._content_label.setPixmap(self._scaled_content_pixmap)

    def _layout_children(self) -> None:
        title_rect = self._title_bar_rect()
        content_box_rect = self._content_box_rect()
        content_rect = self._content_rect()
        close_button_y = title_rect.y() + max(
            0,
            (title_rect.height() - self.CLOSE_BUTTON_SIZE_PX) // 2,
        )
        self._close_button.setGeometry(
            title_rect.right() - self.CLOSE_BUTTON_SIZE_PX,
            close_button_y,
            self.CLOSE_BUTTON_SIZE_PX,
            self.CLOSE_BUTTON_SIZE_PX,
        )
        self._title_label.setGeometry(
            title_rect.x() + 14,
            title_rect.y(),
            max(1, title_rect.width() - self.CLOSE_BUTTON_SIZE_PX - 26),
            title_rect.height(),
        )
        self._content_label.setGeometry(content_rect)
        self._refresh_scaled_content()
        self._content_label.raise_()
        self._close_button.raise_()
        self._title_label.raise_()

    def _close_panel(self) -> None:
        self.hide()
        self.closed.emit()

    def _clamp_position(self, position: QPoint) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return QPoint(position)
        max_x = max(0, parent.width() - self.width())
        max_y = max(0, parent.height() - self.height())
        return QPoint(
            max(0, min(max_x, position.x())),
            max(0, min(max_y, position.y())),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_children()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.activated.emit()
        self.setFocus(Qt.MouseFocusReason)

        if (
            event.button() == Qt.LeftButton
            and self._title_bar_rect().contains(event.position().toPoint())
            and not self._close_button.geometry().contains(event.position().toPoint())
        ):
            self._drag_active = True
            self._drag_offset_global = (
                event.globalPosition().toPoint() - self.mapToGlobal(QPoint(0, 0))
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_active:
            parent = self.parentWidget()
            next_global = event.globalPosition().toPoint() - self._drag_offset_global
            next_pos = (
                parent.mapFromGlobal(next_global) if parent is not None else next_global
            )
            clamped_pos = self._clamp_position(next_pos)
            if clamped_pos != self.pos():
                self.move(clamped_pos)
                self.positionChanged.emit(clamped_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._drag_active:
            self._drag_active = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        outer_rect = self._outer_rect()
        if outer_rect.width() <= 0 or outer_rect.height() <= 0:
            return

        title_rect = self._title_bar_rect()
        content_box_rect = self._content_box_rect()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accent_with_alpha(42))
        painter.drawRoundedRect(
            outer_rect.adjusted(3, 3, -3, -3),
            self.WINDOW_RADIUS_PX,
            self.WINDOW_RADIUS_PX,
        )

        painter.setPen(QPen(self._accent_with_alpha(220), 1.6))
        painter.setBrush(self.FRAME_COLOR)
        painter.drawRoundedRect(
            outer_rect,
            self.WINDOW_RADIUS_PX,
            self.WINDOW_RADIUS_PX,
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accent_with_alpha(56))
        painter.drawRoundedRect(title_rect, 10, 10)

        painter.setBrush(self.BODY_COLOR)
        painter.drawRoundedRect(content_box_rect, 12, 12)

        painter.setPen(QPen(self._accent_with_alpha(136), 1.0))
        painter.drawLine(
            title_rect.left() + 10,
            title_rect.bottom() + 6,
            title_rect.right() - 10,
            title_rect.bottom() + 6,
        )

        painter.setPen(QPen(self._accent_with_alpha(120), 1.0))
        painter.setBrush(self.CONTENT_BG_COLOR)
        painter.drawRoundedRect(content_box_rect.adjusted(1, 1, -1, -1), 12, 12)
