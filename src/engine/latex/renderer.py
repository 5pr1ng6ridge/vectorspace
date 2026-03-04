# src/engine/latex/renderer.py
from io import BytesIO

import matplotlib
matplotlib.use("Agg")  # 无需 GUI 后端
import matplotlib.pyplot as plt

from PySide6.QtGui import QImage, QPixmap


def render_latex_block(expr: str, dpi: int = 150, font_size: int = 18) -> QPixmap:
    """
    渲染一条 LaTeX 数学表达式为 QPixmap。
    expr: 不含外层美元符号的表达式，比如 "f(x)=x^2+1"
    """

    # 新建 figure，大小先随便给，反正用 bbox_inches='tight' 截取内容
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.patch.set_alpha(0.0)  # 透明背景

    # 把公式画上去
    # 注意这里加一层 $ ... $，告诉 mathtext 这是数学模式
    fig.text(0, 0, f"${expr}$", fontsize=font_size)

    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.close(fig)

    buf.seek(0)
    data = buf.getvalue()

    img = QImage.fromData(data, "PNG")
    return QPixmap.fromImage(img)