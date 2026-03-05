from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PySide6.QtGui import QImage, QPixmap

matplotlib.rcParams["mathtext.fontset"] = "stix"          # 比较接近 Times / STIX 那挂
#matplotlib.rcParams["mathtext.fontset"] = "dejavuserif"   # 和 DejaVu Serif 系统 UI 比较搭
#matplotlib.rcParams["mathtext.fontset"] = "stixsans"

def _render_latex(expr: str, dpi: int, font_size: int, pad_inches: float, color: str = "white") -> QPixmap:
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_alpha(0.0)
    fig.text(0, 0, f"${expr}$", fontsize=font_size, color=color)

    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        transparent=True,
        bbox_inches="tight",
        pad_inches=pad_inches,
    )
    plt.close(fig)

    buf.seek(0)
    image = QImage.fromData(buf.getvalue(), "PNG")
    return QPixmap.fromImage(image)


def render_latex_block(expr: str, dpi: int = 150, font_size: int = 18) -> QPixmap:
    return _render_latex(expr, dpi=dpi, font_size=font_size, pad_inches=0.1)


def render_latex_inline(expr: str, dpi: int = 200, font_size: int = 28) -> QPixmap:
    return _render_latex(expr, dpi=dpi, font_size=font_size, pad_inches=0.02)
