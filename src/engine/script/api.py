"""Python 场景脚本辅助。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

SceneNode = dict[str, Any]
SceneCallable = Callable[..., Any]
SceneLinearItem = SceneNode | SceneCallable
SceneLinearScript = Iterable[SceneLinearItem]


def bg(file: str) -> SceneNode:
    return {"type": "bg", "file": file}


def say(speaker: str, text: str) -> SceneNode:
    return {"type": "say", "speaker": speaker, "text": text}


def formula(latex: str) -> SceneNode:
    return {"type": "formula", "latex": latex}


def style(
    *,
    font_size: int | None = None,
    color: str | None = None,
    name_font_size: int | None = None,
    name_color: str | None = None,
) -> SceneNode:
    node: SceneNode = {"type": "style"}
    if font_size is not None:
        node["font_size"] = int(font_size)
    if color is not None:
        node["color"] = color
    if name_font_size is not None:
        node["name_font_size"] = int(name_font_size)
    if name_color is not None:
        node["name_color"] = name_color
    return node


def typing(
    *,
    speed_ms: int | None = None,
    cps: float | None = None,
) -> SceneNode:
    node: SceneNode = {"type": "typing"}
    if speed_ms is not None:
        node["speed_ms"] = int(speed_ms)
    if cps is not None:
        node["cps"] = float(cps)
    return node


def call(fn: SceneCallable) -> SceneNode:
    return {"type": "call", "fn": fn}


def jump(scene_name: str) -> SceneNode:
    return {"type": "jump", "scene": scene_name}


def wait(
    seconds: float | None = None,
    *,
    ms: int | None = None,
    s: float | None = None,
) -> SceneNode:
    resolved_ms: int | None = None
    if ms is not None:
        resolved_ms = int(ms)
    elif s is not None:
        resolved_ms = int(round(float(s) * 1000.0))
    elif seconds is not None:
        resolved_ms = int(round(float(seconds) * 1000.0))

    if resolved_ms is None:
        resolved_ms = 0
    return {"type": "wait", "duration_ms": max(0, int(resolved_ms))}


def delay(*args: Any, **kwargs: Any) -> SceneNode:
    return wait(*args, **kwargs)


def sleep(*args: Any, **kwargs: Any) -> SceneNode:
    return wait(*args, **kwargs)


def wait_click() -> SceneNode:
    return {"type": "wait_click"}


def gap() -> SceneNode:
    return wait_click()


def beat() -> SceneNode:
    return wait_click()


def dialogue_ui_show(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "dialogue_ui_show", "wait": bool(wait)}
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def dialogue_ui_hide(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "dialogue_ui_hide", "wait": bool(wait)}
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def ui_show(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    return dialogue_ui_show(duration_ms=duration_ms, easing=easing, wait=wait)


def ui_hide(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    return dialogue_ui_hide(duration_ms=duration_ms, easing=easing, wait=wait)


def textbox_register(
    textbox_id: str,
    rect_x: float,
    rect_y: float,
    rect_w: float,
    rect_h: float,
    *,
    text: str | None = None,
    font_size: int | None = None,
    color: str | None = None,
    x: float | None = None,
    y: float | None = None,
    scale: float | None = None,
    opacity: float | None = None,
    z: int | None = None,
    visible: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "textbox_register",
        "id": textbox_id,
        "rect_x": float(rect_x),
        "rect_y": float(rect_y),
        "rect_w": float(rect_w),
        "rect_h": float(rect_h),
        "visible": bool(visible),
    }
    if text is not None:
        node["text"] = text
    if font_size is not None:
        node["font_size"] = int(font_size)
    if color is not None:
        node["color"] = color
    if x is not None:
        node["pos_x"] = float(x)
    if y is not None:
        node["pos_y"] = float(y)
    if scale is not None:
        node["scale"] = float(scale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if z is not None:
        node["z"] = int(z)
    return node


def textbox_set_text(
    textbox_id: str,
    text: str,
    *,
    visible: bool | None = None,
) -> SceneNode:
    node: SceneNode = {"type": "textbox_set_text", "id": textbox_id, "text": text}
    if visible is not None:
        node["visible"] = bool(visible)
    return node


def textbox_show(
    textbox_id: str,
    *,
    text: str | None = None,
    font_size: int | None = None,
    color: str | None = None,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "textbox_show", "id": textbox_id, "wait": bool(wait)}
    if text is not None:
        node["text"] = text
    if font_size is not None:
        node["font_size"] = int(font_size)
    if color is not None:
        node["color"] = color
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def textbox_hide(
    textbox_id: str,
    *,
    dx: float | None = None,
    dy: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
    remove: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "textbox_hide",
        "id": textbox_id,
        "wait": bool(wait),
        "remove": bool(remove),
    }
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def textbox_transform(
    textbox_id: str,
    *,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {"type": "textbox_transform", "id": textbox_id, "wait": bool(wait)}
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def textbox_remove(textbox_id: str) -> SceneNode:
    return {"type": "textbox_remove", "id": textbox_id}


def textbox_clear() -> SceneNode:
    return {"type": "textbox_clear"}


def extra_textbox_register(*args: Any, **kwargs: Any) -> SceneNode:
    return textbox_register(*args, **kwargs)


def extra_textbox_set_text(*args: Any, **kwargs: Any) -> SceneNode:
    return textbox_set_text(*args, **kwargs)


def extra_textbox_show(*args: Any, **kwargs: Any) -> SceneNode:
    return textbox_show(*args, **kwargs)


def extra_textbox_hide(*args: Any, **kwargs: Any) -> SceneNode:
    return textbox_hide(*args, **kwargs)


def extra_textbox_transform(*args: Any, **kwargs: Any) -> SceneNode:
    return textbox_transform(*args, **kwargs)


def extra_textbox_remove(textbox_id: str) -> SceneNode:
    return textbox_remove(textbox_id)


def extra_textbox_clear() -> SceneNode:
    return textbox_clear()


def image_register(
    image_id: str,
    file: str,
    *,
    folder: str | None = None,
    x: float | None = None,
    y: float | None = None,
    scale: float | None = None,
    opacity: float | None = None,
    z: int | None = None,
    anchor_x: float | None = None,
    anchor_y: float | None = None,
    visible: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_register",
        "id": image_id,
        "file": file,
        "visible": bool(visible),
    }
    if folder is not None:
        node["folder"] = folder
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if scale is not None:
        node["scale"] = float(scale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if z is not None:
        node["z"] = int(z)
    if anchor_x is not None:
        node["anchor_x"] = float(anchor_x)
    if anchor_y is not None:
        node["anchor_y"] = float(anchor_y)
    return node


def image_show(
    image_id: str,
    *,
    file: str | None = None,
    folder: str | None = None,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_show",
        "id": image_id,
        "wait": bool(wait),
    }
    if file is not None:
        node["file"] = file
    if folder is not None:
        node["folder"] = folder
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_hide(
    image_id: str,
    *,
    dx: float | None = None,
    dy: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
    remove: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_hide",
        "id": image_id,
        "wait": bool(wait),
        "remove": bool(remove),
    }
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_transform(
    image_id: str,
    *,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node: SceneNode = {
        "type": "image_transform",
        "id": image_id,
        "wait": bool(wait),
    }
    if x is not None:
        node["x"] = float(x)
    if y is not None:
        node["y"] = float(y)
    if dx is not None:
        node["dx"] = float(dx)
    if dy is not None:
        node["dy"] = float(dy)
    if scale is not None:
        node["scale"] = float(scale)
    if dscale is not None:
        node["dscale"] = float(dscale)
    if opacity is not None:
        node["opacity"] = float(opacity)
    if dopacity is not None:
        node["dopacity"] = float(dopacity)
    if z is not None:
        node["z"] = int(z)
    if duration_ms is not None:
        node["duration_ms"] = int(duration_ms)
    if easing is not None:
        node["easing"] = easing
    return node


def image_remove(image_id: str) -> SceneNode:
    return {"type": "image_remove", "id": image_id}


def image_clear() -> SceneNode:
    return {"type": "image_clear"}


def scene(
    scene_id: str,
    script: SceneLinearScript,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造标准场景字典。"""
    return {"id": scene_id, "defaults": dict(defaults or {}), "script": script}
