"""Cornice immagine: l'immagine originale resta a piena risoluzione nel file
e nel PDF; a schermo si usa una copia ridotta per restare veloci."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from charta.i18n import tr
from charta.items.base import FrameItem, color_from, color_to, r3

SCREEN_MAX_PX = 1800

FIT_MODES = {
    "fill": "Riempi la cornice (ritaglia)",
    "fit": "Adatta alla cornice (intera)",
    "stretch": "Deforma per riempire",
}


class ImageFrame(FrameItem):
    kind = "image"

    def __init__(self, document, asset_id=None, w: float = 200, h: float = 150):
        super().__init__(w, h)
        self.document = document
        self.asset = None
        self.fit = "fill"
        self.stroke = QColor(0, 0, 0, 0)
        self.stroke_width = 1.0
        self.corner = 0.0
        self._img = QImage()
        self._screen = QImage()
        self.set_asset(asset_id)

    def set_asset(self, asset_id):
        self.asset = asset_id
        self._img = QImage()
        if asset_id and asset_id in self.document.assets:
            self._img = QImage.fromData(self.document.assets[asset_id])
        self._screen = self._img
        if not self._img.isNull() and max(self._img.width(), self._img.height()) > SCREEN_MAX_PX:
            self._screen = self._img.scaled(SCREEN_MAX_PX, SCREEN_MAX_PX,
                                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.update()

    def has_image(self) -> bool:
        return not self._img.isNull()

    def natural_aspect(self) -> float:
        if self._img.isNull() or self._img.height() == 0:
            return 1.0
        return self._img.width() / self._img.height()

    def keep_aspect_by_default(self) -> bool:
        return self.has_image() and self.fit == "stretch"

    def stroke_extent(self) -> float:
        return self.stroke_width / 2 if self.stroke.alpha() else 0.0

    def paint_content(self, painter):
        r = self.rect()
        if self._img.isNull():
            if self.exporting():
                return
            painter.fillRect(r, QColor(225, 228, 232))
            pen = QPen(QColor(150, 155, 160), 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())
            f = QFont()
            f.setPointSizeF(max(4.0, min(r.width(), r.height()) / 14))
            painter.setFont(f)
            painter.setPen(QColor(90, 95, 100))
            painter.drawText(r.adjusted(4, 4, -4, -4), Qt.AlignCenter | Qt.TextWordWrap,
                             tr("Doppio clic per inserire un'immagine"))
            return

        img = self._img if self.exporting() else self._screen
        iw, ih = img.width(), img.height()
        src = QRectF(0, 0, iw, ih)
        dst = QRectF(r)
        if self.fit == "fit":
            s = min(r.width() / iw, r.height() / ih)
            dst = QRectF(0, 0, iw * s, ih * s)
            dst.moveCenter(r.center())
        elif self.fit == "fill":
            s = max(r.width() / iw, r.height() / ih)
            sw, sh = r.width() / s, r.height() / s
            src = QRectF((iw - sw) / 2, (ih - sh) / 2, sw, sh)
        painter.save()
        painter.setClipRect(r)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawImage(dst, img, src)
        painter.restore()
        if self.stroke.alpha() and self.stroke_width > 0:
            painter.setPen(QPen(self.stroke, self.stroke_width))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)

    def mouseDoubleClickEvent(self, event):
        sc = self.scene()
        if sc is not None and not self.locked:
            sc.image_pick_requested.emit(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def to_dict(self) -> dict:
        d = self.base_dict()
        d.update({
            "asset": self.asset,
            "fit": self.fit,
            "stroke": color_to(self.stroke),
            "stroke_width": r3(self.stroke_width),
        })
        return d

    def apply_dict(self, d: dict):
        self.fit = d.get("fit", "fill")
        self.stroke = color_from(d.get("stroke"))
        self.stroke_width = float(d.get("stroke_width", 1.0))
        self.set_asset(d.get("asset"))
        self.apply_base(d)
