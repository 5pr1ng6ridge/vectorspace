"""应用入口。"""

import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .resources.fonts import load_font_family
from .resources.paths import init_resource_root
from .window import GameWindow


def run() -> None:
    """启动 Qt 应用并进入事件循环。"""
    app = QApplication(sys.argv)

    # 打包后环境下优先用 _MEIPASS；开发环境下回退到仓库根目录。
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    game_dir = base_dir / "game"
    init_resource_root(game_dir)

    # 设置应用默认字体（用于非 WebView 组件，如姓名框等）。
    family = load_font_family("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")
    if family:
        app.setFont(QFont(family, 20))

    win = GameWindow()
    win.show()#FullScreen() 
    sys.exit(app.exec())
