"""Righelli in millimetri e area di lavoro (righelli + vista). Trascinando
dal righello sulla pagina si crea una guida."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QWidget

from charta.i18n import tr
from charta.units import MM

RULER = 22


class Ruler(QWidget):
    def __init__(self, view, horizontal: bool, parent=None):
        super().__init__(parent)
        self.view = view
        self.horizontal = horizontal
        self.cursor_pos = None
        self._dragging = False
        if horizontal:
            self.setFixedHeight(RULER)
        else:
            self.setFixedWidth(RULER)
        self.setCursor(Qt.SplitVCursor if horizontal else Qt.SplitHCursor)
        self.setToolTip(tr("Trascina sulla pagina per creare una guida"))

    # coordinate: scena → pixel del righello
    def _to_px(self, v: float) -> float:
        vp = self.view.viewport()
        if self.horizontal:
            return vp.x() + self.view.mapFromScene(QPointF(v, 0)).x()
        return vp.y() + self.view.mapFromScene(QPointF(0, v)).y()

    def _scale(self) -> float:
        return self.view.transform().m11()

    def set_cursor(self, p: QPointF):
        self.cursor_pos = p.x() if self.horizontal else p.y()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        pal = self.palette()
        bg = pal.window().color()
        fg = pal.windowText().color()
        p.fillRect(self.rect(), bg.darker(103))
        sc = self.view.scene()
        if sc is None:
            p.end()
            return
        page_len = sc.page_w if self.horizontal else sc.page_h
        a, b = self._to_px(0), self._to_px(page_len)
        page_band = QRectF(a, 0, b - a, RULER) if self.horizontal else QRectF(0, a, RULER, b - a)
        p.fillRect(page_band, bg.lighter(108))

        px_mm = self._scale() * MM
        major = next((m for m in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if m * px_mm >= 48), 1000)
        minor = next((major / n for n in (10, 5, 2) if major / n * px_mm >= 5), major)
        length = self.width() if self.horizontal else self.height()
        # intervallo visibile in millimetri
        if self.horizontal:
            s0 = self.view.mapToScene(-self.view.viewport().x(), 0).x()
            s1 = self.view.mapToScene(length, 0).x()
        else:
            s0 = self.view.mapToScene(0, -self.view.viewport().y()).y()
            s1 = self.view.mapToScene(0, length).y()
        mm0, mm1 = s0 / MM, s1 / MM
        f = QFont()
        f.setPixelSize(9)
        p.setFont(f)
        pen = QPen(fg)
        pen.setWidthF(1)
        p.setPen(pen)
        k = int(mm0 // minor) - 1
        while k * minor <= mm1 + minor:
            v = k * minor
            x = self._to_px(v * MM)
            is_major = abs(v / major - round(v / major)) < 1e-6
            size = RULER * (0.55 if is_major else (0.35 if abs((v * 2) / major - round((v * 2) / major)) < 1e-6 else 0.2))
            if self.horizontal:
                p.drawLine(QPointF(x, RULER), QPointF(x, RULER - size))
                if is_major:
                    p.drawText(QPointF(x + 2, 10), f"{v:g}")
            else:
                p.drawLine(QPointF(RULER, x), QPointF(RULER - size, x))
                if is_major:
                    p.save()
                    p.translate(10, x + 2)
                    p.rotate(-90)
                    p.drawText(QPointF(-p.fontMetrics().horizontalAdvance(f"{v:g}"), 0), f"{v:g}")
                    p.restore()
            k += 1
        if self.cursor_pos is not None:
            x = self._to_px(self.cursor_pos)
            p.setPen(QPen(QColor("#e5007d"), 1))
            if self.horizontal:
                p.drawLine(QPointF(x, 0), QPointF(x, RULER))
            else:
                p.drawLine(QPointF(0, x), QPointF(RULER, x))
        p.setPen(QPen(fg.lighter(150) if fg.lightness() < 128 else fg.darker(150), 1))
        if self.horizontal:
            p.drawLine(0, RULER - 1, self.width(), RULER - 1)
        else:
            p.drawLine(RULER - 1, 0, RULER - 1, self.height())
        p.end()

    # ------------------------------------------------- nuova guida
    def _scene_value(self, global_pos):
        vp = self.view.viewport()
        local = vp.mapFromGlobal(global_pos)
        sp = self.view.mapToScene(local)
        inside = vp.rect().contains(local)
        return (sp.y() if self.horizontal else sp.x()), inside

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.view.scene() is not None:
            self._dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        sc = self.view.scene()
        v, inside = self._scene_value(event.globalPosition().toPoint())
        sc.drag_guide = (("y" if self.horizontal else "x"), v) if inside else None
        sc.update()

    def mouseReleaseEvent(self, event):
        if not self._dragging:
            return
        self._dragging = False
        sc = self.view.scene()
        sc.drag_guide = None
        v, inside = self._scene_value(event.globalPosition().toPoint())
        if inside:
            sc.add_guide("y" if self.horizontal else "x", v)
            self.view.guides_changed.emit()
        sc.update()


class CanvasArea(QWidget):
    """La vista con i righelli in alto e a sinistra."""

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        corner = QWidget()
        corner.setFixedSize(RULER, RULER)
        self.hruler = Ruler(view, True)
        self.vruler = Ruler(view, False)
        grid.addWidget(corner, 0, 0)
        grid.addWidget(self.hruler, 0, 1)
        grid.addWidget(self.vruler, 1, 0)
        grid.addWidget(view, 1, 1)
        self.corner = corner
        view.horizontalScrollBar().valueChanged.connect(self.refresh)
        view.verticalScrollBar().valueChanged.connect(self.refresh)
        view.zoom_changed.connect(self.refresh)
        view.cursor_moved.connect(self._cursor)

    def refresh(self, *_):
        self.hruler.update()
        self.vruler.update()

    def _cursor(self, p):
        self.hruler.set_cursor(p)
        self.vruler.set_cursor(p)

    def set_rulers_visible(self, visible: bool):
        for w in (self.hruler, self.vruler, self.corner):
            w.setVisible(visible)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.refresh()
