"""对话文本渲染组件（Web 方案）。

设计目标:
1. 文本主体走 QWebEngineView，支持 KaTeX 与 CSS 动画。
2. 逐字机与布局稳定并存：未显示内容透明占位，不触发行重排。
3. 对外接口保持简单：``set_text_segments`` / ``set_formula_text``。
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import html
import json
import os
import re
import sys

from PySide6.QtCore import QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QKeySequence, QPixmap
try:
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "QtWebEngine is unavailable. Install dependencies (including pyside6-addons) first."
    ) from exc

from ..resources.paths import asset_path

_DIALOGUE_FONT_ASSET = "fonts/fusion-pixel-12px-monospaced-zh_hans.ttf"
# 仅解析并放行有限标签，避免脚本直接注入任意 HTML。
_HTML_TAG_RE = re.compile(r"<\s*(/)?\s*([a-zA-Z][a-zA-Z0-9-]*)\s*([^<>]*?)\s*(/?)\s*>")
_HTML_ATTR_RE = re.compile(
    r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')'
)
_ALLOWED_SIMPLE_TAGS = {"b", "i", "u", "em", "strong", "small", "sup", "sub"}
_FX_TAG_CLASS_MAP = {
    "shake": "fx-shake",
    "wave": "fx-wave",
    "pulse": "fx-pulse",
    "glow": "fx-glow",
    "rainbow": "fx-rainbow",
    "epsilon": "fx-epsilon",
    "delta": "fx-delta"
}
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
_PAUSE_TAG_RE = re.compile(r"<\s*pause\b([^<>]*?)\s*/?\s*>", re.IGNORECASE)
_SPEED_TAG_RE = re.compile(r"<\s*speed\b([^<>]*?)\s*/?\s*>", re.IGNORECASE)


def _is_truthy_env(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def _allow_unsafe_html_tags_by_default() -> bool:
    """开发阶段默认放行所有 HTML 标签。

    覆盖方式:
    - `VECTSPACE_ALLOW_ALL_HTML_TAGS=1`: 强制放行
    - `VECTSPACE_FORCE_SAFE_HTML_TAGS=1`: 强制白名单
    """
    if _is_truthy_env("VECTSPACE_ALLOW_ALL_HTML_TAGS"):
        return True
    if _is_truthy_env("VECTSPACE_FORCE_SAFE_HTML_TAGS"):
        return False
    return getattr(sys, "_MEIPASS", None) is None


@dataclass(frozen=True)
class DialogueSegment:
    """对话片段。

    kind:
    - ``text``: 普通文本
    - ``formula``: ``$...$`` 公式
    - ``html``: 受控 HTML 标签
    """
    kind: str
    content: str


def _append_text_segment(segments: list[DialogueSegment], content: str) -> None:
    if not content:
        return

    if segments and segments[-1].kind == "text":
        last = segments[-1]
        segments[-1] = DialogueSegment("text", last.content + content)
        return

    segments.append(DialogueSegment("text", content))


def _parse_span_attrs(attrs_text: str) -> str | None:
    """解析并过滤 ``<span ...>`` 属性。

    安全策略:
    - 仅允许 ``class=...``
    - class 值仅允许字母、数字、下划线、连字符与空格
    """
    attrs_text = attrs_text.strip()
    if not attrs_text:
        return ""

    normalized_parts: list[str] = []
    index = 0
    while index < len(attrs_text):
        while index < len(attrs_text) and attrs_text[index].isspace():
            index += 1
        if index >= len(attrs_text):
            break

        match = _HTML_ATTR_RE.match(attrs_text, index)
        if match is None:
            return None

        attr_name = match.group(1).lower()
        attr_value_raw = match.group(2) if match.group(2) is not None else match.group(3)
        attr_value = " ".join(attr_value_raw.split())

        if attr_name != "class":
            return None

        if not re.fullmatch(r"[a-zA-Z0-9_\- ]{1,128}", attr_value):
            return None

        normalized_parts.append(f'class="{html.escape(attr_value, quote=True)}"')
        index = match.end()

    return " ".join(normalized_parts)


def _parse_pause_duration_literal(value: str, default_unit: str) -> int | None:

    token = value.strip().lower()
    if not token:
        return None

    unit = default_unit
    if token.endswith("ms"):
        unit = "ms"
        token = token[:-2].strip()
    elif token.endswith("s"):
        unit = "s"
        token = token[:-1].strip()

    if not re.fullmatch(r"\d+(?:\.\d+)?", token):
        return None

    number = float(token)
    if number < 0:
        return None

    duration_ms = number if unit == "ms" else number * 1000.0
    return max(0, min(600_000, int(round(duration_ms))))


def _parse_pause_duration_ms(attrs_text: str) -> int | None:
    """解析 <pause ...> 时长，返回毫秒。"""
    attrs_text = attrs_text.strip()
    if not attrs_text:
        return 500

    durations: list[int] = []
    index = 0
    used_named_attrs = False

    while index < len(attrs_text):
        while index < len(attrs_text) and attrs_text[index].isspace():
            index += 1
        if index >= len(attrs_text):
            break

        match = _HTML_ATTR_RE.match(attrs_text, index)
        if match is None:
            break

        used_named_attrs = True
        attr_name = match.group(1).lower()
        raw_value = match.group(2) if match.group(2) is not None else match.group(3)

        if attr_name in {"ms", "millisecond", "milliseconds"}:
            duration = _parse_pause_duration_literal(raw_value, default_unit="ms")
        elif attr_name in {
            "s",
            "sec",
            "secs",
            "second",
            "seconds",
            "t",
            "time",
            "duration",
        }:
            duration = _parse_pause_duration_literal(raw_value, default_unit="s")
        else:
            return None

        if duration is None:
            return None

        durations.append(duration)
        index = match.end()

    if used_named_attrs:
        if attrs_text[index:].strip():
            return None
        return durations[-1] if durations else 500

    return _parse_pause_duration_literal(attrs_text, default_unit="s")


def _parse_speed_interval_ms(attrs_text: str) -> int | None:
    """解析 <speed ...> 配置，返回打字间隔毫秒。"""
    attrs_text = attrs_text.strip()
    if not attrs_text:
        return None

    values: list[int] = []
    index = 0
    used_named_attrs = False

    while index < len(attrs_text):
        while index < len(attrs_text) and attrs_text[index].isspace():
            index += 1
        if index >= len(attrs_text):
            break

        match = _HTML_ATTR_RE.match(attrs_text, index)
        if match is None:
            break

        used_named_attrs = True
        attr_name = match.group(1).lower()
        raw_value = (match.group(2) if match.group(2) is not None else match.group(3)).strip()

        if attr_name in {"ms", "interval", "speed", "speed_ms", "type_interval_ms", "interval_ms"}:
            if raw_value == "-1":
                interval = -1
            else:
                interval = _parse_pause_duration_literal(raw_value, default_unit="ms")
                if interval is None:
                    return None
        elif attr_name in {"cps", "chars_per_second"}:
            if not re.fullmatch(r"\d+(?:\.\d+)?", raw_value):
                return None
            cps = float(raw_value)
            if cps <= 0:
                return None
            interval = int(round(1000.0 / cps))
        else:
            return None

        if interval == -1:
            values.append(-1)
        else:
            values.append(max(1, min(60_000, interval)))
        index = match.end()

    if used_named_attrs:
        if attrs_text[index:].strip():
            return None
        return values[-1] if values else None

    token = attrs_text.strip().lower()
    if token == "-1":
        return -1

    token_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(ms|s|cps)?", token)
    if token_match is None:
        return None

    number = float(token_match.group(1))
    if number <= 0:
        return None

    unit = token_match.group(2) or "ms"
    if unit == "cps":
        interval_ms = int(round(1000.0 / number))
    elif unit == "s":
        interval_ms = int(round(number * 1000.0))
    else:
        interval_ms = int(round(number))

    return max(1, min(60_000, interval_ms))


def _extract_pause_segment(text: str, start_index: int) -> tuple[int | None, int]:
    """从 text[start_index] 处提取 <pause ...> 指令。"""
    closing_index = text.find(">", start_index + 1)
    if closing_index == -1:
        return None, start_index

    if closing_index - start_index > 256:
        return None, start_index

    candidate = text[start_index : closing_index + 1]
    if "\n" in candidate or "\r" in candidate:
        return None, start_index

    match = _PAUSE_TAG_RE.fullmatch(candidate)
    if match is None:
        return None, start_index

    attrs_text = match.group(1) or ""
    duration_ms = _parse_pause_duration_ms(attrs_text)
    if duration_ms is None:
        return None, start_index

    return duration_ms, closing_index + 1


def _extract_speed_segment(text: str, start_index: int) -> tuple[int | None, int]:
    """从 text[start_index] 处提取 <speed ...> 指令。"""
    closing_index = text.find(">", start_index + 1)
    if closing_index == -1:
        return None, start_index

    if closing_index - start_index > 256:
        return None, start_index

    candidate = text[start_index : closing_index + 1]
    if "\n" in candidate or "\r" in candidate:
        return None, start_index

    match = _SPEED_TAG_RE.fullmatch(candidate)
    if match is None:
        return None, start_index

    attrs_text = match.group(1) or ""
    interval_ms = _parse_speed_interval_ms(attrs_text)
    if interval_ms is None:
        return None, start_index

    return interval_ms, closing_index + 1


def _sanitize_html_tag(candidate: str) -> str | None:
    """将候选标签规范化为可安全插入的 HTML。

    返回 ``None`` 表示标签不被允许，会按普通文本处理。
    """
    match = _HTML_TAG_RE.fullmatch(candidate)
    if match is None:
        return None

    is_closing = bool(match.group(1))
    tag_name = match.group(2).lower()
    attrs_text = match.group(3) or ""
    is_self_closing = bool(match.group(4))

    if is_closing:
        if attrs_text.strip() or is_self_closing:
            return None
        if tag_name in _FX_TAG_CLASS_MAP:
            return "</span>"
        if tag_name in _ALLOWED_SIMPLE_TAGS or tag_name == "span":
            return f"</{tag_name}>"
        return None

    if tag_name in _FX_TAG_CLASS_MAP:
        if attrs_text.strip() or is_self_closing:
            return None
        fx_class = _FX_TAG_CLASS_MAP[tag_name]
        return f'<span class="{fx_class}">'

    if tag_name == "br":
        if attrs_text.strip():
            return None
        return "<br/>"

    if tag_name == "span":
        if is_self_closing:
            return None
        attrs = _parse_span_attrs(attrs_text)
        if attrs is None:
            return None
        if attrs:
            return f"<span {attrs}>"
        return "<span>"

    if tag_name in _ALLOWED_SIMPLE_TAGS:
        if attrs_text.strip() or is_self_closing:
            return None
        return f"<{tag_name}>"

    return None


def _extract_supported_html_tag(
    text: str, start_index: int, allow_unsafe_html_tags: bool
) -> tuple[str | None, int]:
    """从文本中提取受支持标签。

    返回:
    - (sanitized_tag, next_index): 成功
    - (None, start_index): 失败
    """
    closing_index = text.find(">", start_index + 1)
    if closing_index == -1:
        return None, start_index

    if closing_index - start_index > 256:
        return None, start_index

    candidate = text[start_index : closing_index + 1]
    if "\n" in candidate or "\r" in candidate:
        return None, start_index

    if allow_unsafe_html_tags:
        # 开发阶段全放行时，仍优先保留内建标签规范化/简写映射（如 <rainbow> -> <span class="fx-rainbow">）。
        sanitized = _sanitize_html_tag(candidate)
        if sanitized is not None:
            return sanitized, closing_index + 1
        return candidate, closing_index + 1

    sanitized = _sanitize_html_tag(candidate)
    if sanitized is None:
        return None, start_index

    return sanitized, closing_index + 1


def parse_dialogue_segments(
    text: str, allow_unsafe_html_tags: bool | None = None
) -> list[DialogueSegment]:
    """将对话文本解析为片段序列。

    解析规则:
    - ``$...$`` -> formula
    - 受支持的 ``<tag>`` -> html
    - 其余内容 -> text
    """
    allow_all_html = (
        _allow_unsafe_html_tags_by_default()
        if allow_unsafe_html_tags is None
        else allow_unsafe_html_tags
    )

    segments: list[DialogueSegment] = []
    text_buffer: list[str] = []
    formula_buffer: list[str] = []
    in_formula = False
    formula_delimiter_len = 1
    formula_kind = "formula"
    index = 0

    while index < len(text):
        char = text[index]

        if char == "\\" and index + 1 < len(text) and text[index + 1] == "$":
            if in_formula:
                formula_buffer.append("\\$")
            else:
                text_buffer.append("$")
            index += 2
            continue

        if char == "$":
            if in_formula:
                is_closing = False
                if formula_delimiter_len == 2:
                    is_closing = index + 1 < len(text) and text[index + 1] == "$"
                else:
                    is_closing = True

                if is_closing:
                    expr = "".join(formula_buffer).strip()
                    if expr:
                        _append_text_segment(segments, "".join(text_buffer))
                        text_buffer.clear()
                        segments.append(DialogueSegment(formula_kind, expr))
                    else:
                        text_buffer.append("$" * (formula_delimiter_len * 2))

                    consumed = formula_delimiter_len
                    formula_buffer.clear()
                    in_formula = False
                    formula_delimiter_len = 1
                    formula_kind = "formula"
                    index += consumed
                    continue
            else:
                _append_text_segment(segments, "".join(text_buffer))
                text_buffer.clear()
                if index + 1 < len(text) and text[index + 1] == "$":
                    in_formula = True
                    formula_delimiter_len = 2
                    formula_kind = "formula_display"
                    index += 2
                else:
                    in_formula = True
                    formula_delimiter_len = 1
                    formula_kind = "formula"
                    index += 1
                continue

        if not in_formula and char == "<":
            pause_ms, next_index = _extract_pause_segment(text, index)
            if pause_ms is not None:
                _append_text_segment(segments, "".join(text_buffer))
                text_buffer.clear()
                segments.append(DialogueSegment("pause", str(pause_ms)))
                index = next_index
                continue

            speed_ms, next_index = _extract_speed_segment(text, index)
            if speed_ms is not None:
                _append_text_segment(segments, "".join(text_buffer))
                text_buffer.clear()
                segments.append(DialogueSegment("speed", str(speed_ms)))
                index = next_index
                continue

            html_tag, next_index = _extract_supported_html_tag(
                text, index, allow_all_html
            )
            if html_tag is not None:
                _append_text_segment(segments, "".join(text_buffer))
                text_buffer.clear()
                segments.append(DialogueSegment("html", html_tag))
                index = next_index
                continue

        target = formula_buffer if in_formula else text_buffer
        target.append(char)
        index += 1

    if in_formula:
        text_buffer.append("$" * formula_delimiter_len)
        text_buffer.extend(formula_buffer)

    _append_text_segment(segments, "".join(text_buffer))
    return segments


def count_reveal_units(segments: list[DialogueSegment]) -> int:
    """统计逐字机推进单位数。

    约定:
    - 文本按字符计数
    - 公式按 1 个单位计数
    - HTML 标签计 0（不会打断标签）
    """
    total = 0
    for segment in segments:
        if segment.kind in {"formula", "formula_display"}:
            total += 1
        elif segment.kind in {"html", "pause", "speed"}:
            total += 0
        else:
            total += len(segment.content)
    return total


def _hidden_text_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")


def _visible_text_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")


def _protect_formula_for_markdown(formula_text: str) -> str:
    """保护公式文本，避免 markdown 改写反斜杠导致矩阵行丢失。"""
    escaped = html.escape(formula_text, quote=False)
    return escaped.replace("\\", "&#92;")


def _segments_to_html(
    segments: list[DialogueSegment], visible_units: int | None
) -> str:
    """将片段拼装为 Markdown/HTML 混合文本。

    注意:
    - 未显示文本/公式使用 hidden-* class 占位，保持布局稳定。
    - HTML 标签总是原样输出（受上游白名单保护）。
    """
    remaining = visible_units
    parts: list[str] = []

    for segment in segments:
        if segment.kind in {"pause", "speed"}:
            continue

        if segment.kind == "html":
            parts.append(segment.content)
            continue

        if segment.kind in {"formula", "formula_display"}:
            if segment.kind == "formula_display":
                formula = f"$${segment.content}$$"
            else:
                formula = f"${segment.content}$"
            protected_formula = _protect_formula_for_markdown(formula)
            visible = remaining is None or remaining > 0
            if visible:
                parts.append(protected_formula)
            else:
                parts.append(f'<span class="hidden-math">{protected_formula}</span>')

            if remaining is not None and remaining > 0:
                remaining -= 1
            continue

        if remaining is None:
            parts.append(_visible_text_html(segment.content))
            continue

        if remaining <= 0:
            parts.append(f'<span class="hidden-text">{_hidden_text_html(segment.content)}</span>')
            continue

        visible_text = segment.content[:remaining]
        hidden_text = segment.content[remaining:]
        if visible_text:
            parts.append(_visible_text_html(visible_text))
        if hidden_text:
            parts.append(f'<span class="hidden-text">{_hidden_text_html(hidden_text)}</span>')
        remaining -= len(visible_text)

    return "".join(parts)


def _escape_css_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_shell_html(font_family: str, font_size_px: int, color_hex: str) -> str:
    """构建 WebView 的完整 HTML 壳页面。"""
    fallback_family = _escape_css_string(font_family)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="vendor/katex/katex.min.css">
  <style>
    @font-face {{
      font-family: "VectspaceDialogue";
      src: url("{_DIALOGUE_FONT_ASSET}") format("truetype");
      font-display: block;
    }}
    .katex {{
      font-size: 1.05em;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      background: transparent;
      overflow: hidden;
    }}
    #dialogue-root {{
      color: {color_hex};
      font-family: "VectspaceDialogue", "{fallback_family}", sans-serif;
      font-size: {font_size_px}px;
      line-height: 1.35;
      word-break: break-word;
      white-space: pre-wrap;
      user-select: none;
      -webkit-user-select: none;
      -webkit-touch-callout: none;
    }}
    #dialogue-root p {{
      margin: 0;
    }}
    #dialogue-root .hidden-text,
    #dialogue-root .hidden-math {{
      opacity: 0;
    }}
    #dialogue-root .katex-display {{
      margin: 0.05em 0;
      text-align: left;
    }}
    #dialogue-root .fx-shake,
    #dialogue-root .fx-wave,
    #dialogue-root .fx-pulse,
    #dialogue-root .fx-glow,
    #dialogue-root .fx-delta,
    #dialogue-root .fx-epsilon,
    #dialogue-root .fx-rainbow {{
      display: inline-block;
      will-change: transform, opacity, filter, text-shadow, color;
    }}
    #dialogue-root .fx-shake {{
      animation: fx-shake 0.18s linear infinite;
    }}
    #dialogue-root .fx-wave {{
      animation: fx-wave 0.9s ease-in-out infinite;
    }}
    #dialogue-root .fx-pulse {{
      animation: fx-pulse 1.0s ease-in-out infinite;
      transform-origin: center;
    }}
    #dialogue-root .fx-glow {{
      animation: fx-glow 1.1s ease-in-out infinite;
    }}
    #dialogue-root .fx-rainbow {{
      animation: fx-rainbow 1.6s linear infinite;
      color: #ff4d4d;
      -webkit-text-fill-color: currentColor;
    }}
    #dialogue-root .fx-rainbow * {{
      color: inherit !important;
      -webkit-text-fill-color: inherit !important;
    }}
    #dialogue-root .fx-epsilon {{
      animation: fx-epsilon 0.5s linear infinite;
      color: #5BCEFA;
      -webkit-text-fill-color: currentColor;
    }}
    #dialogue-root .fx-epsilon * {{
      color: inherit !important;
      -webkit-text-fill-color: inherit !important;
    }}
    @keyframes fx-shake {{
      0%   {{ transform: translateY(0); }}
      25%  {{ transform: translateY(-1px); }}
      50%  {{ transform: translateY(1px); }}
      75%  {{ transform: translateY(-1px); }}
      100% {{ transform: translateY(0); }}
    }}
    @keyframes fx-wave {{
      0%   {{ transform: translateY(0); }}
      50%  {{ transform: translateY(-0.12em); }}
      100% {{ transform: translateY(0); }}
    }}
    @keyframes fx-pulse {{
      0%, 100% {{ transform: scale(1.0); opacity: 1; }}
      50%      {{ transform: scale(1.06); opacity: 0.9; }}
    }}
    @keyframes fx-glow {{
      0%, 100% {{ text-shadow: 0 0 0.0em rgba(255,255,255,0.0); }}
      50%      {{ text-shadow: 0 0 0.32em rgba(255,255,255,0.85); }}
    }}
    @keyframes fx-rainbow {{
      0%   {{ color: #ff4d4d; -webkit-text-fill-color: #ff4d4d; }}
      17%  {{ color: #ff9f40; -webkit-text-fill-color: #ff9f40; }}
      34%  {{ color: #ffe14d; -webkit-text-fill-color: #ffe14d; }}
      50%  {{ color: #56f27f; -webkit-text-fill-color: #56f27f; }}
      67%  {{ color: #5ab0ff; -webkit-text-fill-color: #5ab0ff; }}
      84%  {{ color: #b57dff; -webkit-text-fill-color: #b57dff; }}
      100% {{ color: #ff4d4d; -webkit-text-fill-color: #ff4d4d; }}
    }}
    @keyframes fx-epsilon {{
      0%   {{ color: #5BCEFA; -webkit-text-fill-color: #5BCEFA; }}
      100% {{ color: #5BCEFA; -webkit-text-fill-color: #5BCEFA; }}
    }}
  </style>
</head>
<body>
  <div id="dialogue-root"></div>

  <script defer src="vendor/katex/katex.min.js"></script>
  <script defer src="vendor/katex/contrib/auto-render.min.js"></script>
  <script>
    window.__animSessionId = null;
    window.__animStartMs = null;

    function __syncAnimationTimeline(root) {{
      const sessionElem = root.querySelector("[data-anim-session]");
      const sessionId = sessionElem ? sessionElem.getAttribute("data-anim-session") : null;
      if (sessionId !== null && window.__animSessionId !== sessionId) {{
        window.__animSessionId = sessionId;
        window.__animStartMs = Date.now();
      }}
      if (window.__animStartMs === null) {{
        window.__animStartMs = Date.now();
      }}

      const elapsedSec = (Date.now() - window.__animStartMs) / 1000.0;
      const fxNodes = root.querySelectorAll(
        ".fx-shake, .fx-wave, .fx-pulse, .fx-glow, .fx-delta, .fx-epsilon, .fx-rainbow"
      );
      fxNodes.forEach(function(node) {{
        node.style.animationDelay = "-" + elapsedSec + "s";
      }});
    }}

    window.__applyDialogueHtml = function(payload, attempt) {{
      const currentAttempt = attempt || 0;
      const root = document.getElementById("dialogue-root");
      root.innerHTML = payload;
      if (!window.renderMathInElement) {{
        if (currentAttempt < 20) {{
          setTimeout(function() {{
            window.__applyDialogueHtml(payload, currentAttempt + 1);
          }}, 16);
        }}
        return;
      }}
      window.renderMathInElement(root, {{
        delimiters: [
          {{ left: "$$", right: "$$", display: true }},
          {{ left: "$", right: "$", display: false }}
        ],
        throwOnError: false,
        strict: "ignore"
      }});
      __syncAnimationTimeline(root);
    }};

    document.addEventListener("copy", function(event) {{
      event.preventDefault();
    }});
    document.addEventListener("cut", function(event) {{
      event.preventDefault();
    }});
    document.addEventListener("selectstart", function(event) {{
      event.preventDefault();
    }});
    document.addEventListener("dragstart", function(event) {{
      event.preventDefault();
    }});
    document.addEventListener("contextmenu", function(event) {{
      event.preventDefault();
    }});
  </script>
</body>
</html>
"""


