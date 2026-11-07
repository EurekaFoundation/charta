"""Traduzioni dell'interfaccia.

Il testo di riferimento è l'italiano, scritto direttamente nel codice dentro
tr("..."). Ogni altra lingua è un dizionario {italiano: traduzione} in un
modulo di questo pacchetto (en.py). Per aggiungere una lingua basta creare
un nuovo modulo con lo stesso dizionario e aggiungerla a LANGUAGES.
"""

from __future__ import annotations

LANGUAGES = {"it": "Italiano", "en": "English"}

_lang = "it"
_table: dict[str, str] = {}


def set_language(code: str):
    global _lang, _table
    code = (code or "it").split("_")[0].lower()
    if code not in LANGUAGES:
        code = "en"
    _lang = code
    if code == "it":
        _table = {}
    else:
        _table = _load(code)


def _load(code: str) -> dict:
    # import scritti per esteso: così PyInstaller include le traduzioni
    # nei programmi installabili
    if code == "en":
        from charta.i18n import en
        return en.STRINGS
    return {}


def language() -> str:
    return _lang


def tr(text: str) -> str:
    return _table.get(text, text)
