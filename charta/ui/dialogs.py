"""Finestre di dialogo: nuovo documento, esportazioni, tabella, stampa unione."""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QListView, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QRadioButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from charta import merge
from charta.document.model import Document
from charta.export.render import find_ghostscript
from charta.i18n import tr
from charta.templates.builtin import TEMPLATES, blank
from charta.ui.pages_panel import _thumb_icon
from charta.ui.widgets import mm_spin
from charta.units import PAGE_FORMATS

_THUMBS: dict = {}


def _buttons(dlg, ok_text: str) -> QDialogButtonBox:
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok_text)
    bb.button(QDialogButtonBox.Cancel).setText(tr("Annulla"))
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _small(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet("color: palette(mid); font-size: 11px;")
    return lab


def template_thumb(key, fn, size=150):
    if key not in _THUMBS:
        from charta.export.render import thumbnail
        from charta.merge import scenes_for_state
        doc = Document()
        scene = scenes_for_state(fn(), doc)[0]
        _THUMBS[key] = _thumb_icon(thumbnail(scene, size))
    return _THUMBS[key]


class NewDocumentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Nuovo documento"))
        self.resize(780, 540)
        v = QVBoxLayout(self)
        v.addWidget(QLabel(tr("<b>Scegli un modello</b> — potrai cambiare tutto in seguito.")))
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(150, 150))
        self.list.setGridSize(QSize(180, 200))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        for key, name, fn in TEMPLATES:
            it = QListWidgetItem(template_thumb(key, fn), tr(name))
            it.setData(Qt.UserRole, key)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self.list.currentRowChanged.connect(self._sync)
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.fmt = QComboBox()
        for name in PAGE_FORMATS:
            self.fmt.addItem(tr(name), name)
        self.fmt.setCurrentIndex(self.fmt.findData("A4"))
        self.portrait = QRadioButton(tr("Verticale"))
        self.landscape = QRadioButton(tr("Orizzontale"))
        self.portrait.setChecked(True)
        self.blank_label = QLabel(tr("Formato della pagina vuota:"))
        for w in (self.blank_label, self.fmt, self.portrait, self.landscape):
            row.addWidget(w)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(_buttons(self, tr("Crea")))
        self._sync()

    def _sync(self):
        is_blank = self.list.currentRow() == 0
        for w in (self.blank_label, self.fmt, self.portrait, self.landscape):
            w.setEnabled(is_blank)

    def state(self) -> dict:
        key = self.list.currentItem().data(Qt.UserRole)
        if key == "blank":
            w, h = PAGE_FORMATS[self.fmt.currentData()]
            if self.landscape.isChecked():
                w, h = h, w
            return blank(w, h)
        for k, _, fn in TEMPLATES:
            if k == key:
                return fn()
        return blank()


