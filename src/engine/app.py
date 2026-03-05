# src/engine/app.py
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from .window import GameWindow
from .resources.paths import init_resource_root, asset_path

def run() -> None:
    app = QApplication(sys.argv)

    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    game_dir = base_dir / "game"
    init_resource_root(game_dir)

    # 在这里加载一次字体，然后设成默认字体
    font_path = asset_path("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 20))
    #def show_fullscreen(self):
    #    self
    win = GameWindow()
    win.show()
    sys.exit(app.exec())