# src/engine/ui/game_view.py
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import QPixmap, QMouseEvent, QFontDatabase, QFont

from ..resources.paths import asset_path


class GameView(QWidget):
    advanceRequested = Signal()

    # 以 1920x1080 为“设计稿”尺寸
    DESIGN_WIDTH = 1920
    DESIGN_HEIGHT = 1080

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        
        # === 场景背景层 ===
        
        self.scene_bg = QLabel(self)
        self.scene_bg.setScaledContents(True)
        self._bg_pixmap = QPixmap()  # 原始背景图存这里

        # === UI 覆盖 ===
        ui_path = asset_path("ui", "dial_box_overlay.png")
        self.ui_overlay = QLabel(self)
        self.ui_overlay.setScaledContents(True)
        self._ui_pixmap = QPixmap(str(ui_path))

        # 角色 label
        self.char_layer = QLabel(self)
        self.char_layer.setScaledContents(True)
        self.char_layer.setAttribute(Qt.WA_TranslucentBackground)

        # 姓名 label
        self.name_label = QLabel(self)
        self.name_label.setAttribute(Qt.WA_TranslucentBackground)
        self.name_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        # 对话 label
        self.text_label = QLabel(self)
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text_label.setAttribute(Qt.WA_TranslucentBackground)

        # 初始大小：你可以直接把主窗口设成 1920x1080，下面的 resizeEvent 会自动调整
        self._apply_fonts()
        
    def _setup_z_order(self) -> None:
        self.bg_scene.lower()
        self.char_layer.raise_()
        self.ui_overlay.raise_()
        self.name_label.raise_()
        self.text_label.raise_()
        
    def _apply_fonts(self) -> None:
        # 加载像素体字体
        font_path = asset_path("fonts", "fusion-pixel-12px-monospaced-zh_hans.ttf")  # 替换成你的文件名
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            print("加载 fusion-pixel-12px-monospaced-zh_hans.ttf 失败喵")
            return

        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            print("没拿到字体 family 喵")
            return

        family = families[0]
        print("使用字体 family:", family)

        # 给姓名框/对话框各自设字号
        name_font = QFont(family, 40)   # 姓名稍微大一点
        text_font = QFont(family, 35)   # 正文小一点

        self.name_label.setFont(name_font)
        self.text_label.setFont(text_font)
        
        self.name_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.text_label.setStyleSheet("color: #FFFFFF; background: transparent;")

    # ========== 背景切换接口 ==========
    def set_background(self, filename: str) -> None:
        """切换场景背景，比如 'room_day.png'."""
        path = asset_path("backgrounds", filename)
        pix = QPixmap(str(path))
        if pix.isNull():
            print(f"[GameView] 无法加载背景: {path}")
            return
        self._bg_pixmap = pix
        self._update_bg_geometry()

    def _update_bg_geometry(self) -> None:
        """根据窗口大小重新铺背景图。"""
        if self._bg_pixmap.isNull():
            return
        self.scene_bg.setGeometry(self.rect())
        scaled = self._bg_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self.scene_bg.setPixmap(scaled)

    # ========== 原来的文本/公式接口 ==========
    def set_name(self, name: str) -> None:
        self.name_label.setText(name)

    def show_text(self, text: str) -> None:
        self.text_label.setPixmap(QPixmap())  # 清掉公式图
        self.text_label.setText(text)
        self.text_label.setVisible(True)

    def show_formula(self, pixmap: QPixmap) -> None:
        self.text_label.setText("")
        self.text_label.setPixmap(pixmap)
        self.text_label.setVisible(True)

    # ====== 布局：根据窗口大小，把 UI 图和 label 放到设计位置 ======

    # ========== 尺寸变化时重新铺层 ==========
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # 背景 & UI 全屏铺
        self._update_bg_geometry()

        self.ui_overlay.setGeometry(self.rect())
        scaled_ui = self._ui_pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self.ui_overlay.setPixmap(scaled_ui)
        w = self.width()
        h = self.height()

        NAME_RECT_DESIGN = QRect(0, 746, 468, 70)
        TEXT_RECT_DESIGN = QRect(140, 874, 1640, 256)

        # 按比例映射到当前窗口大小（保证放大缩小时位置和尺寸整体跟着缩放）
        def map_rect(r: QRect) -> QRect:
            x = int(r.x() * w / self.DESIGN_WIDTH)
            y = int(r.y() * h / self.DESIGN_HEIGHT)
            rw = int(r.width() * w / self.DESIGN_WIDTH)
            rh = int(r.height() * h / self.DESIGN_HEIGHT)
            return QRect(x, y, rw, rh)

        name_rect = map_rect(NAME_RECT_DESIGN)
        text_rect = map_rect(TEXT_RECT_DESIGN)

        self.name_label.setGeometry(name_rect)
        self.text_label.setGeometry(text_rect)

    # ====== 点击过场 ======

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.advanceRequested.emit()
        super().mousePressEvent(event)