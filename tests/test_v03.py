"""Funzioni della v0.2 e v0.3: testo collegato, tabelle, gruppi, guide e
righelli, stampa unione, importazione, CMYK, traduzione."""

import os
import re
import shutil

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from charta.document.model import Document
from charta.items import GroupFrame, ShapeFrame, TextFrame, flow
from charta.items import table as tables
from charta.units import mm2pt, pt2mm

DATA = os.path.join(os.path.dirname(__file__), "data")
LONG = "".join(f"<p>Paragrafo {i}: " + "parola " * 30 + "</p>" for i in range(8))


def _texts(w):
    return [f for f in w.scene().all_frames() if isinstance(f, TextFrame)]


def _story(frames):
    story, _ = flow.merge_story(flow.chain(frames[0]))
    return story.toPlainText()


# ------------------------------------------------------------ testo collegato
def test_testo_collegato_salva_riapri(window, app, tmp_path):
    sc = window.scene()
    a, b = TextFrame(mm2pt(70), mm2pt(40)), TextFrame(mm2pt(70), mm2pt(60))
    b.setPos(mm2pt(100), 0)
    sc.add_frame(a)
    sc.add_frame(b)
    a.set_html(LONG)
    full = a.plain_text()
    assert flow.link(a, b)
    assert a.plain_text() and b.plain_text()
    assert _story([a]) == full
    window.commit()
    p = tmp_path / "catena.charta"
    window._write(str(p))
    window.load_document(Document.load(str(p)), str(p))
    t = sorted(_texts(window), key=lambda f: f.pos().x())
    assert t[0].next is t[1] and t[1].prev is t[0]
    assert _story(t) == full


def test_collega_tra_pagine_ed_elimina(window, app):
    a = TextFrame(mm2pt(60), mm2pt(30))
    window.scene().add_frame(a)
    a.set_html(LONG)
    full = a.plain_text()
    window.add_page()  # le pagine vengono ricostruite: riprendiamo la cornice
    b = TextFrame(mm2pt(60), mm2pt(200))
    window.scene().add_frame(b)
    window.show_page(0)
    a = _texts(window)[0]
    window.link_source = a
    window._link_target(b)
    assert a.next is b
    window.show_page(1)
    assert b.plain_text()
    # eliminando la seconda cornice il testo torna tutto nella prima
    b.setSelected(True)
    window.delete_selected()
    window.show_page(0)
    a2 = _texts(window)[0]
    assert a2.plain_text() == full
    window.undo()
    t0 = _texts(window)[0]
    assert t0.next is not None


def test_scrivendo_il_testo_passa_alla_cornice_dopo(window, app):
    a, b = TextFrame(mm2pt(60), mm2pt(20)), TextFrame(mm2pt(60), mm2pt(60))
    window.scene().add_frame(a)
    window.scene().add_frame(b)
    flow.link(a, b)
    a.start_edit()
    a.text.textCursor().insertText("parola " * 120)
    app.processEvents()
    app.processEvents()
    assert b.plain_text()
    assert b.editing and not a.editing


def test_duplica_pagina_mantiene_catena_interna(window, app):
    a, b = TextFrame(mm2pt(60), mm2pt(20)), TextFrame(mm2pt(60), mm2pt(60))
    window.scene().add_frame(a)
    window.scene().add_frame(b)
    a.set_html(LONG)
    flow.link(a, b)
    window.commit()
    window.duplicate_page()
    ids0 = {f.uid for f in window.scenes[0].all_frames()}
    ids1 = {f.uid for f in window.scenes[1].all_frames()}
    assert not ids0 & ids1
    heads = [f for f in window.scenes[1].all_frames() if isinstance(f, TextFrame) and f.next]
    assert len(heads) == 1 and heads[0].next.scene() is window.scenes[1]