class PdfOptionsDialog(QDialog):
    def __init__(self, parent=None, title: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(title or tr("Esporta in PDF"))
        self.form = f = QFormLayout(self)
        self.print_ready = QCheckBox(tr("PDF per la tipografia (abbondanza e segni di taglio)"))
        f.addRow(self.print_ready)
        self.bleed = mm_spin(0, 20, 1, " mm", 0.5)
        self.bleed.setValue(3)
        f.addRow(tr("Abbondanza"), self.bleed)
        f.addRow(_small(tr("L'abbondanza estende lo sfondo e gli oggetti che toccano il bordo, "
                           "così dopo il taglio non restano filetti bianchi. Le tipografie di solito "
                           "chiedono 3 mm.")))
        self.cmyk = QCheckBox(tr("Colori in CMYK (per la stampa professionale)"))
        has_gs = find_ghostscript() is not None
        self.cmyk.setEnabled(has_gs)
        f.addRow(self.cmyk)
        if not has_gs:
            f.addRow(_small(tr("La conversione in CMYK richiede Ghostscript, gratuito: "
                               "installalo da ghostscript.com e riavvia Charta.")))
        self.print_ready.toggled.connect(self.bleed.setEnabled)
        self.bleed.setEnabled(False)
        self.extra_row = f.rowCount()
        f.addRow(_buttons(self, tr("Esporta…")))

    def options(self) -> dict:
        o = {"bleed_mm": 0.0, "crop_marks": False, "cmyk": self.cmyk.isChecked()}
        if self.print_ready.isChecked():
            o.update(bleed_mm=self.bleed.value(), crop_marks=True)
        return o


class ImageOptionsDialog(QDialog):
    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Esporta come immagine"))
        f = QFormLayout(self)
        self.dpi = QComboBox()
        for label, dpi in ((tr("Schermo e social (96 dpi)"), 96), (tr("Buona (150 dpi)"), 150),
                           (tr("Stampa (300 dpi)"), 300)):
            self.dpi.addItem(label, dpi)
        self.dpi.setCurrentIndex(1)
        f.addRow(tr("Risoluzione"), self.dpi)
        self.current = QRadioButton(tr("Solo la pagina corrente"))
        self.all = QRadioButton(tr("Tutte le pagine ({n} file)").format(n=page_count))
        self.current.setChecked(True)
        self.all.setEnabled(page_count > 1)
        f.addRow(tr("Pagine"), self.current)
        f.addRow("", self.all)
        f.addRow(_buttons(self, tr("Esporta…")))

    def options(self) -> dict:
        return {"dpi": self.dpi.currentData(), "all": self.all.isChecked()}


class TableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Inserisci tabella"))
        f = QFormLayout(self)
        self.rows = QSpinBox()
        self.rows.setRange(1, 200)
        self.rows.setValue(4)
        self.cols = QSpinBox()
        self.cols.setRange(1, 30)
        self.cols.setValue(3)
        self.header = QCheckBox(tr("Prima riga di intestazione"))
        self.header.setChecked(True)
        f.addRow(tr("Righe"), self.rows)
        f.addRow(tr("Colonne"), self.cols)
        f.addRow(self.header)
        f.addRow(_buttons(self, tr("Inserisci")))

    def values(self):
        return self.rows.value(), self.cols.value(), self.header.isChecked()


class MergeDialog(QDialog):
    """Anteprima della stampa unione ed esportazione."""

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.window = window
        self.setWindowTitle(tr("Stampa unione"))
        self.resize(900, 620)
        self.headers, self.records = [], []
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        self.src_label = QLabel()
        self.src_label.setWordWrap(True)
        b = QPushButton(tr("Scegli il file dei dati…"))
        b.clicked.connect(self.choose_source)
        row.addWidget(self.src_label, 1)
        row.addWidget(b)
        v.addLayout(row)
        self.fields_label = QLabel()
        self.fields_label.setWordWrap(True)
        v.addWidget(self.fields_label)
        body = QHBoxLayout()
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.currentCellChanged.connect(lambda r, *_: self._preview(r))
        body.addWidget(self.table, 3)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumWidth(300)
        self.preview.setStyleSheet("background: palette(dark);")
        body.addWidget(self.preview, 2)
        v.addLayout(body, 1)

        f = QFormLayout()
        self.one_file = QRadioButton(tr("Un unico PDF con tutte le copie"))
        self.many = QRadioButton(tr("Un PDF per ogni riga"))
        self.one_file.setChecked(True)
        self.name_field = QComboBox()
        self.many.toggled.connect(self.name_field.setEnabled)
        self.name_field.setEnabled(False)
        f.addRow(tr("Risultato"), self.one_file)
        f.addRow("", self.many)
        f.addRow(tr("Nome dei file da"), self.name_field)
        self.print_ready = QCheckBox(tr("PDF per la tipografia (abbondanza 3 mm e segni di taglio)"))
        f.addRow(self.print_ready)
        v.addLayout(f)
        bb = _buttons(self, tr("Esporta…"))
        self.export_btn = bb.button(QDialogButtonBox.Ok)
        bb.accepted.disconnect()
        bb.accepted.connect(self.export)
        v.addWidget(bb)
        src = window.doc.merge.get("source")
        if src and os.path.exists(src):
            self.load_source(src)
        else:
            self._update_labels()

    def _update_labels(self):
        src = self.window.doc.merge.get("source")
        self.src_label.setText(tr("<b>Dati:</b> {f} — {n} righe").format(
            f=os.path.basename(src), n=len(self.records)) if src and self.headers
            else tr("<b>Dati:</b> nessun file scelto (CSV o Excel, con i nomi delle colonne nella prima riga)"))
        used = merge.fields_in_state(self.window.current_state())
        missing = [f for f in used if f.casefold() not in {h.casefold() for h in self.headers}]
        if not used:
            msg = tr("Nel documento non ci sono ancora campi. Scrivi i campi nel testo tra doppie "
                     "graffe, per esempio {{Nome}}, oppure usa “Inserisci un campo” nel pannello Testo.")
        elif missing and self.headers:
            msg = tr("Campi nel documento: {u}. <b>Senza colonna corrispondente:</b> {m}").format(
                u=", ".join(used), m=", ".join(missing))
        else:
            msg = tr("Campi nel documento: {u}").format(u=", ".join(used))
        self.fields_label.setText(msg)
        self.export_btn.setEnabled(bool(self.records))

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Scegli il file dei dati"),
                                              self.window._last_dir(),
                                              tr("Dati (*.csv *.xlsx *.xlsm *.txt *.tsv)"))
        if path:
            self.load_source(path)

    def load_source(self, path: str):
        try:
            self.headers, self.records = merge.read_table(path)
        except merge.DataError as e:
            QMessageBox.warning(self, tr("Stampa unione"), str(e))
            return
        self.window.set_merge_source(path, self.headers)
        self.table.clear()
        self.table.setColumnCount(len(self.headers))
        self.table.setRowCount(len(self.records))
        self.table.setHorizontalHeaderLabels(self.headers)
        for r, rec in enumerate(self.records):
            for c, h in enumerate(self.headers):
                self.table.setItem(r, c, QTableWidgetItem(rec.get(h, "")))
        self.table.resizeColumnsToContents()
        self.name_field.clear()
        self.name_field.addItems(self.headers)
        self._update_labels()
        if self.records:
            self.table.selectRow(0)
            self._preview(0)

    def _preview(self, row: int):
        if not (0 <= row < len(self.records)):
            return
        from charta.export.render import page_image
        st = merge.apply_record(self.window.current_state(), self.records[row])
        scenes = merge.scenes_for_state(st, self.window.doc)
        img = page_image(scenes[0], 50)
        pm = QPixmap.fromImage(img).scaled(self.preview.width() - 20, self.preview.height() - 20,
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pm)

    def export(self):
        one = self.one_file.isChecked()
        if one:
            path, _ = QFileDialog.getSaveFileName(self, tr("Esporta stampa unione"),
                                                  self.window._base_name() + "-unione.pdf", "PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
        else:
            path = QFileDialog.getExistingDirectory(self, tr("Cartella dove salvare i PDF"),
                                                    self.window._last_dir())
            if not path:
                return
        opts = {"bleed_mm": 3.0, "crop_marks": True} if self.print_ready.isChecked() else {}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            files = merge.export_merged(self.window.current_state(), self.window.doc, self.records,
                                        path, one_file=one, name_field=self.name_field.currentText(),
                                        progress=lambda i: QApplication.processEvents(), **opts)
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, tr("Stampa unione"),
                                tr("Creati {n} file PDF.").format(n=len(files)) if not one
                                else tr("PDF creato con {n} copie.").format(n=len(self.records)))
        self.accept()
