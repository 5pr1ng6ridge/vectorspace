"""Font loading helpers with memoization."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from .paths import asset_path

_FONT_FAMILY_CACHE: dict[str, str | None] = {}


def load_font_family(*parts: str) -> str | None:
    """Load an application font once and return its first family name."""
    font_path = asset_path(*parts)
    cache_key = str(font_path)

    if cache_key in _FONT_FAMILY_CACHE:
        return _FONT_FAMILY_CACHE[cache_key]

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        _FONT_FAMILY_CACHE[cache_key] = None
        return None

    families = QFontDatabase.applicationFontFamilies(font_id)
    family = families[0] if families else None
    _FONT_FAMILY_CACHE[cache_key] = family
    return family