# ------------------------------------------------------------------ tabelle
def test_tabella(window, app, tmp_path):
    t = TextFrame(mm2pt(120), mm2pt(50))
    window.scene().add_frame(t)
    tables.insert_table(QTextCursor(t.text.document()), 3, 3)
    tables.insert_row(t)
    tables.insert_column(t)
    tables.set_table_border(t, width=2)
    window.commit()
    p = tmp_path / "tabella.charta"
    window._write(str(p))
    window.load_document(Document.load(str(p)), str(p))
    tb = tables.tables(_texts(window)[0].text.document())[0]
    assert (tb.rows(), tb.columns()) == (4, 4)
    assert tb.format().border() == 2


# ------------------------------------------------------------------- gruppi
def test_raggruppa_separa(window, app, tmp_path):
    sc = window.scene()
    r = ShapeFrame("rect", 100, 50)
    e = ShapeFrame("ellipse", 60, 60)
    e.setPos(150, 100)
    sc.add_frame(r)
    sc.add_frame(e)
    r.setSelected(True)
    e.setSelected(True)
    window.group_selected()
    assert len(sc.frames()) == 1 and isinstance(sc.frames()[0], GroupFrame)
    p = tmp_path / "gruppo.charta"
    window._write(str(p))
    window.load_document(Document.load(str(p)), str(p))
    g = window.scene().frames()[0]
    assert isinstance(g, GroupFrame) and len(g.children_frames()) == 2
    g.setSelected(True)
    window.ungroup_selected()
    assert len(window.scene().frames()) == 2
    pos = sorted((round(f.pos().x()), round(f.pos().y())) for f in window.scene().frames())
    assert pos == [(0, 0), (150, 100)]


# ------------------------------------------------------------ guide e righelli
def test_guida_dal_righello_e_calamita(window, app):
    window.view.set_zoom(1.0)
    window.view.centerOn(window.scene().page_rect().center())
    app.processEvents()
    ruler = window.area.vruler  # righello verticale → guida verticale (asse x)
    vp = window.view.viewport()
    target = vp.mapToGlobal(window.view.mapFromScene(QPointF(mm2pt(50), mm2pt(100))))
    QTest.mousePress(ruler, Qt.LeftButton, Qt.NoModifier, QPoint(10, 200))
    ev_pos = ruler.mapFromGlobal(target)
    QTest.mouseMove(ruler, ev_pos)
    QTest.mouseRelease(ruler, Qt.LeftButton, Qt.NoModifier, ev_pos)
    app.processEvents()
    gx = window.scene().guides["x"]
    assert len(gx) == 1 and abs(pt2mm(gx[0]) - 50) < 0.5
    window.commit()
    page = window.doc.pages[0]
    assert len(page["guides"]["x"]) == 1
    # un oggetto trascinato vicino alla guida si aggancia
    r = ShapeFrame("rect", mm2pt(20), mm2pt(20))
    r.setPos(mm2pt(80), mm2pt(150))
    window.scene().add_frame(r)
    app.processEvents()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, window.view.mapFromScene(QPointF(mm2pt(90), mm2pt(160))))
    QTest.mouseMove(vp, window.view.mapFromScene(QPointF(mm2pt(61.5), mm2pt(160))))
    QTest.mouseMove(vp, window.view.mapFromScene(QPointF(mm2pt(61), mm2pt(160))))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier,
                       window.view.mapFromScene(QPointF(mm2pt(61), mm2pt(160))))
    app.processEvents()
    assert abs(pt2mm(r.pos().x()) - pt2mm(gx[0])) < 0.05


# ------------------------------------------------------------ stampa unione
def _pdf_pages(path):
    return len(re.findall(rb"/Type\s*/Page[^s]", open(path, "rb").read()))


