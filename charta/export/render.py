"""Esportazione in PDF (anche con abbondanza e segni di taglio per la
tipografia), in immagine PNG/JPG e stampa."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from charta.i18n import tr
from charta.system import external_env
from charta import APP_NAME, __version__
from charta.units import mm2pt

MARK_AREA_MM = 8.0   # spazio esterno per i segni di taglio
MARK_LEN_MM = 5.0


@contextmanager
def export_mode(scene, bleed_pt: float = 0.0):
    """Nasconde maniglie, margini e griglia mentre si disegna la pagina."""
    selected = scene.selectedItems()
    editing = scene.editing_item
    if editing is not None:
        editing.end_edit()
    scene.clearSelection()
    scene.export_mode = True
    scene.export_bleed = bleed_pt
    old_lines = scene.snap_lines
    scene.snap_lines = []
    try:
        yield
    finally:
        scene.export_mode = False
        scene.export_bleed = 0.0
        scene.snap_lines = old_lines
        for it in selected:
            it.setSelected(True)


def render_page(scene, painter: QPainter, target: QRectF, bleed_pt: float = 0.0):
    """Disegna la pagina (più l'eventuale abbondanza) nel rettangolo target,
    espresso in punti nel sistema di coordinate del painter."""
    source = scene.page_rect().adjusted(-bleed_pt, -bleed_pt, bleed_pt, bleed_pt)
    with export_mode(scene, bleed_pt):
        scene.render(painter, target, source, Qt.IgnoreAspectRatio)


def _crop_marks(painter: QPainter, trim: QRectF, bleed: float):
    pen = QPen(QColor("black"), 0.25)
    painter.setPen(pen)
    gap = bleed + mm2pt(1)          # i segni iniziano oltre l'abbondanza
    ln = mm2pt(MARK_LEN_MM)
    for x in (trim.left(), trim.right()):
        for y, sign in ((trim.top(), -1), (trim.bottom(), 1)):
            painter.drawLine(QPointF(x, y + sign * gap), QPointF(x, y + sign * (gap + ln)))
    for y in (trim.top(), trim.bottom()):
        for x, sign in ((trim.left(), -1), (trim.right(), 1)):
            painter.drawLine(QPointF(x + sign * gap, y), QPointF(x + sign * (gap + ln), y))


class CmykError(Exception):
    pass


def find_ghostscript() -> str | None:
    for name in ("gs", "gswin64c", "gswin32c"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform.startswith("win"):
        for pattern in (r"C:\Program Files\gs\*\bin\gswin64c.exe",
                        r"C:\Program Files (x86)\gs\*\bin\gswin32c.exe"):
            found = sorted(glob.glob(pattern))
            if found:
                return found[-1]
    for p in ("/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        if os.path.exists(p):
            return p
    return None


def convert_pdf_to_cmyk(path: str):
    """Converte i colori del PDF in CMYK con Ghostscript (richiesto da molte
    tipografie). Il file viene sostituito solo se la conversione riesce."""
    gs = find_ghostscript()
    if gs is None:
        raise CmykError(tr("Ghostscript non è installato. Scaricalo gratuitamente da "
                           "ghostscript.com e riprova."))
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    cmd = [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite",
           "-dCompatibilityLevel=1.6", "-sColorConversionStrategy=CMYK",
           "-dProcessColorModel=/DeviceCMYK", "-dPDFSETTINGS=/prepress",
           "-dAutoRotatePages=/None", f"-sOutputFile={tmp}", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                           env=external_env(),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or not os.path.getsize(tmp):
            raise CmykError(tr("Conversione in CMYK non riuscita:") + "\n" + (r.stderr or r.stdout)[-800:])
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def export_pdf(scenes, path: str, title: str = "", bleed_mm: float = 0.0,
               crop_marks: bool = False, resolution: int = 1200, cmyk: bool = False):
    _write_pdf(scenes, path, title, bleed_mm, crop_marks, resolution)
    if cmyk:
        convert_pdf_to_cmyk(path)


def _write_pdf(scenes, path, title, bleed_mm, crop_marks, resolution):
    writer = QPdfWriter(path)
    writer.setResolution(resolution)
    writer.setCreator(f"{APP_NAME} {__version__}")
    writer.setTitle(title)
    bleed = mm2pt(bleed_mm)
    extra = bleed + (mm2pt(MARK_AREA_MM) if crop_marks else 0.0)

    painter = None
    for i, scene in enumerate(scenes):
        pw, ph = scene.page_w + 2 * extra, scene.page_h + 2 * extra
        layout = QPageLayout(QPageSize(QSizeF(pw, ph), QPageSize.Point, "", QPageSize.ExactMatch),
                             QPageLayout.Portrait, QMarginsF(0, 0, 0, 0))
        writer.setPageLayout(layout)
        if i == 0:
            painter = QPainter(writer)
            painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform
                                   | QPainter.TextAntialiasing)
        else:
            writer.newPage()
        painter.save()
        s = writer.resolution() / 72.0
        painter.scale(s, s)
        target = QRectF(extra - bleed, extra - bleed, scene.page_w + 2 * bleed, scene.page_h + 2 * bleed)
        render_page(scene, painter, target, bleed)
        if crop_marks:
            trim = QRectF(extra, extra, scene.page_w, scene.page_h)
            _crop_marks(painter, trim, bleed)
        painter.restore()
    if painter is not None:
        painter.end()


def page_image(scene, dpi: int = 150, transparent: bool = False) -> QImage:
    s = dpi / 72.0
    img = QImage(max(1, round(scene.page_w * s)), max(1, round(scene.page_h * s)),
                 QImage.Format_ARGB32_Premultiplied)
    dpm = round(dpi / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    img.fill(Qt.transparent if transparent else Qt.white)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    render_page(scene, p, QRectF(0, 0, img.width(), img.height()))
    p.end()
    return img


def thumbnail(scene, max_px: int = 256) -> QImage:
    side = max(scene.page_w, scene.page_h)
    dpi = max(10, int(72 * max_px / side))
    return page_image(scene, dpi)


def print_pages(scenes, printer):
    """Stampa le pagine adattandole all'area stampabile del foglio scelto."""
    painter = QPainter(printer)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    for i, scene in enumerate(scenes):
        if i > 0:
            printer.newPage()
        area = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
        area.moveTo(0, 0)
        s = min(area.width() / scene.page_w, area.height() / scene.page_h)
        target = QRectF(0, 0, scene.page_w * s, scene.page_h * s)
        target.moveCenter(area.center())
        render_page(scene, painter, target)
    painter.end()
