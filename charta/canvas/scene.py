"""Scena di una pagina: foglio, margini, griglia, calamita e guide intelligenti."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsScene

from charta.items import FrameItem, item_from_dict
from charta.units import mm2pt

PASTEBOARD_COLOR = QColor("#c8ccd3")
MARGIN_COLOR = QColor(217, 70, 239, 170)
GRID_COLOR = QColor(80, 120, 200, 45)
SNAP_COLOR = QColor("#e5007d")
GUIDE_COLOR = QColor("#00a3e0")


class PageScene(QGraphicsScene):
    changed_by_user = Signal()
    image_pick_requested = Signal(object)

    PASTEBOARD = mm2pt(70)

    def __init__(self, page: dict, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.export_mode = False
        self.export_bleed = 0.0
        self.handle_size = 6.0
        self.show_grid = False
        self.grid_mm = 5.0
        self.snap_enabled = True
        self.show_margins = True
        self.show_guides = True
        self.guides = {"x": [], "y": []}   # in punti
        self.drag_guide = None             # (asse, valore) durante il trascinamento
        self.editing_item = None
        self._refs = set()   # riferimenti Python: senza, PySide può distruggere gli oggetti
        self.snap_lines: list[tuple[str, float]] = []
        self._collect = None
        self.set_page_props(page)
        self.load_items(page.get("items", []))

    # ---------------------------------------------------------------- pagina
    def set_page_props(self, page: dict):
        self.page_w = mm2pt(page["width"])
        self.page_h = mm2pt(page["height"])
        self.margins = [mm2pt(m) for m in page.get("margins", [12.7] * 4)]
        self.background = QColor(page.get("background") or "#ffffff")
        if "guides" in page:
            g = page["guides"] or {}
            self.guides = {"x": [mm2pt(v) for v in g.get("x", [])],
                           "y": [mm2pt(v) for v in g.get("y", [])]}
        p = self.PASTEBOARD
        self.setSceneRect(QRectF(-p, -p, self.page_w + 2 * p, self.page_h + 2 * p))
        self.update()

    def page_props(self) -> dict:
        from charta.units import pt2mm
        return {
            "width": round(pt2mm(self.page_w), 3),
            "height": round(pt2mm(self.page_h), 3),
            "margins": [round(pt2mm(m), 3) for m in self.margins],
            "background": self.background.name(),
            "guides": {"x": [round(pt2mm(v), 3) for v in self.guides["x"]],
                       "y": [round(pt2mm(v), 3) for v in self.guides["y"]]},
        }

    # ------------------------------------------------------------------ guide
    def add_guide(self, axis: str, value: float):
        self.guides[axis].append(value)
        self.update()

    def guide_at(self, pos: QPointF, tol: float):
        """(asse, indice) della guida più vicina entro la tolleranza."""
        if not self.show_guides:
            return None
        best = None
        for axis, coord in (("x", pos.x()), ("y", pos.y())):
            for i, v in enumerate(self.guides[axis]):
                d = abs(v - coord)
                if d <= tol and (best is None or d < best[0]):
                    best = (d, axis, i)
        return (best[1], best[2]) if best else None

    def clear_guides(self):
        self.guides = {"x": [], "y": []}
        self.update()

    def page_rect(self) -> QRectF:
        return QRectF(0, 0, self.page_w, self.page_h)

    def margin_rect(self) -> QRectF:
        t, r, b, l = self.margins
        return QRectF(l, t, self.page_w - l - r, self.page_h - t - b)

    # ---------------------------------------------------------------- oggetti
    def frames(self) -> list[FrameItem]:
        """Oggetti di primo livello della pagina, dal più in basso al più in alto
        (gli oggetti dentro un gruppo appartengono al gruppo)."""
        items = [i for i in self.items() if isinstance(i, FrameItem) and i.parentItem() is None]
        items.sort(key=lambda i: i.zValue())
        return items

    def all_frames(self) -> list[FrameItem]:
        """Tutti gli oggetti, compresi quelli dentro i gruppi."""
        return [i for i in self.items() if isinstance(i, FrameItem)]

    def selected_frames(self) -> list[FrameItem]:
        return [i for i in self.selectedItems() if isinstance(i, FrameItem)]

    def load_items(self, items: list[dict]):
        for d in items:
            it = item_from_dict(d, self.document)
            if it is not None:
                self.add_frame(it)

    def addItem(self, item):
        if isinstance(item, FrameItem):
            self._refs.add(item)
        super().addItem(item)

    def removeItem(self, item):
        self._refs.discard(item)
        super().removeItem(item)

    def add_frame(self, item: FrameItem):
        frames = self.frames()
        item.setZValue((frames[-1].zValue() + 1) if frames else 0)
        self.addItem(item)

    def normalize_z(self):
        for i, it in enumerate(self.frames()):
            it.setZValue(i)

    def to_page_dict(self) -> dict:
        d = self.page_props()
        d["items"] = [it.to_dict() for it in self.frames()]
        return d

    def notify_changed(self):
        self.changed_by_user.emit()

    # ---------------------------------------------------------------- disegno
    def drawBackground(self, painter, rect):
        if self.export_mode:
            b = self.export_bleed
            painter.fillRect(self.page_rect().adjusted(-b, -b, b, b), self.background)
            return
        painter.fillRect(rect, PASTEBOARD_COLOR)
        shadow = self.page_rect().translated(2.5, 2.5)
        painter.fillRect(shadow, QColor(0, 0, 0, 55))
        painter.fillRect(self.page_rect(), self.background)

    def drawForeground(self, painter, rect):
        if self.export_mode:
            return
        page = self.page_rect()
        if self.show_grid and self.grid_mm > 0:
            g = mm2pt(self.grid_mm)
            pen = QPen(GRID_COLOR, 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            area = rect.intersected(page)
            x = page.left() + g * int((area.left() - page.left()) / g)
            lines = []
            while x <= area.right():
                lines.append(QLineF(x, area.top(), x, area.bottom()))
                x += g
            y = page.top() + g * int((area.top() - page.top()) / g)
            while y <= area.bottom():
                lines.append(QLineF(area.left(), y, area.right(), y))
                y += g
            painter.drawLines(lines)
        if self.show_margins:
            pen = QPen(MARGIN_COLOR, 0, Qt.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.margin_rect())
        pen = QPen(QColor(0, 0, 0, 90), 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(page)
        if self.show_guides or self.drag_guide:
            pen = QPen(GUIDE_COLOR, 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            sr = self.sceneRect()
            lines = []
            if self.show_guides:
                lines += [("x", v) for v in self.guides["x"]] + [("y", v) for v in self.guides["y"]]
            if self.drag_guide:
                lines.append(self.drag_guide)
            for axis, v in lines:
                if axis == "x":
                    painter.drawLine(QPointF(v, sr.top()), QPointF(v, sr.bottom()))
                else:
                    painter.drawLine(QPointF(sr.left(), v), QPointF(sr.right(), v))
        if self.snap_lines:
            pen = QPen(SNAP_COLOR, 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            sr = self.sceneRect()
            for axis, v in self.snap_lines:
                if axis == "x":
                    painter.drawLine(QPointF(v, sr.top()), QPointF(v, sr.bottom()))
                else:
                    painter.drawLine(QPointF(sr.left(), v), QPointF(sr.right(), v))

    # --------------------------------------------------------------- calamita
    def _targets(self, axis: str, exclude) -> list[float]:
        p, m = self.page_rect(), self.margin_rect()
        if axis == "x":
            t = [p.left(), p.center().x(), p.right(), m.left(), m.right()]
        else:
            t = [p.top(), p.center().y(), p.bottom(), m.top(), m.bottom()]
        if self.show_guides:
            t += self.guides[axis]
        skip = set(self.selected_frames())
        skip.add(exclude)
        for it in self.frames():
            if it in skip:
                continue
            r = it.mapRectToScene(it.rect())
            if axis == "x":
                t += [r.left(), r.center().x(), r.right()]
            else:
                t += [r.top(), r.center().y(), r.bottom()]
        return t

    def _best(self, values, targets):
        thr = self.handle_size * 1.2
        best = None
        for v in values:
            for t in targets:
                d = t - v
                if abs(d) <= thr and (best is None or abs(d) < abs(best[0])):
                    best = (d, t)
        return best

    def _grid_delta(self, v: float) -> float:
        g = mm2pt(self.grid_mm)
        return round(v / g) * g - v

    def snap_position(self, item: FrameItem, new_pos: QPointF) -> QPointF:
        if not self.snap_enabled:
            return new_pos
        r = item.mapRectToScene(item.rect()).translated(new_pos - item.pos())
        lines = []
        bx = self._best([r.left(), r.center().x(), r.right()], self._targets("x", item))
        if bx:
            new_pos.setX(new_pos.x() + bx[0])
            lines.append(("x", bx[1]))
        elif self.show_grid:
            new_pos.setX(new_pos.x() + self._grid_delta(r.left()))
        by = self._best([r.top(), r.center().y(), r.bottom()], self._targets("y", item))
        if by:
            new_pos.setY(new_pos.y() + by[0])
            lines.append(("y", by[1]))
        elif self.show_grid:
            new_pos.setY(new_pos.y() + self._grid_delta(r.top()))
        if lines != self.snap_lines:
            self.snap_lines = lines
            self.update()
        return new_pos

    def begin_snap(self):
        self._collect = []

    def end_snap(self):
        self.snap_lines = self._collect or []
        self._collect = None
        self.update()

    def snap_coord(self, v: float, axis: str, exclude) -> float:
        b = self._best([v], self._targets(axis, exclude))
        if b:
            if self._collect is not None:
                self._collect.append((axis, b[1]))
            return v + b[0]
        if self.show_grid:
            return v + self._grid_delta(v)
        return v

    def clear_snap_lines(self):
        if self.snap_lines:
            self.snap_lines = []
            self.update()
