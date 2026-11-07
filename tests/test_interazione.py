"""Uso con mouse e tastiera simulati."""

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from charta.items import ShapeFrame, TextFrame
from charta.units import mm2pt, pt2mm


def _at(w, x_mm, y_mm):
    return w.view.mapFromScene(QPointF(mm2pt(x_mm), mm2pt(y_mm)))


def _prepare(w, app):
    w.view.set_zoom(1.0)
    w.view.centerOn(w.scene().page_rect().center())
    app.processEvents()
    return w.view.viewport()


def test_disegna_rettangolo(window, app):
    vp = _prepare(window, app)
    window.set_tool("rect")
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 30, 40))
    QTest.mouseMove(vp, _at(window, 80, 70))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 80, 70))
    app.processEvents()
    r = window.scene().frames()[0]
    assert isinstance(r, ShapeFrame)
    assert abs(pt2mm(r.width()) - 50) < 1
    assert window.view.tool == "select"


def test_scrivi_testo_e_annulla(window, app):
    vp = _prepare(window, app)
    window.set_tool("text")
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 30, 100))
    app.processEvents()
    t = window.scene().frames()[0]
    assert isinstance(t, TextFrame) and t.editing
    QTest.keyClicks(vp, "Ciao")
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 150, 250))
    app.processEvents()
    window.commit()
    assert not t.editing
    assert window.scene().frames()[0].plain_text() == "Ciao"
    window.undo()
    assert window.scene().frames()[0].plain_text() == ""
    window.redo()
    assert window.scene().frames()[0].plain_text() == "Ciao"


def test_calamita_e_ridimensiona(window, app):
    vp = _prepare(window, app)
    r = ShapeFrame("rect", mm2pt(40), mm2pt(30))
    r.setPos(mm2pt(40), mm2pt(40))
    window.scene().add_frame(r)
    app.processEvents()
    # trascinando vicino al margine sinistro (12,7 mm) l'oggetto si aggancia
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 50, 50))
    QTest.mouseMove(vp, _at(window, 23.5, 50))
    QTest.mouseMove(vp, _at(window, 23.0, 50))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, _at(window, 23.0, 50))
    app.processEvents()
    assert abs(pt2mm(r.pos().x()) - 12.7) < 0.05
    # maniglia in basso a destra
    p0 = window.view.mapFromScene(r.mapToScene(r.rect().bottomRight()))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, p0)
    QTest.mouseMove(vp, p0 + QPoint(40, 20))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, p0 + QPoint(40, 20))
    app.processEvents()
    assert pt2mm(r.width()) > 45


def test_copia_incolla_duplica_pagine(window, app):
    sc = window.scene()
    r = ShapeFrame("ellipse", 80, 80)
    sc.add_frame(r)
    r.setSelected(True)
    window.copy()
    window.paste()
    window.duplicate()
    assert len(window.scene().frames()) == 3
    window.add_page()
    window.duplicate_page()
    assert len(window.scenes) == 3
    window.show_page(0)
    assert len(window.scene().frames()) == 3


def test_formattazione_testo(window, app):
    t = TextFrame()
    t.text.setPlainText("Titolo")
    window.scene().add_frame(t)
    t.setSelected(True)
    app.processEvents()
    window.props.t_size.setValue(30)
    window.props.t_bold.setChecked(True)
    window.commit()
    cf = t.char_format()
    assert cf.fontPointSize() == 30
    assert cf.fontWeight() >= 700
