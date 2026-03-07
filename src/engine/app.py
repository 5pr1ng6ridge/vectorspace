"""应用入口。"""

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from .resources.paths import asset_path, init_resource_root
from .window import GameWindow


def run() -> None:
    """启动 Qt 应用并进入事件循环。"""
    app = QApplication(sys.argv)

    # 打包后环境下优先用 _MEIPASS；开发环境下回退到仓库根目录。
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    game_dir = base_dir / "game"
    init_resource_root(game_dir)

    # 设置应用默认字体（用于非 WebView 组件，如姓名框等）。
    font_path = asset_path("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 20))

    win = GameWindow()
    win.showFullScreen()  # .show()
    sys.exit(app.exec())
