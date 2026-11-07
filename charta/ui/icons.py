"""Icone disegnate in codice: nessun file esterno, nitide a ogni scala e
adattate al tema chiaro o scuro."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication

ACCENT = QColor("#1f6feb")


def _fg() -> QColor:
    return QApplication.palette().windowText().color()


def _make(draw, size=48) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    draw(p, _fg())
    p.end()
    return QIcon(pm)


def _pen(c, w=1.6):
    pen = QPen(c, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def select_icon():
    def d(p, fg):
        path = QPainterPath(QPointF(6, 3))
        for x, y in ((6, 19), (10, 15), (13, 21), (15.5, 20), (12.5, 14), (18, 14)):
            path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(_pen(fg, 1.4))
        p.setBrush(fg)
        p.drawPath(path)
    return _make(d)


def text_icon():
    def d(p, fg):
        f = QFont()
        f.setPixelSize(18)
        f.setBold(True)
        f.setFamily("serif")
        p.setFont(f)
        p.setPen(fg)
        p.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "T")
    return _make(d)


def image_icon():
    def d(p, fg):
        p.setPen(_pen(fg))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        path = QPainterPath(QPointF(4, 18))
        path.lineTo(9.5, 11.5)
        path.lineTo(13, 15)
        path.lineTo(15.5, 12.5)
        path.lineTo(20, 18)
        p.setBrush(ACCENT)
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        p.setBrush(QColor("#f2a900"))
        p.drawEllipse(QPointF(16.5, 8.8), 1.7, 1.7)
    return _make(d)


def rect_icon():
    def d(p, fg):
        p.setPen(_pen(fg))
        p.setBrush(QColor(31, 111, 235, 70))
        p.drawRect(QRectF(4, 6, 16, 12))
    return _make(d)


def ellipse_icon():
    def d(p, fg):
        p.setPen(_pen(fg))
        p.setBrush(QColor(31, 111, 235, 70))
        p.drawEllipse(QRectF(4, 5, 16, 14))
    return _make(d)


def line_icon():
    def d(p, fg):
        p.setPen(_pen(fg, 2))
        p.drawLine(QPointF(5, 19), QPointF(19, 5))
    return _make(d)


def app_icon(size: int = 256) -> QIcon:
    """Un foglio con l'angolo piegato e una 'C' tipografica."""
    def d(p, fg):
        sheet = QPainterPath(QPointF(5, 2))
        sheet.lineTo(15, 2)
        sheet.lineTo(20, 7)
        sheet.lineTo(20, 22)
        sheet.lineTo(5, 22)
        sheet.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0f4c81"))
        p.drawPath(sheet)
        fold = QPainterPath(QPointF(15, 2))
        fold.lineTo(15, 7)
        fold.lineTo(20, 7)
        fold.closeSubpath()
        p.setBrush(QColor("#6fa3d6"))
        p.drawPath(fold)
        p.setBrush(QColor("#f2a900"))
        p.drawRect(QRectF(5, 17, 15, 2))
        f = QFont()
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(5, 4, 15, 13), Qt.AlignCenter, "C")
    return _make(d, size)


def table_icon():
    def d(p, fg):
        p.setPen(_pen(fg, 1.4))
        p.setBrush(QColor(31, 111, 235, 70))
        p.drawRect(QRectF(3.5, 5, 17, 4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.5, 5, 17, 14))
        for y in (9, 14):
            p.drawLine(QPointF(3.5, y), QPointF(20.5, y))
        for x in (9.2, 14.8):
            p.drawLine(QPointF(x, 5), QPointF(x, 19))
    return _make(d)
