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
        "I feel that my δ is very serious. What should I do? I feel that I am a person with a very serious δ. It's because a+b is rather fragmented, and there are no orthogonal bases around me. So I feel like I am a strange matrix in the solution space. Therefore, when new vectors appear around me, many of the other party's linear transformations might just be due to unit orthogonalization.",
    )
    yield jump("Ch1/loop1")
