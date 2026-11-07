"""Importazione di disegni OpenDocument (.odg, .fodg) in oggetti Charta.

È anche la seconda metà dell'importazione di Microsoft Publisher: i file .pub
vengono prima convertiti in .odg da LibreOffice (vedi publisher.py), poi
letti da qui. Testi, forme, linee, immagini, rotazioni e colori diventano
oggetti Charta modificabili."""

from __future__ import annotations

import base64
import html
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile

from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QTransform

from charta.i18n import tr
from charta.document.model import FORMAT_VERSION, Document
from charta.items.base import new_uid

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
}


def q(tag: str) -> str:
    p, n = tag.split(":")
    return f"{{{NS[p]}}}{n}"


class ImportError_(Exception):
    pass


# ----------------------------------------------------------------- misure
_UNITS = {"cm": 10.0, "mm": 1.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6,
          "px": 25.4 / 96, "": 25.4 / 96}


def mm(v, default=None):
    """'2.5cm' → 25.0 (millimetri)."""
    if v is None:
        return default
    m = re.match(r"\s*(-?[\d.]+(?:e-?\d+)?)\s*([a-z]*)", str(v))
    if not m:
        return default
    return float(m.group(1)) * _UNITS.get(m.group(2), 1.0)


def pt(v, default=None):
    r = mm(v)
    return default if r is None else r * 72 / 25.4


def percent(v, default=None):
    if v and str(v).strip().endswith("%"):
        try:
            return float(str(v).strip()[:-1]) / 100
        except ValueError:
            pass
    return default


# ----------------------------------------------------------------- stili
class Styles:
    def __init__(self, roots):
        self.named = {}       # (famiglia, nome) -> elemento
        self.defaults = {}    # famiglia -> elemento
        self.fonts = {}
        self.layouts = {}
        self.masters = {}
        for root in roots:
            for decls in root.iter(q("office:font-face-decls")):
                for f in decls:
                    fam = f.get(q("svg:font-family"), f.get(q("style:name"), ""))
                    self.fonts[f.get(q("style:name"))] = fam.strip("'\"")
            for st in root.iter(q("style:style")):
                self.named[(st.get(q("style:family")), st.get(q("style:name")))] = st
            for st in root.iter(q("style:default-style")):
                self.defaults[st.get(q("style:family"))] = st
            for pl in root.iter(q("style:page-layout")):
                props = pl.find(q("style:page-layout-properties"))
                self.layouts[pl.get(q("style:name"))] = dict(props.attrib) if props is not None else {}
            for mp in root.iter(q("style:master-page")):
                self.masters[mp.get(q("style:name"))] = mp

    def props(self, family: str, name: str | None, kind: str) -> dict:
        """Proprietà di un tipo (es. 'style:text-properties') risolvendo la
        catena degli stili genitori e lo stile predefinito."""
        chain, seen = [], set()
        while name and (family, name) in self.named and name not in seen:
            seen.add(name)
            st = self.named[(family, name)]
            chain.append(st)
            name = st.get(q("style:parent-style-name"))
        out = {}
        d = self.defaults.get(family)
        if d is not None:
            el = d.find(q(kind))
            if el is not None:
                out.update(el.attrib)
        for st in reversed(chain):
            el = st.find(q(kind))
            if el is not None:
                out.update(el.attrib)
            if kind == "style:text-properties":
                # LibreOffice a volte mette le proprietà del testo in loext
                for sub in st:
                    if sub.tag.endswith("}text-properties") and sub is not el:
                        out.update(sub.attrib)
        return out

    def font_family(self, tp: dict) -> str | None:
        name = tp.get(q("style:font-name"))
        if name and name in self.fonts:
            return self.fonts[name]
        fam = tp.get(q("fo:font-family"))
        return fam.strip("'\"") if fam else None


