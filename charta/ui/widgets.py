"""Piccoli widget riutilizzabili."""

from __future__ import annotations

from charta.i18n import tr
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QColorDialog, QDoubleSpinBox, QMenu, QToolButton


def swatch_icon(color: QColor, size: int = 18) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = pm.rect().adjusted(1, 1, -1, -1)
    if color.alpha() == 0:
        p.fillRect(r, QColor("white"))
        p.setPen(QPen(QColor("#d92d20"), 1.5))
        p.drawLine(r.bottomLeft(), r.topRight())
    else:
        # scacchiera per i colori semitrasparenti
        p.fillRect(r, QColor("white"))
        p.fillRect(r.adjusted(0, 0, -r.width() // 2, -r.height() // 2), QColor("#cccccc"))
        p.fillRect(r.adjusted(r.width() // 2, r.height() // 2, 0, 0), QColor("#cccccc"))
        p.fillRect(r, color)
    p.setPen(QPen(QColor("#777777"), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r)
    p.end()
    return QIcon(pm)


class ColorButton(QToolButton):
    """Pulsante colore: clic per scegliere, freccia per 'Nessuno'."""
    color_changed = Signal(QColor)

    def __init__(self, title: str = "Colore", allow_none: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._color = QColor("black")
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.clicked.connect(self._pick)
        if allow_none:
            menu = QMenu(self)
            menu.addAction(tr("Scegli colore…"), self._pick)
            menu.addAction(tr("Nessuno (trasparente)"), lambda: self._set(QColor(0, 0, 0, 0)))
            self.setMenu(menu)
            self.setPopupMode(QToolButton.MenuButtonPopup)
        self._refresh()

    def color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, c: QColor):
        self._color = QColor(c)
        self._refresh()

    def _refresh(self):
        self.setIcon(swatch_icon(self._color))
        name = tr("nessuno") if self._color.alpha() == 0 else self._color.name()
        self.setToolTip(f"{self._title}: {name}")

    def _set(self, c: QColor):
        self._color = QColor(c)
        self._refresh()
        self.color_changed.emit(QColor(c))

    def _pick(self):
        start = self._color if self._color.alpha() else QColor("black")
        c = QColorDialog.getColor(start, self, self._title, QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self._set(c)


def mm_spin(minimum=-9999.0, maximum=9999.0, decimals=1, suffix=" mm", step=1.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(minimum, maximum)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setSingleStep(step)
    s.setKeyboardTracking(False)
    s.setAccelerated(True)
    return s
