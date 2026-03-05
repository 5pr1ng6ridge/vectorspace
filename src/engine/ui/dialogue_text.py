from __future__ import annotations

from dataclasses import dataclass
import base64
import html
import json
import re

import markdown
from PySide6.QtCore import QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QPixmap
try:
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "QtWebEngine is unavailable. Install dependencies (including pyside6-addons) first."
    ) from exc

from ..resources.paths import asset_path

_MARKDOWN_ESCAPE_RE = re.compile(r"([\\`*_{}\[\]()#+\-.!|>])")
_DIALOGUE_FONT_ASSET = "fonts/fusion-pixel-12px-monospaced-zh_hans.ttf"


@dataclass(frozen=True)
class DialogueSegment:
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


def parse_dialogue_segments(text: str) -> list[DialogueSegment]:
    segments: list[DialogueSegment] = []
    text_buffer: list[str] = []
    formula_buffer: list[str] = []
    in_formula = False
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
                expr = "".join(formula_buffer).strip()
                if expr:
                    _append_text_segment(segments, "".join(text_buffer))
                    text_buffer.clear()
                    segments.append(DialogueSegment("formula", expr))
                else:
                    text_buffer.append("$$")

                formula_buffer.clear()
                in_formula = False
            else:
                _append_text_segment(segments, "".join(text_buffer))
                text_buffer.clear()
                in_formula = True

            index += 1
            continue

        target = formula_buffer if in_formula else text_buffer
        target.append(char)
        index += 1

    if in_formula:
        text_buffer.append("$")
        text_buffer.extend(formula_buffer)

    _append_text_segment(segments, "".join(text_buffer))
    return segments


def count_reveal_units(segments: list[DialogueSegment]) -> int:
    total = 0
    for segment in segments:
        if segment.kind == "formula":
            total += 1
        else:
            total += len(segment.content)
    return total


def _escape_markdown_text(text: str) -> str:
    return _MARKDOWN_ESCAPE_RE.sub(r"\\\1", text)


def _hidden_text_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br/>")


def _segments_to_markdown(
    segments: list[DialogueSegment], visible_units: int | None
) -> str:
    remaining = visible_units
    parts: list[str] = []

    for segment in segments:
        if segment.kind == "formula":
            formula = f"${segment.content}$"
            visible = remaining is None or remaining > 0
            if visible:
                parts.append(formula)
            else:
                parts.append(f'<span class="hidden-math">{formula}</span>')

            if remaining is not None and remaining > 0:
                remaining -= 1
            continue

        if remaining is None:
            parts.append(_escape_markdown_text(segment.content))
            continue

        if remaining <= 0:
            parts.append(f'<span class="hidden-text">{_hidden_text_html(segment.content)}</span>')
            continue

        visible_text = segment.content[:remaining]
        hidden_text = segment.content[remaining:]
        if visible_text:
            parts.append(_escape_markdown_text(visible_text))
        if hidden_text:
            parts.append(f'<span class="hidden-text">{_hidden_text_html(hidden_text)}</span>')
        remaining -= len(visible_text)

    return "".join(parts)


def _markdown_to_html(markdown_text: str) -> str:
    # nl2br keeps dialogue line breaks predictable inside the web container.
    return markdown.markdown(markdown_text, extensions=["nl2br"])


def _escape_css_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_shell_html(font_family: str, font_size_px: int, color_hex: str) -> str:
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
  </style>
</head>
<body>
  <div id="dialogue-root"></div>

  <script defer src="vendor/katex/katex.min.js"></script>
  <script defer src="vendor/katex/contrib/auto-render.min.js"></script>
  <script>
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
    }};
  </script>
</body>
</html>
"""


class DialogueTextView(QWebEngineView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._font_family = "sans-serif"
        self._font_size_px = 24
        self._font_color = "#FFFFFF"
        self._page_ready = False
        self._pending_html: str | None = None
        self._current_html = ""
        self._base_url = self._resolve_assets_base_url()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self.setContextMenuPolicy(Qt.NoContextMenu)

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
        markdown_text = _segments_to_markdown(segments, visible_units)
        self._set_content_html(_markdown_to_html(markdown_text))

    def set_plain_dialogue(self, text: str) -> None:
        self.set_text_segments(parse_dialogue_segments(text), None)

    def set_formula_text(self, expr: str) -> None:
        markdown_text = f"$$\n{expr}\n$$"
        self._set_content_html(_markdown_to_html(markdown_text))

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

    def _resolve_assets_base_url(self) -> QUrl:
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