# ----------------------------------------------------------------- testo
def _css(tp: dict, styles: Styles) -> str:
    out = []
    fam = styles.font_family(tp)
    if fam:
        out.append(f"font-family:'{fam}'")
    size = tp.get(q("fo:font-size"))
    if size and not size.endswith("%"):
        out.append(f"font-size:{pt(size, 12):.2f}pt")
    color = tp.get(q("fo:color"))
    if color:
        out.append(f"color:{color}")
    if tp.get(q("fo:font-weight")) in ("bold", "600", "700", "800", "900"):
        out.append("font-weight:700")
    if tp.get(q("fo:font-style")) == "italic":
        out.append("font-style:italic")
    if tp.get(q("style:text-underline-style"), "none") != "none":
        out.append("text-decoration:underline")
    bg = tp.get(q("fo:background-color"))
    if bg and bg != "transparent":
        out.append(f"background-color:{bg}")
    return ";".join(out)


def _runs(el, tp: dict, styles: Styles) -> str:
    out = []

    def text(t, props):
        if t:
            out.append(f'<span style="{_css(props, styles)}">{html.escape(t)}</span>')

    text(el.text, tp)
    for ch in el:
        tag = ch.tag
        if tag == q("text:span"):
            sub = dict(tp)
            sub.update(styles.props("text", ch.get(q("text:style-name")), "style:text-properties"))
            out.append(_runs(ch, sub, styles))
        elif tag == q("text:s"):
            out.append("&nbsp;" * int(ch.get(q("text:c"), "1")))
        elif tag == q("text:tab"):
            out.append("&nbsp;" * 4)
        elif tag == q("text:line-break"):
            out.append("<br />")
        else:
            out.append(_runs(ch, tp, styles))
        text(ch.tail, tp)
    return "".join(out)


_ALIGN = {"start": "left", "left": "left", "center": "center", "end": "right",
          "right": "right", "justify": "justify"}


def _paragraphs(container, base_tp: dict, base_pp: dict, styles: Styles, bullet="") -> list[str]:
    out = []
    for el in container:
        if el.tag in (q("text:p"), q("text:h")):
            sname = el.get(q("text:style-name"))
            pp = dict(base_pp)
            pp.update(styles.props("paragraph", sname, "style:paragraph-properties"))
            tp = dict(base_tp)
            tp.update(styles.props("paragraph", sname, "style:text-properties"))
            align = _ALIGN.get(pp.get(q("fo:text-align"), "start"), "left")
            mb = pt(pp.get(q("fo:margin-bottom")), 0.0)
            mt = pt(pp.get(q("fo:margin-top")), 0.0)
            inner = _runs(el, tp, styles)
            if bullet:
                inner = f'<span style="{_css(tp, styles)}">{bullet}&nbsp;</span>' + inner
            if not re.sub(r"<[^>]+>", "", inner).strip():
                inner = f'<span style="{_css(tp, styles)}">&nbsp;</span>'
            out.append(f'<p align="{align}" style="margin-top:{mt:.1f}pt;'
                       f'margin-bottom:{mb:.1f}pt">{inner}</p>')
        elif el.tag == q("text:list"):
            for item in el:
                out += _paragraphs(item, base_tp, base_pp, styles, bullet="•")
        elif el.tag == q("table:table"):
            out.append(_table(el, base_tp, base_pp, styles))
    return out


def _table(el, tp, pp, styles) -> str:
    rows = []
    for row in el.iter(q("table:table-row")):
        cells = []
        for cell in row:
            if cell.tag != q("table:table-cell"):
                continue
            cp = styles.props("table-cell", cell.get(q("table:style-name")), "style:table-cell-properties")
            bg = cp.get(q("fo:background-color"))
            attr = f' bgcolor="{bg}"' if bg and bg != "transparent" else ""
            span = cell.get(q("table:number-columns-spanned"))
            if span:
                attr += f' colspan="{span}"'
            cells.append(f"<td{attr}>{''.join(_paragraphs(cell, tp, pp, styles))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return ('<table width="100%" border="1" cellspacing="0" cellpadding="4" '
            'style="border-collapse:collapse;border-color:#7a8696">' + "".join(rows) + "</table>")


