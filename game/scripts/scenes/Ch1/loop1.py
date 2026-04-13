"""
- 使用 `yield` 逐条产出节点，便于直接写 if/for/while 与函数返回值分支。
"""

from __future__ import annotations

from collections.abc import Iterator

from src.engine.script.api import SceneLinearItem, bg, image_hide, image_register, image_show, image_transform, jump, say, style, typing

SCENE_ID = "loop1"
DEFAULTS = {
    "style": {
        "name_font_size": 27,
        "font_size": 33,
        "color": "#F5A9B8",
        "name_color": "#FFFFFF",
    },
    "typing": {"speed_ms": 30},
}


def build_scene() -> Iterator[SceneLinearItem]:
    """按顺序产出场景节点。"""
    yield bg("bg_vstest.png")
    yield typing(speed_ms=3)
    yield style(font_size=27, color="#FF0000", name_font_size=40, name_color="#FF0000")
    yield say(
        "",
        "现在的小孩真是一点都不满足，以前我们老资历连核被膜都没有，DNA复制只有一个起始位点，但那时候很方便，mRNA都是多顺反子，也不用剪切、加帽加尾，只有核糖体、鞭毛就很满足了，丙酮酸倒在细胞质基质上吃，有的类囊体都直接裸露在细胞质基质中，不过当时还是很方便的，能边转录边翻译，一个mRNA能结合多个核糖体，现在的这些小孩居然不想要限制性内切酶，去要什么表观遗传、分化，真是搞不懂",
    )
    yield jump("Ch1/loop1")
