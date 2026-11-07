"""Forme: rettangolo (anche con angoli arrotondati), ellisse, linea."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen

from charta.items.base import FrameItem, color_from, color_to, r3
from charta.units import mm2pt, pt2mm

SHAPES = {"rect": "Rettangolo", "ellipse": "Ellisse", "line": "Linea", "path": "Forma libera"}


def build_path(cmds, w: float, h: float) -> QPainterPath:
    """Comandi normalizzati (coordinate da 0 a 1) → tracciato in punti."""
    path = QPainterPath()
    for c in cmds:
        op, v = c[0], c[1:]
        pts = [QPointF(v[i] * w, v[i + 1] * h) for i in range(0, len(v) - 1, 2)]
        if op == "M":
            path.moveTo(pts[0])
        elif op == "L":
            path.lineTo(pts[0])
        elif op == "Q":
            path.quadTo(pts[0], pts[1])
        elif op == "C":
            path.cubicTo(pts[0], pts[1], pts[2])
        elif op == "Z":
            path.closeSubpath()
    return path


class ShapeFrame(FrameItem):
    kind = "shape"

    def __init__(self, shape: str = "rect", w: float = 120, h: float = 80):
        super().__init__(w, h)
        self.shape_kind = shape
        if shape == "line":
            self.fill = QColor(0, 0, 0, 0)
            self.stroke = QColor("#222222")
            self.stroke_width = 2.0
        else:
            self.fill = QColor("#4a90d9")
            self.stroke = QColor(0, 0, 0, 0)
            self.stroke_width = 1.0
        self.radius = 0.0  # punti
        self.path_cmds: list = []  # solo per le forme libere (importate)

    def stroke_extent(self) -> float:
        return self.stroke_width / 2 if self.stroke.alpha() else 0.0

    def paint_content(self, painter):
        r = self.rect()
        has_stroke = self.stroke.alpha() and self.stroke_width > 0
        pen = QPen(self.stroke, self.stroke_width) if has_stroke else QPen(Qt.NoPen)
        if self.shape_kind == "line":
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(0, r.height() / 2), QPointF(r.width(), r.height() / 2))
            return
        painter.setPen(pen)
        painter.setBrush(QBrush(self.fill) if self.fill.alpha() else Qt.NoBrush)
        if self.shape_kind == "path":
            painter.drawPath(build_path(self.path_cmds, r.width(), r.height()))
        elif self.shape_kind == "ellipse":
            painter.drawEllipse(r)
        else:
            rad = min(self.radius, r.width() / 2, r.height() / 2)
            if rad > 0:
                painter.drawRoundedRect(r, rad, rad)
            else:
                painter.drawRect(r)
        if not self.fill.alpha() and not has_stroke:
            self.draw_guide_frame(painter)

    def to_dict(self) -> dict:
        d = self.base_dict()
        d.update({
            "shape": self.shape_kind,
            "fill": color_to(self.fill),
            "stroke": color_to(self.stroke),
            "stroke_width": r3(self.stroke_width),
            "radius": r3(pt2mm(self.radius)),
        })
        if self.shape_kind == "path":
            d["path"] = [[c[0]] + [round(x, 5) for x in c[1:]] for c in self.path_cmds]
        return d

    def apply_dict(self, d: dict):
        self.shape_kind = d.get("shape", "rect")
        self.fill = color_from(d.get("fill"))
        self.stroke = color_from(d.get("stroke"))
        self.stroke_width = float(d.get("stroke_width", 1.0))
        self.radius = mm2pt(d.get("radius", 0.0))
        self.path_cmds = [list(c) for c in d.get("path", [])]
        self.apply_base(d)