class DialogueTextView(QWebEngineView):
    """对话 Web 控件。

    协作约定:
    - 渲染入口优先用 ``set_text_segments``。
    - 样式调整走 ``set_text_style``，内部会保留当前内容并热更新页面。
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._font_family = "sans-serif"
        self._font_size_px = 24
        self._font_color = "#FFFFFF"
        self._page_ready = False
        self._pending_html: str | None = None
        self._current_html = ""
        self._anim_session_id = 0
        self._base_url = self._resolve_assets_base_url()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setFocusPolicy(Qt.NoFocus) 

        self.page().setBackgroundColor(Qt.transparent)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        self.loadFinished.connect(self._on_page_loaded)
        self._reload_shell()

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._font_family = font.family() or "sans-serif"
        self._font_size_px = max(1, int(round(font.pointSizeF())))
        self._reload_shell()

    def set_text_style(
        self, font_size_px: int | None = None, color_hex: str | None = None
    ) -> None:
        """动态更新字号与颜色。"""
        style_changed = False

        if font_size_px is not None:
            new_font_size = max(1, int(font_size_px))
            if new_font_size != self._font_size_px:
                self._font_size_px = new_font_size
                style_changed = True

        if color_hex is not None:
            parsed = QColor(color_hex)
            if parsed.isValid():
                normalized = parsed.name()
                if normalized != self._font_color:
                    self._font_color = normalized
                    style_changed = True

        if style_changed:
            self._reload_shell()

    def set_text_segments(
        self, segments: list[DialogueSegment], visible_units: int | None = None
    ) -> None:
        """按分段渲染对话（用于打字机）。"""
        if visible_units == 0:
            self._anim_session_id += 1

        content_html = _segments_to_html(segments, visible_units)
        self._set_content_html(self._wrap_with_anim_session(content_html))

    def set_plain_dialogue(self, text: str) -> None:
        """直接渲染完整纯文本（内部仍支持公式/标签解析）。"""
        self._anim_session_id += 1
        self.set_text_segments(parse_dialogue_segments(text), None)

    def set_formula_text(self, expr: str) -> None:
        """渲染独立公式块。"""
        self._anim_session_id += 1
        content_html = _protect_formula_for_markdown(f"$$\n{expr}\n$$")
        self._set_content_html(self._wrap_with_anim_session(content_html))

    def set_formula_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self._set_content_html("")
            return
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
        self._set_content_html(
            "<img alt='formula' "
            "style='display:block;max-width:100%;height:auto;' "
            f"src='data:image/png;base64,{encoded}' />"
        )

    def _reload_shell(self) -> None:
        # 重载页面前保留当前内容，避免样式更新时出现闪空。
        self._page_ready = False
        self._pending_html = self._current_html
        shell_html = _build_shell_html(
            font_family=self._font_family,
            font_size_px=self._font_size_px,
            color_hex=self._font_color,
        )
        self.setHtml(shell_html, self._base_url)

    def _set_content_html(self, html_content: str) -> None:
        self._current_html = html_content
        payload = json.dumps(html_content)
        script = f"window.__applyDialogueHtml({payload});"
        if self._page_ready:
            self.page().runJavaScript(script)
            return
        self._pending_html = html_content

    def _on_page_loaded(self, ok: bool) -> None:
        self._page_ready = ok
        if not ok:
            return
        if self._pending_html is None:
            return
        self._set_content_html(self._pending_html)

    def _wrap_with_anim_session(self, html_content: str) -> str:
        return (
            f'<div data-anim-session="{self._anim_session_id}">'
            f"{html_content}"
            "</div>"
        )

    def _resolve_assets_base_url(self) -> QUrl:
        """校验本地资源并返回 ``assets/`` 的 baseUrl。"""
        assets_dir = asset_path()
        katex_dir = assets_dir / "vendor" / "katex"
        if not katex_dir.exists():
            raise RuntimeError(
                f"Local KaTeX assets are missing: {katex_dir}. "
                "Place katex.min.css/js, contrib/auto-render.min.js and fonts/ under this directory."
            )

        dialogue_font = assets_dir / _DIALOGUE_FONT_ASSET
        if not dialogue_font.exists():
            raise RuntimeError(
                f"Dialogue font file is missing: {dialogue_font}. "
                "Place the custom font under game/assets/fonts."
            )

        return QUrl.fromLocalFile(str(assets_dir) + "/")

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.Copy):
            event.accept()
            return

        if event.modifiers() & Qt.ControlModifier and event.key() in (
            Qt.Key_C,
            Qt.Key_Insert,
        ):
            event.accept()
            return

        super().keyPressEvent(event)
