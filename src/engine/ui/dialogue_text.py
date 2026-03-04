from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
    QTextOption,
)
from PySide6.QtWidgets import QFrame, QTextBrowser

from ..latex.renderer import render_latex_inline


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


def slice_dialogue_segments(
    segments: list[DialogueSegment], visible_units: int
) -> list[DialogueSegment]:
    if visible_units <= 0:
        return []

    visible: list[DialogueSegment] = []
    remaining = visible_units

    for segment in segments:
        if remaining <= 0:
            break

        if segment.kind == "formula":
            visible.append(segment)
            remaining -= 1
            continue

        if remaining >= len(segment.content):
            visible.append(segment)
            remaining -= len(segment.content)
            continue

        visible.append(DialogueSegment("text", segment.content[:remaining]))
        remaining = 0

    return visible


class DialogueTextView(QTextBrowser):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._formula_cache: dict[tuple[str, int], QImage] = {}
        self._resource_counter = 0

        self.setFrameShape(QFrame.NoFrame)
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(0)

        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)

        self._refresh_style()

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self.document().setDefaultFont(font)

    def set_text_segments(self, segments: list[DialogueSegment]) -> None:
        self._render_segments(segments)

    def set_plain_dialogue(self, text: str) -> None:
        self._render_segments(parse_dialogue_segments(text))

    def set_formula_pixmap(self, pixmap: QPixmap) -> None:
        document = self.document()
        document.clear()

        cursor = QTextCursor(document)
        image_format = QTextImageFormat()
        image_format.setName(self._register_image(pixmap.toImage()))
        image_format.setWidth(pixmap.width())
        image_format.setHeight(pixmap.height())
        cursor.insertImage(image_format)

    def _render_segments(self, segments: list[DialogueSegment]) -> None:
        document = self.document()
        document.clear()

        cursor = QTextCursor(document)
        text_format = QTextCharFormat()
        text_format.setFont(self.font())
        text_format.setForeground(self.textColor())
        cursor.setCharFormat(text_format)

        inline_font_size = max(16, int(round(self.font().pointSizeF() * 0.4)))

        for segment in segments:
            if segment.kind == "formula":
                image = self._get_formula_image(segment.content, inline_font_size)
                image_format = QTextImageFormat()
                image_format.setName(self._register_image(image))
                image_format.setWidth(image.width())
                image_format.setHeight(image.height())
                image_format.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
                cursor.insertImage(image_format)
                continue

            cursor.insertText(segment.content, text_format)

        cursor.clearSelection()

    def _get_formula_image(self, expr: str, font_size: int) -> QImage:
        cache_key = (expr, font_size)
        cached = self._formula_cache.get(cache_key)
        if cached is not None:
            return cached

        image = render_latex_inline(expr, font_size=font_size).toImage()
        self._formula_cache[cache_key] = image
        return image

    def _register_image(self, image: QImage) -> str:
        resource_name = f"formula://{self._resource_counter}"
        self._resource_counter += 1
        self.document().addResource(
            QTextDocument.ImageResource,
            QUrl(resource_name),
            image,
        )
        return resource_name

    def _refresh_style(self) -> None:
        color = self.textColor().name()
        self.setStyleSheet(
            "QTextBrowser {"
            "background: transparent;"
            "border: none;"
            f"color: {color};"
            "}"
        )

    def textColor(self) -> QColor:
        return QColor("#FFFFFF")
