"""Scelta di font predefiniti presenti sul sistema (Windows, macOS, Linux)."""

from functools import lru_cache

from PySide6.QtGui import QFontDatabase

SANS = ["Segoe UI", "Helvetica Neue", "Arial", "Liberation Sans", "DejaVu Sans", "Noto Sans"]
SERIF = ["Georgia", "Times New Roman", "Liberation Serif", "DejaVu Serif", "Noto Serif"]


@lru_cache(maxsize=None)
def _families() -> frozenset:
    return frozenset(QFontDatabase.families())


def first_available(candidates) -> str:
    fams = _families()
    for f in candidates:
        if f in fams:
            return f
    return candidates[-1]


def sans() -> str:
    return first_available(SANS)


def serif() -> str:
    return first_available(SERIF)


def css_list(candidates) -> str:
    return ", ".join(f"'{f}'" for f in candidates)
