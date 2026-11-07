"""Stampa unione: un documento con campi {{nome}} viene ripetuto per ogni riga
di un foglio CSV o Excel (attestati, badge, inviti, cartellini...)."""

from __future__ import annotations

from charta.i18n import tr
import copy
import csv
import datetime as _dt
import html
import os
import re

FIELD_RE = re.compile(r"\{\{\s*([^{}<>]+?)\s*\}\}")
# nell'HTML un campo può essere spezzato da tag di formattazione: {{no<span>me}}
FIELD_HTML_RE = re.compile(r"\{\{((?:<[^>]*>|[^{}<])*?)\}\}")
TAG_RE = re.compile(r"<[^>]+>")


class DataError(Exception):
    pass


# ------------------------------------------------------------- lettura dati
def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, _dt.datetime):
        return v.strftime("%d/%m/%Y") if (v.hour, v.minute) == (0, 0) else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, _dt.date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _read_csv(path: str):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = list(csv.reader(text.splitlines(), dialect))
    return rows


def _read_xlsx(path: str):
    try:
        import openpyxl
    except ImportError as e:
        raise DataError(tr("Per leggere i file Excel serve il pacchetto 'openpyxl'.")) from e
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def read_table(path: str) -> tuple[list[str], list[dict]]:
    """Intestazioni e righe (come dizionari) dal primo foglio del file."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            rows = _read_xlsx(path)
        elif ext in (".csv", ".txt", ".tsv"):
            rows = _read_csv(path)
        else:
            raise DataError(tr("Formato non supportato: usa un file .csv o .xlsx."))
    except OSError as e:
        raise DataError(str(e)) from e
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        raise DataError(tr("Il file non contiene dati."))
    headers = []
    for i, h in enumerate(rows[0]):
        h = str(h).strip() or tr("Colonna{n}").format(n=i + 1)
        while h in headers:
            h += "_"
        headers.append(h)
    records = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(headers) - len(r))
        records.append({h: _cell(v) for h, v in zip(headers, r)})
    return headers, records


# ------------------------------------------------------------ sostituzione
def _walk_text_items(items):
    for it in items:
        if it.get("type") == "text":
            yield it
        yield from _walk_text_items(it.get("items", []))


def fields_in_state(state: dict) -> list[str]:
    found = []
    for page in state["pages"]:
        for it in _walk_text_items(page["items"]):
            for m in FIELD_RE.finditer(html.unescape(re.sub(r"<[^>]+>", "", it.get("html", "")))):
                if m.group(1) not in found:
                    found.append(m.group(1))
    return found


def _lookup(record: dict, name: str):
    if name in record:
        return record[name]
    low = name.casefold()
    for k, v in record.items():
        if k.casefold() == low:
            return v
    return None


def apply_record(state: dict, record: dict) -> dict:
    """Copia dello stato con i campi sostituiti dai valori della riga.
    I campi senza colonna corrispondente restano visibili, così si notano."""
    st = copy.deepcopy(state)

    def sub(m):
        name = html.unescape(TAG_RE.sub("", m.group(1))).strip()
        v = _lookup(record, name)
        if v is None:
            return m.group(0)
        return html.escape(str(v)).replace("\n", "<br />")
    for page in st["pages"]:
        for it in _walk_text_items(page["items"]):
            it["html"] = FIELD_HTML_RE.sub(sub, it.get("html", ""))
    return st


def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s).strip(" ._")
    return s[:80] or "documento"


# ---------------------------------------------------------------- rendering
def scenes_for_state(state: dict, document) -> list:
    """Pagine pronte da esportare (fuori dalla finestra) per uno stato."""
    from charta.canvas.scene import PageScene
    from charta.document.model import Document
    from charta.items import flow
    doc = Document()
    doc.assets, doc.asset_ext = document.assets, document.asset_ext
    doc.set_state(state)
    scenes = [PageScene(p, doc) for p in doc.pages]
    flow.resolve_links([f for sc in scenes for f in sc.all_frames()])
    return scenes


def iter_merged_scenes(state: dict, document, records):
    for rec in records:
        for sc in scenes_for_state(apply_record(state, rec), document):
            yield sc


def export_merged(state: dict, document, records, path: str, one_file: bool = True,
                  name_field: str | None = None, progress=None, **pdf_opts) -> list[str]:
    """Esporta in PDF: un unico file con tutte le copie, oppure un file per
    ogni riga (nominato con il valore di `name_field`). Restituisce i file."""
    from charta.export.render import export_pdf
    if one_file:
        def gen():
            for i, rec in enumerate(records):
                if progress:
                    progress(i)
                yield from scenes_for_state(apply_record(state, rec), document)
        export_pdf(gen(), path, title=state.get("title", ""), **pdf_opts)
        return [path]
    out_dir = path if os.path.isdir(path) else os.path.dirname(path)
    base = os.path.splitext(os.path.basename(path))[0] if not os.path.isdir(path) else "documento"
    files, used = [], set()
    for i, rec in enumerate(records):
        if progress:
            progress(i)
        name = safe_filename(rec.get(name_field, "") if name_field else "") if name_field else ""
        name = name or f"{base}-{i + 1:03d}"
        while name in used:
            name += "_"
        used.add(name)
        fp = os.path.join(out_dir, name + ".pdf")
        export_pdf(scenes_for_state(apply_record(state, rec), document), fp,
                   title=state.get("title", ""), **pdf_opts)
        files.append(fp)
    return files
