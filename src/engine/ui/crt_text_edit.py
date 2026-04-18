from __future__ import annotations

from PySide6.QtCore import QRect, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QPlainTextEdit

from ..resources.fonts import load_font_family


class CrtTextEdit(QPlainTextEdit):
    CRT_ANIMATION_INTERVAL_MS = 100
    SCANLINE_SPACING_PX = 3
    SCANLINE_ALPHA = 38
    SCANLINE_SOFT_ALPHA = 20
    CRT_TINT_ALPHA = 8
    VIGNETTE_ALPHA = 110
    APERTURE_GRILLE_ALPHA = 16
    NOISE_ALPHA = 26
    SWEEP_ALPHA = 54
    BORDER_GLOW_ALPHA = 72
    GLASS_GLARE_ALPHA = 36
    CORNER_RADIUS_PX = 18
    ENABLE_CRT_TINT = True
    ENABLE_APERTURE_GRILLE = True
    ENABLE_SCANLINES = True
    ENABLE_VIGNETTE = True
    ENABLE_SCAN_SWEEP = False
    ENABLE_NOISE = False
    ENABLE_GLASS_GLARE = False
    ENABLE_BEZEL = False
    ENABLE_SCANLINE_DRIFT = False

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._crt_phase = 0
        self._crt_static_overlay = QPixmap()
        self._crt_static_overlay_key: tuple[int, int, float] | None = None
        self._crt_anim_timer = QTimer(self)
        self._crt_anim_timer.setInterval(self.CRT_ANIMATION_INTERVAL_MS)
        self._crt_anim_timer.timeout.connect(self._advance_crt_animation)
        if self._has_dynamic_crt_layers():
            self._crt_anim_timer.start()

    def apply_crt_style(self, font_size: int) -> None:
        self.setFont(self._load_terminal_font(font_size))
        self.setCursorWidth(0)
        self.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #08110b;
                color: #d8ffd8;
                border: 1px solid #25422b;
                selection-background-color: rgba(58, 123, 66, 180);
                selection-color: #f3fff3;
            }
            """
        )
        self._invalidate_crt_cache()
        self._refresh_crt_animation_state()

    @staticmethod
    def _load_terminal_font(size: int) -> QFont:
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

        if families:
            font = QFont()
            font.setPointSize(size)
            font.setFamilies(families)
            return font

        if fallback_family:
            return QFont(fallback_family, size)
        return QFont("monospace", size)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_crt_animation_state()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._crt_anim_timer.stop()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._invalidate_crt_cache()

    def _advance_crt_animation(self) -> None:
        if not self._has_dynamic_crt_layers():
            self._crt_anim_timer.stop()
            return

        old_dirty_rect = self._dynamic_crt_dirty_rect_for_phase(self._crt_phase)
        self._crt_phase = (self._crt_phase + 1) % 4096
        if self.viewport().isVisible():
            if self.ENABLE_NOISE or self.ENABLE_SCANLINE_DRIFT:
                self.viewport().update()
                return

            new_dirty_rect = self._dynamic_crt_dirty_rect_for_phase(self._crt_phase)
            dirty_rect = old_dirty_rect.united(new_dirty_rect)
            if dirty_rect.isValid() and not dirty_rect.isEmpty():
                self.viewport().update(dirty_rect.adjusted(-2, -2, 2, 2))
            else:
                self.viewport().update()

    def _invalidate_crt_cache(self) -> None:
        self._crt_static_overlay = QPixmap()
        self._crt_static_overlay_key = None

    def _refresh_crt_animation_state(self) -> None:
        if self._has_dynamic_crt_layers() and self.isVisible():
            if not self._crt_anim_timer.isActive():
                self._crt_anim_timer.start()
            return
        self._crt_anim_timer.stop()

    def _has_dynamic_crt_layers(self) -> bool:
        return any(
            (
                self.ENABLE_SCAN_SWEEP,
                self.ENABLE_NOISE,
                self.ENABLE_SCANLINE_DRIFT,
            )
        )

    def _ensure_crt_static_overlay(self) -> None:
        size = self.viewport().size()
        if size.isEmpty():
            return

        dpr = self.viewport().devicePixelRatioF()
        cache_key = (size.width(), size.height(), dpr)
        if self._crt_static_overlay_key == cache_key and not self._crt_static_overlay.isNull():
            return

        self._crt_static_overlay = self._build_crt_static_overlay()
        self._crt_static_overlay_key = cache_key

    def _build_crt_static_overlay(self) -> QPixmap:
        size = self.viewport().size()
        dpr = self.viewport().devicePixelRatioF()
        pixmap = QPixmap(
            max(1, int(round(size.width() * dpr))),
            max(1, int(round(size.height() * dpr))),
        )
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = QRect(0, 0, size.width(), size.height())
        self._paint_crt_static_layers(painter, rect)
        painter.end()
        return pixmap

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        self._ensure_crt_static_overlay()
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)
        if not self._crt_static_overlay.isNull():
            painter.drawPixmap(0, 0, self._crt_static_overlay)
        if self._has_dynamic_crt_layers():
            self._paint_crt_dynamic_layers(painter)

    def _paint_crt_static_layers(self, painter: QPainter, rect: QRect) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self.ENABLE_CRT_TINT:
            painter.fillRect(rect, QColor(90, 255, 150, self.CRT_TINT_ALPHA))
        if self.ENABLE_GLASS_GLARE:
            self._paint_glass_glare(painter, rect)
        if self.ENABLE_APERTURE_GRILLE:
            self._paint_aperture_grille(painter, rect)
        if self.ENABLE_SCANLINES:
            self._paint_scanlines(painter, rect, phase_offset=0)
        if self.ENABLE_VIGNETTE:
            self._paint_vignette(painter, rect)
        if self.ENABLE_BEZEL:
            self._paint_bezel(painter, rect)
        painter.restore()

    def _paint_crt_dynamic_layers(self, painter: QPainter) -> None:
        rect = self.viewport().rect()
        if rect.isEmpty():
            return

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self.ENABLE_SCAN_SWEEP:
            self._paint_scan_sweep(painter, rect)
        if self.ENABLE_SCANLINES and self.ENABLE_SCANLINE_DRIFT:
            self._paint_scanlines(
                painter,
                rect,
                phase_offset=self._crt_phase % self.SCANLINE_SPACING_PX,
            )
        if self.ENABLE_NOISE:
            self._paint_noise(painter, rect)
        painter.restore()

    def _paint_scan_sweep(self, painter: QPainter, rect) -> None:
        sweep_margin = 140
        sweep_cycle = max(1, rect.height() + sweep_margin * 2)
        sweep_center = rect.top() + ((self._crt_phase * 19) % sweep_cycle) - sweep_margin

        sweep = QLinearGradient(
            rect.left(),
            sweep_center - 90,
            rect.left(),
            sweep_center + 90,
        )
        sweep.setColorAt(0.0, QColor(0, 0, 0, 0))
        sweep.setColorAt(0.15, QColor(80, 255, 150, 0))
        sweep.setColorAt(0.5, QColor(170, 255, 200, self.SWEEP_ALPHA))
        sweep.setColorAt(0.85, QColor(80, 255, 150, 0))
        sweep.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, sweep)

    def _paint_glass_glare(self, painter: QPainter, rect) -> None:
        glare = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        glare.setColorAt(0.0, QColor(255, 255, 255, self.GLASS_GLARE_ALPHA))
        glare.setColorAt(0.08, QColor(240, 255, 245, 10))
        glare.setColorAt(0.3, QColor(160, 255, 200, 0))
        glare.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glare)

        top_glow = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        top_glow.setColorAt(0.0, QColor(255, 255, 255, 18))
        top_glow.setColorAt(0.04, QColor(255, 255, 255, 0))
        top_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, top_glow)

    def _paint_aperture_grille(self, painter: QPainter, rect) -> None:
        for x in range(rect.left(), rect.right(), 6):
            painter.fillRect(
                x,
                rect.top(),
                1,
                rect.height(),
                QColor(100, 255, 140, self.APERTURE_GRILLE_ALPHA),
            )
            if x + 2 < rect.right():
                painter.fillRect(
                    x + 2,
                    rect.top(),
                    1,
                    rect.height(),
                    QColor(40, 160, 80, max(6, self.APERTURE_GRILLE_ALPHA - 8)),
                )

    def _paint_scanlines(self, painter: QPainter, rect, *, phase_offset: int) -> None:
        strong_line = QColor(0, 0, 0, self.SCANLINE_ALPHA)
        soft_line = QColor(0, 0, 0, self.SCANLINE_SOFT_ALPHA)
        for y in range(rect.top() + phase_offset, rect.bottom(), self.SCANLINE_SPACING_PX):
            painter.fillRect(rect.left(), y, rect.width(), 1, strong_line)
            if y + 1 < rect.bottom():
                painter.fillRect(rect.left(), y + 1, rect.width(), 1, soft_line)

    def _paint_noise(self, painter: QPainter, rect) -> None:
        noise_step_x = 10
        noise_step_y = 8
        phase = self._crt_phase * 31
        for y in range(rect.top(), rect.bottom(), noise_step_y):
            for x in range(rect.left(), rect.right(), noise_step_x):
                value = (x * 17 + y * 29 + phase) % 97
                if value < 4:
                    alpha = self.NOISE_ALPHA + value * 6
                    painter.fillRect(x, y, 2, 1, QColor(160, 255, 190, alpha))
                elif value == 47:
                    painter.fillRect(x, y, 1, 1, QColor(255, 255, 255, 22))

    def _paint_vignette(self, painter: QPainter, rect) -> None:
        edge_fade = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.72)
        edge_fade.setColorAt(0.0, QColor(0, 0, 0, 0))
        edge_fade.setColorAt(0.58, QColor(0, 0, 0, 0))
        edge_fade.setColorAt(0.88, QColor(0, 18, 0, 40))
        edge_fade.setColorAt(1.0, QColor(0, 0, 0, self.VIGNETTE_ALPHA))
        painter.fillRect(rect, edge_fade)

        side_shade = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        side_shade.setColorAt(0.0, QColor(0, 0, 0, 44))
        side_shade.setColorAt(0.08, QColor(0, 0, 0, 0))
        side_shade.setColorAt(0.92, QColor(0, 0, 0, 0))
        side_shade.setColorAt(1.0, QColor(0, 0, 0, 44))
        painter.fillRect(rect, side_shade)

    def _paint_bezel(self, painter: QPainter, rect) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        bezel_rect = rect.adjusted(1, 1, -2, -2)
        bezel_path = QPainterPath()
        bezel_path.addRoundedRect(bezel_rect, self.CORNER_RADIUS_PX, self.CORNER_RADIUS_PX)

        painter.setPen(QPen(QColor(90, 255, 150, self.BORDER_GLOW_ALPHA), 1.4))
        painter.drawPath(bezel_path)

        inner_path = QPainterPath()
        inner_path.addRoundedRect(
            bezel_rect.adjusted(3, 3, -3, -3),
            max(4, self.CORNER_RADIUS_PX - 3),
            max(4, self.CORNER_RADIUS_PX - 3),
        )
        painter.setPen(QPen(QColor(0, 0, 0, 86), 2.0))
        painter.drawPath(inner_path)
        painter.restore()

    def _dynamic_crt_dirty_rect_for_phase(self, phase: int) -> QRect:
        rect = self.viewport().rect()
        if rect.isEmpty():
            return QRect()

        if self.ENABLE_NOISE or self.ENABLE_SCANLINE_DRIFT:
            return rect

        if self.ENABLE_SCAN_SWEEP:
            sweep_margin = 140
            sweep_half_height = 90
            sweep_cycle = max(1, rect.height() + sweep_margin * 2)
            sweep_center = rect.top() + ((phase * 19) % sweep_cycle) - sweep_margin
            top = max(rect.top(), sweep_center - sweep_half_height)
            bottom = min(rect.bottom(), sweep_center + sweep_half_height)
            if bottom >= top:
                return QRect(rect.left(), top, rect.width(), bottom - top + 1)

        return QRect()
