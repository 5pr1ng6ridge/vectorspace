# src/engine/window.py
from PySide6.QtWidgets import QMainWindow
from .ui.game_view import GameView
from .scene_manager import SceneManager

class GameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("VECTORSP∀⊂∃(prototype)")
        self.resize(1920, 1080)
        # 如果你现在就想锁死分辨率也可以：
        # self.setFixedSize(1920, 1080)

        self.game_view = GameView(self)
        self.setCentralWidget(self.game_view)

        self.scene_manager = SceneManager(self.game_view)
        self.scene_manager.load_scene("prologue")