"""游戏主视图。

图层顺序:
1. 背景图层
2. 角色层（预留）
3. 对话框 UI 贴图
4. 姓名框
5. 对话文本（WebView）
"""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from ..resources.paths import asset_path
from .dialogue_text import DialogueSegment, DialogueTextView


class GameView(QWidget):
    """承载游戏画面的主 Widget。"""

    advanceRequested = Signal()

    DESIGN_WIDTH = 1920
    DESIGN_HEIGHT = 1080

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.scene_bg = QLabel(self)
        self.scene_bg.setScaledContents(True)
        self._bg_pixmap = QPixmap()

        self.ui_overlay = QLabel(self)
        self.ui_overlay.setScaledContents(True)
        self._ui_pixmap = QPixmap(str(asset_path("ui", "dial_box_overlay.png")))

        self.char_layer = QLabel(self)
        self.char_layer.setScaledContents(True)
        self.char_layer.setAttribute(Qt.WA_TranslucentBackground)

        self.name_label = QLabel(self)
        self.name_label.setAttribute(Qt.WA_TranslucentBackground)
        self.name_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.text_label = DialogueTextView(self)
        self.text_label.setAttribute(Qt.WA_TranslucentBackground)
        # 点击交给父级处理，保证点击对话区域也能推进流程。
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._apply_fonts()
        self._setup_z_order()

    def _setup_z_order(self) -> None:
        self.scene_bg.lower()
        self.char_layer.raise_()
        self.ui_overlay.raise_()
        self.name_label.raise_()
        self.text_label.raise_()

    def _apply_fonts(self) -> None:
        """加载像素字体并应用到姓名框/对话框。"""
        font_path = asset_path("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            print("[GameView] failed to load dialogue font")
            return

        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            print("[GameView] no font families returned")
            return

        family = families[0]
        self.name_label.setFont(QFont(family, 40))
        self.text_label.setFont(QFont(family, 35))
        self.name_label.setStyleSheet("color: #FFFFFF; background: transparent;")

    def set_dialogue_style(
        self,
        font_size: int | None = None,
        color: str | None = None,
        name_font_size: int | None = None,
        name_color: str | None = None,
    ) -> None:
        """更新对话与姓名框样式（供 ``style`` 节点调用）。"""
        if name_font_size is not None:
            current_name_font = QFont(self.name_label.font())
            current_name_font.setPointSize(max(1, int(name_font_size)))
            self.name_label.setFont(current_name_font)

        if name_color is not None:
            self.name_label.setStyleSheet(
                f"color: {name_color}; background: transparent;"
            )

        self.text_label.set_text_style(font_size_px=font_size, color_hex=color)

    def set_background(self, filename: str) -> None:
        """切换背景图。"""
        path = asset_path("backgrounds", filename)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            print(f"[GameView] failed to load background: {path}")
            return

        self._bg_pixmap = pixmap
        self._update_bg_geometry()

    def _update_bg_geometry(self) -> None:
        if self._bg_pixmap.isNull():
            return

        self.scene_bg.setGeometry(self.rect())
        self.scene_bg.setPixmap(
            self._bg_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        )

    def set_name(self, name: str) -> None:
        self.name_label.setText(name)

    def show_text(self, text: str) -> None:
        self.text_label.set_plain_dialogue(text)
        self.text_label.setVisible(True)

    def show_text_segments(
        self, segments: list[DialogueSegment], visible_units: int | None = None
    ) -> None:
        self.text_label.set_text_segments(segments, visible_units)
        self.text_label.setVisible(True)

    def show_formula(self, expr: str) -> None:
        self.text_label.set_formula_text(expr)
        self.text_label.setVisible(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        self._update_bg_geometry()
        self.ui_overlay.setGeometry(self.rect())
        self.ui_overlay.setPixmap(
            self._ui_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        )

        width = self.width()
        height = self.height()

        name_rect_design = QRect(0, 746, 468, 70)
        text_rect_design = QRect(140, 874, 1640, 256)

        def map_rect(rect: QRect) -> QRect:
            """按设计分辨率映射到当前窗口尺寸。"""
            x = int(rect.x() * width / self.DESIGN_WIDTH)
            y = int(rect.y() * height / self.DESIGN_HEIGHT)
            mapped_width = int(rect.width() * width / self.DESIGN_WIDTH)
            mapped_height = int(rect.height() * height / self.DESIGN_HEIGHT)
            return QRect(x, y, mapped_width, mapped_height)

        self.name_label.setGeometry(map_rect(name_rect_design))
        self.text_label.setGeometry(map_rect(text_rect_design))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.advanceRequested.emit()
        super().mousePressEvent(event)
