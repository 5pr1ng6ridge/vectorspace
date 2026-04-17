"""序章场景脚本（Generator 版）。

说明：
- 内容由 `prologue.json` 迁移而来。
- 使用 `yield` 逐条产出节点，便于直接写 if/for/while 与函数返回值分支。
"""

from __future__ import annotations

from collections.abc import Iterator

from src.engine.script.api import (
    SceneLinearItem,
    bg, dialogue_ui_hide, dialogue_ui_show, 
    image_hide, image_register, image_show, image_transform,
    jump, say, style, 
    textbox_hide, textbox_register, textbox_set_text, textbox_show, textbox_transform, typing
)
SCENE_ID = "prologue"
DEFAULTS = {
    "style": {
        "name_font_size": 27,
        "font_size": 33,
        "color": "#F5A9B8",
        "name_color": "#FFFFFF",
    },
    "typing": {"speed_ms": 25},
}


def build_scene() -> Iterator[SceneLinearItem]:
    """按顺序产出场景节点。"""
    yield dialogue_ui_hide(duration_ms=0, easing="in_circ", wait=True)
    yield bg("line1.png")
    yield image_register(
        "idge",
        "jelly.png",
        folder="char",
        x=1260,
        y=1000,
        scale=0.8,
        z=10,above_web=True
    )
    yield typing(
        speed_ms=24,
        sfx=True,
        sfx_volume=.6,
        sfx_min_interval_ms=45,
    )
    yield dialogue_ui_show(duration_ms=400, easing="out_circ", wait=False)
    ###################
    yield say(
        "ヨミビトシラズ",
        "在不计其数的<span style=\"color: white;\"><i>archive</i></span>之上  在半径25cm的窗户上  注视着你 <pause ms=\"500\"/><h1 style=\"font-size:30px;\"><i><epsilon>掃いて捨てるほどの記録の上  半径25cmの窓で  きみを見ている  </epsilon></i></h1>",
    )
    yield image_show(
        "idge",
        opacity=1.0,
        duration_ms=260,
        easing="out_quad",
        
    )
    yield style(font_size=43, color="#F5A9B8", name_font_size=40, name_color="#FFFFFF")
    yield say(
        "?",
        "ciallo~<shake><rainbow>这是一行测试文本这是一行测试文本</rainbow></shake>$f'(x) = \\lim_{\\Delta x \\to 0} \\frac{f(x+\\Delta x)-f(x)}{\\Delta x} $这是一行测试文本！@#￥%……&*（",
    )
    yield image_transform(
        "idge",
        dx=-340,
        #dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
        wait=True,
    )
    yield image_transform(
        "idge",
        dx=340,
        #dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
        wait=True,
    )
    yield image_transform(
        "idge",
        dx=-340,
        #dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
        wait=True,
    )
    yield image_transform(
        "idge",
        dx=340,
        #dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
        wait=True,
    )
    yield image_transform(
        "idge",
        dx=-340,
        #dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
        wait=True,
    )
    yield image_transform(
        "idge",
        dx=340,
        #dscale=0.05,
        duration_ms=2200,
        easing="in_out_sine",
        wait=False,
    )
    yield style(font_size=43, color="#F5A9B8", name_font_size=40, name_color="#FFFFFF")
    yield say("!", "这是<epsilon>$f(x) = f(a) + f'(a)(x-a) + \\frac{f''(a)}{2!}(x-a)^2...$</epsilon>")
    yield say("?", "$\\mathcal{L}\\{f(t)\\} = F(s) = \\int_0^\\infty f(t)e^{-st}\\,dt $喵")
    yield image_hide("idge", duration_ms=180, easing="in_quad")
    yield textbox_register(
        "hint", rect_x=0, rect_y=120, rect_w=420, rect_h=220,
        text="<mt style=\"font-size:54px;\">$$\\begin{pmatrix} a & b & c \\\\ e & f & g \\\\ i & j & k \\end{pmatrix} $$</mt>", font_size=28, color="#FF0000", opacity=0.0, z=30
    )
    yield textbox_show("hint", opacity=1.0, duration_ms=220, easing="out_quad", wait=True)
    yield textbox_transform("hint", dy=30, duration_ms=180, easing="in_out_sine")
    yield say(
        "!",
        "这里可以放矩阵。",
    )
    yield textbox_set_text("hint", "这个文本框的内容是可以修改的。$E=mc^2$。")
    yield textbox_set_text("hint", "是可以修改的。$E=mc^2$。")
    yield textbox_hide("hint", duration_ms=180, easing="in_quad",wait=True)
    yield say("?", "by VECTSPACE vibe coding 开发组。vectorちゃん可愛い、大好き！偉いね、すごい、天才！(?")
    yield typing(speed_ms=3)
    yield jump("Ch1/loop1")
