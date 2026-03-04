# src/engine/ui/game_view.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QMouseEvent


class GameView(QWidget):
    """
    主游戏画面容器。
    现在版：
      - 左键点击全屏触发 advanceRequested
      - show_text / show_formula 二选一显示
    以后可以替换成多层结构。
    """

    advanceRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 文本区域
        self.text_label = QLabel("点击继续喵")
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignCenter)

        # 简单粗暴一点：讲述者名字也先合并进文本里或者先不用
        # 以后可以分名字框、对话框控件

        # 公式区域
        self.formula_label = QLabel()
        self.formula_label.setAlignment(Qt.AlignCenter)
        self.formula_label.setVisible(False)

        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.formula_label, 2)

    # ====== 对 ScriptRunner 暴露的接口 ======

    def show_text(self, text: str) -> None:
        """显示一段对白文本。"""
        self.formula_label.setVisible(False)
        self.formula_label.clear()

        self.text_label.setText(text)
        self.text_label.setVisible(True)

    def show_formula(self, pixmap: QPixmap) -> None:
        """显示一张公式图片。"""
        self.text_label.setVisible(False)

        self.formula_label.setPixmap(pixmap)
        self.formula_label.setVisible(True)

    # ====== 点击过场 ======

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.advanceRequested.emit()
        super().mousePressEvent(event)