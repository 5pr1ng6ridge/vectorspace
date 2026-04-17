"""Helpers for building scene script nodes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

SceneNode = dict[str, Any]
SceneCallable = Callable[..., Any]
SceneLinearItem = SceneNode | SceneCallable
SceneLinearScript = Iterable[SceneLinearItem]


def _node(node_type: str, **fields: Any) -> SceneNode:
    node: SceneNode = {"type": node_type}
    node.update(fields)
    return node


def _set_optional(
    node: SceneNode,
    key: str,
    value: Any,
    *,
    caster: Callable[[Any], Any] | None = None,
) -> None:
    if value is None:
        return
    node[key] = caster(value) if caster is not None else value


def _set_many(
    node: SceneNode,
    values: dict[str, Any],
    *,
    caster: Callable[[Any], Any] | None = None,
) -> None:
    for key, value in values.items():
        _set_optional(node, key, value, caster=caster)


def _apply_timing_fields(
    node: SceneNode,
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool | None = None,
) -> None:
    _set_optional(node, "duration_ms", duration_ms, caster=int)
    _set_optional(node, "easing", easing)
    if wait is not None:
        node["wait"] = bool(wait)


def _apply_axis_fields(
    node: SceneNode,
    *,
    x: float | None = None,
    y: float | None = None,
    dx: float | None = None,
    dy: float | None = None,
) -> None:
    _set_many(
        node,
        {
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
        },
        caster=float,
    )


def _apply_visual_fields(
    node: SceneNode,
    *,
    scale: float | None = None,
    dscale: float | None = None,
    opacity: float | None = None,
    dopacity: float | None = None,
    z: int | None = None,
) -> None:
    _set_many(
        node,
        {
            "scale": scale,
            "dscale": dscale,
            "opacity": opacity,
            "dopacity": dopacity,
        },
        caster=float,
    )
    _set_optional(node, "z", z, caster=int)


def _apply_text_style_fields(
    node: SceneNode,
    *,
    text: str | None = None,
    font_size: int | None = None,
    color: str | None = None,
) -> None:
    _set_optional(node, "text", text)
    _set_optional(node, "font_size", font_size, caster=int)
    _set_optional(node, "color", color)


def bg(file: str) -> SceneNode:
    return _node("bg", file=file)


def say(
    speaker: str,
    text: str,
    *,
    auto_next: bool = False,
) -> SceneNode:
    node = _node("say", speaker=speaker, text=text)
    if auto_next:
        node["auto_next"] = True
    return node


def formula(latex: str) -> SceneNode:
    return _node("formula", latex=latex)


def style(
    *,
    font_size: int | None = None,
    color: str | None = None,
    name_font_size: int | None = None,
    name_color: str | None = None,
) -> SceneNode:
    node = _node("style")
    _set_optional(node, "font_size", font_size, caster=int)
    _set_optional(node, "color", color)
    _set_optional(node, "name_font_size", name_font_size, caster=int)
    _set_optional(node, "name_color", name_color)
    return node


def typing(
    *,
    speed_ms: int | None = None,
    cps: float | None = None,
    sfx: bool | None = None,
    sfx_volume: float | None = None,
    sfx_file: str | None = None,
    sfx_folder: str | None = None,
    sfx_min_interval_ms: int | None = None,
) -> SceneNode:
    node = _node("typing")
    _set_optional(node, "speed_ms", speed_ms, caster=int)
    _set_optional(node, "cps", cps, caster=float)
    if sfx is not None:
        node["sfx"] = bool(sfx)
    _set_optional(node, "sfx_volume", sfx_volume, caster=float)
    _set_optional(node, "sfx_file", sfx_file)
    _set_optional(node, "sfx_folder", sfx_folder)
    _set_optional(node, "sfx_min_interval_ms", sfx_min_interval_ms, caster=int)
    return node


def call(fn: SceneCallable) -> SceneNode:
    return _node("call", fn=fn)


def jump(scene_name: str) -> SceneNode:
    return _node("jump", scene=scene_name)


def terminal_write(text: str, *, end: str = "\n") -> SceneNode:
    return _node("terminal_write", text=text, end=end)


def close_gameview(*, confirm: bool = False) -> SceneNode:
    return _node("close_gameview", confirm=bool(confirm))


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

    return _node("wait", duration_ms=max(0, int(resolved_ms or 0)))


def delay(*args: Any, **kwargs: Any) -> SceneNode:
    return wait(*args, **kwargs)


def sleep(*args: Any, **kwargs: Any) -> SceneNode:
    return wait(*args, **kwargs)


def wait_click() -> SceneNode:
    return _node("wait_click")


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
    node = _node("dialogue_ui_show", wait=bool(wait))
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
    return node


def dialogue_ui_hide(
    *,
    duration_ms: int | None = None,
    easing: str | None = None,
    wait: bool = False,
) -> SceneNode:
    node = _node("dialogue_ui_hide", wait=bool(wait))
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
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
    node = _node(
        "textbox_register",
        id=textbox_id,
        rect_x=float(rect_x),
        rect_y=float(rect_y),
        rect_w=float(rect_w),
        rect_h=float(rect_h),
        visible=bool(visible),
    )
    _apply_text_style_fields(node, text=text, font_size=font_size, color=color)
    _set_optional(node, "pos_x", x, caster=float)
    _set_optional(node, "pos_y", y, caster=float)
    _apply_visual_fields(node, scale=scale, opacity=opacity, z=z)
    return node


def textbox_set_text(
    textbox_id: str,
    text: str,
    *,
    visible: bool | None = None,
) -> SceneNode:
    node = _node("textbox_set_text", id=textbox_id, text=text)
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
    node = _node("textbox_show", id=textbox_id, wait=bool(wait))
    _apply_text_style_fields(node, text=text, font_size=font_size, color=color)
    _apply_axis_fields(node, x=x, y=y, dx=dx, dy=dy)
    _apply_visual_fields(
        node,
        scale=scale,
        dscale=dscale,
        opacity=opacity,
        dopacity=dopacity,
        z=z,
    )
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
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
    node = _node(
        "textbox_hide",
        id=textbox_id,
        wait=bool(wait),
        remove=bool(remove),
    )
    _apply_axis_fields(node, dx=dx, dy=dy)
    _apply_visual_fields(node, dscale=dscale, opacity=opacity)
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
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
    node = _node("textbox_transform", id=textbox_id, wait=bool(wait))
    _apply_axis_fields(node, x=x, y=y, dx=dx, dy=dy)
    _apply_visual_fields(
        node,
        scale=scale,
        dscale=dscale,
        opacity=opacity,
        dopacity=dopacity,
        z=z,
    )
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
    return node


def textbox_remove(textbox_id: str) -> SceneNode:
    return _node("textbox_remove", id=textbox_id)


def textbox_clear() -> SceneNode:
    return _node("textbox_clear")


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
    node = _node(
        "image_register",
        id=image_id,
        file=file,
        visible=bool(visible),
    )
    _set_optional(node, "folder", folder)
    _apply_axis_fields(node, x=x, y=y)
    _apply_visual_fields(node, scale=scale, opacity=opacity, z=z)
    _set_optional(node, "anchor_x", anchor_x, caster=float)
    _set_optional(node, "anchor_y", anchor_y, caster=float)
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
    node = _node("image_show", id=image_id, wait=bool(wait))
    _set_optional(node, "file", file)
    _set_optional(node, "folder", folder)
    _apply_axis_fields(node, x=x, y=y, dx=dx, dy=dy)
    _apply_visual_fields(
        node,
        scale=scale,
        dscale=dscale,
        opacity=opacity,
        dopacity=dopacity,
        z=z,
    )
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
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
    node = _node(
        "image_hide",
        id=image_id,
        wait=bool(wait),
        remove=bool(remove),
    )
    _apply_axis_fields(node, dx=dx, dy=dy)
    _apply_visual_fields(node, dscale=dscale, opacity=opacity)
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
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
    node = _node("image_transform", id=image_id, wait=bool(wait))
    _apply_axis_fields(node, x=x, y=y, dx=dx, dy=dy)
    _apply_visual_fields(
        node,
        scale=scale,
        dscale=dscale,
        opacity=opacity,
        dopacity=dopacity,
        z=z,
    )
    _apply_timing_fields(node, duration_ms=duration_ms, easing=easing)
    return node


def image_remove(image_id: str) -> SceneNode:
    return _node("image_remove", id=image_id)


def image_clear() -> SceneNode:
    return _node("image_clear")


def scene(
    scene_id: str,
    script: SceneLinearScript,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a standard scene dict."""
    return {"id": scene_id, "defaults": dict(defaults or {}), "script": script}
