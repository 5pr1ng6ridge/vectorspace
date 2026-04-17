"""主窗口封装。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QWidget

from .save_system import SaveSystem
from .scene_manager import SceneManager
from .ui.game_view import GameView
from .ui.save_slot_view import SaveSlotView
from .ui.terminal_view import TerminalView


class GameWindow(QMainWindow):
    """终端主窗口；游戏窗口按需创建。"""

    MESSAGE_BOX_FONT_SIZE_PT = 16
    ENTER_GAME_AFTER_LOAD_DELAY_MS = 80

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("VECTSPACE Terminal")
        self.resize(1280, 720)

        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self.terminal_view = TerminalView(self, history_mode=False)
        self.save_slot_view = SaveSlotView(self)
        self._stack.addWidget(self.terminal_view)
        self._stack.addWidget(self.save_slot_view)
        self._stack.setCurrentWidget(self.terminal_view)

        self._save_system = SaveSystem()
        self._save_ui_active = False
        self._resume_game_after_save_ui = False

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
            self._game_window.showFullScreen()
            self._game_window.raise_()
            self._game_window.activateWindow()
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
        game_window.resize(1920, 1080)

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

    def _on_scene_changed(self, scene_name: str) -> None:
        self._loaded_scene_name = str(scene_name).strip() or None

    def _set_terminal_windowed_after_start(self) -> None:
        if self.isFullScreen() or self.isMinimized():
            self.showNormal()
        self.resize(1280, 720)
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
        if self._save_ui_active:
            return
        if self._game_window is None or not self._game_window.isVisible():
            return

        self._save_ui_active = True
        self._resume_game_after_save_ui = (
            self._game_view is not None and not self._game_view.is_paused()
        )
        if self._game_view is not None:
            self._game_view.set_paused(True)

        self._refresh_save_slots()
        self._stack.setCurrentWidget(self.save_slot_view)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.save_slot_view.setFocus(Qt.ActiveWindowFocusReason)

    def _close_save_ui(self) -> None:
        if not self._save_ui_active:
            return

        self._save_ui_active = False
        self._stack.setCurrentWidget(self.terminal_view)
        self._set_terminal_windowed_after_start()
        self.lower()

        if self._game_view is not None and self._resume_game_after_save_ui:
            self._game_view.set_paused(False)
        self._resume_game_after_save_ui = False

        if self._game_window is not None and self._game_window.isVisible():
            self._game_window.raise_()
            self._game_window.activateWindow()
            self._focus_game_view()

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

        self._save_ui_active = False
        self._resume_game_after_save_ui = False
        self._stack.setCurrentWidget(self.terminal_view)
        self.terminal_view.set_collapse_on_down_enabled(False)
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
                if event.key() == Qt.Key_Up:
                    self._bring_terminal_above_game()
                    return True
                if event.key() == Qt.Key_Down:
                    self._collapse_terminal_below_game()
                    return True
        return super().eventFilter(watched, event)
