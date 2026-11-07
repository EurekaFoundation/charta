"""Tabelle dentro le cornici di testo (QTextTable): si scrivono come il
testo normale e restano modificabili, anche nella stampa unione."""

from __future__ import annotations

from charta.i18n import tr
from PySide6.QtGui import (QBrush, QColor, QFont, QTextCharFormat, QTextCursor,
                           QTextFrameFormat, QTextLength, QTextTable, QTextTableFormat)

HEADER_BG = QColor("#e8eef7")


def table_format(cols: int, border_color: QColor = QColor("#7a8696"),
                 border: float = 0.75, padding: float = 4.0) -> QTextTableFormat:
    fmt = QTextTableFormat()
    fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
    fmt.setBorder(border)
    fmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
    fmt.setBorderBrush(QBrush(border_color))
    fmt.setCellPadding(padding)
    fmt.setCellSpacing(0)
    fmt.setBorderCollapse(False)  # con True Qt 6 non disegna i bordi interni
    fmt.setColumnWidthConstraints([QTextLength(QTextLength.PercentageLength, 100 / cols)] * cols)
    return fmt


def insert_table(cursor: QTextCursor, rows: int, cols: int, header: bool = True,
                 labels: bool = True) -> QTextTable:
    fmt = table_format(cols)
    table = cursor.insertTable(rows, cols, fmt)
    table.setFormat(fmt)  # insertTable non applica stile e colore dei bordi
    if header:
        for c in range(cols):
            cell = table.cellAt(0, c)
            cf = cell.format()
            cf.setBackground(HEADER_BG)
            cell.setFormat(cf)
            cur = cell.firstCursorPosition()
            bold = QTextCharFormat()
            bold.setFontWeight(QFont.Bold)
            cur.mergeBlockCharFormat(bold)
            cur.setCharFormat(cur.blockCharFormat())
            if labels:
                cur.insertText(tr("Colonna {n}").format(n=c + 1))
    return table


def tables(doc) -> list[QTextTable]:
    out = []
    for fr in doc.rootFrame().childFrames():
        if isinstance(fr, QTextTable):
            out.append(fr)
    return out


def current_table(frame):
    """(tabella, riga, colonna, cursore) dove sta scrivendo l'utente; se non
    sta scrivendo dentro una tabella, l'ultima cella della prima tabella."""
    if frame.editing:
        c = frame.text.textCursor()
        t = c.currentTable()
        if t is not None:
            cell = t.cellAt(c)
            return t, cell.row(), cell.column(), c
    ts = tables(frame.text.document())
    if not ts:
        return None
    t = ts[0]
    return t, t.rows() - 1, t.columns() - 1, None


def _fix_widths(t: QTextTable):
    fmt = t.format()
    n = t.columns()
    fmt.setColumnWidthConstraints([QTextLength(QTextLength.PercentageLength, 100 / n)] * n)
    t.setFormat(fmt)


def insert_row(frame, below: bool = True):
    info = current_table(frame)
    if info:
        t, r, _, _ = info
        t.insertRows(r + 1 if below else r, 1)


def insert_column(frame, right: bool = True):
    info = current_table(frame)
    if info:
        t, _, c, _ = info
        t.insertColumns(c + 1 if right else c, 1)
        _fix_widths(t)


def remove_row(frame):
    info = current_table(frame)
    if info and info[0].rows() > 1:
        info[0].removeRows(info[1], 1)


def remove_column(frame):
    info = current_table(frame)
    if info and info[0].columns() > 1:
        info[0].removeColumns(info[2], 1)
        _fix_widths(info[0])


def merge_cells(frame):
    info = current_table(frame)
    if info and info[3] is not None and info[3].hasSelection():
        info[0].mergeCells(info[3])


def split_cell(frame):
    info = current_table(frame)
    if info:
        t, r, c, _ = info
        t.splitCell(r, c, 1, 1)


def set_cell_background(frame, color: QColor):
    info = current_table(frame)
    if not info:
        return
    t, r, c, cur = info
    cells = []
    if cur is not None and cur.hasSelection():
        r0, nr, c0, nc = cur.selectedTableCells()
        if nr > 0:
            cells = [(rr, cc) for rr in range(r0, r0 + nr) for cc in range(c0, c0 + nc)]
    if not cells:
        cells = [(r, c)]
    for rr, cc in cells:
        cell = t.cellAt(rr, cc)
        cf = cell.format()
        if color.alpha() == 0:
            cf.clearBackground()
        else:
            cf.setBackground(color)
        cell.setFormat(cf)


def set_table_border(frame, color: QColor | None = None, width: float | None = None,
                     padding: float | None = None):
    info = current_table(frame)
    if not info:
        return
    t = info[0]
    fmt = t.format()
    if color is not None:
        fmt.setBorderBrush(QBrush(color))
    if width is not None:
        fmt.setBorder(width)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid if width > 0
                           else QTextFrameFormat.BorderStyle_None)
    if padding is not None:
        fmt.setCellPadding(padding)
    t.setFormat(fmt)
