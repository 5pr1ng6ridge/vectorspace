"""主窗口封装。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QMainWindow

from .scene_manager import SceneManager
from .ui.game_view import GameView
from .ui.terminal_view import TerminalView


class GameWindow(QMainWindow):
    """终端主窗口；游戏窗口按需创建。"""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("VECTSPACE Terminal")
        self.resize(1280, 720)

        self.terminal_view = TerminalView(self, history_mode=False)
        self.setCentralWidget(self.terminal_view)

        self._game_window: QMainWindow | None = None
        self._game_view: GameView | None = None
        self._scene_manager: SceneManager | None = None
        self._scene_loaded = False

        self.terminal_view.startGameRequested.connect(self.enter_game)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._game_window is not None and self._game_window.isVisible():
            self._game_window.close()
        super().closeEvent(event)

    def enter_game(self) -> None:
        if self._game_window is None:
            self._create_game_window()

        if self._scene_manager is not None and not self._scene_loaded:
            self._scene_manager.load_scene("prologue")
            self._scene_loaded = True

        if self._game_window is None:
            return
        self._game_window.showFullScreen()
        self._game_window.raise_()
        self._game_window.activateWindow()
        self._set_terminal_windowed_after_start()
        self.lower()

    def _create_game_window(self) -> None:
        game_window = QMainWindow()
        game_window.setWindowTitle("VECTSPACE")
        game_window.resize(1920, 1080)

        game_view = GameView(game_window)
        game_window.setCentralWidget(game_view)
        game_window.installEventFilter(self)
        game_view.installEventFilter(self)

        self._game_window = game_window
        self._game_view = game_view
        self._scene_manager = SceneManager(
            game_view,
            history_logger=self.terminal_view.append_history,
        )

    def _set_terminal_windowed_after_start(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        self.resize(1280, 720)
        if not self.isVisible():
            self.show()

    def _bring_terminal_above_game(self) -> None:
        self._set_terminal_windowed_after_start()
        self.raise_()
        self.activateWindow()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.KeyPress and watched in {
            self._game_window,
            self._game_view,
        }:
            if isinstance(event, QKeyEvent) and event.key() == Qt.Key_Up:
                self._bring_terminal_above_game()
                return True
        return super().eventFilter(watched, event)
