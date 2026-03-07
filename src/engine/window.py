"""主窗口封装。"""

from PySide6.QtWidgets import QMainWindow

from .scene_manager import SceneManager
from .ui.game_view import GameView


class GameWindow(QMainWindow):
    """应用主窗口。

    这里负责装配 ``GameView`` 与 ``SceneManager``，并启动默认场景。
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("VECTORSP∀⊂∃(prototype?) - 并没有renpy好用")
        self.resize(1920, 1080)
        # 若需要固定分辨率可启用:
        # self.setFixedSize(1920, 1080)

        self.game_view = GameView(self)
        self.setCentralWidget(self.game_view)

        self.scene_manager = SceneManager(self.game_view)
        self.scene_manager.load_scene("prologue")
