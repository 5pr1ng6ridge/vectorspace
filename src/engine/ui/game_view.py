"""游戏主视图。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Callable

from PySide6.QtCore import QEasingCurve, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget
from PySide6.QtMultimedia import QSoundEffect

from ..resources.fonts import load_font_family
from ..resources.paths import asset_path
from .dialogue_text import DialogueSegment, DialogueTextView


_IMAGE_SEARCH_FOLDERS = (
    "characters",
    "sprites",
    "standing",
    "portrait",
    "VECTORSPACE_pic",
    "ui",
)
_AUDIO_SEARCH_FOLDERS = ("sfx", "audio", "sounds", "se")

_EASING_MAP: dict[str, QEasingCurve.Type] = {
    "linear": QEasingCurve.Type.Linear,
    "in_quad": QEasingCurve.Type.InQuad,
    "out_quad": QEasingCurve.Type.OutQuad,
    "in_out_quad": QEasingCurve.Type.InOutQuad,
    "in_cubic": QEasingCurve.Type.InCubic,
    "out_cubic": QEasingCurve.Type.OutCubic,
    "in_out_cubic": QEasingCurve.Type.InOutCubic,
    "in_sine": QEasingCurve.Type.InSine,
    "out_sine": QEasingCurve.Type.OutSine,
    "in_out_sine": QEasingCurve.Type.InOutSine,
    "in_back": QEasingCurve.Type.InBack,
    "out_back": QEasingCurve.Type.OutBack,
    "in_out_back": QEasingCurve.Type.InOutBack,
    "out_bounce": QEasingCurve.Type.OutBounce,
    "in_out_bounce": QEasingCurve.Type.InOutBounce,
    "out_elastic": QEasingCurve.Type.OutElastic,
    "in_circ": QEasingCurve.Type.InCirc, 
    "out_circ": QEasingCurve.Type.OutCirc,
}
_CACHE_MISS = object()


@dataclass
class _SpriteState:
    image_id: str
    label: QLabel
    opacity_effect: QGraphicsOpacityEffect
    pixmap: QPixmap
    source: str
    x: float = 960.0
    y: float = 1080.0
    scale: float = 1.0
    opacity: float = 1.0
    z: int = 0
    anchor_x: float = 0.5
    anchor_y: float = 1.0
    above_web: bool = False
    visible: bool = False
    scaled_size: tuple[int, int] | None = None
    scaled_pixmap: QPixmap | None = None


@dataclass
class _SpriteAnimation:
    image_id: str
    started_at: float
    duration_ms: int
    easing: QEasingCurve
    from_x: float
    from_y: float
    from_scale: float
    from_opacity: float
    to_x: float
    to_y: float
    to_scale: float
    to_opacity: float
    hide_on_finish: bool
    remove_on_finish: bool
    on_finished: Callable[[], None] | None


@dataclass
class _DialogueUiAnimation:
    started_at: float
    duration_ms: int
    easing: QEasingCurve
    from_offset_design: float
    to_offset_design: float
    hide_on_finish: bool
    on_finished: Callable[[], None] | None


@dataclass
class _ExtraTextBoxState:
    textbox_id: str
    view: DialogueTextView
    opacity_effect: QGraphicsOpacityEffect
    rect_x: float
    rect_y: float
    rect_w: float
    rect_h: float
    x: float
    y: float
    scale: float = 1.0
    opacity: float = 1.0
    z: int = 0
    above_web: bool = False
    visible: bool = False


@dataclass
class _ExtraTextBoxAnimation:
    textbox_id: str
    started_at: float
    duration_ms: int
    easing: QEasingCurve
    from_x: float
    from_y: float
    from_scale: float
    from_opacity: float
    to_x: float
    to_y: float
    to_scale: float
    to_opacity: float
    hide_on_finish: bool
    remove_on_finish: bool
    on_finished: Callable[[], None] | None


class GameView(QWidget):
    """承载游戏画面的主 Widget。"""

    advanceRequested = Signal()
    pauseStateChanged = Signal(bool)

    DESIGN_WIDTH = 1920
    DESIGN_HEIGHT = 1080
    NAME_RECT_DESIGN = QRect(0, 746, 468, 70)
    TEXT_RECT_DESIGN = QRect(140, 874, 1640, 256)
    DIALOGUE_UI_HIDDEN_OFFSET_DESIGN = 360.0
    TYPEWRITER_SFX_DEFAULT_VOLUME = 0.35
    TYPEWRITER_SFX_DEFAULT_MIN_INTERVAL_MS = 40
    SCENE_NOISE_FRAME_MS = 67
    NOISE_CLEAR_SETTLE_MS = 67

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

        self.scene_bg = QLabel(self)
        self.scene_bg.setScaledContents(True)
        self._bg_pixmap = QPixmap()
        self._bg_scaled_size: tuple[int, int] | None = None
        self._bg_scaled_pixmap = QPixmap()

        self.sprite_root = QWidget(self)
        self.sprite_root.setAttribute(Qt.WA_TranslucentBackground)

        self.ui_overlay = QLabel(self)
        self.ui_overlay.setScaledContents(True)
        self._ui_pixmap = QPixmap(str(asset_path("ui", "dial_box_overlay.png")))
        self._ui_scaled_size: tuple[int, int] | None = None
        self._ui_scaled_pixmap = QPixmap()

        self.name_label = QLabel(self)
        self.name_label.setAttribute(Qt.WA_TranslucentBackground)
        self.name_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.text_label = DialogueTextView(self)
        self.text_label.setAttribute(Qt.WA_TranslucentBackground)
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._pause_overlay = QLabel(self)
        self._pause_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._pause_overlay.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self._pause_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self._pause_overlay.hide()
        self._paused = False
        self._pause_started_at = 0.0
        self._paused_anim_timer_was_active = False
        self._paused_extra_textbox_timer_was_active = False
        self._paused_dialogue_ui_timer_was_active = False
        self._paused_scene_noise_timer_was_active = False
        self._scene_noise_overlay = QLabel(self)
        self._scene_noise_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._scene_noise_overlay.setScaledContents(True)
        self._scene_noise_overlay.hide()

        self._asset_resolve_cache: dict[tuple[str, str | None], str | None] = {}
        self._audio_resolve_cache: dict[tuple[str, str | None], str | None] = {}
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._sprites: dict[str, _SpriteState] = {}
        self._sprite_anims: dict[str, _SpriteAnimation] = {}
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_sprite_anim_tick)
        self._extra_textboxes: dict[str, _ExtraTextBoxState] = {}
        self._extra_textbox_anims: dict[str, _ExtraTextBoxAnimation] = {}
        self._extra_textbox_timer = QTimer(self)
        self._extra_textbox_timer.setInterval(16)
        self._extra_textbox_timer.timeout.connect(self._on_extra_textbox_anim_tick)
        self._dialogue_ui_offset_design = 0.0
        self._dialogue_ui_visible = True
        self._dialogue_ui_anim: _DialogueUiAnimation | None = None
        self._dialogue_ui_timer = QTimer(self)
        self._dialogue_ui_timer.setInterval(16)
        self._dialogue_ui_timer.timeout.connect(self._on_dialogue_ui_anim_tick)
        self._typewriter_sfx = QSoundEffect(self)
        self._typewriter_sfx_enabled = True
        self._typewriter_sfx_min_interval_ms = self.TYPEWRITER_SFX_DEFAULT_MIN_INTERVAL_MS
        self._typewriter_sfx_last_played = 0.0
        self._setup_typewriter_sfx()
        self._scene_noise_timer = QTimer(self)
        self._scene_noise_timer.setInterval(self.SCENE_NOISE_FRAME_MS)
        self._scene_noise_timer.timeout.connect(self._on_scene_noise_tick)
        self._scene_noise_frames: list[QPixmap] = self._load_scene_noise_frames()
        self._scene_noise_index = 0
        self._scene_noise_on_finished: Callable[[], None] | None = None

        self._apply_fonts()
        self._setup_z_order()

    def _setup_z_order(self) -> None:
        self.scene_bg.lower()
        self.sprite_root.raise_()
        self._refresh_sprite_stack()
        self._refresh_extra_textboxes_stack()
        self.ui_overlay.raise_()
        self.name_label.raise_()
        self.text_label.raise_()
        self._refresh_above_web_stack()
        self._scene_noise_overlay.raise_()
        self._pause_overlay.raise_()

    def _apply_fonts(self) -> None:
        """加载像素字体并应用到姓名框和对话框。"""
        family = load_font_family("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")
        if not family:
            print("[GameView] failed to load dialogue font")
            return
        self.name_label.setFont(QFont(family, 40))
        self.text_label.setFont(QFont(family, 35))
        self.name_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        for state in self._extra_textboxes.values():
            state.view.setFont(QFont(family, 35))

    def set_dialogue_style(
        self,
        font_size: int | None = None,
        color: str | None = None,
        name_font_size: int | None = None,
        name_color: str | None = None,
    ) -> None:
        if name_font_size is not None:
            current_name_font = QFont(self.name_label.font())
            current_name_font.setPointSize(max(1, int(name_font_size)))
            self.name_label.setFont(current_name_font)

        if name_color is not None:
            self.name_label.setStyleSheet(
                f"color: {name_color}; background: transparent;"
            )

        self.text_label.set_text_style(font_size_px=font_size, color_hex=color)

    def _setup_typewriter_sfx(self) -> None:
        self._typewriter_sfx.setLoopCount(1)
        self._typewriter_sfx.setVolume(self.TYPEWRITER_SFX_DEFAULT_VOLUME)
        default_sfx = asset_path("sfx", "sfx_typing.wav")
        if default_sfx.exists():
            self._typewriter_sfx.setSource(QUrl.fromLocalFile(str(default_sfx)))
            return
        self._typewriter_sfx_enabled = False

    def configure_typewriter_sfx(
        self,
        *,
        enabled: bool | None = None,
        volume: float | None = None,
        file: str | None = None,
        folder: str | None = None,
        min_interval_ms: int | None = None,
    ) -> None:
        if enabled is not None:
            self._typewriter_sfx_enabled = bool(enabled)

        if volume is not None:
            clamped = max(0.0, min(1.0, float(volume)))
            self._typewriter_sfx.setVolume(clamped)

        if min_interval_ms is not None:
            self._typewriter_sfx_min_interval_ms = max(0, int(min_interval_ms))

        if file is not None:
            resolved = self._resolve_audio_file(file=file, folder=folder)
            if resolved is None:
                print(f"[GameView] failed to resolve typewriter sfx: {file}")
            else:
                self._typewriter_sfx.setSource(QUrl.fromLocalFile(str(resolved)))
                self._typewriter_sfx_enabled = True

    def play_typewriter_sfx(self) -> None:
        if not self._typewriter_sfx_enabled:
            return
        if self._typewriter_sfx.source().isEmpty():
            return

        now = time.monotonic()
        elapsed_ms = (now - self._typewriter_sfx_last_played) * 1000.0
        if elapsed_ms < float(self._typewriter_sfx_min_interval_ms):
            return

        self._typewriter_sfx_last_played = now
        self._typewriter_sfx.play()

    def set_background(self, filename: str) -> None:
        path = self._resolve_asset_file(filename, folder="pic/backgrounds")
        if path is None:
            print(f"[GameView] failed to resolve background: {filename}")
            return

        pixmap = self._load_cached_pixmap(path)
        if pixmap is None:
            print(f"[GameView] failed to load background: {path}")
            return

        self._bg_pixmap = pixmap
        self._bg_scaled_size = None
        self._bg_scaled_pixmap = QPixmap()
        self._update_bg_geometry()

    def set_name(self, name: str) -> None:
        self.name_label.setText(name)

    def show_text(self, text: str) -> None:
        self.text_label.set_plain_dialogue(text)
        if self._dialogue_ui_visible or self._dialogue_ui_anim is not None:
            self.text_label.setVisible(True)

    def show_text_segments(
        self, segments: list[DialogueSegment], visible_units: int | None = None
    ) -> None:
        self.text_label.set_text_segments(segments, visible_units)
        if self._dialogue_ui_visible or self._dialogue_ui_anim is not None:
            self.text_label.setVisible(True)

    def show_formula(self, expr: str) -> None:
        self.text_label.set_formula_text(expr)
        if self._dialogue_ui_visible or self._dialogue_ui_anim is not None:
            self.text_label.setVisible(True)

    def clear_dialogue_content(self) -> None:
        """清空姓名与对话内容，避免切场景时残留上一句。"""
        self.set_name("")
        self.text_label.set_plain_dialogue("")
        # 先隐藏文本层，避免 WebEngine 异步提交空内容前出现旧文本残影。
        self.text_label.setVisible(False)

    def set_paused(self, paused: bool) -> None:
        target = bool(paused)
        if target == self._paused:
            return

        self._paused = target
        if self._paused:
            self._pause_started_at = time.monotonic()

            self._paused_anim_timer_was_active = self._anim_timer.isActive()
            self._paused_extra_textbox_timer_was_active = self._extra_textbox_timer.isActive()
            self._paused_dialogue_ui_timer_was_active = self._dialogue_ui_timer.isActive()
            self._paused_scene_noise_timer_was_active = self._scene_noise_timer.isActive()

            self._anim_timer.stop()
            self._extra_textbox_timer.stop()
            self._dialogue_ui_timer.stop()
            self._scene_noise_timer.stop()

            self._pause_overlay.setVisible(True)
            self._pause_overlay.raise_()
            self.pauseStateChanged.emit(True)
            return

        paused_seconds = max(0.0, time.monotonic() - self._pause_started_at)
        if paused_seconds > 0.0:
            for anim in self._sprite_anims.values():
                anim.started_at += paused_seconds
            for anim in self._extra_textbox_anims.values():
                anim.started_at += paused_seconds
            if self._dialogue_ui_anim is not None:
                self._dialogue_ui_anim.started_at += paused_seconds

        if self._paused_anim_timer_was_active and self._sprite_anims:
            self._anim_timer.start()
        if self._paused_extra_textbox_timer_was_active and self._extra_textbox_anims:
            self._extra_textbox_timer.start()
        if self._paused_dialogue_ui_timer_was_active and self._dialogue_ui_anim is not None:
            self._dialogue_ui_timer.start()
        if self._paused_scene_noise_timer_was_active and self._scene_noise_overlay.isVisible():
            self._scene_noise_timer.start()

        self._paused_anim_timer_was_active = False
        self._paused_extra_textbox_timer_was_active = False
        self._paused_dialogue_ui_timer_was_active = False
        self._paused_scene_noise_timer_was_active = False
        self._pause_overlay.setVisible(False)
        self._setup_z_order()
        self.pauseStateChanged.emit(False)

    def toggle_paused(self) -> None:
        self.set_paused(not self._paused)

    def is_paused(self) -> bool:
        return self._paused

    def play_scene_noise_once(
        self,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """在最上层播放一轮 noise_* 过渡帧。"""
        self._scene_noise_on_finished = on_finished
        if not self._scene_noise_frames:
            self._finish_scene_noise_playback()
            return

        self._scene_noise_timer.stop()
        self._scene_noise_index = 0
        # 噪声播放期间先隐藏对话 UI，避免 WebEngine 层级覆盖 noise。
        self._set_dialogue_ui_widgets_visible(False)
        self._apply_scene_noise_frame(0)
        self._scene_noise_overlay.show()
        self._scene_noise_overlay.raise_()

        if len(self._scene_noise_frames) <= 1:
            QTimer.singleShot(self.SCENE_NOISE_FRAME_MS, self._finish_scene_noise_playback)
            return
        self._scene_noise_timer.start()

    def show_dialogue_ui(
        self,
        *,
        duration_ms: int = 220,
        easing: str = "out_quad",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        self._dialogue_ui_visible = True
        self._set_dialogue_ui_widgets_visible(True)
        return self._start_dialogue_ui_animation(
            to_offset_design=0.0,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=False,
            on_finished=on_finished,
        )

    def hide_dialogue_ui(
        self,
        *,
        duration_ms: int = 220,
        easing: str = "in_quad",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        self._set_dialogue_ui_widgets_visible(True)
        return self._start_dialogue_ui_animation(
            to_offset_design=self.DIALOGUE_UI_HIDDEN_OFFSET_DESIGN,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=True,
            on_finished=on_finished,
        )

    def register_extra_textbox(
        self,
        textbox_id: str,
        rect_x: float,
        rect_y: float,
        rect_w: float,
        rect_h: float,
        *,
        x: float | None = None,
        y: float | None = None,
        scale: float | None = None,
        opacity: float | None = None,
        z: int | None = None,
        above_web: bool | None = None,
        text: str | None = None,
        font_size: int | None = None,
        color: str | None = None,
        visible: bool = False,
    ) -> bool:
        key = textbox_id.strip()
        if not key:
            return False

        rect_w_value = float(rect_w)
        rect_h_value = float(rect_h)
        if rect_w_value <= 0.0 or rect_h_value <= 0.0:
            return False

        state = self._extra_textboxes.get(key)
        if state is None:
            initial_above_web = bool(above_web) if above_web is not None else False
            parent_widget: QWidget = self if initial_above_web else self.sprite_root
            view = DialogueTextView(parent_widget)
            view.setAttribute(Qt.WA_TranslucentBackground)
            view.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            view.setAttribute(Qt.WA_AlwaysStackOnTop, bool(initial_above_web))
            if initial_above_web:
                view.setAttribute(Qt.WA_NativeWindow, True)
            view.setFont(QFont(self.text_label.font()))
            effect = QGraphicsOpacityEffect(view)
            view.setGraphicsEffect(effect)
            state = _ExtraTextBoxState(
                textbox_id=key,
                view=view,
                opacity_effect=effect,
                rect_x=float(rect_x),
                rect_y=float(rect_y),
                rect_w=rect_w_value,
                rect_h=rect_h_value,
                x=float(rect_x),
                y=float(rect_y),
                above_web=initial_above_web,
                visible=bool(visible),
            )
            self._extra_textboxes[key] = state
        else:
            self._cancel_extra_textbox_animation(key)
            state.rect_x = float(rect_x)
            state.rect_y = float(rect_y)
            state.rect_w = rect_w_value
            state.rect_h = rect_h_value
            state.visible = bool(visible)

        if x is not None:
            state.x = float(x)
        if y is not None:
            state.y = float(y)
        if scale is not None:
            state.scale = max(0.01, float(scale))
        if opacity is not None:
            state.opacity = self._clamp_opacity(opacity)
        if z is not None:
            state.z = int(z)
        if above_web is not None:
            self._set_extra_textbox_above_web(state, bool(above_web))
        if text is not None:
            state.view.set_plain_dialogue(text)
        if font_size is not None or color is not None:
            state.view.set_text_style(font_size_px=font_size, color_hex=color)

        self._apply_extra_textbox_state(state)
        self._refresh_extra_textboxes_stack()
        return True

    def set_extra_textbox_text(
        self,
        textbox_id: str,
        text: str,
        *,
        visible: bool | None = None,
    ) -> bool:
        state = self._extra_textboxes.get(textbox_id)
        if state is None:
            return False
        state.view.set_plain_dialogue(text)
        if visible is not None:
            state.visible = bool(visible)
        self._apply_extra_textbox_state(state)
        return True

    def show_extra_textbox(
        self,
        textbox_id: str,
        *,
        text: str | None = None,
        font_size: int | None = None,
        color: str | None = None,
        x: float | None = None,
        y: float | None = None,
        dx: float | None = None,
        dy: float | None = None,
        scale: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        dopacity: float | None = None,
        z: int | None = None,
        above_web: bool | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._extra_textboxes.get(textbox_id)
        if state is None:
            return False

        if text is not None:
            state.view.set_plain_dialogue(text)
        if font_size is not None or color is not None:
            state.view.set_text_style(font_size_px=font_size, color_hex=color)
        if z is not None:
            state.z = int(z)
            self._refresh_extra_textboxes_stack()
        if above_web is not None:
            self._set_extra_textbox_above_web(state, bool(above_web))
            self._refresh_extra_textboxes_stack()

        target_x, target_y, target_scale, target_opacity = self._resolve_targets(
            state,
            x=x,
            y=y,
            dx=dx,
            dy=dy,
            scale=scale,
            dscale=dscale,
            opacity=opacity,
            dopacity=dopacity,
        )
        state.visible = True
        return self._start_extra_textbox_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=False,
            remove_on_finish=False,
            on_finished=on_finished,
        )

    def hide_extra_textbox(
        self,
        textbox_id: str,
        *,
        dx: float | None = None,
        dy: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        remove: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._extra_textboxes.get(textbox_id)
        if state is None:
            return False

        target_x, target_y, target_scale, _ = self._resolve_targets(
            state,
            dx=dx,
            dy=dy,
            dscale=dscale,
        )
        target_opacity = self._clamp_opacity(0.0 if opacity is None else opacity)

        state.visible = True
        return self._start_extra_textbox_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=True,
            remove_on_finish=bool(remove),
            on_finished=on_finished,
        )

    def transform_extra_textbox(
        self,
        textbox_id: str,
        *,
        x: float | None = None,
        y: float | None = None,
        dx: float | None = None,
        dy: float | None = None,
        scale: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        dopacity: float | None = None,
        z: int | None = None,
        above_web: bool | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._extra_textboxes.get(textbox_id)
        if state is None:
            return False

        if z is not None:
            state.z = int(z)
            self._refresh_extra_textboxes_stack()
        if above_web is not None:
            self._set_extra_textbox_above_web(state, bool(above_web))
            self._refresh_extra_textboxes_stack()

        target_x, target_y, target_scale, target_opacity = self._resolve_targets(
            state,
            x=x,
            y=y,
            dx=dx,
            dy=dy,
            scale=scale,
            dscale=dscale,
            opacity=opacity,
            dopacity=dopacity,
        )
        if target_opacity > 0.0:
            state.visible = True

        return self._start_extra_textbox_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=False,
            remove_on_finish=False,
            on_finished=on_finished,
        )

    def remove_extra_textbox(self, textbox_id: str) -> bool:
        state = self._extra_textboxes.get(textbox_id)
        if state is None:
            return False

        self._cancel_extra_textbox_animation(textbox_id)
        state.view.hide()
        state.view.deleteLater()
        del self._extra_textboxes[textbox_id]
        return True

    def clear_extra_textboxes(self) -> None:
        for textbox_id in list(self._extra_textboxes.keys()):
            self.remove_extra_textbox(textbox_id)
        self._extra_textbox_anims.clear()
        self._extra_textbox_timer.stop()

    def register_image(
        self,
        image_id: str,
        file: str,
        *,
        folder: str | None = None,
        x: float | None = None,
        y: float | None = None,
        scale: float | None = None,
        opacity: float | None = None,
        z: int | None = None,
        anchor_x: float | None = None,
        anchor_y: float | None = None,
        above_web: bool | None = None,
        visible: bool = False,
    ) -> bool:
        sprite_id = image_id.strip()
        if not sprite_id:
            return False

        loaded = self._load_sprite_pixmap(file=file, folder=folder)
        if loaded is None:
            return False
        pixmap, resolved_source = loaded

        state = self._sprites.get(sprite_id)
        if state is None:
            initial_above_web = bool(above_web) if above_web is not None else False
            parent_widget: QWidget = self if initial_above_web else self.sprite_root
            label = QLabel(parent_widget)
            label.setAttribute(Qt.WA_TranslucentBackground)
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            label.setScaledContents(True)
            effect = QGraphicsOpacityEffect(label)
            label.setGraphicsEffect(effect)
            label.setAttribute(Qt.WA_AlwaysStackOnTop, bool(initial_above_web))
            if initial_above_web:
                label.setAttribute(Qt.WA_NativeWindow, True)

            state = _SpriteState(
                image_id=sprite_id,
                label=label,
                opacity_effect=effect,
                pixmap=pixmap,
                source=resolved_source,
                above_web=initial_above_web,
                visible=bool(visible),
            )
            self._sprites[sprite_id] = state
        else:
            self._cancel_sprite_animation(sprite_id)
            state.pixmap = pixmap
            state.source = resolved_source
            state.visible = bool(visible)
            state.scaled_size = None
            state.scaled_pixmap = None

        if x is not None:
            state.x = float(x)
        if y is not None:
            state.y = float(y)
        if scale is not None:
            state.scale = max(0.01, float(scale))
        if opacity is not None:
            state.opacity = self._clamp_opacity(opacity)
        if z is not None:
            state.z = int(z)
        if anchor_x is not None:
            state.anchor_x = float(anchor_x)
        if anchor_y is not None:
            state.anchor_y = float(anchor_y)
        if above_web is not None:
            self._set_sprite_above_web(state, bool(above_web))

        self._refresh_sprite_stack()
        self._apply_sprite_state(state)
        return True

    def set_image_source(
        self,
        image_id: str,
        file: str,
        *,
        folder: str | None = None,
    ) -> bool:
        state = self._sprites.get(image_id)
        if state is None:
            return False

        loaded = self._load_sprite_pixmap(file=file, folder=folder)
        if loaded is None:
            return False

        pixmap, resolved_source = loaded
        state.pixmap = pixmap
        state.source = resolved_source
        state.scaled_size = None
        state.scaled_pixmap = None
        self._apply_sprite_state(state)
        return True

    def show_image(
        self,
        image_id: str,
        *,
        x: float | None = None,
        y: float | None = None,
        dx: float | None = None,
        dy: float | None = None,
        scale: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        dopacity: float | None = None,
        z: int | None = None,
        above_web: bool | None = None,
        file: str | None = None,
        folder: str | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._sprites.get(image_id)
        if state is None:
            return False

        if file:
            if not self.set_image_source(image_id, file, folder=folder):
                return False

        if z is not None:
            state.z = int(z)
            self._refresh_sprite_stack()
        if above_web is not None:
            self._set_sprite_above_web(state, bool(above_web))

        target_x, target_y, target_scale, target_opacity = self._resolve_targets(
            state,
            x=x,
            y=y,
            dx=dx,
            dy=dy,
            scale=scale,
            dscale=dscale,
            opacity=opacity,
            dopacity=dopacity,
        )

        state.visible = True
        return self._start_sprite_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=False,
            remove_on_finish=False,
            on_finished=on_finished,
        )

    def hide_image(
        self,
        image_id: str,
        *,
        dx: float | None = None,
        dy: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        remove: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._sprites.get(image_id)
        if state is None:
            return False

        target_x, target_y, target_scale, _ = self._resolve_targets(
            state,
            dx=dx,
            dy=dy,
            dscale=dscale,
        )
        target_opacity = self._clamp_opacity(0.0 if opacity is None else opacity)

        state.visible = True
        return self._start_sprite_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=True,
            remove_on_finish=bool(remove),
            on_finished=on_finished,
        )

    def transform_image(
        self,
        image_id: str,
        *,
        x: float | None = None,
        y: float | None = None,
        dx: float | None = None,
        dy: float | None = None,
        scale: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        dopacity: float | None = None,
        z: int | None = None,
        above_web: bool | None = None,
        duration_ms: int = 0,
        easing: str = "linear",
        on_finished: Callable[[], None] | None = None,
    ) -> bool:
        state = self._sprites.get(image_id)
        if state is None:
            return False

        if z is not None:
            state.z = int(z)
            self._refresh_sprite_stack()
        if above_web is not None:
            self._set_sprite_above_web(state, bool(above_web))

        target_x, target_y, target_scale, target_opacity = self._resolve_targets(
            state,
            x=x,
            y=y,
            dx=dx,
            dy=dy,
            scale=scale,
            dscale=dscale,
            opacity=opacity,
            dopacity=dopacity,
        )

        if target_opacity > 0.0:
            state.visible = True

        return self._start_sprite_animation(
            state,
            to_x=target_x,
            to_y=target_y,
            to_scale=target_scale,
            to_opacity=target_opacity,
            duration_ms=duration_ms,
            easing_name=easing,
            hide_on_finish=False,
            remove_on_finish=False,
            on_finished=on_finished,
        )

    def remove_image(self, image_id: str) -> bool:
        state = self._sprites.get(image_id)
        if state is None:
            return False

        self._cancel_sprite_animation(image_id)
        state.label.hide()
        state.label.deleteLater()
        del self._sprites[image_id]
        return True

    def clear_images(self) -> None:
        for image_id in list(self._sprites.keys()):
            self.remove_image(image_id)
        self._sprite_anims.clear()
        self._anim_timer.stop()

    def _load_sprite_pixmap(
        self, file: str, folder: str | None = None
    ) -> tuple[QPixmap, str] | None:
        if not isinstance(file, str) or not file.strip():
            return None

        resolved = self._resolve_asset_file(file.strip(), folder=folder)
        if resolved is None:
            print(f"[GameView] failed to resolve image asset: {file}")
            return None

        pixmap = self._load_cached_pixmap(resolved)
        if pixmap is None:
            print(f"[GameView] failed to load image: {resolved}")
            return None

        return pixmap, str(resolved)

    def _set_sprite_above_web(self, state: _SpriteState, enabled: bool) -> None:
        target = bool(enabled)
        if state.above_web == target:
            return

        parent_widget: QWidget = self if target else self.sprite_root
        if state.label.parentWidget() is not parent_widget:
            state.label.setParent(parent_widget)

        state.label.setAttribute(Qt.WA_AlwaysStackOnTop, target)
        if target:
            state.label.setAttribute(Qt.WA_NativeWindow, True)
        state.above_web = target

    def _set_extra_textbox_above_web(
        self, state: _ExtraTextBoxState, enabled: bool
    ) -> None:
        target = bool(enabled)
        if state.above_web == target:
            return

        parent_widget: QWidget = self if target else self.sprite_root
        if state.view.parentWidget() is not parent_widget:
            state.view.setParent(parent_widget)

        state.view.setAttribute(Qt.WA_AlwaysStackOnTop, target)
        if target:
            state.view.setAttribute(Qt.WA_NativeWindow, True)
        state.above_web = target

    def _resolve_asset_file(self, file: str, folder: str | None = None) -> Path | None:
        return self._resolve_cached_file(
            file=file,
            folder=folder,
            cache=self._asset_resolve_cache,
            default_folders=_IMAGE_SEARCH_FOLDERS,
        )

    def _resolve_audio_file(self, file: str, folder: str | None = None) -> Path | None:
        return self._resolve_cached_file(
            file=file,
            folder=folder,
            cache=self._audio_resolve_cache,
            default_folders=_AUDIO_SEARCH_FOLDERS,
        )

    def _resolve_cached_file(
        self,
        *,
        file: str,
        folder: str | None,
        cache: dict[tuple[str, str | None], str | None],
        default_folders: tuple[str, ...],
    ) -> Path | None:
        normalized_file = file.strip()
        normalized_folder = folder.strip() if isinstance(folder, str) else None
        cache_key = (normalized_file, normalized_folder)
        cached = cache.get(cache_key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return Path(cached) if cached is not None else None

        candidate = Path(normalized_file)
        if candidate.is_absolute() and candidate.exists():
            cache[cache_key] = str(candidate)
            return candidate

        for path in self._iter_candidate_asset_paths(
            candidate,
            folder=normalized_folder,
            default_folders=default_folders,
        ):
            if path.exists():
                cache[cache_key] = str(path)
                return path

        matched = self._find_asset_by_name(candidate.name)
        cache[cache_key] = str(matched) if matched is not None else None
        return matched

    def _iter_candidate_asset_paths(
        self,
        candidate: Path,
        *,
        folder: str | None,
        default_folders: tuple[str, ...],
    ):
        seen: set[str] = set()

        def _yield_if_new(path: Path):
            path_key = str(path)
            if path_key in seen:
                return
            seen.add(path_key)
            yield path

        if folder:
            folder_path = Path(folder)
            yield from _yield_if_new(asset_path(*(folder_path / candidate).parts))

        if len(candidate.parts) > 1:
            yield from _yield_if_new(asset_path(*candidate.parts))
            return

        for base_folder in default_folders:
            yield from _yield_if_new(asset_path(base_folder, candidate.name))
        yield from _yield_if_new(asset_path(candidate.name))

    def _find_asset_by_name(self, name: str) -> Path | None:
        assets_root = asset_path()
        if not assets_root.exists() or not name:
            return None

        for matched in assets_root.rglob(name):
            if matched.is_file():
                return matched
        return None

    def _load_cached_pixmap(self, path: Path) -> QPixmap | None:
        cache_key = str(path)
        cached = self._pixmap_cache.get(cache_key)
        if cached is not None:
            return cached

        pixmap = QPixmap(cache_key)
        if pixmap.isNull():
            return None

        self._pixmap_cache[cache_key] = pixmap
        return pixmap

    def _resolve_targets(
        self,
        state: Any,
        *,
        x: float | None = None,
        y: float | None = None,
        dx: float | None = None,
        dy: float | None = None,
        scale: float | None = None,
        dscale: float | None = None,
        opacity: float | None = None,
        dopacity: float | None = None,
    ) -> tuple[float, float, float, float]:
        target_x = float(x) if x is not None else state.x
        target_y = float(y) if y is not None else state.y

        if dx is not None:
            target_x += float(dx)
        if dy is not None:
            target_y += float(dy)

        target_scale = float(scale) if scale is not None else state.scale
        if dscale is not None:
            target_scale += float(dscale)
        target_scale = max(0.01, target_scale)

        target_opacity = (
            self._clamp_opacity(opacity) if opacity is not None else state.opacity
        )
        if dopacity is not None:
            target_opacity = self._clamp_opacity(target_opacity + float(dopacity))

        return target_x, target_y, target_scale, target_opacity

    def _start_sprite_animation(
        self,
        state: _SpriteState,
        *,
        to_x: float,
        to_y: float,
        to_scale: float,
        to_opacity: float,
        duration_ms: int,
        easing_name: str,
        hide_on_finish: bool,
        remove_on_finish: bool,
        on_finished: Callable[[], None] | None,
    ) -> bool:
        self._cancel_sprite_animation(state.image_id)

        clamped_duration = max(0, int(duration_ms))
        if clamped_duration == 0:
            state.x = to_x
            state.y = to_y
            state.scale = max(0.01, to_scale)
            state.opacity = self._clamp_opacity(to_opacity)
            if hide_on_finish:
                state.visible = False
            self._apply_sprite_state(state)
            if remove_on_finish:
                self.remove_image(state.image_id)
            if on_finished is not None:
                on_finished()
            return False

        easing = self._make_easing_curve(easing_name)
        anim = _SpriteAnimation(
            image_id=state.image_id,
            started_at=time.monotonic(),
            duration_ms=clamped_duration,
            easing=easing,
            from_x=state.x,
            from_y=state.y,
            from_scale=state.scale,
            from_opacity=state.opacity,
            to_x=to_x,
            to_y=to_y,
            to_scale=max(0.01, to_scale),
            to_opacity=self._clamp_opacity(to_opacity),
            hide_on_finish=hide_on_finish,
            remove_on_finish=remove_on_finish,
            on_finished=on_finished,
        )

        state.visible = True
        self._sprite_anims[state.image_id] = anim
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        return True

    def _cancel_sprite_animation(self, image_id: str) -> None:
        self._sprite_anims.pop(image_id, None)
        if not self._sprite_anims:
            self._anim_timer.stop()

    def _on_sprite_anim_tick(self) -> None:
        if not self._sprite_anims:
            self._anim_timer.stop()
            return

        now = time.monotonic()
        completed_ids: list[str] = []
        callback_queue: list[Callable[[], None]] = []

        for image_id, anim in list(self._sprite_anims.items()):
            state = self._sprites.get(image_id)
            if state is None:
                completed_ids.append(image_id)
                continue

            elapsed_ms = (now - anim.started_at) * 1000.0
            progress = min(1.0, max(0.0, elapsed_ms / float(anim.duration_ms)))
            eased = float(anim.easing.valueForProgress(progress))

            state.x = anim.from_x + (anim.to_x - anim.from_x) * eased
            state.y = anim.from_y + (anim.to_y - anim.from_y) * eased
            state.scale = anim.from_scale + (anim.to_scale - anim.from_scale) * eased
            state.scale = max(0.01, state.scale)
            state.opacity = self._clamp_opacity(
                anim.from_opacity + (anim.to_opacity - anim.from_opacity) * eased
            )
            self._apply_sprite_state(state)

            if progress >= 1.0:
                state.x = anim.to_x
                state.y = anim.to_y
                state.scale = anim.to_scale
                state.opacity = anim.to_opacity
                if anim.hide_on_finish:
                    state.visible = False
                self._apply_sprite_state(state)
                if anim.remove_on_finish:
                    self.remove_image(image_id)
                if anim.on_finished is not None:
                    callback_queue.append(anim.on_finished)
                completed_ids.append(image_id)

        for image_id in completed_ids:
            self._sprite_anims.pop(image_id, None)

        if not self._sprite_anims:
            self._anim_timer.stop()

        for callback in callback_queue:
            callback()

    def _start_extra_textbox_animation(
        self,
        state: _ExtraTextBoxState,
        *,
        to_x: float,
        to_y: float,
        to_scale: float,
        to_opacity: float,
        duration_ms: int,
        easing_name: str,
        hide_on_finish: bool,
        remove_on_finish: bool,
        on_finished: Callable[[], None] | None,
    ) -> bool:
        self._cancel_extra_textbox_animation(state.textbox_id)

        clamped_duration = max(0, int(duration_ms))
        if clamped_duration == 0:
            state.x = to_x
            state.y = to_y
            state.scale = max(0.01, to_scale)
            state.opacity = self._clamp_opacity(to_opacity)
            if hide_on_finish:
                state.visible = False
            self._apply_extra_textbox_state(state)
            if remove_on_finish:
                self.remove_extra_textbox(state.textbox_id)
            if on_finished is not None:
                on_finished()
            return False

        anim = _ExtraTextBoxAnimation(
            textbox_id=state.textbox_id,
            started_at=time.monotonic(),
            duration_ms=clamped_duration,
            easing=self._make_easing_curve(easing_name),
            from_x=state.x,
            from_y=state.y,
            from_scale=state.scale,
            from_opacity=state.opacity,
            to_x=to_x,
            to_y=to_y,
            to_scale=max(0.01, to_scale),
            to_opacity=self._clamp_opacity(to_opacity),
            hide_on_finish=hide_on_finish,
            remove_on_finish=remove_on_finish,
            on_finished=on_finished,
        )
        state.visible = True
        self._extra_textbox_anims[state.textbox_id] = anim
        if not self._extra_textbox_timer.isActive():
            self._extra_textbox_timer.start()
        return True

    def _cancel_extra_textbox_animation(self, textbox_id: str) -> None:
        self._extra_textbox_anims.pop(textbox_id, None)
        if not self._extra_textbox_anims:
            self._extra_textbox_timer.stop()

    def _on_extra_textbox_anim_tick(self) -> None:
        if not self._extra_textbox_anims:
            self._extra_textbox_timer.stop()
            return

        now = time.monotonic()
        completed_ids: list[str] = []
        callback_queue: list[Callable[[], None]] = []

        for textbox_id, anim in list(self._extra_textbox_anims.items()):
            state = self._extra_textboxes.get(textbox_id)
            if state is None:
                completed_ids.append(textbox_id)
                continue

            elapsed_ms = (now - anim.started_at) * 1000.0
            progress = min(1.0, max(0.0, elapsed_ms / float(anim.duration_ms)))
            eased = float(anim.easing.valueForProgress(progress))

            state.x = anim.from_x + (anim.to_x - anim.from_x) * eased
            state.y = anim.from_y + (anim.to_y - anim.from_y) * eased
            state.scale = max(
                0.01, anim.from_scale + (anim.to_scale - anim.from_scale) * eased
            )
            state.opacity = self._clamp_opacity(
                anim.from_opacity + (anim.to_opacity - anim.from_opacity) * eased
            )
            self._apply_extra_textbox_state(state)

            if progress >= 1.0:
                state.x = anim.to_x
                state.y = anim.to_y
                state.scale = anim.to_scale
                state.opacity = anim.to_opacity
                if anim.hide_on_finish:
                    state.visible = False
                self._apply_extra_textbox_state(state)
                if anim.remove_on_finish:
                    self.remove_extra_textbox(textbox_id)
                if anim.on_finished is not None:
                    callback_queue.append(anim.on_finished)
                completed_ids.append(textbox_id)

        for textbox_id in completed_ids:
            self._extra_textbox_anims.pop(textbox_id, None)

        if not self._extra_textbox_anims:
            self._extra_textbox_timer.stop()

        for callback in callback_queue:
            callback()

    def _apply_sprite_state(self, state: _SpriteState) -> None:
        if state.pixmap.isNull():
            state.label.hide()
            return

        sx = self.width() / float(self.DESIGN_WIDTH)
        sy = self.height() / float(self.DESIGN_HEIGHT)
        pixel_scale = min(sx, sy) * max(0.01, state.scale)

        target_w = max(1, int(round(state.pixmap.width() * pixel_scale)))
        target_h = max(1, int(round(state.pixmap.height() * pixel_scale)))
        x_px = int(round(state.x * sx - target_w * state.anchor_x))
        y_px = int(round(state.y * sy - target_h * state.anchor_y))

        state.label.setGeometry(x_px, y_px, target_w, target_h)
        scaled_size = (target_w, target_h)
        if state.scaled_size != scaled_size or state.scaled_pixmap is None:
            state.scaled_pixmap = state.pixmap.scaled(
                target_w,
                target_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            state.scaled_size = scaled_size
        state.label.setPixmap(state.scaled_pixmap)
        state.opacity_effect.setOpacity(self._clamp_opacity(state.opacity))
        state.label.setVisible(state.visible)

    def _apply_extra_textbox_state(self, state: _ExtraTextBoxState) -> None:
        sx = self.width() / float(self.DESIGN_WIDTH)
        sy = self.height() / float(self.DESIGN_HEIGHT)
        target_w = max(1, int(round(state.rect_w * sx * max(0.01, state.scale))))
        target_h = max(1, int(round(state.rect_h * sy * max(0.01, state.scale))))
        x_px = int(round(state.x * sx))
        y_px = int(round(state.y * sy))
        state.view.setGeometry(x_px, y_px, target_w, target_h)
        state.opacity_effect.setOpacity(self._clamp_opacity(state.opacity))
        state.view.setVisible(state.visible)

    def _refresh_sprite_stack(self) -> None:
        for state in sorted(self._sprites.values(), key=lambda item: item.z):
            if state.above_web:
                continue
            state.label.raise_()
        self._refresh_above_web_stack()

    def _refresh_extra_textboxes_stack(self) -> None:
        for state in sorted(self._extra_textboxes.values(), key=lambda item: item.z):
            if state.above_web:
                continue
            state.view.raise_()
        self._refresh_above_web_stack()

    def _refresh_above_web_stack(self) -> None:
        overlay_widgets: list[tuple[int, int, QWidget]] = []
        for state in self._sprites.values():
            if state.above_web:
                overlay_widgets.append((state.z, 0, state.label))
        for state in self._extra_textboxes.values():
            if state.above_web:
                overlay_widgets.append((state.z, 1, state.view))

        for _, _, widget in sorted(overlay_widgets, key=lambda item: (item[0], item[1])):
            widget.raise_()

    def _make_easing_curve(self, easing_name: str) -> QEasingCurve:
        easing_type = _EASING_MAP.get(
            (easing_name or "linear").strip().lower(), QEasingCurve.Type.Linear
        )
        return QEasingCurve(easing_type)

    def _start_dialogue_ui_animation(
        self,
        *,
        to_offset_design: float,
        duration_ms: int,
        easing_name: str,
        hide_on_finish: bool,
        on_finished: Callable[[], None] | None,
    ) -> bool:
        self._dialogue_ui_anim = None

        target_offset = max(0.0, float(to_offset_design))
        clamped_duration = max(0, int(duration_ms))
        if abs(self._dialogue_ui_offset_design - target_offset) < 1e-6:
            if hide_on_finish:
                self._dialogue_ui_visible = False
                self._set_dialogue_ui_widgets_visible(False)
            else:
                self._dialogue_ui_visible = True
                self._set_dialogue_ui_widgets_visible(True)
            self._update_dialogue_ui_geometry()
            if on_finished is not None:
                on_finished()
            return False

        if clamped_duration == 0:
            self._dialogue_ui_offset_design = target_offset
            if hide_on_finish:
                self._dialogue_ui_visible = False
                self._set_dialogue_ui_widgets_visible(False)
            else:
                self._dialogue_ui_visible = True
                self._set_dialogue_ui_widgets_visible(True)
            self._update_dialogue_ui_geometry()
            if on_finished is not None:
                on_finished()
            return False

        easing = self._make_easing_curve(easing_name)
        self._dialogue_ui_anim = _DialogueUiAnimation(
            started_at=time.monotonic(),
            duration_ms=clamped_duration,
            easing=easing,
            from_offset_design=self._dialogue_ui_offset_design,
            to_offset_design=target_offset,
            hide_on_finish=hide_on_finish,
            on_finished=on_finished,
        )
        if not self._dialogue_ui_timer.isActive():
            self._dialogue_ui_timer.start()
        return True

    def _on_dialogue_ui_anim_tick(self) -> None:
        anim = self._dialogue_ui_anim
        if anim is None:
            self._dialogue_ui_timer.stop()
            return

        elapsed_ms = (time.monotonic() - anim.started_at) * 1000.0
        progress = min(1.0, max(0.0, elapsed_ms / float(anim.duration_ms)))
        eased = float(anim.easing.valueForProgress(progress))
        self._dialogue_ui_offset_design = (
            anim.from_offset_design
            + (anim.to_offset_design - anim.from_offset_design) * eased
        )
        self._update_dialogue_ui_geometry()

        if progress < 1.0:
            return

        self._dialogue_ui_offset_design = anim.to_offset_design
        self._dialogue_ui_anim = None
        self._dialogue_ui_timer.stop()
        if anim.hide_on_finish:
            self._dialogue_ui_visible = False
            self._set_dialogue_ui_widgets_visible(False)
        else:
            self._dialogue_ui_visible = True
            self._set_dialogue_ui_widgets_visible(True)
        self._update_dialogue_ui_geometry()
        if anim.on_finished is not None:
            anim.on_finished()

    def _set_dialogue_ui_widgets_visible(self, visible: bool) -> None:
        self.ui_overlay.setVisible(visible)
        self.name_label.setVisible(visible)
        self.text_label.setVisible(visible)

    def _dialogue_ui_offset_px(self) -> int:
        if self.height() <= 0:
            return 0
        return int(
            round(
                self._dialogue_ui_offset_design
                * self.height()
                / float(self.DESIGN_HEIGHT)
            )
        )

    def _map_design_rect(self, rect: QRect) -> QRect:
        width = max(1, self.width())
        height = max(1, self.height())
        x = int(rect.x() * width / self.DESIGN_WIDTH)
        y = int(rect.y() * height / self.DESIGN_HEIGHT)
        mapped_width = int(rect.width() * width / self.DESIGN_WIDTH)
        mapped_height = int(rect.height() * height / self.DESIGN_HEIGHT)
        return QRect(x, y, mapped_width, mapped_height)

    def _update_dialogue_ui_geometry(self) -> None:
        offset_px = self._dialogue_ui_offset_px()
        self.ui_overlay.setGeometry(0, offset_px, self.width(), self.height())
        overlay_size = (max(1, self.width()), max(1, self.height()))
        if not self._ui_pixmap.isNull():
            if self._ui_scaled_size != overlay_size:
                self._ui_scaled_pixmap = self._ui_pixmap.scaled(
                    self.size(),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
                self._ui_scaled_size = overlay_size
            self.ui_overlay.setPixmap(self._ui_scaled_pixmap)

        name_rect = self._map_design_rect(self.NAME_RECT_DESIGN)
        text_rect = self._map_design_rect(self.TEXT_RECT_DESIGN)
        name_rect.translate(0, offset_px)
        text_rect.translate(0, offset_px)
        self.name_label.setGeometry(name_rect)
        self.text_label.setGeometry(text_rect)

    @staticmethod
    def _clamp_opacity(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _update_bg_geometry(self) -> None:
        if self._bg_pixmap.isNull():
            return

        self.scene_bg.setGeometry(self.rect())
        bg_size = (max(1, self.width()), max(1, self.height()))
        if self._bg_scaled_size != bg_size:
            self._bg_scaled_pixmap = self._bg_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            self._bg_scaled_size = bg_size
        self.scene_bg.setPixmap(self._bg_scaled_pixmap)

    def _load_scene_noise_frames(self) -> list[QPixmap]:
        root = asset_path("pic", "backgrounds")
        if not root.exists():
            return []

        frame_paths = sorted(root.glob("noise_*.*"), key=lambda p: p.name.lower())
        frames: list[QPixmap] = []
        for path in frame_paths:
            pixmap = self._load_cached_pixmap(path)
            if pixmap is None:
                continue
            frames.append(pixmap)
        return frames

    def _apply_scene_noise_frame(self, frame_index: int) -> None:
        if frame_index < 0 or frame_index >= len(self._scene_noise_frames):
            return
        frame = self._scene_noise_frames[frame_index]
        if frame.isNull():
            return

        target_size = self._scene_noise_overlay.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = self.size()
        scaled = frame.scaled(
            target_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self._scene_noise_overlay.setPixmap(scaled)

    def _on_scene_noise_tick(self) -> None:
        self._scene_noise_index += 1
        if self._scene_noise_index >= len(self._scene_noise_frames):
            self._finish_scene_noise_playback()
            return
        self._apply_scene_noise_frame(self._scene_noise_index)

    def _finish_scene_noise_playback(self) -> None:
        self._scene_noise_timer.stop()
        self._scene_noise_overlay.hide()
        # 在 noise 结束后再清一次，防止旧文本在过渡收尾时闪回。
        self.clear_dialogue_content()

        callback = self._scene_noise_on_finished
        self._scene_noise_on_finished = None
        if callback is not None:
            callback()

        # 稍后再恢复对话层，让 WebView 有机会完成空内容刷新。
        QTimer.singleShot(self.NOISE_CLEAR_SETTLE_MS, self._restore_dialogue_ui_after_noise)

    def _restore_dialogue_ui_after_noise(self) -> None:
        self._set_dialogue_ui_widgets_visible(
            self._dialogue_ui_visible or self._dialogue_ui_anim is not None
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        self._update_bg_geometry()
        self.sprite_root.setGeometry(self.rect())
        self._pause_overlay.setGeometry(self.rect())
        self._scene_noise_overlay.setGeometry(self.rect())
        if self._scene_noise_overlay.isVisible():
            self._apply_scene_noise_frame(self._scene_noise_index)
        self._update_dialogue_ui_geometry()

        for state in self._sprites.values():
            self._apply_sprite_state(state)
        for state in self._extra_textboxes.values():
            self._apply_extra_textbox_state(state)
        self._refresh_sprite_stack()
        self._refresh_extra_textboxes_stack()
        self._setup_z_order()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._paused:
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.advanceRequested.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.toggle_paused()
            event.accept()
            return

        if self._paused:
            event.accept()
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.advanceRequested.emit()
        super().keyPressEvent(event)
