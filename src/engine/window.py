"""主窗口封装。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QWidget

from .save_system import SaveSystem
from .scene_manager import SceneManager
from .ui.game_view import GameView
from .ui.crt_text_edit import CrtTextEdit
from .ui.save_slot_view import SaveSlotView
from .ui.settings_view import SettingsView
from .ui.terminal_view import TerminalView


class GameWindow(QMainWindow):
    """终端主窗口；游戏窗口按需创建。"""

    MESSAGE_BOX_FONT_SIZE_PT = 16
    ENTER_GAME_AFTER_LOAD_DELAY_MS = 80
    TERMINAL_WINDOW_SIZE = (1280, 720)
    DEFAULT_GAME_RESOLUTION = (1920, 1080)
    FULLSCREEN_RESOLUTION_LABEL = "\u5168\u5c4f"
    _MAX_WINDOW_DIMENSION = 16_777_215
    RESOLUTION_OPTIONS: tuple[tuple[str, tuple[int, int]], ...] = (
        ("1280x720", (1280, 720)),
        ("1920x1080", (1920, 1080)),
        ("2560x1440", (2560, 1440)),
    )
    TEST_OPTIONS: tuple[str, ...] = ("ALPHA", "BETA", "GAMMA")

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("VECTSPACE Terminal")
        self.resize(*self.TERMINAL_WINDOW_SIZE)

        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self.terminal_view = TerminalView(self, history_mode=False)
        self.save_slot_view = SaveSlotView(self)
        self.settings_view = SettingsView(self)
        self._stack.addWidget(self.terminal_view)
        self._stack.addWidget(self.save_slot_view)
        self._stack.addWidget(self.settings_view)
        self._stack.setCurrentWidget(self.terminal_view)

        self._save_system = SaveSystem()
        self._overlay_mode: str | None = None
        self._resume_game_after_overlay = False
        self._game_resolution = self.DEFAULT_GAME_RESOLUTION
        self._resolution_label = self.FULLSCREEN_RESOLUTION_LABEL
        self._pending_resolution_label = self._resolution_label
        self._test_option_label = self.TEST_OPTIONS[0]

        self._game_window: QMainWindow | None = None
        self._game_view: GameView | None = None
        self._scene_manager: SceneManager | None = None
        self._loaded_scene_name: str | None = None
        self._closing_application = False
        self._skip_next_game_close_confirm = False
        self._shortcut_terminal_up: QShortcut | None = None
        self._shortcut_terminal_down: QShortcut | None = None

        self.terminal_view.startGameRequested.connect(self.enter_game)
        self.terminal_view.collapseRequested.connect(self._collapse_terminal_below_game)
        self.save_slot_view.closeRequested.connect(self._close_save_ui)
        self.save_slot_view.saveRequested.connect(self._save_to_slot)
        self.save_slot_view.loadRequested.connect(self._load_from_slot)
        self.settings_view.closeRequested.connect(self._close_settings_ui)
        self.settings_view.settingChanged.connect(self._on_setting_changed)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._show_confirm_dialog(
            parent=self,
            title=" ",
            text=(
                "确定要关闭 world2vec_Terminal 吗？\n"
                "这将关闭所有连接，未保存的数据将会丢失。"
            ),
        ):
            event.ignore()
            return

        self._closing_application = True
        if self._game_window is not None and self._game_window.isVisible():
            self._game_window.close()
        event.accept()

    def enter_game(self, scene_name: str = "") -> None:
        if self._game_window is None:
            self._create_game_window()

        if self._game_window is None:
            return

        def _after_scene_loaded() -> None:
            if self._game_window is None:
                return
            self._show_game_window()
            self.terminal_view.set_collapse_on_down_enabled(True)
            self._focus_game_view()
            QTimer.singleShot(
                self.ENTER_GAME_AFTER_LOAD_DELAY_MS,
                self._finish_enter_game_transition,
            )

        target_scene = scene_name.strip() or (self._loaded_scene_name or "prologue")
        if self._scene_manager is not None and target_scene != self._loaded_scene_name:
            self._scene_manager.load_scene(target_scene, on_loaded=_after_scene_loaded)
            return
        _after_scene_loaded()

    def _finish_enter_game_transition(self) -> None:
        if self._game_window is None or not self._game_window.isVisible():
            return
        self._set_terminal_windowed_after_start()
        self.lower()
        self._focus_game_view()

    def _focus_game_view(self) -> None:
        if self._game_view is None:
            return
        self._game_view.setFocus(Qt.ActiveWindowFocusReason)
        QTimer.singleShot(
            0,
            lambda: self._game_view.setFocus(Qt.ActiveWindowFocusReason),
        )

    def _create_game_window(self) -> None:
        game_window = QMainWindow()
        game_window.setWindowTitle("VECTSPACE")

        game_view = GameView(game_window)
        game_window.setCentralWidget(game_view)
        game_window.installEventFilter(self)
        game_view.installEventFilter(self)

        shortcut_up = QShortcut(QKeySequence(Qt.Key_Up), game_window)
        shortcut_up.setContext(Qt.WindowShortcut)
        shortcut_up.activated.connect(self._bring_terminal_above_game)

        shortcut_down = QShortcut(QKeySequence(Qt.Key_Down), game_window)
        shortcut_down.setContext(Qt.WindowShortcut)
        shortcut_down.activated.connect(self._collapse_terminal_below_game)

        self._game_window = game_window
        self._game_view = game_view
        self._shortcut_terminal_up = shortcut_up
        self._shortcut_terminal_down = shortcut_down
        self._scene_manager = SceneManager(
            game_view,
            history_logger=self.terminal_view.append_history,
            terminal_logger=self._write_terminal_from_scene,
            close_game_callback=self._close_game_from_scene,
            scene_changed_callback=self._on_scene_changed,
        )
        self._apply_game_resolution()

    def _on_scene_changed(self, scene_name: str) -> None:
        self._loaded_scene_name = str(scene_name).strip() or None

    def _show_game_window(self) -> None:
        if self._game_window is None:
            return
        self._apply_game_resolution()
        if self._is_fullscreen_resolution_selected():
            self._game_window.showFullScreen()
        else:
            self._game_window.show()
        self._game_window.raise_()
        self._game_window.activateWindow()

    def _apply_game_resolution(self) -> None:
        if self._game_window is None:
            return

        if self._is_fullscreen_resolution_selected():
            self._apply_fullscreen_resolution()
            return

        self._game_resolution = self._label_to_resolution(self._resolution_label)
        width, height = self._game_resolution
        self._game_window.showNormal()
        self._game_window.setFixedSize(width, height)
        self._center_game_window()

    def _apply_fullscreen_resolution(self) -> None:
        if self._game_window is None:
            return

        screen = self._target_game_screen()
        geometry = screen.geometry() if screen is not None else None
        self._game_resolution = self._fullscreen_layout_resolution(screen)
        self._game_window.setMinimumSize(0, 0)
        self._game_window.setMaximumSize(
            self._MAX_WINDOW_DIMENSION,
            self._MAX_WINDOW_DIMENSION,
        )
        if geometry is not None:
            self._game_window.setGeometry(geometry)

    def _center_game_window(self) -> None:
        if self._game_window is None:
            return

        screen = self._target_game_screen()
        if screen is None:
            return

        geometry = screen.geometry()
        width, height = self._game_resolution
        x = geometry.x() + max(0, (geometry.width() - width) // 2)
        y = geometry.y() + max(0, (geometry.height() - height) // 2)
        self._game_window.move(QPoint(x, y))

    def _set_terminal_windowed_after_start(self) -> None:
        if self.isFullScreen() or self.isMinimized():
            self.showNormal()
        self.resize(*self.TERMINAL_WINDOW_SIZE)
        if not self.isVisible():
            self.show()

    def _bring_terminal_above_game(self) -> None:
        self._set_terminal_windowed_after_start()
        self.raise_()
        self.activateWindow()

    def _collapse_terminal_below_game(self) -> None:
        if self._game_window is None or not self._game_window.isVisible():
            return
        if self.isVisible():
            self.lower()
        self._game_window.raise_()
        self._game_window.activateWindow()
        self._focus_game_view()

    def _open_save_ui(self) -> None:
        self._refresh_save_slots()
        self._open_overlay_ui("save", self.save_slot_view)

    def _close_save_ui(self) -> None:
        if self._overlay_mode != "save":
            return
        self._close_overlay_ui()

    def _refresh_save_slots(self) -> None:
        self.save_slot_view.set_slots(self._save_system.list_slots())

    def _save_to_slot(self, slot_index: int) -> None:
        if self._scene_manager is None:
            return

        payload = self._scene_manager.create_save_payload()
        if payload is None:
            return

        payload["title"] = f"Archive Slot {slot_index + 1:02d}"
        self._save_system.save_slot(slot_index, payload)
        self._refresh_save_slots()

    def _load_from_slot(self, slot_index: int) -> None:
        if self._scene_manager is None:
            return

        payload = self._save_system.load_slot(slot_index)
        if payload is None:
            return

        if self._scene_manager.load_save_payload(payload):
            self._close_save_ui()

    def _open_settings_ui(self) -> None:
        self._pending_resolution_label = self._resolution_label
        self._refresh_settings_items()
        self._open_overlay_ui("settings", self.settings_view)

    @staticmethod
    def _prepare_widget_fullscreen_crt(widget: QWidget) -> None:
        if isinstance(widget, CrtTextEdit):
            widget.prepare_fullscreen_postprocess()

    def _close_settings_ui(self) -> None:
        if self._overlay_mode != "settings":
            return
        self._apply_pending_settings()
        self._close_overlay_ui()

    def _refresh_settings_items(self) -> None:
        resolution_options = [self.FULLSCREEN_RESOLUTION_LABEL]
        resolution_options.extend(label for label, _ in self.RESOLUTION_OPTIONS)
        self.settings_view.set_items(
            [
                {
                    "key": "resolution",
                    "label": "Resolution",
                    "options": resolution_options,
                    "selected_index": self._resolution_option_index(
                        self._pending_resolution_label
                    ),
                },
                {
                    "key": "test_item",
                    "label": "Test Item",
                    "options": list(self.TEST_OPTIONS),
                    "selected_index": self._test_option_index(),
                },
            ]
        )

    def _on_setting_changed(self, key: str, value: str) -> None:
        if key == "resolution":
            self._pending_resolution_label = value
            return

        if key == "test_item":
            self._test_option_label = value

    def _apply_pending_settings(self) -> None:
        if self._resolution_label != self._pending_resolution_label:
            self._resolution_label = self._pending_resolution_label
            self._apply_game_resolution()
            if self._game_window is not None and self._game_window.isVisible():
                self._show_game_window()

    def _open_overlay_ui(self, mode: str, widget: QWidget) -> None:
        if self._overlay_mode is not None:
            return
        if self._game_window is None or not self._game_window.isVisible():
            return

        self._overlay_mode = mode
        self._resume_game_after_overlay = (
            self._game_view is not None and not self._game_view.is_paused()
        )
        if self._game_view is not None:
            self._game_view.set_paused(True)

        self._stack.setCurrentWidget(widget)
        self._prepare_widget_fullscreen_crt(widget)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        widget.setFocus(Qt.ActiveWindowFocusReason)

    def _close_overlay_ui(self) -> None:
        if self._overlay_mode is None:
            return

        self._overlay_mode = None
        self._stack.setCurrentWidget(self.terminal_view)
        self._set_terminal_windowed_after_start()
        self.lower()

        if self._game_view is not None and self._resume_game_after_overlay:
            self._game_view.set_paused(False, animate=False)
        self._resume_game_after_overlay = False

        if self._game_window is not None and self._game_window.isVisible():
            self._game_window.raise_()
            self._game_window.activateWindow()
            self._focus_game_view()

    def _show_confirm_dialog(
        self,
        *,
        parent: QWidget | None,
        title: str,
        text: str,
    ) -> bool:
        box = QMessageBox(parent if parent is not None else self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setEscapeButton(QMessageBox.No)

        font = box.font()
        font.setPointSize(self.MESSAGE_BOX_FONT_SIZE_PT)
        box.setFont(font)

        return box.exec() == QMessageBox.Yes

    def _can_close_game_window_now(self) -> bool:
        if self._closing_application:
            return True

        if self._skip_next_game_close_confirm:
            self._skip_next_game_close_confirm = False
            return True

        if self._game_window is None:
            return True

        return self._show_confirm_dialog(
            parent=self._game_window,
            title="关闭游戏",
            text="确定要关闭与 world 的连接吗？未保存的数据将会丢失。",
        )

    def _on_game_window_closed(self) -> None:
        if self._closing_application:
            return

        if self._game_window is not None and self._game_window.isVisible():
            return

        self._overlay_mode = None
        self._resume_game_after_overlay = False
        self._stack.setCurrentWidget(self.terminal_view)
        self.terminal_view.set_collapse_on_down_enabled(False)
        self._prepare_widget_fullscreen_crt(self.terminal_view)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.terminal_view.ensure_input_mode(append_prompt=True)

    def close_game_view(self, *, confirm: bool = True) -> bool:
        if self._game_window is None or not self._game_window.isVisible():
            return False

        if not confirm:
            self._skip_next_game_close_confirm = True

        self._game_window.close()
        return self._game_window is not None and not self._game_window.isVisible()

    def _write_terminal_from_scene(self, text: str) -> None:
        payload = text if isinstance(text, str) else str(text)
        if not payload:
            return
        self.terminal_view.print_block(payload)

    def _close_game_from_scene(self, confirm: bool = False) -> None:
        self.close_game_view(confirm=bool(confirm))

    def _resolution_option_index(self, label: str | None = None) -> int:
        resolution_options = [self.FULLSCREEN_RESOLUTION_LABEL]
        resolution_options.extend(label for label, _ in self.RESOLUTION_OPTIONS)
        current_label = label if label is not None else self._resolution_label
        for index, label in enumerate(resolution_options):
            if label == current_label:
                return index
        return 0

    def _test_option_index(self) -> int:
        for index, label in enumerate(self.TEST_OPTIONS):
            if label == self._test_option_label:
                return index
        return 0

    def _label_to_resolution(self, label: str) -> tuple[int, int]:
        for option_label, resolution in self.RESOLUTION_OPTIONS:
            if option_label == label:
                return resolution
        return self.DEFAULT_GAME_RESOLUTION

    def _resolution_to_label(self, resolution: tuple[int, int]) -> str:
        for option_label, option_resolution in self.RESOLUTION_OPTIONS:
            if option_resolution == resolution:
                return option_label
        width, height = resolution
        return f"{width}x{height}"

    def _is_fullscreen_resolution_selected(self) -> bool:
        return self._resolution_label == self.FULLSCREEN_RESOLUTION_LABEL

    def _target_game_screen(self):
        if self._game_window is not None:
            screen = self._game_window.screen()
            if screen is not None:
                return screen
        return self.screen() or QGuiApplication.primaryScreen()

    def _fullscreen_layout_resolution(self, screen) -> tuple[int, int]:
        if screen is None:
            return self.DEFAULT_GAME_RESOLUTION

        screen_size = screen.geometry().size()
        resolution = (screen_size.width(), screen_size.height())
        for _, option_resolution in self.RESOLUTION_OPTIONS:
            if option_resolution == resolution:
                return option_resolution
        return resolution

    def eventFilter(self, watched, event) -> bool:
        if watched is self._game_window and event.type() == QEvent.Close:
            if not self._can_close_game_window_now():
                event.ignore()
                return True

            QTimer.singleShot(0, self._on_game_window_closed)
            return False

        if event.type() == QEvent.KeyPress and watched in {
            self._game_window,
            self._game_view,
        }:
            if isinstance(event, QKeyEvent):
                if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_S:
                    self._open_save_ui()
                    return True
                if event.modifiers() == Qt.NoModifier and event.key() == Qt.Key_P:
                    self._open_settings_ui()
                    return True
                if event.key() == Qt.Key_Up:
                    self._bring_terminal_above_game()
                    return True
                if event.key() == Qt.Key_Down:
                    self._collapse_terminal_below_game()
                    return True
        return super().eventFilter(watched, event)