def test_stampa_unione_csv_ed_excel(window, app, tmp_path):
    from charta import merge
    csv_path = tmp_path / "iscritti.csv"
    csv_path.write_bytes("Nome;Cognome;Corso\nAnna;Rossi;Arduino\nLuca;Bianchi;Scratch\n"
                         "Sofia;Esposito;Micro:bit\n".encode("cp1252"))
    headers, rows = merge.read_table(str(csv_path))
    assert headers == ["Nome", "Cognome", "Corso"] and rows[2]["Cognome"] == "Esposito"

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nome", "Importo"])
    ws.append(["Città di prova", 12.0])
    xp = tmp_path / "dati.xlsx"
    wb.save(xp)
    h2, r2 = merge.read_table(str(xp))
    assert r2[0] == {"Nome": "Città di prova", "Importo": "12"}

    t = TextFrame(mm2pt(150), mm2pt(30))
    window.scene().add_frame(t)
    t.set_html("<p>Attestato per <b>{{Nome}}</b> {{cognome}} — corso {{Corso}} {{Assente}}</p>")
    window.set_merge_source(str(csv_path), headers)
    st = window.current_state()
    assert merge.fields_in_state(st) == ["Nome", "cognome", "Corso", "Assente"]
    out = merge.apply_record(st, rows[0])
    html = out["pages"][0]["items"][0]["html"]
    assert "Anna" in html and "Rossi" in html and "Arduino" in html and "{{Assente}}" in html

    one = tmp_path / "unione.pdf"
    merge.export_merged(st, window.doc, rows, str(one), one_file=True)
    assert _pdf_pages(str(one)) == 3
    files = merge.export_merged(st, window.doc, rows, str(tmp_path), one_file=False, name_field="Cognome")
    assert sorted(os.path.basename(f) for f in files) == ["Bianchi.pdf", "Esposito.pdf", "Rossi.pdf"]


# -------------------------------------------------------------- importazione
def test_importa_odg(window, app):
    from charta.importers.publisher import import_file
    doc, report = import_file(os.path.join(DATA, "prova.fodg"))
    items = doc.pages[0]["items"]
    kinds = [(i["type"], i.get("shape")) for i in items]
    assert ("image", None) in kinds and ("shape", "ellipse") in kinds and ("shape", "path") in kinds
    assert ("shape", "line") in kinds
    rotated = [i for i in items if i["type"] == "shape" and abs(i["rotation"] + 30) < 0.1]
    assert rotated and abs(rotated[0]["x"] - 151.7) < 0.5
    title = next(i for i in items if i["type"] == "text" and "Festa" in i["html"])
    assert "font-size:28.00pt" in title["html"] and 'align="center"' in title["html"]
    assert doc.pages[0]["background"] == "#fff8e7"
    window.load_document(doc)
    assert len(window.scene().frames()) == len(items)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice non installato")
def test_importa_publisher(window, app, tmp_path):
    """Converte con LibreOffice: va a buon fine anche con un .odg al posto del .pub
    (la catena di conversione è la stessa)."""
    from charta.importers.publisher import convert_to_odg
    from charta.importers.odg import import_odg
    src = os.environ.get("CHARTA_TEST_PUB") or os.path.join(DATA, "prova.fodg")
    odg = convert_to_odg(src, str(tmp_path))
    doc, _ = import_odg(odg)
    assert doc.pages and doc.pages[0]["items"]


# ---------------------------------------------------------------------- CMYK
def test_pdf_cmyk(window, app, tmp_path):
    from charta.export import render
    if render.find_ghostscript() is None:
        pytest.skip("Ghostscript non installato")
    r = ShapeFrame("rect", 200, 100)
    window.scene().add_frame(r)
    out = tmp_path / "cmyk.pdf"
    render.export_pdf(window.scenes, str(out), cmyk=True, bleed_mm=3, crop_marks=True)
    data = out.read_bytes()
    assert b"DeviceCMYK" in data or b"/ICCBased" in data
    assert b"DeviceRGB" not in data


# ---------------------------------------------------------------- traduzione
def test_inglese(app):
    from charta import i18n
    from charta.ui.properties import PropertiesPanel
    i18n.set_language("en_GB")
    try:
        assert i18n.language() == "en"
        p = PropertiesPanel()
        assert p.grp_page.title() == "Page"
        assert p.btn_link.text() == "Link to…"
    finally:
        i18n.set_language("it")
    assert i18n.tr("Pagina") == "Pagina"
