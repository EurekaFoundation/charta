"""Pannello Pagine: miniature, aggiunta, duplicazione, eliminazione, ordine."""

from __future__ import annotations

from charta.i18n import tr
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QListView, QListWidget, QListWidgetItem,
                               QToolButton, QVBoxLayout, QWidget)

THUMB = 120


def _thumb_icon(img) -> QIcon:
    """Miniatura con un sottile bordo, uguale anche quando è selezionata."""
    pm = QPixmap.fromImage(img)
    p = QPainter(pm)
    p.setPen(QColor(0, 0, 0, 90))
    p.drawRect(pm.rect().adjusted(0, 0, -1, -1))
    p.end()
    icon = QIcon()
    icon.addPixmap(pm, QIcon.Normal)
    icon.addPixmap(pm, QIcon.Selected)
    return icon


class PagesPanel(QWidget):
    page_selected = Signal(int)
    add_page = Signal()
    duplicate_page = Signal()
    delete_page = Signal()
    move_page = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setFlow(QListView.TopToBottom)
        self.list.setWrapping(False)
        self.list.setMovement(QListView.Static)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setSpacing(6)
        self.list.setUniformItemSizes(False)
        self.list.currentRowChanged.connect(self._row)
        v.addWidget(self.list, 1)
        row = QHBoxLayout()
        for txt, tip, sig in (("+", tr("Aggiungi pagina"), self.add_page),
                              ("⧉", tr("Duplica pagina"), self.duplicate_page),
                              ("−", tr("Elimina pagina"), self.delete_page)):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(sig.emit)
            row.addWidget(b)
        for txt, tip, d in (("▲", tr("Sposta su"), -1), ("▼", tr("Sposta giù"), 1)):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, d=d: self.move_page.emit(d))
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.setMinimumWidth(THUMB + 50)
        self._silent = False

    def _row(self, r):
        if not self._silent and r >= 0:
            self.page_selected.emit(r)

    def set_pages(self, thumbs: list, current: int):
        self._silent = True
        self.list.clear()
        for i, img in enumerate(thumbs):
            it = QListWidgetItem(_thumb_icon(img), f"{i + 1}")
            it.setTextAlignment(Qt.AlignHCenter)
            self.list.addItem(it)
        self.list.setCurrentRow(current)
        self._silent = False

    def update_thumb(self, index: int, img):
        it = self.list.item(index)
        if it is not None:
            it.setIcon(_thumb_icon(img))

    def set_current(self, index: int):
        self._silent = True
        self.list.setCurrentRow(index)
        self._silent = False
