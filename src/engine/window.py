# src/engine/window.py
from PySide6.QtWidgets import QMainWindow
from .ui.game_view import GameView
from .scene_manager import SceneManager

class GameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Math VN Engine (WIP)")
        self.resize(1280, 720)

        self.game_view = GameView(self)
        self.setCentralWidget(self.game_view)

        # 场景管理器：负责加载脚本、切换场景
        self.scene_manager = SceneManager(self.game_view)

        # 启动时先加载一个场景
        self.scene_manager.load_scene("prologue")