"""Modello del documento e formato file .charta.

Un file .charta è un archivio ZIP che contiene:

    mimetype            "application/x-charta" (primo file, non compresso)
    document.json       pagine, oggetti e proprietà (misure in millimetri)
    assets/<id>.<ext>   immagini originali, a piena risoluzione
    thumbnail.png       anteprima della prima pagina (facoltativa)

Il formato è aperto e documentato in docs/formato-file.md.
"""

from __future__ import annotations

import copy
import hashlib
import json
import zipfile

FORMAT_VERSION = 1
MIMETYPE = "application/x-charta"


def new_page(width_mm: float = 210.0, height_mm: float = 297.0,
             margins=(12.7, 12.7, 12.7, 12.7), background: str = "#ffffff") -> dict:
    return {
        "width": width_mm,
        "height": height_mm,
        "margins": list(margins),  # alto, destra, basso, sinistra
        "background": background,
        "items": [],
    }


class CorruptFileError(Exception):
    pass


class Document:
    def __init__(self):
        self.title = "Senza titolo"
        self.pages: list[dict] = [new_page()]
        self.assets: dict[str, bytes] = {}   # id -> byte dell'immagine
        self.asset_ext: dict[str, str] = {}  # id -> estensione
        self.merge: dict = {}                # stampa unione: {"source": percorso}

    # ---------------------------------------------------------------- asset
    def add_asset(self, data: bytes, ext: str) -> str:
        ext = (ext or "png").lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        asset_id = hashlib.sha1(data).hexdigest()[:16]
        if asset_id not in self.assets:
            self.assets[asset_id] = data
            self.asset_ext[asset_id] = ext
        return asset_id

    def used_assets(self) -> set[str]:
        used = set()

        def walk(items):
            for item in items:
                if item.get("type") == "image" and item.get("asset"):
                    used.add(item["asset"])
                walk(item.get("items", []))
        for page in self.pages:
            walk(page["items"])
        return used

    # ---------------------------------------------------------------- stato
    def state(self) -> dict:
        """Stato serializzabile (senza i byte delle immagini)."""
        st = {"version": FORMAT_VERSION, "title": self.title,
              "pages": copy.deepcopy(self.pages)}
        if self.merge:
            st["merge"] = dict(self.merge)
        return st

    def set_state(self, state: dict):
        self.title = state.get("title", self.title)
        self.pages = copy.deepcopy(state["pages"])
        self.merge = dict(state.get("merge", {}))

    # ------------------------------------------------------------ salvataggio
    def save(self, path: str, thumbnail_png: bytes | None = None):
        used = self.used_assets()
        state = self.state()
        state["assets"] = {a: self.asset_ext[a] for a in sorted(used)}
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
            z.writestr("document.json", json.dumps(state, ensure_ascii=False, indent=2),
                       compress_type=zipfile.ZIP_DEFLATED)
            for a in sorted(used):
                # le immagini sono già compresse: le salviamo così come sono
                z.writestr(f"assets/{a}.{self.asset_ext[a]}", self.assets[a],
                           compress_type=zipfile.ZIP_STORED)
            if thumbnail_png:
                z.writestr("thumbnail.png", thumbnail_png, compress_type=zipfile.ZIP_STORED)

    @classmethod
    def load(cls, path: str) -> "Document":
        try:
            with zipfile.ZipFile(path) as z:
                state = json.loads(z.read("document.json").decode("utf-8"))
                doc = cls()
                for a, ext in state.get("assets", {}).items():
                    doc.assets[a] = z.read(f"assets/{a}.{ext}")
                    doc.asset_ext[a] = ext
        except (zipfile.BadZipFile, KeyError, ValueError) as e:
            raise CorruptFileError(str(e)) from e
        if state.get("version", 0) > FORMAT_VERSION:
            raise CorruptFileError(
                "Il file è stato creato con una versione più recente di Charta.")
        if not state.get("pages"):
            raise CorruptFileError("Il documento non contiene pagine.")
        doc.set_state(state)
        return doc
