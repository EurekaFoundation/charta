"""Oggetto base dell'impaginazione: una cornice rettangolare che si può
spostare, ridimensionare con le maniglie, ruotare e bloccare."""

from __future__ import annotations

import uuid

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem

from charta.units import mm2pt, pt2mm

SELECTION_COLOR = QColor("#1f6feb")

HANDLE_NAMES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")
HANDLE_CURSORS = {
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
    "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
    "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
}


def color_from(value) -> QColor:
    """Colore da stringa ('#rrggbb', '#aarrggbb'); None = trasparente."""
    if not value:
        return QColor(0, 0, 0, 0)
    return QColor(value)


def color_to(c: QColor):
    if c.alpha() == 0:
        return None
    if c.alpha() < 255:
        return c.name(QColor.HexArgb)
    return c.name()


def r3(v: float) -> float:
    return round(float(v), 3)


def new_uid() -> str:
    return uuid.uuid4().hex[:12]


class FrameItem(QGraphicsItem):
    kind = "frame"
    MIN_SIZE = 4.0

    def __init__(self, w: float, h: float):
        super().__init__()
        self._w = float(w)
        self._h = float(h)
        self.uid = new_uid()
        self.locked = False
        self._drag = None          # stato del ridimensionamento in corso
        self._moving = False       # spostamento con il mouse in corso
        self._press_pos = None
        self.setFlags(QGraphicsItem.ItemIsMovable
                      | QGraphicsItem.ItemIsSelectable
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setTransformOriginPoint(self._w / 2, self._h / 2)

    # ------------------------------------------------------------ geometria
    def width(self) -> float:
        return self._w

    def height(self) -> float:
        return self._h

    def rect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def _hs(self) -> float:
        sc = self.scene()
        return getattr(sc, "handle_size", 6.0) if sc is not None else 6.0

    def exporting(self) -> bool:
        sc = self.scene()
        return bool(sc is not None and getattr(sc, "export_mode", False))

    def stroke_extent(self) -> float:
        return 0.0

    def boundingRect(self) -> QRectF:
        m = self._hs() + self.stroke_extent() + 1
        return self.rect().adjusted(-m, -m, m, m)

    def handle_points(self) -> dict:
        w, h = self._w, self._h
        return {"tl": QPointF(0, 0), "t": QPointF(w / 2, 0), "tr": QPointF(w, 0),
                "r": QPointF(w, h / 2), "br": QPointF(w, h), "b": QPointF(w / 2, h),
                "bl": QPointF(0, h), "l": QPointF(0, h / 2)}

    def handle_rects(self) -> dict:
        s = self._hs()
        return {n: QRectF(p.x() - s / 2, p.y() - s / 2, s, s)
                for n, p in self.handle_points().items()}

    def handle_at(self, pos: QPointF):
        if not self.isSelected() or self.locked:
            return None
        for name, r in self.handle_rects().items():
            if r.adjusted(-1, -1, 1, 1).contains(pos):
                return name
        return None

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.rect())
        if self.isSelected() and not self.locked:
            for r in self.handle_rects().values():
                path.addRect(r)
        return path

    def set_geometry(self, top_left: QPointF, w: float, h: float):
        """Imposta dimensioni e posizione dell'angolo in alto a sinistra
        (in coordinate del genitore: la scena o il gruppo), tenendo conto
        della rotazione."""
        self.prepareGeometryChange()
        self._w = max(self.MIN_SIZE, float(w))
        self._h = max(self.MIN_SIZE, float(h))
        o = QPointF(self._w / 2, self._h / 2)
        self.setTransformOriginPoint(o)
        t = QTransform().rotate(self.rotation())
        self.setPos(top_left - o + t.map(o))
        self.on_resized()
        self.update()

    def resize_to(self, w: float, h: float):
        self.set_geometry(self.mapToParent(QPointF(0, 0)), w, h)

    def on_resized(self):
        """Da ridefinire nelle sottoclassi che devono reagire al ridimensionamento."""

    def set_locked(self, locked: bool):
        self.locked = bool(locked)
        self.setFlag(QGraphicsItem.ItemIsMovable, not self.locked)
        self.prepareGeometryChange()
        self.update()

    # -------------------------------------------------------------- disegno
    def paint_content(self, painter):
        raise NotImplementedError

    def draw_guide_frame(self, painter):
        """Cornice tratteggiata leggera, visibile solo a schermo."""
        if self.exporting():
            return
        pen = QPen(QColor(120, 120, 120, 140), 0, Qt.DotLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())

    def paint(self, painter, option, widget=None):
        painter.save()
        self.paint_content(painter)
        painter.restore()
        if self.isSelected() and not self.exporting():
            pen = QPen(SELECTION_COLOR, 0, Qt.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect())
            pen = QPen(SELECTION_COLOR if not self.locked else QColor("#888888"), 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor("white")))
            if self.locked:
                s = self._hs()
                painter.setBrush(QBrush(QColor("#888888")))
                painter.drawRect(QRectF(-s / 2, -s / 2, s, s))
            else:
                for r in self.handle_rects().values():
                    painter.drawRect(r)

    # --------------------------------------------------------------- mouse
    def hoverMoveEvent(self, event):
        h = self.handle_at(event.pos())
        if h:
            self.setCursor(HANDLE_CURSORS[h])
        elif self.locked:
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            h = self.handle_at(event.pos())
            if h:
                t = self.sceneTransform()
                self._drag = (h, self.rect(), t, t.inverted()[0].map(event.scenePos()))
                event.accept()
                return
            self._moving = True
            self._press_pos = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag:
            self._resize_move(event)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _resize_move(self, event):
        name, r0, t0, p0 = self._drag
        p = t0.inverted()[0].map(event.scenePos())
        dx, dy = p.x() - p0.x(), p.y() - p0.y()
        left, top, right, bottom = r0.left(), r0.top(), r0.right(), r0.bottom()
        mv_l = name in ("tl", "bl", "l")
        mv_r = name in ("tr", "br", "r")
        mv_t = name in ("tl", "t", "tr")
        mv_b = name in ("bl", "b", "br")
        if mv_l:
            left += dx
        if mv_r:
            right += dx
        if mv_t:
            top += dy
        if mv_b:
            bottom += dy

        sc = self.scene()
        if sc is not None and getattr(sc, "snap_enabled", False) and abs(self.rotation()) < 0.01:
            off = t0.map(QPointF(0, 0))
            sc.begin_snap()
            if mv_l:
                left = sc.snap_coord(left + off.x(), "x", self) - off.x()
            if mv_r:
                right = sc.snap_coord(right + off.x(), "x", self) - off.x()
            if mv_t:
                top = sc.snap_coord(top + off.y(), "y", self) - off.y()
            if mv_b:
                bottom = sc.snap_coord(bottom + off.y(), "y", self) - off.y()
            sc.end_snap()

        keep = bool(event.modifiers() & Qt.ShiftModifier) != self.keep_aspect_by_default()
        if keep and len(name) == 2 and r0.height() > 0:
            ratio = r0.width() / r0.height()
            w = abs(right - left)
            h = w / ratio
            if mv_t:
                top = bottom - h
            else:
                bottom = top + h

        m = self.MIN_SIZE
        if right - left < m:
            if mv_l:
                left = right - m
            else:
                right = left + m
        if bottom - top < m:
            if mv_t:
                top = bottom - m
            else:
                bottom = top + m
        r = QRectF(QPointF(left, top), QPointF(right, bottom))
        self.set_geometry(t0.map(r.topLeft()), r.width(), r.height())

    def keep_aspect_by_default(self) -> bool:
        return False

    def mouseReleaseEvent(self, event):
        sc = self.scene()
        if self._drag:
            self._drag = None
            if sc is not None:
                sc.clear_snap_lines()
                sc.notify_changed()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._moving = False
        if sc is not None:
            sc.clear_snap_lines()
            if self._press_pos is not None and self.pos() != self._press_pos:
                sc.notify_changed()
        self._press_pos = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self._moving:
            sc = self.scene()
            if sc is not None and len(sc.selectedItems()) <= 1:
                return sc.snap_position(self, value)
        return super().itemChange(change, value)

    # ------------------------------------------------------- serializzazione
    def base_dict(self) -> dict:
        return {
            "type": self.kind,
            "id": self.uid,
            "x": r3(pt2mm(self.pos().x())), "y": r3(pt2mm(self.pos().y())),
            "w": r3(pt2mm(self._w)), "h": r3(pt2mm(self._h)),
            "rotation": r3(self.rotation()),
            "opacity": r3(self.opacity()),
            "locked": self.locked,
        }

    def apply_base(self, d: dict):
        self.uid = d.get("id") or new_uid()
        self.prepareGeometryChange()
        self._w = max(self.MIN_SIZE, mm2pt(d.get("w", 50)))
        self._h = max(self.MIN_SIZE, mm2pt(d.get("h", 50)))
        self.setTransformOriginPoint(self._w / 2, self._h / 2)
        self.setRotation(d.get("rotation", 0))
        self.setPos(mm2pt(d.get("x", 0)), mm2pt(d.get("y", 0)))
        self.setOpacity(d.get("opacity", 1.0))
        self.set_locked(d.get("locked", False))
        self.on_resized()

    def to_dict(self) -> dict:
        raise NotImplementedError