# ------------------------------------------------------------ geometria
def _geometry(el):
    """(x, y, w, h, rotazione) in mm e gradi Charta (orari)."""
    w = mm(el.get(q("svg:width")), 0.0)
    h = mm(el.get(q("svg:height")), 0.0)
    tr = el.get(q("draw:transform"))
    if not tr:
        return mm(el.get(q("svg:x")), 0.0), mm(el.get(q("svg:y")), 0.0), w, h, 0.0
    rot, tx, ty = 0.0, mm(el.get(q("svg:x")), 0.0), mm(el.get(q("svg:y")), 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", tr):
        parts = args.replace(",", " ").split()
        if name == "rotate" and parts:
            rot = float(parts[0])
        elif name == "translate" and parts:
            tx = mm(parts[0], 0.0)
            ty = mm(parts[1], 0.0) if len(parts) > 1 else 0.0
    deg = -math.degrees(rot)  # ODF: antiorario in radianti; Charta: orario in gradi
    c = QTransform().rotate(deg).map(QPointF(w / 2, h / 2))
    cx, cy = tx + c.x(), ty + c.y()
    return cx - w / 2, cy - h / 2, w, h, round(deg, 4)


def _base(x, y, w, h, rot, opacity=1.0):
    return {"id": new_uid(), "x": round(x, 3), "y": round(y, 3), "w": round(max(w, 0.5), 3),
            "h": round(max(h, 0.5), 3), "rotation": rot, "opacity": opacity, "locked": False}


# ----------------------------------------------------------------- tracciati
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_svg_path(d: str) -> list:
    """Comandi SVG → comandi assoluti M/L/C/Q/Z (archi approssimati con linee)."""
    toks = _TOKEN.findall(d or "")
    out, i, cmd = [], 0, None
    x = y = sx = sy = 0.0
    last_c = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                out.append(["Z"])
                x, y = sx, sy
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        try:
            if c == "M":
                nx, ny = num(), num()
                x, y = (x + nx, y + ny) if rel else (nx, ny)
                sx, sy = x, y
                out.append(["M", x, y])
                cmd = "l" if rel else "L"
            elif c == "L":
                nx, ny = num(), num()
                x, y = (x + nx, y + ny) if rel else (nx, ny)
                out.append(["L", x, y])
            elif c == "H":
                nx = num()
                x = x + nx if rel else nx
                out.append(["L", x, y])
            elif c == "V":
                ny = num()
                y = y + ny if rel else ny
                out.append(["L", x, y])
            elif c == "C":
                v = [num() for _ in range(6)]
                if rel:
                    v = [v[k] + (x if k % 2 == 0 else y) for k in range(6)]
                out.append(["C"] + v)
                last_c = (v[2], v[3])
                x, y = v[4], v[5]
            elif c == "S":
                v = [num() for _ in range(4)]
                if rel:
                    v = [v[k] + (x if k % 2 == 0 else y) for k in range(4)]
                c1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
                out.append(["C", c1[0], c1[1]] + v)
                last_c = (v[0], v[1])
                x, y = v[2], v[3]
            elif c == "Q":
                v = [num() for _ in range(4)]
                if rel:
                    v = [v[k] + (x if k % 2 == 0 else y) for k in range(4)]
                out.append(["Q"] + v)
                x, y = v[2], v[3]
            elif c == "T":
                nx, ny = num(), num()
                x, y = (x + nx, y + ny) if rel else (nx, ny)
                out.append(["L", x, y])
            elif c == "A":
                v = [num() for _ in range(7)]
                nx, ny = (x + v[5], y + v[6]) if rel else (v[5], v[6])
                x, y = nx, ny
                out.append(["L", x, y])
            else:
                i += 1
        except (IndexError, ValueError):
            break
        if c not in "CS":
            last_c = None
    return out


def _normalize(cmds, vb):
    vx, vy, vw, vh = vb
    vw = vw or 1
    vh = vh or 1
    out = []
    for c in cmds:
        v = c[1:]
        out.append([c[0]] + [((v[k] - vx) / vw if k % 2 == 0 else (v[k] - vy) / vh)
                             for k in range(len(v))])
    return out


def _viewbox(el, w_mm, h_mm):
    vb = el.get(q("svg:viewBox"))
    if vb:
        try:
            a = [float(t) for t in vb.replace(",", " ").split()]
            if len(a) == 4:
                return a
        except ValueError:
            pass
    return [0, 0, w_mm * 100, h_mm * 100]


# ------------------------------------------------------------------ importa
class OdgImporter:
    def __init__(self, files: dict, content: ET.Element, styles_root: ET.Element | None):
        self.files = files  # nome nel pacchetto -> byte (Pictures/...)
        self.content = content
        self.styles = Styles([r for r in (styles_root, content) if r is not None])
        self.doc = Document()
        self.skipped = 0
        self.missing_images = 0

    # proprietà grafiche di un elemento
    def _gp(self, el) -> dict:
        return self.styles.props("graphic", el.get(q("draw:style-name")), "style:graphic-properties")

    def _fill_stroke(self, gp: dict, is_frame: bool):
        fill_mode = gp.get(q("draw:fill"), "none" if is_frame else "solid")
        fill = None
        if fill_mode in ("solid", "gradient", "hatch", "bitmap"):
            fill = gp.get(q("draw:fill-color"), "#729fcf" if not is_frame else None)
        stroke_mode = gp.get(q("draw:stroke"), "none" if is_frame else "solid")
        stroke, sw = None, 1.0
        if stroke_mode != "none":
            stroke = gp.get(q("svg:stroke-color"), "#000000")
            sw = pt(gp.get(q("svg:stroke-width")), 0.0) or 0.5
        op = percent(gp.get(q("draw:opacity")), 1.0)
        return fill, stroke, round(sw, 3), op

    def _text_defaults(self, el):
        sname = el.get(q("draw:style-name"))
        tp = self.styles.props("graphic", sname, "style:text-properties")
        pp = self.styles.props("graphic", sname, "style:paragraph-properties")
        tsn = el.get(q("draw:text-style-name"))
        if tsn:
            tp.update(self.styles.props("paragraph", tsn, "style:text-properties"))
            pp.update(self.styles.props("paragraph", tsn, "style:paragraph-properties"))
        return tp, pp

    def _text_item(self, el, container, geom, gp, fill=None, stroke=None, sw=1.0,
                   valign_default="top", align_default=None):
        tp, pp = self._text_defaults(el)
        if align_default and q("fo:text-align") not in pp:
            pp[q("fo:text-align")] = align_default
        paras = _paragraphs(container, tp, pp, self.styles)
        if not paras or not re.sub(r"&nbsp;|<[^>]+>|\s", "", "".join(paras)):
            return None  # LibreOffice aggiunge paragrafi vuoti a ogni forma
        x, y, w, h, rot = geom
        va = {"top": "top", "middle": "middle", "center": "middle", "bottom": "bottom"}.get(
            gp.get(q("draw:textarea-vertical-align"), valign_default), valign_default)
        pad = mm(gp.get(q("fo:padding-left")), None)
        if pad is None:
            pad = mm(gp.get(q("fo:padding")), 1.25)
        h = max(h, mm(gp.get(q("fo:min-height")), 0.0) or 0.0)
        d = _base(x, y, w, h, rot)
        d.update({"type": "text", "html": "<html><body>" + "".join(paras) + "</body></html>",
                  "fill": fill, "stroke": stroke, "stroke_width": sw,
                  "padding": round(pad, 3), "valign": va, "next": None, "continues": False})
        return d

    def _image(self, frame, img_el, geom):
        data, ext = None, "png"
        for cand in [img_el] + [e for e in frame if e.tag == q("draw:image") and e is not img_el]:
            href = cand.get(q("xlink:href"))
            raw, e = None, None
            if href and href in self.files:
                raw, e = self.files[href], os.path.splitext(href)[1].lstrip(".") or "png"
            else:
                bin_el = cand.find(q("office:binary-data"))
                if bin_el is not None and bin_el.text:
                    raw, e = base64.b64decode(bin_el.text), "png"
            if raw is not None:
                img = QImage.fromData(raw)
                if not img.isNull():
                    data, ext = raw, e.lower()
                    if ext not in ("png", "jpg", "jpeg", "gif", "bmp", "webp"):
                        data, ext = _to_png(img), "png"
                    break
        x, y, w, h, rot = geom
        d = _base(x, y, w, h, rot)
        d.update({"type": "image", "fit": "stretch", "stroke": None, "stroke_width": 1.0,
                  "asset": self.doc.add_asset(data, ext) if data else None})
        if data is None:
            self.missing_images += 1
        return d

    def _shape(self, el, kind, geom, extra=None):
        gp = self._gp(el)
        fill, stroke, sw, op = self._fill_stroke(gp, False)
        x, y, w, h, rot = geom
        d = _base(x, y, w, h, rot, op)
        d.update({"type": "shape", "shape": kind, "fill": fill, "stroke": stroke,
                  "stroke_width": sw, "radius": 0.0})
        if extra:
            d.update(extra)
        return d

    def _shape_text(self, el, geom):
        """Testo scritto dentro una forma: diventa una cornice sopra la forma."""
        if el.find(q("text:p")) is None and el.find(q("text:list")) is None:
            return None
        gp = self._gp(el)
        return self._text_item(el, el, geom, gp, valign_default="middle", align_default="center")

    def convert(self, el, out: list):
        tag = el.tag
        if tag == q("draw:g"):
            for ch in el:
                self.convert(ch, out)
            return
        if tag == q("draw:frame"):
            geom = _geometry(el)
            tb = el.find(q("draw:text-box"))
            img = el.find(q("draw:image"))
            if tb is not None:
                gp = self._gp(el)
                fill, stroke, sw, _ = self._fill_stroke(gp, True)
                d = self._text_item(el, tb, geom, gp, fill, stroke, sw)
                if d:
                    out.append(d)
            elif img is not None:
                out.append(self._image(el, img, geom))
            else:
                self.skipped += 1
            return
        if tag in (q("draw:rect"), q("draw:ellipse"), q("draw:circle"), q("draw:custom-shape"),
                   q("draw:path"), q("draw:polygon"), q("draw:polyline")):
            geom = _geometry(el)
            if tag == q("draw:rect"):
                d = self._shape(el, "rect", geom, {"radius": round(mm(el.get(q("draw:corner-radius")), 0.0), 3)})
            elif tag in (q("draw:ellipse"), q("draw:circle")):
                d = self._shape(el, "ellipse", geom)
            elif tag == q("draw:custom-shape"):
                eg = el.find(q("draw:enhanced-geometry"))
                t = eg.get(q("draw:type"), "rectangle") if eg is not None else "rectangle"
                if "ellipse" in t or t == "circle":
                    d = self._shape(el, "ellipse", geom)
                elif "round" in t:
                    d = self._shape(el, "rect", geom, {"radius": round(min(geom[2], geom[3]) * 0.16, 3)})
                else:
                    d = self._shape(el, "rect", geom)
            elif tag == q("draw:path"):
                cmds = parse_svg_path(el.get(q("svg:d")))
                d = self._shape(el, "path", geom, {"path": _normalize(cmds, _viewbox(el, geom[2], geom[3]))})
            else:
                pts = [float(v) for v in re.split(r"[ ,]+", (el.get(q("draw:points")) or "").strip()) if v]
                cmds = []
                for k in range(0, len(pts) - 1, 2):
                    cmds.append(["M" if k == 0 else "L", pts[k], pts[k + 1]])
                if tag == q("draw:polygon"):
                    cmds.append(["Z"])
                extra = {"path": _normalize(cmds, _viewbox(el, geom[2], geom[3]))}
                d = self._shape(el, "path", geom, extra)
                if tag == q("draw:polyline"):
                    d["fill"] = None
            out.append(d)
            t = self._shape_text(el, geom)
            if t:
                out.append(t)
            return
        if tag in (q("draw:line"), q("draw:connector")):
            x1, y1 = mm(el.get(q("svg:x1")), 0.0), mm(el.get(q("svg:y1")), 0.0)
            x2, y2 = mm(el.get(q("svg:x2")), 0.0), mm(el.get(q("svg:y2")), 0.0)
            length = math.hypot(x2 - x1, y2 - y1)
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            hh = 2.8
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            gp = self._gp(el)
            _, stroke, sw, op = self._fill_stroke(gp, False)
            d = _base(cx - length / 2, cy - hh / 2, length, hh, round(ang, 4), op)
            d.update({"type": "shape", "shape": "line", "fill": None,
                      "stroke": stroke or "#000000", "stroke_width": sw, "radius": 0.0})
            out.append(d)
            return
        if tag.startswith("{%s}" % NS["draw"]):
            self.skipped += 1

    def _page_background(self, page_el) -> str:
        for name in (page_el.get(q("draw:style-name")),):
            dp = self.styles.props("drawing-page", name, "style:drawing-page-properties")
            if dp.get(q("draw:fill")) == "solid" and dp.get(q("draw:fill-color")):
                return dp[q("draw:fill-color")]
        mp = self.styles.masters.get(page_el.get(q("draw:master-page-name")))
        if mp is not None:
            dp = self.styles.props("drawing-page", mp.get(q("draw:style-name")), "style:drawing-page-properties")
            if dp.get(q("draw:fill")) == "solid" and dp.get(q("draw:fill-color")):
                return dp[q("draw:fill-color")]
        return "#ffffff"

    def run(self, title: str) -> Document:
        pages = []
        for page_el in self.content.iter(q("draw:page")):
            mp = self.styles.masters.get(page_el.get(q("draw:master-page-name")))
            layout = self.styles.layouts.get(mp.get(q("style:page-layout-name"))) if mp is not None else None
            layout = layout or {}
            w = mm(layout.get(q("fo:page-width")), 210.0)
            h = mm(layout.get(q("fo:page-height")), 297.0)
            margins = [mm(layout.get(q(f"fo:margin-{s}")), 10.0) or 0.0
                       for s in ("top", "right", "bottom", "left")]
            items = []
            # gli oggetti della pagina mastro (sfondi ripetuti) vanno sotto
            if mp is not None:
                for ch in mp:
                    if ch.get(q("presentation:class")) is None:
                        self.convert(ch, items)
            for ch in page_el:
                self.convert(ch, items)
            pages.append({"width": round(w, 3), "height": round(h, 3),
                          "margins": [round(m, 3) for m in margins],
                          "background": self._page_background(page_el),
                          "guides": {"x": [], "y": []}, "items": items})
        if not pages:
            raise ImportError_(tr("Il file non contiene pagine."))
        self.doc.set_state({"version": FORMAT_VERSION, "title": title, "pages": pages})
        return self.doc



def _to_png(img: QImage) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def import_odg(path: str) -> tuple[Document, dict]:
    """Legge un .odg (zip) o .fodg (XML unico). Restituisce il documento e un
    riepilogo di ciò che non è stato possibile convertire."""
    title = os.path.splitext(os.path.basename(path))[0]
    try:
        if path.lower().endswith(".fodg"):
            root = ET.parse(path).getroot()
            imp = OdgImporter({}, root, None)
        else:
            with zipfile.ZipFile(path) as z:
                files = {n: z.read(n) for n in z.namelist() if n.startswith("Pictures/")}
                content = ET.fromstring(z.read("content.xml"))
                styles = ET.fromstring(z.read("styles.xml")) if "styles.xml" in z.namelist() else None
            imp = OdgImporter(files, content, styles)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as e:
        raise ImportError_(tr("File non leggibile: {err}").format(err=e)) from e
    doc = imp.run(title)
    return doc, {"skipped": imp.skipped, "missing_images": imp.missing_images}
