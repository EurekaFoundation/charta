"""Vista dell'area di lavoro: zoom, strumenti di disegno, spostamento con le
frecce e trascinamento di immagini dal computer."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsView

from charta.units import SCREEN_SCALE, mm2pt

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
CREATION_TOOLS = ("text", "rect", "ellipse", "line", "image", "table")


class CanvasView(QGraphicsView):
    zoom_changed = Signal(float)
    create_requested = Signal(str, QPointF, QPointF)  # strumento, inizio, fine (punti)
    images_dropped = Signal(list, QPointF)        # percorsi, posizione
    nudge_done = Signal()
    cursor_moved = Signal(QPointF)
    guides_changed = Signal()
    link_target = Signal(object)                  # cornice cliccata in modalità collegamento

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                            | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.zoom = 1.0
        self.tool = "select"
        self._start = None
        self._preview = None
        self._panning = None
        self._guide = None   # (asse, indice) della guida trascinata

    # ----------------------------------------------------------------- zoom
    def set_zoom(self, z: float, anchor_mouse: bool = False):
        z = max(0.1, min(8.0, z))
        self.zoom = z
        if not anchor_mouse:
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        s = z * SCREEN_SCALE
        self.resetTransform()
        self.scale(s, s)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        if self.scene() is not None:
            self.scene().handle_size = 7.0 / s
        self.zoom_changed.emit(z)

    def fit_page(self):
        sc = self.scene()
        if sc is None:
            return
        page = sc.page_rect()
        vw = self.viewport().width() - 40
        vh = self.viewport().height() - 40
        if vw <= 0 or vh <= 0:
            return
        z = min(vw / page.width(), vh / page.height()) / SCREEN_SCALE
        self.set_zoom(z)
        self.centerOn(page.center())

    def fit_width(self):
        sc = self.scene()
        if sc is None:
            return
        page = sc.page_rect()
        z = (self.viewport().width() - 40) / page.width() / SCREEN_SCALE
        self.set_zoom(z)
        self.centerOn(QPointF(page.center().x(), page.top() + self.viewport().height() / 2 / (z * SCREEN_SCALE)))

    def setScene(self, scene):
        super().setScene(scene)
        if scene is not None:
            scene.handle_size = 7.0 / (self.zoom * SCREEN_SCALE)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom * factor, anchor_mouse=True)
            event.accept()
            return
        super().wheelEvent(event)

    # -------------------------------------------------------------- strumenti
    def set_tool(self, tool: str):
        self.tool = tool
        if tool == "link":
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.PointingHandCursor)
        elif tool in CREATION_TOOLS:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        sc = self.scene()
        if self.tool == "link" and event.button() == Qt.LeftButton:
            p = self.mapToScene(event.position().toPoint())
            self.link_target.emit(self._frame_at(p))
            event.accept()
            return
        if self.tool == "select" and event.button() == Qt.LeftButton and sc is not None:
            p = self.mapToScene(event.position().toPoint())
            hit = sc.guide_at(p, 4 / self.transform().m11())
            under = self._frame_at(p)
            if hit and (under is None or under.locked):
                self._guide = hit
                event.accept()
                return
        if self.tool in CREATION_TOOLS and event.button() == Qt.LeftButton:
            self._start = self.mapToScene(event.position().toPoint())
            pen = QPen(QColor("#1f6feb"), 0, Qt.DashLine)
            pen.setCosmetic(True)
            self._preview = QGraphicsRectItem(QRectF(self._start, self._start))
            self._preview.setPen(pen)
            self._preview.setZValue(1e9)
            self.scene().addItem(self._preview)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning is not None:
            d = event.position() - self._panning
            self._panning = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            event.accept()
            return
        p = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(p)
        sc = self.scene()
        if self._guide is not None and sc is not None:
            axis, i = self._guide
            sc.guides[axis][i] = p.x() if axis == "x" else p.y()
            sc.update()
            event.accept()
            return
        if self.tool == "select" and sc is not None and not event.buttons():
            hit = sc.guide_at(p, 4 / self.transform().m11())
            under = self._frame_at(p)
            if hit and (under is None or under.locked):
                self.viewport().setCursor(Qt.SplitHCursor if hit[0] == "x" else Qt.SplitVCursor)
            else:
                self.viewport().unsetCursor()
        if self._start is not None and self._preview is not None:
            self._preview.setRect(QRectF(self._start, p).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _handle_under(self, p: QPointF) -> bool:
        from charta.items.base import FrameItem
        it = self.scene().itemAt(p, self.transform())
        while it is not None and not isinstance(it, FrameItem):
            it = it.parentItem()
        return it is not None and it.handle_at(it.mapFromScene(p)) is not None

    def _frame_at(self, p: QPointF):
        from charta.items.base import FrameItem
        it = self.scene().itemAt(p, self.transform())
        while it is not None and not isinstance(it, FrameItem):
            it = it.parentItem()
        return it

    def mouseReleaseEvent(self, event):
        if self._guide is not None:
            axis, i = self._guide
            self._guide = None
            sc = self.scene()
            # trascinata fuori dalla vista (sul righello): la guida si elimina
            if not self.viewport().rect().contains(event.position().toPoint()):
                del sc.guides[axis][i]
            sc.update()
            self.guides_changed.emit()
            event.accept()
            return
        if self._panning is not None and event.button() == Qt.MiddleButton:
            self._panning = None
            self.viewport().unsetCursor() if self.tool == "select" else self.viewport().setCursor(Qt.CrossCursor)
            event.accept()
            return
        if self._start is not None and event.button() == Qt.LeftButton:
            start = self._start
            end = self.mapToScene(event.position().toPoint())
            self.scene().removeItem(self._preview)
            self._preview = None
            self._start = None
            # un semplice clic crea un oggetto di dimensione predefinita
            if abs(end.x() - start.x()) < 6 and abs(end.y() - start.y()) < 6:
                end = QPointF(start)
            self.create_requested.emit(self.tool, start, end)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ----------------------------------------------------------- tastiera
    def keyPressEvent(self, event):
        sc = self.scene()
        editing = sc is not None and sc.editing_item is not None
        key = event.key()
        if not editing and sc is not None and key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            frames = [f for f in sc.selected_frames() if not f.locked]
            if frames:
                step = mm2pt(10 if event.modifiers() & Qt.ShiftModifier else 1)
                if event.modifiers() & Qt.AltModifier:
                    step = mm2pt(0.1)
                dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(key, 0)
                dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(key, 0)
                for f in frames:
                    f.moveBy(dx, dy)
                self.nudge_done.emit()
                event.accept()
                return
        if key == Qt.Key_Escape and self.tool == "link":
            self.set_tool("select")
            self.link_target.emit(None)
            event.accept()
            return
        if not editing and key == Qt.Key_Escape:
            if self.tool != "select":
                self.set_tool("select")
            elif sc is not None:
                sc.clearSelection()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------- trascina e rilascia
    def _image_paths(self, mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(IMAGE_EXTS)]

    def dragEnterEvent(self, event):
        if self._image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = self._image_paths(event.mimeData())
        if paths:
            self.images_dropped.emit(paths, self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
