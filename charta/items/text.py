"""Cornice di testo: testo ricco (font, dimensioni, colori, allineamenti)
che si modifica con un doppio clic."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImage, QPen, QTextBlockFormat,
                           QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QGraphicsTextItem, QStyle

from charta import fonts
from charta.items import flow
from charta.items.base import FrameItem, color_from, color_to, r3
from charta.units import mm2pt, pt2mm

_POINTS_DEVICE = None


def points_device() -> QImage:
    """Superficie a 72 dpi: fa sì che 1 punto del font = 1 unità della scena,
    così il testo ha la stessa dimensione a schermo, in PDF e in stampa."""
    global _POINTS_DEVICE
    if _POINTS_DEVICE is None:
        img = QImage(4, 4, QImage.Format_ARGB32)
        dpm = round(72 / 0.0254)
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)
        _POINTS_DEVICE = img
    return _POINTS_DEVICE


class FrameText(QGraphicsTextItem):
    def __init__(self, frame: "TextFrame"):
        super().__init__(frame)
        self.frame = frame
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.document().documentLayout().setPaintDevice(points_device())

    def paint(self, painter, option, widget=None):
        painter.save()
        clip = self.mapFromParent(self.frame.rect()).boundingRect()
        painter.setClipRect(clip, Qt.IntersectClip)
        option.state &= ~(QStyle.State_HasFocus | QStyle.State_Selected)
        super().paint(painter, option, widget)
        painter.restore()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        sc = self.scene()
        # se il fuoco va al pannello delle proprietà restiamo in modifica,
        # così si può formattare il testo selezionato
        if sc is not None and sc.hasFocus() and event.reason() != Qt.PopupFocusReason:
            self.frame.end_edit()


class TextFrame(FrameItem):
    kind = "text"

    def __init__(self, w: float = mm2pt(80), h: float = mm2pt(30)):
        super().__init__(w, h)
        self.fill = QColor(0, 0, 0, 0)
        self.stroke = QColor(0, 0, 0, 0)
        self.stroke_width = 1.0
        self.padding = mm2pt(2)
        self.valign = "top"
        self.editing = False
        self.next = None          # cornice successiva nella catena
        self.prev = None          # cornice precedente
        self.continues = False    # il testo prosegue il paragrafo della precedente
        self._next_id = None
        self.text = FrameText(self)
        doc = self.text.document()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(QFont(fonts.sans(), 12))
        doc.contentsChanged.connect(self._contents_changed)
        self.on_resized()

    def _contents_changed(self):
        self.layout_text()
        if flow.is_chained(self):
            flow.schedule_reflow(self)

    # --------------------------------------------------------- impaginazione
    def on_resized(self):
        self.text.setTextWidth(max(1.0, self._w - 2 * self.padding))
        self.layout_text()
        if flow.is_chained(self):
            flow.schedule_reflow(self)

    def layout_text(self):
        doc_h = self.text.document().size().height()
        avail = self._h - 2 * self.padding
        y = self.padding
        if self.valign == "middle":
            y += max(0.0, (avail - doc_h) / 2)
        elif self.valign == "bottom":
            y += max(0.0, avail - doc_h)
        self.text.setPos(self.padding, y)
        self.update()

    def overflowing(self) -> bool:
        return self.text.document().size().height() > self._h - 2 * self.padding + 0.5

    def stroke_extent(self) -> float:
        return self.stroke_width / 2 if self.stroke.alpha() else 0.0

    def paint_content(self, painter):
        r = self.rect()
        if self.fill.alpha():
            painter.fillRect(r, self.fill)
        if self.stroke.alpha() and self.stroke_width > 0:
            painter.setPen(QPen(self.stroke, self.stroke_width))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)
        else:
            self.draw_guide_frame(painter)
        if not self.exporting():
            self._paint_link_marks(painter)
        if not self.exporting() and self.next is None and self.overflowing():
            # come in Publisher: un segnale rosso indica testo che non entra
            s = self._hs() * 1.6
            box = QRectF(self._w - s, self._h - s, s, s)
            painter.fillRect(box, QColor("#d92d20"))
            pen = QPen(QColor("white"), 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            c = box.center()
            painter.drawLine(QPointF(c.x() - s / 4, c.y()), QPointF(c.x() + s / 4, c.y()))
            painter.drawLine(QPointF(c.x(), c.y() - s / 4), QPointF(c.x(), c.y() + s / 4))

    def _paint_link_marks(self, painter):
        """Piccole frecce blu: testo che arriva da / continua in un'altra cornice."""
        s = self._hs() * 1.6
        pen = QPen(QColor("white"), 0)
        pen.setCosmetic(True)
        for show, box in ((self.prev is not None, QRectF(0, 0, s, s)),
                          (self.next is not None, QRectF(self._w - s, self._h - s, s, s))):
            if not show:
                continue
            painter.fillRect(box, QColor("#1f6feb"))
            painter.setPen(pen)
            c = box.center()
            painter.drawLine(QPointF(c.x() - s / 4, c.y()), QPointF(c.x() + s / 4, c.y()))
            painter.drawLine(QPointF(c.x() + s / 4, c.y()), QPointF(c.x(), c.y() - s / 5))
            painter.drawLine(QPointF(c.x() + s / 4, c.y()), QPointF(c.x(), c.y() + s / 5))

    # ------------------------------------------------------------- modifica
    def mouseDoubleClickEvent(self, event):
        if self.locked:
            return super().mouseDoubleClickEvent(event)
        self.start_edit()
        pos = self.text.mapFromParent(event.pos())
        idx = self.text.document().documentLayout().hitTest(pos, Qt.FuzzyHit)
        if idx >= 0:
            c = self.text.textCursor()
            c.setPosition(idx)
            self.text.setTextCursor(c)
        event.accept()

    def start_edit(self, select_all: bool = False):
        if self.editing:
            return
        self.editing = True
        self.text.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.text.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlag(FrameItem.ItemIsMovable, False)
        self.text.setFocus(Qt.MouseFocusReason)
        c = self.text.textCursor()
        if select_all:
            c.select(QTextCursor.Document)
        else:
            c.movePosition(QTextCursor.End)
        self.text.setTextCursor(c)
        sc = self.scene()
        if sc is not None:
            sc.editing_item = self

    def end_edit(self, notify: bool = True):
        if not self.editing:
            return
        self.editing = False
        c = self.text.textCursor()
        c.clearSelection()
        self.text.setTextCursor(c)
        self.text.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text.setAcceptedMouseButtons(Qt.NoButton)
        self.setFlag(FrameItem.ItemIsMovable, not self.locked and self.parentItem() is None)
        self.text.clearFocus()
        sc = self.scene()
        if sc is not None:
            if getattr(sc, "editing_item", None) is self:
                sc.editing_item = None
            if notify:
                sc.notify_changed()

    # ----------------------------------------------------------- formattazione
    def _target_cursor(self) -> QTextCursor:
        """Il testo selezionato durante la modifica, altrimenti tutto il testo."""
        if self.editing and self.text.textCursor().hasSelection():
            return self.text.textCursor()
        c = QTextCursor(self.text.document())
        c.select(QTextCursor.Document)
        return c

    def char_format(self) -> QTextCharFormat:
        if self.editing:
            return self.text.textCursor().charFormat()
        c = QTextCursor(self.text.document())
        c.setPosition(1 if self.text.document().characterCount() > 1 else 0)
        return c.charFormat()

    def block_format(self) -> QTextBlockFormat:
        if self.editing:
            return self.text.textCursor().blockFormat()
        return QTextCursor(self.text.document()).blockFormat()

    def merge_char_format(self, fmt: QTextCharFormat):
        c = self._target_cursor()
        c.mergeCharFormat(fmt)
        if not (self.editing and self.text.textCursor().hasSelection()):
            # anche il testo che verrà scritto dopo eredita il formato
            tc = self.text.textCursor()
            tc.mergeCharFormat(fmt)
        self.layout_text()

    def merge_block_format(self, fmt: QTextBlockFormat):
        self._target_cursor().mergeBlockFormat(fmt)
        self.layout_text()

    def set_valign(self, v: str):
        self.valign = v
        self.layout_text()

    def set_padding(self, pad_pt: float):
        self.padding = max(0.0, pad_pt)
        self.on_resized()

    def set_html(self, html: str):
        self.text.setHtml(html)
        self.layout_text()

    def plain_text(self) -> str:
        return self.text.toPlainText()

    # ------------------------------------------------------- serializzazione
    def to_dict(self) -> dict:
        d = self.base_dict()
        d.update({
            "html": self.text.toHtml(),
            "fill": color_to(self.fill),
            "stroke": color_to(self.stroke),
            "stroke_width": r3(self.stroke_width),
            "padding": r3(pt2mm(self.padding)),
            "valign": self.valign,
            "next": self.next.uid if self.next is not None else None,
            "continues": self.continues,
        })
        return d

    def apply_dict(self, d: dict):
        self.fill = color_from(d.get("fill"))
        self.stroke = color_from(d.get("stroke"))
        self.stroke_width = float(d.get("stroke_width", 1.0))
        self.padding = mm2pt(d.get("padding", 2.0))
        self.valign = d.get("valign", "top")
        self._next_id = d.get("next")
        self.continues = bool(d.get("continues", False))
        if "html" in d:
            self.text.setHtml(d["html"])
        self.apply_base(d)
