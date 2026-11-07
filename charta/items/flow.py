"""Testo che scorre tra cornici collegate (come le "caselle di testo
collegate" di Publisher).

Ogni cornice della catena contiene solo la propria parte di testo, quindi si
può scrivere in qualunque cornice. Dopo ogni modifica la catena viene
"ricucita": i testi vengono riuniti in un'unica storia e redistribuiti
riempiendo le cornici nell'ordine del collegamento. Il flag `continues` dice
se la parte di una cornice prosegue l'ultimo paragrafo della precedente.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment

_busy = False
_pending: set = set()


# ------------------------------------------------------------------ catena
def chain(frame) -> list:
    """Tutte le cornici della catena di `frame`, dalla prima all'ultima."""
    head, seen = frame, {frame}
    while head.prev is not None and head.prev not in seen:
        head = head.prev
        seen.add(head)
    out, f, seen = [], head, set()
    while f is not None and f not in seen:
        out.append(f)
        seen.add(f)
        f = f.next
    return out


def is_chained(frame) -> bool:
    return frame.prev is not None or frame.next is not None


def _empty(doc: QTextDocument) -> bool:
    return doc.characterCount() <= 1


def _set_content(dst: QTextDocument, src: QTextDocument | None):
    dst.clear()
    if src is None or _empty(src):
        return
    c = QTextCursor(dst)
    c.setBlockFormat(src.begin().blockFormat())
    c.setBlockCharFormat(src.begin().charFormat())
    c.insertFragment(QTextDocumentFragment(src))


# ------------------------------------------------------------- riunisci
def merge_story(frames) -> tuple[QTextDocument, list[int]]:
    """Riunisce i testi della catena; restituisce la storia e, per ogni
    cornice, la posizione da cui inizia il suo testo nella storia."""
    story = frames[0].text.document().clone()
    offsets = [0]
    cur = QTextCursor(story)
    for f in frames[1:]:
        d = f.text.document()
        cur.movePosition(QTextCursor.End)
        if _empty(d):
            offsets.append(cur.position())
            continue
        if _empty(story):
            cur.setBlockFormat(d.begin().blockFormat())
        elif not f.continues:
            cur.insertBlock(d.begin().blockFormat(), d.begin().charFormat())
        offsets.append(cur.position())
        cur.insertFragment(QTextDocumentFragment(d))
    return story, offsets


# ------------------------------------------------------------ distribuisci
def split_position(frame) -> int | None:
    """Posizione del primo carattere che non entra nella cornice (None se
    entra tutto). Non spezza mai una tabella."""
    doc = frame.text.document()
    doc.documentLayout().documentSize()  # forza l'impaginazione
    avail = frame.height() - 2 * frame.padding
    block = doc.begin()
    pos = None
    while block.isValid() and pos is None:
        bl = block.layout()
        for i in range(bl.lineCount()):
            line = bl.lineAt(i)
            if bl.position().y() + line.y() + line.height() > avail + 0.5:
                pos = block.position() + line.textStart()
                break
        block = block.next()
    if pos is None:
        return None
    c = QTextCursor(doc)
    c.setPosition(pos)
    table = c.currentTable()
    if table is not None:
        pos = max(0, table.firstPosition() - 1)
    return pos


def distribute(frames, story: QTextDocument) -> list[int]:
    """Riempie le cornici con la storia; restituisce l'inizio di ciascuna."""
    remaining = story
    starts, start, cont = [], 0, False
    for i, f in enumerate(frames):
        d = f.text.document()
        _set_content(d, remaining)
        f.continues = cont if i > 0 else False
        starts.append(start)
        f.text.setTextWidth(max(1.0, f.width() - 2 * f.padding))
        if i == len(frames) - 1 or remaining is None:
            remaining = None
            continue
        p = split_position(f)
        if p is None:
            remaining = None
            continue
        c = QTextCursor(d)
        c.setPosition(p)
        block = c.block()
        at_block_start = p == block.position()
        bf, cf = block.blockFormat(), block.charFormat()
        c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        frag = c.selection()
        c.removeSelectedText()
        if at_block_start and p > 0:
            # il paragrafo successivo inizia nella prossima cornice:
            # togliamo il separatore rimasto in fondo
            e = QTextCursor(d)
            e.movePosition(QTextCursor.End)
            e.deletePreviousChar()
        nxt = QTextDocument()
        nxt.setDefaultFont(d.defaultFont())
        nc = QTextCursor(nxt)
        nc.setBlockFormat(bf)
        nc.setBlockCharFormat(cf)
        nc.insertFragment(frag)
        remaining = nxt
        cont = (not at_block_start) if p > 0 else f.continues
        start += p
    return starts


