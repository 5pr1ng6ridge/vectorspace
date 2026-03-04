# src/engine/app.py
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from .window import GameWindow
from .resources.paths import init_resource_root

def run() -> None:
    """应用入口。"""
    app = QApplication(sys.argv)

    # 计算工程根目录（打包/源码两种情况都尽量适配）
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    game_dir = base_dir / "game"

    # 告诉资源模块：资源在哪
    init_resource_root(game_dir)

    # 创建主窗口
    win = GameWindow()
    win.show()

    sys.exit(app.exec())