"""Gruppi: più oggetti che si spostano, ridimensionano e ruotano insieme."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsItem

from charta.items.base import FrameItem


class GroupFrame(FrameItem):
    kind = "group"

    def __init__(self, w: float = 10, h: float = 10):
        super().__init__(w, h)
        self._last = (self._w, self._h)
        self._kids = []  # riferimenti Python ai figli (vedi PageScene._refs)

    def children_frames(self) -> list[FrameItem]:
        kids = [c for c in self.childItems() if isinstance(c, FrameItem)]
        kids.sort(key=lambda c: c.zValue())
        return kids

    def adopt(self, item: FrameItem, z: float):
        item.setSelected(False)
        self._kids.append(item)
        item.setParentItem(self)
        item.setZValue(z)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)

    def on_resized(self):
        w0, h0 = self._last
        if w0 > 0 and h0 > 0 and (abs(w0 - self._w) > 1e-6 or abs(h0 - self._h) > 1e-6):
            sx, sy = self._w / w0, self._h / h0
            for c in self.children_frames():
                c.setPos(c.pos().x() * sx, c.pos().y() * sy)
                c.resize_to(c.width() * sx, c.height() * sy)
        self._last = (self._w, self._h)

    def paint_content(self, painter):
        pass  # i figli si disegnano da soli

    def to_dict(self) -> dict:
        d = self.base_dict()
        d["items"] = [c.to_dict() for c in self.children_frames()]
        return d

    def apply_dict(self, d: dict, document=None):
        from charta.items import item_from_dict
        self.apply_base(d)
        self._last = (self._w, self._h)
        for i, cd in enumerate(d.get("items", [])):
            c = item_from_dict(cd, document)
            if c is not None:
                self.adopt(c, i)


def make_group(scene, items) -> GroupFrame | None:
    items = [it for it in items if it.parentItem() is None]
    if len(items) < 2:
        return None
    rect = QRectF()
    for it in items:
        rect = rect.united(it.mapRectToScene(it.rect()))
    g = GroupFrame(rect.width(), rect.height())
    g.setPos(rect.topLeft())
    scene.add_frame(g)
    for i, it in enumerate(sorted(items, key=lambda x: x.zValue())):
        p = it.pos() - g.pos()
        g.adopt(it, i)
        it.setPos(p)
    scene.normalize_z()
    return g


def ungroup(scene, g: GroupFrame) -> list[FrameItem]:
    kids = g.children_frames()
    z = g.zValue()
    out = []
    for i, c in enumerate(kids):
        top_left = c.mapToScene(QPointF(0, 0))
        rot = c.rotation() + g.rotation()
        c.setParentItem(None)
        scene._refs.add(c)
        c.setRotation(rot)
        c.set_geometry(top_left, c.width(), c.height())
        c.setFlag(QGraphicsItem.ItemIsSelectable, True)
        c.setFlag(QGraphicsItem.ItemIsMovable, not c.locked)
        c.setZValue(z + i * 0.001)
        out.append(c)
    scene.removeItem(g)
    scene.normalize_z()
    return out