# ----------------------------------------------------------------- riflusso
def reflow(frame):
    """Ricalcola la distribuzione del testo in tutta la catena di `frame`,
    mantenendo il cursore di chi sta scrivendo."""
    global _busy
    if _busy:
        return
    frames = chain(frame)
    if len(frames) < 2:
        frames[0].layout_text()
        return
    _busy = True
    try:
        editing = next((f for f in frames if f.editing), None)
        story_pos = None
        story, offsets = merge_story(frames)
        if editing is not None:
            story_pos = offsets[frames.index(editing)] + editing.text.textCursor().position()
        starts = distribute(frames, story)
        for f in frames:
            f.text.document().setUndoRedoEnabled(False)
            f.layout_text()
        if story_pos is not None:
            target = frames[-1]
            for j, f in enumerate(frames):
                if story_pos <= starts[j] + f.text.document().characterCount() - 1:
                    target = f
                    break
            local = story_pos - starts[frames.index(target)]
            local = max(0, min(local, target.text.document().characterCount() - 1))
            if target is not editing:
                editing.end_edit(notify=False)
                target.start_edit()
            c = target.text.textCursor()
            c.setPosition(local)
            target.text.setTextCursor(c)
    finally:
        _busy = False


def schedule_reflow(frame):
    """Riflusso al prossimo giro del ciclo eventi (mai dentro un segnale
    del documento che stiamo modificando)."""
    if _busy:
        return
    head = chain(frame)[0]
    if head in _pending:
        return
    _pending.add(head)

    def run():
        _pending.discard(head)
        if head.scene() is not None:
            reflow(head)
    QTimer.singleShot(0, run)


# --------------------------------------------------------- collegamenti
def can_link(a, b) -> bool:
    return (a is not b and a.next is None and b.prev is None
            and b not in chain(a))


def link(a, b):
    """Collega la cornice `b` (e l'eventuale catena che inizia da b) dopo `a`."""
    if not can_link(a, b):
        return False
    a.next = b
    b.prev = a
    b.continues = False
    for f in chain(a):
        f.text.document().setUndoRedoEnabled(False)
    reflow(a)
    return True


def unlink_after(a):
    """Interrompe la catena dopo `a`: il testo delle cornici successive torna
    nelle cornici precedenti (se non entra, `a` mostra il segnale rosso)."""
    b = a.next
    if b is None:
        return
    frames = chain(a)
    story, _ = merge_story(frames)
    keep = frames[:frames.index(a) + 1]
    rest = frames[frames.index(a) + 1:]
    a.next = None
    b.prev = None
    global _busy
    _busy = True
    try:
        for f in rest:
            _set_content(f.text.document(), None)
            f.continues = False
            f.layout_text()
        if len(keep) == 1:
            _set_content(a.text.document(), story)
            a.layout_text()
    finally:
        _busy = False
    if len(keep) > 1:
        _busy = True
        try:
            distribute(keep, story)
            for f in keep:
                f.layout_text()
        finally:
            _busy = False
    for f in rest:
        f.text.document().setUndoRedoEnabled(not is_chained(f))
    a.text.document().setUndoRedoEnabled(not is_chained(a))


def remove_from_chain(f):
    """Toglie `f` dalla catena (per esempio prima di eliminarlo) senza
    perdere il testo: le cornici rimaste si ricuciono tra loro."""
    if not is_chained(f):
        return
    global _busy
    frames = chain(f)
    story, _ = merge_story(frames)
    p, n = f.prev, f.next
    if p is not None:
        p.next = n
    if n is not None:
        n.prev = p
    f.prev = f.next = None
    rest = [x for x in frames if x is not f]
    _busy = True
    try:
        _set_content(f.text.document(), None)
        if len(rest) == 1:
            _set_content(rest[0].text.document(), story)
            rest[0].continues = False
            rest[0].layout_text()
        elif rest:
            distribute(rest, story)
            for x in rest:
                x.layout_text()
    finally:
        _busy = False


def resolve_links(frames):
    """Dopo il caricamento: trasforma gli id salvati in collegamenti veri e
    ricalcola le catene. `frames` può comprendere più pagine."""
    from charta.items.text import TextFrame
    texts = [f for f in frames if isinstance(f, TextFrame)]
    by_id = {f.uid: f for f in texts}
    for f in texts:
        f.next = f.prev = None
    for f in texts:
        n = by_id.get(getattr(f, "_next_id", None))
        if n is not None and can_link(f, n):
            f.next = n
            n.prev = f
            f.text.document().setUndoRedoEnabled(False)
            n.text.document().setUndoRedoEnabled(False)
    heads = [f for f in texts if f.prev is None and f.next is not None]
    for h in heads:
        if len(chain(h)) > 1:
            reflow(h)
