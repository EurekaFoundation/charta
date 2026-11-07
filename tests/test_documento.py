"""Modelli, salvataggio/riapertura del formato .charta ed esportazione."""

import zipfile

import pytest

from charta.document.model import Document
from charta.export import render
from charta.templates.builtin import TEMPLATES


@pytest.mark.parametrize("key,name,fn", TEMPLATES, ids=[t[0] for t in TEMPLATES])
def test_modello_salva_riapri_esporta(window, app, tmp_path, key, name, fn):
    doc = Document()
    doc.set_state(fn())
    window.load_document(doc)
    path = tmp_path / f"{key}.charta"
    assert window._write(str(path))

    with zipfile.ZipFile(path) as z:
        assert z.namelist()[0] == "mimetype"
        assert z.read("mimetype") == b"application/x-charta"
        assert "document.json" in z.namelist()

    window.load_document(Document.load(str(path)), str(path))
    app.processEvents()
    assert window._state_json() == window.history.current()
    assert len(window.scenes) == len(doc.pages)

    pdf = tmp_path / f"{key}.pdf"
    render.export_pdf(window.scenes, str(pdf), bleed_mm=3, crop_marks=True)
    assert pdf.read_bytes().startswith(b"%PDF")
    img = render.page_image(window.scenes[0], 72)
    assert not img.isNull()


def test_immagini_incluse_nel_file(window, app, tmp_path):
    from PySide6.QtGui import QColor, QImage
    img = QImage(300, 200, QImage.Format_RGB32)
    img.fill(QColor("#e4572e"))
    p = tmp_path / "foto.png"
    img.save(str(p))
    window.add_image_file(str(p), window.scene().page_rect().center())
    out = tmp_path / "con-immagine.charta"
    window._write(str(out))
    doc = Document.load(str(out))
    assert len(doc.assets) == 1
    assert doc.pages[0]["items"][0]["type"] == "image"


def test_file_non_valido(tmp_path):
    from charta.document.model import CorruptFileError
    bad = tmp_path / "rotto.charta"
    bad.write_text("non sono uno zip")
    with pytest.raises(CorruptFileError):
        Document.load(str(bad))
