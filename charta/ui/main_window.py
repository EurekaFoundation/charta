"""Finestra principale di Charta."""

from __future__ import annotations

import base64
import copy
import json
import math
import os

from PySide6.QtCore import QBuffer, QByteArray, QLocale, QMimeData, QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QImage, QKeySequence, QTextCursor
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog,
                               QLabel, QMainWindow, QMessageBox, QToolBar)

from charta import APP_NAME, FILE_EXT, __version__, merge
from charta.canvas.ruler import CanvasArea
from charta.canvas.scene import PageScene
from charta.canvas.view import CanvasView
from charta.document.model import CorruptFileError, Document
from charta.export import render
from charta.i18n import LANGUAGES, language, tr
from charta.items import GroupFrame, ImageFrame, ShapeFrame, TextFrame, flow, item_from_dict
from charta.items import table as tables
from charta.items.base import new_uid
from charta.items.group import make_group, ungroup
from charta.ui import icons
from charta.ui.dialogs import (ImageOptionsDialog, MergeDialog, NewDocumentDialog,
                               PdfOptionsDialog, TableDialog)
from charta.ui.pages_panel import PagesPanel
from charta.ui.properties import PropertiesPanel
from charta.units import mm2pt, pt2mm

MIME_ITEMS = "application/x-charta-items"
MAX_RECENT = 8


def image_filter() -> str:
    return tr("Immagini") + " (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff)"


def file_filter() -> str:
    return tr("Documenti Charta") + f" (*{FILE_EXT})"


def renew_ids(items: list[dict]) -> list[dict]:
    """Copia degli oggetti con id nuovi; i collegamenti tra cornici copiate
    insieme restano, quelli verso cornici non copiate si perdono."""
    items = copy.deepcopy(items)
    mapping, texts = {}, []

    def walk(lst):
        for d in lst:
            if d.get("id"):
                mapping[d["id"]] = new_uid()
            if d.get("type") == "text":
                texts.append(d)
            walk(d.get("items", []))
    walk(items)

    def renumber(lst):
        for d in lst:
            if d.get("id"):
                d["id"] = mapping[d["id"]]
            renumber(d.get("items", []))
    renumber(items)
    for d in texts:
        d["next"] = mapping.get(d.get("next")) if d.get("next") else None
    targets = {d["next"] for d in texts if d.get("next")}
    for d in texts:
        if d.get("id") not in targets:
            d["continues"] = False
    return items


class History:
    """Annulla/ripeti basato su istantanee del documento (leggere: le
    immagini non sono incluse, solo i riferimenti)."""

    def __init__(self, limit: int = 200):
        self.limit = limit
        self.states: list[str] = []
        self.index = -1

    def reset(self, s: str):
        self.states = [s]
        self.index = 0

    def push(self, s: str) -> bool:
        if self.index >= 0 and self.states[self.index] == s:
            return False
        del self.states[self.index + 1:]
        self.states.append(s)
        if len(self.states) > self.limit:
            self.states.pop(0)
        self.index = len(self.states) - 1
        return True

    def can_undo(self):
        return self.index > 0

    def can_redo(self):
        return self.index < len(self.states) - 1

    def undo(self) -> str:
        self.index -= 1
        return self.states[self.index]

    def redo(self) -> str:
        self.index += 1
        return self.states[self.index]

    def current(self) -> str:
        return self.states[self.index]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings()
        self.doc = Document()
        self.path: str | None = None
        self.scenes: list[PageScene] = []
        self.current = 0
        self.history = History()
        self.saved_state = ""
        self.paste_count = 0
        self.link_source = None
        self.merge_headers: list[str] = []
        self.view_opts = {
            "grid": self.settings.value("view/grid", False, type=bool),
            "snap": self.settings.value("view/snap", True, type=bool),
            "margins": self.settings.value("view/margins", True, type=bool),
            "guides": self.settings.value("view/guides", True, type=bool),
            "rulers": self.settings.value("view/rulers", True, type=bool),
        }

        self.setWindowIcon(icons.app_icon())
        self.view = CanvasView()
        self.area = CanvasArea(self.view)
        self.area.set_rulers_visible(self.view_opts["rulers"])
        self.setCentralWidget(self.area)
        self.view.create_requested.connect(self.create_item)
        self.view.images_dropped.connect(self.drop_images)
        self.view.nudge_done.connect(self.commit_soon)
        self.view.zoom_changed.connect(self._zoom_label)
        self.view.cursor_moved.connect(self._cursor_label)
        self.view.guides_changed.connect(self.commit_soon)
        self.view.link_target.connect(self._link_target)

        self.pages = PagesPanel()
        self.pages.page_selected.connect(self.show_page)
        self.pages.add_page.connect(self.add_page)
        self.pages.duplicate_page.connect(self.duplicate_page)
        self.pages.delete_page.connect(self.delete_page)
        self.pages.move_page.connect(self.move_page)
        dock = QDockWidget(tr("Pagine"))
        dock.setObjectName("dock_pages")
        dock.setWidget(self.pages)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self.props = PropertiesPanel()
        self.props.changed.connect(self.commit_soon)
        self.props.page_changed.connect(self._page_props_changed)
        self.props.apply_page_to_all.connect(self.apply_page_to_all)
        self.props.replace_image.connect(self.pick_image_for)
        self.props.link_requested.connect(self.start_link)
        self.props.unlink_requested.connect(self.unlink)
        self.props.insert_table_requested.connect(self.insert_table_into)
        self.props.group_requested.connect(self.group_selected)
        self.props.ungroup_requested.connect(self.ungroup_selected)
        self.props.insert_field.connect(self.insert_merge_field)
        dock = QDockWidget(tr("Proprietà"))
        dock.setObjectName("dock_props")
        dock.setWidget(self.props)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self.commit_timer = QTimer(self, singleShot=True, interval=250)
        self.commit_timer.timeout.connect(self.commit)
        self.thumb_timer = QTimer(self, singleShot=True, interval=400)
        self.thumb_timer.timeout.connect(self._update_current_thumb)

        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_statusbar()
        self.resize(1360, 860)
        geo = self.settings.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.settings.value("window/state")
        if st is not None:
            self.restoreState(st)
        self.load_document(Document())

    # =================================================================== azioni
    def _act(self, text, slot=None, shortcut=None, tip=None, checkable=False, icon=None):
        a = QAction(text, self)
        if icon is not None:
            a.setIcon(icon)
        if shortcut is not None:
            if isinstance(shortcut, (list, tuple)):
                a.setShortcuts([QKeySequence(s) for s in shortcut])
            else:
                a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
            a.setStatusTip(tip)
        a.setCheckable(checkable)
        if slot is not None:
            a.triggered.connect(slot)
        return a

    def _build_actions(self):
        A = self._act
        self.a_new = A(tr("&Nuovo…"), self.new_document, QKeySequence.New)
        self.a_open = A(tr("&Apri…"), self.open_document, QKeySequence.Open)
        self.a_import = A(tr("&Importa da Publisher o LibreOffice…"), self.import_document, "Ctrl+Shift+O",
                          tr("Apre file .pub di Microsoft Publisher e disegni .odg di LibreOffice"))
        self.a_save = A(tr("&Salva"), self.save, QKeySequence.Save)
        self.a_save_as = A(tr("Salva &con nome…"), self.save_as, QKeySequence.SaveAs)
        self.a_pdf = A(tr("Esporta in &PDF…"), self.export_pdf, "Ctrl+E")
        self.a_img = A(tr("Esporta come &immagine…"), self.export_image, "Ctrl+Shift+E")
        self.a_print = A(tr("S&tampa…"), self.print_doc, QKeySequence.Print)
        self.a_quit = A(tr("&Esci"), self.close, QKeySequence.Quit)

        self.a_undo = A(tr("&Annulla"), self.undo, QKeySequence.Undo)
        self.a_redo = A(tr("&Ripeti"), self.redo, [QKeySequence.Redo, "Ctrl+Y"])
        self.a_cut = A(tr("&Taglia"), self.cut, QKeySequence.Cut)
        self.a_copy = A(tr("&Copia"), self.copy, QKeySequence.Copy)
        self.a_paste = A(tr("&Incolla"), self.paste, QKeySequence.Paste)
        self.a_dup = A(tr("&Duplica"), self.duplicate, "Ctrl+D")
        self.a_del = A(tr("&Elimina"), self.delete_selected, [QKeySequence.Delete, "Backspace"])
        self.a_all = A(tr("Seleziona t&utto"), self.select_all, QKeySequence.SelectAll)

        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        for key, label, icon, sc in (("select", tr("Seleziona"), icons.select_icon(), "V"),
                                     ("text", tr("Testo"), icons.text_icon(), "T"),
                                     ("image", tr("Immagine"), icons.image_icon(), "I"),
                                     ("table", tr("Tabella"), icons.table_icon(), "B"),
                                     ("rect", tr("Rettangolo"), icons.rect_icon(), "R"),
                                     ("ellipse", tr("Ellisse"), icons.ellipse_icon(), "E"),
                                     ("line", tr("Linea"), icons.line_icon(), "L")):
            a = A(label, lambda _=False, k=key: self.set_tool(k), sc,
                  f"{label} ({sc})", True, icon)
            self.tool_group.addAction(a)
            self.tool_actions[key] = a
        self.tool_actions["select"].setChecked(True)

        self.a_zoom_in = A(tr("Ingrandisci"), lambda: self.view.set_zoom(self.view.zoom * 1.25),
                           [QKeySequence.ZoomIn, "Ctrl+="])
        self.a_zoom_out = A(tr("Riduci"), lambda: self.view.set_zoom(self.view.zoom / 1.25), QKeySequence.ZoomOut)
        self.a_zoom_100 = A(tr("Dimensione reale (100%)"), lambda: self.view.set_zoom(1.0), "Ctrl+1")
        self.a_fit = A(tr("Adatta pagina"), self.view.fit_page, "Ctrl+0")
        self.a_fit_w = A(tr("Adatta larghezza"), self.view.fit_width, "Ctrl+2")
        self.a_rulers = A(tr("Righelli"), lambda v: self.set_view_opt("rulers", v), "Ctrl+R", checkable=True)
        self.a_guides = A(tr("Guide"), lambda v: self.set_view_opt("guides", v), "Ctrl+;", checkable=True)
        self.a_clear_guides = A(tr("Elimina tutte le guide della pagina"), self.clear_guides)
        self.a_grid = A(tr("Griglia"), lambda v: self.set_view_opt("grid", v), "Ctrl+'", checkable=True)
        self.a_snap = A(tr("Calamita (aggancia a margini, guide e oggetti)"),
                        lambda v: self.set_view_opt("snap", v), "Ctrl+Shift+;", checkable=True)
        self.a_margins = A(tr("Mostra margini"), lambda v: self.set_view_opt("margins", v), checkable=True)
        for key, a in (("rulers", self.a_rulers), ("guides", self.a_guides), ("grid", self.a_grid),
                       ("snap", self.a_snap), ("margins", self.a_margins)):
            a.setChecked(self.view_opts[key])

        self.a_front = A(tr("Porta in primo piano"), lambda: self.props.bring_front(), "Ctrl+Shift+]")
        self.a_forward = A(tr("Porta avanti"), lambda: self.props.bring_forward(), "Ctrl+]")
        self.a_backward = A(tr("Porta indietro"), lambda: self.props.send_backward(), "Ctrl+[")
        self.a_back = A(tr("Porta sullo sfondo"), lambda: self.props.send_back(), "Ctrl+Shift+[")
        self.a_group = A(tr("Raggruppa"), self.group_selected, "Ctrl+G")
        self.a_ungroup = A(tr("Separa"), self.ungroup_selected, "Ctrl+Shift+G")
        self.a_lock = A(tr("Blocca / sblocca"), self.toggle_lock, "Ctrl+L")
        self.a_link = A(tr("Collega cornice di testo…"), lambda: self.start_link(self._single_text()))
        self.a_unlink = A(tr("Scollega cornice di testo"), lambda: self.unlink(self._single_text()))

        self.a_add_page = A(tr("Aggiungi pagina"), self.add_page)
        self.a_dup_page = A(tr("Duplica pagina"), self.duplicate_page)
        self.a_del_page = A(tr("Elimina pagina"), self.delete_page)
        self.a_insert_table = A(tr("Tabella…"), lambda: self.insert_table_into(self._single_text()))

        self.a_merge_source = A(tr("Scegli il file dei dati…"), self.choose_merge_source)
        self.a_merge = A(tr("Anteprima ed esportazione…"), self.open_merge, "Ctrl+M")

        self.a_about = A(tr("Informazioni su Charta"), self.about)
        self.a_keys = A(tr("Scorciatoie da tastiera"), self.shortcuts_help, "F1")

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu(tr("&File"))
        m.addActions([self.a_new, self.a_open, self.a_import])
        self.recent_menu = m.addMenu(tr("Apri &recenti"))
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        m.addSeparator()
        m.addActions([self.a_save, self.a_save_as])
        m.addSeparator()
        m.addActions([self.a_pdf, self.a_img, self.a_print])
        m.addSeparator()
        m.addAction(self.a_quit)

        m = mb.addMenu(tr("&Modifica"))
        m.addActions([self.a_undo, self.a_redo])
        m.addSeparator()
        m.addActions([self.a_cut, self.a_copy, self.a_paste, self.a_dup, self.a_del])
        m.addSeparator()
        m.addAction(self.a_all)

        m = mb.addMenu(tr("&Inserisci"))
        for k in ("text", "image", "table", "rect", "ellipse", "line"):
            m.addAction(self.tool_actions[k])
        m.addAction(self.a_insert_table)
        m.addSeparator()
        m.addActions([self.a_add_page, self.a_dup_page, self.a_del_page])

        m = mb.addMenu(tr("&Disponi"))
        m.addActions([self.a_front, self.a_forward, self.a_backward, self.a_back])
        m.addSeparator()
        m.addActions([self.a_group, self.a_ungroup, self.a_lock])
        m.addSeparator()
        m.addActions([self.a_link, self.a_unlink])

        m = mb.addMenu(tr("&Stampa unione"))
        m.addAction(self.a_merge_source)
        self.fields_menu = m.addMenu(tr("Inserisci campo"))
        self.fields_menu.aboutToShow.connect(self._fill_fields_menu)
        m.addSeparator()
        m.addAction(self.a_merge)

        m = mb.addMenu(tr("&Visualizza"))
        m.addActions([self.a_zoom_in, self.a_zoom_out, self.a_zoom_100, self.a_fit, self.a_fit_w])
        m.addSeparator()
        m.addActions([self.a_rulers, self.a_guides, self.a_clear_guides, self.a_grid,
                      self.a_snap, self.a_margins])
        m.addSeparator()
        lang_menu = m.addMenu(tr("Lingua"))
        group = QActionGroup(self)
        current = self.settings.value("ui/language", "")
        for code, name in LANGUAGES.items():
            a = lang_menu.addAction(name, lambda c=code: self.set_language(c))
            a.setCheckable(True)
            a.setChecked(code == (current or language()))
            group.addAction(a)

        m = mb.addMenu(tr("&Aiuto"))
        m.addActions([self.a_keys, self.a_about])

    def _build_toolbars(self):
        tb = QToolBar(tr("File"))
        tb.setObjectName("tb_file")
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addActions([self.a_new, self.a_open, self.a_save])
        tb.addSeparator()
        tb.addActions([self.a_undo, self.a_redo])
        tb.addSeparator()
        tb.addActions([self.a_pdf, self.a_print])
        self.addToolBar(Qt.TopToolBarArea, tb)
        tb = QToolBar(tr("Strumenti"))
        tb.setObjectName("tb_tools")
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for a in self.tool_actions.values():
            tb.addAction(a)
        self.addToolBar(Qt.TopToolBarArea, tb)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.pos_label = QLabel()
        self.pos_label.setMinimumWidth(170)
        self.page_label = QLabel()
        self.zoom_box = QComboBox()
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(["25%", "50%", "75%", "100%", "150%", "200%", "400%"])
        self.zoom_box.setMinimumWidth(90)
        self.zoom_box.lineEdit().returnPressed.connect(self._zoom_from_box)
        self.zoom_box.activated.connect(lambda _: self._zoom_from_box())
        sb.addPermanentWidget(self.pos_label)
        sb.addPermanentWidget(self.page_label)
        sb.addPermanentWidget(self.zoom_box)

    def _zoom_label(self, z):
        self.zoom_box.setEditText(f"{round(z * 100)}%")

    def _zoom_from_box(self):
        t = self.zoom_box.currentText().replace("%", "").replace(",", ".").strip()
        try:
            self.view.set_zoom(float(t) / 100)
        except ValueError:
            pass

    def _cursor_label(self, p: QPointF):
        loc = QLocale()
        self.pos_label.setText(f"X {loc.toString(pt2mm(p.x()), 'f', 1)} mm   "
                               f"Y {loc.toString(pt2mm(p.y()), 'f', 1)} mm")

    # ================================================================ documento
    def load_document(self, doc: Document, path: str | None = None):
        self.doc = doc
        self.path = path
        self.paste_count = 0
        self._rebuild_scenes()
        self.history.reset(self._state_json())
        self.saved_state = self.history.current()
        self.show_page(0)
        QTimer.singleShot(0, self.view.fit_page)
        self._refresh_thumbs()
        self._update_title()
        self._update_actions()
        self._load_merge_headers()

    def _rebuild_scenes(self):
        for sc in self.scenes:
            sc.deleteLater()
        self.scenes = []
        for page in self.doc.pages:
            sc = PageScene(page, self.doc, self)
            sc.show_grid = self.view_opts["grid"]
            sc.snap_enabled = self.view_opts["snap"]
            sc.show_margins = self.view_opts["margins"]
            sc.show_guides = self.view_opts["guides"]
            sc.changed_by_user.connect(self.commit_soon)
            sc.selectionChanged.connect(self._selection_changed)
            sc.image_pick_requested.connect(self.pick_image_for)
            self.scenes.append(sc)
        flow.resolve_links(self._all_frames())

    def _all_frames(self):
        return [f for sc in self.scenes for f in sc.all_frames()]

    def scene(self) -> PageScene:
        return self.scenes[self.current]

    def _sync_doc(self):
        self.doc.pages = [sc.to_page_dict() for sc in self.scenes]

    def _state_json(self) -> str:
        self._sync_doc()
        return json.dumps(self.doc.state(), sort_keys=True, ensure_ascii=False)

    def current_state(self) -> dict:
        self._sync_doc()
        return self.doc.state()

    def show_page(self, index: int):
        if not self.scenes:
            return
        index = max(0, min(index, len(self.scenes) - 1))
        old = self.view.scene()
        if old is not None and old.editing_item is not None:
            old.editing_item.end_edit()
        self.current = index
        self.view.setScene(self.scenes[index])
        self.props.set_scene(self.scenes[index])
        self.pages.set_current(index)
        self.page_label.setText(tr("Pagina {n} di {total}").format(n=index + 1, total=len(self.scenes)))
        self.area.refresh()
        self._update_actions()

    def _selection_changed(self):
        if self.sender() is self.scene():
            self.props.refresh()
            self._update_actions()

    def commit_soon(self):
        self.commit_timer.start()

    def commit(self):
        self.commit_timer.stop()
        if self.history.push(self._state_json()):
            self.thumb_timer.start()
        self.props.refresh()
        self._update_title()
        self._update_actions()

    def _restore(self, s: str):
        sc = self.view.scene()
        if sc is not None and sc.editing_item is not None:
            sc.editing_item.editing = False  # evita una nuova istantanea
        h, v = self.view.horizontalScrollBar().value(), self.view.verticalScrollBar().value()
        self.doc.set_state(json.loads(s))
        cur = self.current
        self._rebuild_scenes()
        self.show_page(min(cur, len(self.scenes) - 1))
        self.view.horizontalScrollBar().setValue(h)
        self.view.verticalScrollBar().setValue(v)
        self._refresh_thumbs()
        self._update_title()
        self._update_actions()

    def undo(self):
        self.commit()  # registra eventuali modifiche in sospeso
        if self.history.can_undo():
            self._restore(self.history.undo())

    def redo(self):
        if self.history.can_redo():
            self._restore(self.history.redo())

    def is_modified(self) -> bool:
        return self.history.current() != self.saved_state

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else tr("Senza titolo")
        self.setWindowModified(self.is_modified())
        self.setWindowTitle(f"{name}[*] — {APP_NAME}")

    def _update_actions(self):
        self.a_undo.setEnabled(self.history.can_undo())
        self.a_redo.setEnabled(self.history.can_redo())
        sel = self.scene().selected_frames() if self.scenes else []
        for a in (self.a_cut, self.a_copy, self.a_dup, self.a_del, self.a_front,
                  self.a_forward, self.a_backward, self.a_back, self.a_lock):
            a.setEnabled(bool(sel))
        self.a_group.setEnabled(len(sel) >= 2)
        self.a_ungroup.setEnabled(any(isinstance(s, GroupFrame) for s in sel))
        t = self._single_text()
        self.a_link.setEnabled(t is not None and t.next is None)
        self.a_unlink.setEnabled(t is not None and t.next is not None)
        self.a_del_page.setEnabled(len(self.scenes) > 1)

    def _single_text(self):
        if not self.scenes:
            return None
        sel = self.scene().selected_frames()
        return sel[0] if len(sel) == 1 and isinstance(sel[0], TextFrame) else None

    # ================================================================== miniature
    def _refresh_thumbs(self):
        self.pages.set_pages([render.thumbnail(sc, 120) for sc in self.scenes], self.current)

    def _update_current_thumb(self):
        if self.scenes:
            for i, sc in enumerate(self.scenes):
                # il testo collegato può cambiare anche le altre pagine
                if i == self.current or any(isinstance(f, TextFrame) and flow.is_chained(f)
                                            for f in sc.all_frames()):
                    self.pages.update_thumb(i, render.thumbnail(sc, 120))

    # =================================================================== file
    def maybe_save(self) -> bool:
        self.commit()
        if not self.is_modified():
            return True
        r = QMessageBox.question(
            self, APP_NAME, tr("Il documento contiene modifiche non salvate. Vuoi salvarle?"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def new_document(self):
        if not self.maybe_save():
            return
        dlg = NewDocumentDialog(self)
        if dlg.exec():
            doc = Document()
            doc.set_state(dlg.state())
            self.load_document(doc)

    def open_document(self, path: str | None = None):
        if not self.maybe_save():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("Apri documento"), self._last_dir(),
                file_filter() + ";;" + tr("Publisher e LibreOffice") + " (*.pub *.odg *.fodg)")
            if not path:
                return
        if os.path.splitext(path)[1].lower() in (".pub", ".odg", ".fodg"):
            self._import_path(path)
            return
        self.open_path(path)

    def open_path(self, path: str) -> bool:
        if os.path.splitext(path)[1].lower() in (".pub", ".odg", ".fodg"):
            return self._import_path(path)
        try:
            doc = Document.load(path)
        except (OSError, CorruptFileError) as e:
            QMessageBox.critical(self, APP_NAME, tr("Impossibile aprire il file:\n{path}\n\n{err}").format(
                path=path, err=e))
            return False
        self.load_document(doc, path)
        self._remember(path)
        return True

    def import_document(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Importa"), self._last_dir(),
            tr("Publisher e LibreOffice") + " (*.pub *.odg *.fodg);;" + tr("Tutti i file") + " (*)")
        if path:
            self._import_path(path)

    def _import_path(self, path: str) -> bool:
        from charta.importers.odg import ImportError_
        from charta.importers.publisher import import_file
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(tr("Conversione in corso…"))
        QApplication.processEvents()
        try:
            doc, report = import_file(path)
        except ImportError_ as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, tr("Importa"), str(e))
            return False
        finally:
            self.statusBar().clearMessage()
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self.load_document(doc)
        self.settings.setValue("files/last_dir", os.path.dirname(path))
        # il documento importato è nuovo: va salvato come .charta
        self.saved_state = ""
        self._update_title()
        notes = []
        if report.get("missing_images"):
            notes.append(tr("{n} immagini non leggibili sono diventate cornici vuote.").format(
                n=report["missing_images"]))
        if report.get("skipped"):
            notes.append(tr("{n} elementi non supportati sono stati saltati.").format(n=report["skipped"]))
        msg = tr("Importazione completata: {n} pagine.").format(n=len(doc.pages))
        if notes:
            QMessageBox.information(self, tr("Importa"), msg + "\n\n" + "\n".join(notes))
        else:
            self.statusBar().showMessage(msg, 6000)
        return True

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        start = self.path or os.path.join(self._last_dir(), (self.doc.title or "documento") + FILE_EXT)
        path, _ = QFileDialog.getSaveFileName(self, tr("Salva con nome"), start, file_filter())
        if not path:
            return False
        if not path.lower().endswith(FILE_EXT):
            path += FILE_EXT
        return self._write(path)

    def _write(self, path: str) -> bool:
        self.commit()
        try:
            self.doc.save(path, self._png_bytes(render.thumbnail(self.scenes[0], 256)))
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, tr("Impossibile salvare il file:\n{err}").format(err=e))
            return False
        self.path = path
        self.saved_state = self.history.current()
        self._remember(path)
        self._update_title()
        self.statusBar().showMessage(tr("Salvato: {path}").format(path=path), 4000)
        return True

    @staticmethod
    def _png_bytes(img: QImage) -> bytes:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return bytes(ba)

    def _last_dir(self) -> str:
        return self.settings.value("files/last_dir", os.path.expanduser("~"))

    def _remember(self, path: str):
        self.settings.setValue("files/last_dir", os.path.dirname(path))
        recent = [p for p in self.settings.value("files/recent", [], type=list) if p != path]
        recent.insert(0, path)
        self.settings.setValue("files/recent", recent[:MAX_RECENT])

    def _fill_recent(self):
        self.recent_menu.clear()
        recent = [p for p in self.settings.value("files/recent", [], type=list) if os.path.exists(p)]
        if not recent:
            a = self.recent_menu.addAction(tr("(nessun file recente)"))
            a.setEnabled(False)
            return
        for p in recent:
            self.recent_menu.addAction(os.path.basename(p), lambda p=p: self.open_document(p)).setToolTip(p)

    def _base_name(self) -> str:
        if self.path:
            return os.path.splitext(self.path)[0]
        return os.path.join(self._last_dir(), self.doc.title or "documento")

    def export_pdf(self):
        dlg = PdfOptionsDialog(self)
        if not dlg.exec():
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta in PDF"), self._base_name() + ".pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.commit()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            render.export_pdf(self.scenes, path, title=self.doc.title, **dlg.options())
        except render.CmykError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, tr("Esporta in PDF"),
                                tr("Il PDF è stato creato, ma non in CMYK:\n{err}").format(err=e))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("PDF esportato: {path}").format(path=path), 5000)

    def export_image(self):
        dlg = ImageOptionsDialog(len(self.scenes), self)
        if not dlg.exec():
            return
        opts = dlg.options()
        path, _ = QFileDialog.getSaveFileName(self, tr("Esporta come immagine"), self._base_name() + ".png",
                                              "PNG (*.png);;JPEG (*.jpg *.jpeg)")
        if not path:
            return
        root, ext = os.path.splitext(path)
        if ext.lower() not in (".png", ".jpg", ".jpeg"):
            ext = ".png"
        self.commit()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            targets = list(enumerate(self.scenes)) if opts["all"] else [(self.current, self.scene())]
            for i, sc in targets:
                out = f"{root}-{i + 1}{ext}" if opts["all"] else root + ext
                img = render.page_image(sc, opts["dpi"])
                if ext.lower() != ".png":
                    img = img.convertToFormat(QImage.Format_RGB32)
                img.save(out, None, 92)
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(tr("Immagine esportata"), 5000)

    def print_doc(self):
        self.commit()
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec():
            render.print_pages(self.scenes, printer)

    # ================================================================= oggetti
    def set_tool(self, tool: str):
        if self.link_source is not None and tool != "link":
            self.link_source = None
        self.view.set_tool(tool)
        if tool in self.tool_actions:
            self.tool_actions[tool].setChecked(True)
        else:
            for a in self.tool_actions.values():
                a.setChecked(False)

    def create_item(self, tool: str, start: QPointF, end: QPointF):
        sc = self.scene()
        clicked = start == end
        r_w, r_h = abs(end.x() - start.x()), abs(end.y() - start.y())
        top_left = QPointF(min(start.x(), end.x()), min(start.y(), end.y()))
        item = None
        if tool in ("text", "table"):
            if tool == "table":
                dlg = TableDialog(self)
                if not dlg.exec():
                    self.set_tool("select")
                    return
                rows, cols, header = dlg.values()
                w, h = (mm2pt(120), mm2pt(8 * rows + 4)) if clicked else (max(r_w, 40), max(r_h, 20))
                item = TextFrame(w, h)
                tables.insert_table(QTextCursor(item.text.document()), rows, cols, header)
            else:
                w, h = (mm2pt(80), mm2pt(25)) if clicked else (max(r_w, 20), max(r_h, 14))
                item = TextFrame(w, h)
        elif tool in ("rect", "ellipse"):
            d = (mm2pt(50), mm2pt(35)) if tool == "rect" else (mm2pt(40), mm2pt(40))
            w, h = d if clicked else (max(r_w, 4), max(r_h, 4))
            item = ShapeFrame(tool, w, h)
        elif tool == "line":
            if clicked:
                end = QPointF(start.x() + mm2pt(60), start.y())
            length = math.hypot(end.x() - start.x(), end.y() - start.y())
            angle = math.degrees(math.atan2(end.y() - start.y(), end.x() - start.x()))
            item = ShapeFrame("line", max(length, 4), 8)
            center = (start + end) / 2
            item.setRotation(angle)
            sc.add_frame(item)
            item.setPos(center - QPointF(item.width() / 2, item.height() / 2))
            self._select_only(item)
            self.set_tool("select")
            self.commit()
            return
        elif tool == "image":
            self.set_tool("select")
            path, _ = QFileDialog.getOpenFileName(self, tr("Inserisci immagine"), self._last_dir(), image_filter())
            if path:
                rect_size = None if clicked else (r_w, r_h)
                self.add_image_file(path, top_left, rect_size, anchor_center=False)
            return
        if item is None:
            return
        item.setPos(top_left)
        sc.add_frame(item)
        self._select_only(item)
        self.set_tool("select")
        if isinstance(item, TextFrame):
            item.start_edit()
            if tool == "table":
                c = QTextCursor(item.text.document())
                c.movePosition(QTextCursor.Start)
                item.text.setTextCursor(c)
        self.commit()

    def _select_only(self, item):
        sc = item.scene() or self.scene()
        sc.clearSelection()
        item.setSelected(True)

    def _read_image(self, path: str):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, tr("Impossibile leggere l'immagine:\n{err}").format(err=e))
            return None
        if QImage.fromData(data).isNull():
            QMessageBox.warning(self, APP_NAME, tr("Formato immagine non riconosciuto:\n{path}").format(path=path))
            return None
        self.settings.setValue("files/last_dir", os.path.dirname(path))
        return self.doc.add_asset(data, os.path.splitext(path)[1])

    def add_image_asset(self, asset_id: str, pos: QPointF, rect_size=None, anchor_center=True):
        sc = self.scene()
        item = ImageFrame(self.doc, asset_id)
        if rect_size:
            w, h = rect_size
        else:
            img = QImage.fromData(self.doc.assets[asset_id])
            w = min(sc.page_w * 0.6, img.width() * 72 / 150)
            h = w / item.natural_aspect()
            if h > sc.page_h * 0.6:
                h = sc.page_h * 0.6
                w = h * item.natural_aspect()
        item.resize_to(max(w, 10), max(h, 10))
        item.setPos(pos - QPointF(w / 2, h / 2) if anchor_center else pos)
        sc.add_frame(item)
        self._select_only(item)
        self.commit()
        return item

    def add_image_file(self, path, pos, rect_size=None, anchor_center=True):
        asset = self._read_image(path)
        if asset:
            self.add_image_asset(asset, pos, rect_size, anchor_center)

    def drop_images(self, paths, pos: QPointF):
        # trascinata su una cornice immagine (anche vuota): la riempie
        sc = self.scene()
        target = next((it for it in sc.items(pos) if isinstance(it, ImageFrame) and not it.locked), None)
        for i, p in enumerate(paths):
            asset = self._read_image(p)
            if not asset:
                continue
            if i == 0 and target is not None:
                target.set_asset(asset)
                if target.parentItem() is None:
                    self._select_only(target)
                self.commit()
            else:
                self.add_image_asset(asset, pos + QPointF(15 * i, 15 * i))

    def pick_image_for(self, item):
        if not isinstance(item, ImageFrame):
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("Scegli immagine"), self._last_dir(), image_filter())
        if not path:
            return
        asset = self._read_image(path)
        if asset:
            item.set_asset(asset)
            self.commit()

    def _texts_in(self, items):
        out = []
        for it in items:
            if isinstance(it, TextFrame):
                out.append(it)
            elif isinstance(it, GroupFrame):
                out += self._texts_in(it.children_frames())
        return out

    def delete_selected(self):
        sc = self.scene()
        if sc.editing_item is not None:
            return
        sel = sc.selected_frames()
        if not sel:
            return
        # il testo delle cornici collegate passa alle cornici rimaste
        for t in self._texts_in(sel):
            flow.remove_from_chain(t)
        for it in sel:
            sc.removeItem(it)
        self._refresh_thumbs()
        self.commit()

    def select_all(self):
        sc = self.scene()
        if sc.editing_item is not None:
            return
        for it in sc.frames():
            it.setSelected(True)

    def toggle_lock(self):
        sel = self.scene().selected_frames()
        if not sel:
            return
        lock = not all(it.locked for it in sel)
        for it in sel:
            it.set_locked(lock)
        self.commit()

    # --------------------------------------------------------- gruppi
    def group_selected(self):
        sc = self.scene()
        sel = sc.selected_frames()
        if len(sel) < 2:
            return
        g = make_group(sc, sel)
        if g is not None:
            self._select_only(g)
            self.commit()

    def ungroup_selected(self):
        sc = self.scene()
        groups = [g for g in sc.selected_frames() if isinstance(g, GroupFrame)]
        if not groups:
            return
        sc.clearSelection()
        for g in groups:
            for c in ungroup(sc, g):
                c.setSelected(True)
        self.commit()

    # ------------------------------------------------- testo collegato
    def start_link(self, frame):
        if not isinstance(frame, TextFrame) or frame.next is not None:
            return
        self.link_source = frame
        self.set_tool("link")
        self.statusBar().showMessage(
            tr("Clicca la cornice di testo in cui deve continuare il testo (anche su un'altra "
               "pagina). Esc per annullare."))

    def _link_target(self, target):
        src = self.link_source
        self.set_tool("select")
        self.statusBar().clearMessage()
        if src is None or target is None:
            return
        if isinstance(target, GroupFrame):
            target = None
        if not isinstance(target, TextFrame) or not flow.can_link(src, target):
            QMessageBox.information(self, APP_NAME, tr(
                "Scegli una cornice di testo che non riceve già testo da un'altra cornice "
                "e che non fa parte della stessa catena."))
            return
        if target.plain_text().strip() and QMessageBox.question(
                self, APP_NAME, tr("La cornice scelta contiene già del testo: verrà aggiunto "
                                   "in coda al testo collegato. Continuare?")) != QMessageBox.Yes:
            return
        flow.link(src, target)
        self._select_only(target)
        self._refresh_thumbs()
        self.commit()

    def unlink(self, frame):
        if not isinstance(frame, TextFrame) or frame.next is None:
            return
        flow.unlink_after(frame)
        self._refresh_thumbs()
        self.commit()

    # -------------------------------------------------------- tabelle
    def insert_table_into(self, frame):
        dlg = TableDialog(self)
        if not dlg.exec():
            return
        rows, cols, header = dlg.values()
        if isinstance(frame, TextFrame):
            if frame.editing:
                cur = frame.text.textCursor()
            else:
                cur = QTextCursor(frame.text.document())
                cur.movePosition(QTextCursor.End)
                if frame.plain_text().strip():
                    cur.insertBlock()
            tables.insert_table(cur, rows, cols, header)
            frame.layout_text()
            self.commit()
        else:
            sc = self.scene()
            item = TextFrame(mm2pt(120), mm2pt(8 * rows + 4))
            tables.insert_table(QTextCursor(item.text.document()), rows, cols, header)
            item.setPos(sc.margin_rect().topLeft())
            sc.add_frame(item)
            self._select_only(item)
            self.commit()

    # -------------------------------------------------- stampa unione
    def _load_merge_headers(self):
        src = self.doc.merge.get("source")
        self.merge_headers = []
        if src and os.path.exists(src):
            try:
                self.merge_headers = merge.read_table(src)[0]
            except merge.DataError:
                pass
        self.props.set_merge_fields(self.merge_headers)

    def set_merge_source(self, path: str, headers: list[str]):
        self.doc.merge = {"source": path}
        self.merge_headers = headers
        self.props.set_merge_fields(headers)
        self.commit()

    def choose_merge_source(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Scegli il file dei dati"), self._last_dir(),
                                              tr("Dati (*.csv *.xlsx *.xlsm *.txt *.tsv)"))
        if not path:
            return
        try:
            headers, records = merge.read_table(path)
        except merge.DataError as e:
            QMessageBox.warning(self, tr("Stampa unione"), str(e))
            return
        self.set_merge_source(path, headers)
        self.statusBar().showMessage(
            tr("Dati caricati: {n} righe, colonne: {c}").format(n=len(records), c=", ".join(headers)), 8000)

    def _fill_fields_menu(self):
        self.fields_menu.clear()
        if not self.merge_headers:
            a = self.fields_menu.addAction(tr("(scegli prima il file dei dati)"))
            a.setEnabled(False)
            return
        for h in self.merge_headers:
            self.fields_menu.addAction(h, lambda h=h: self.insert_merge_field(h))

    def insert_merge_field(self, name: str):
        token = "{{" + name + "}}"
        t = self._single_text()
        if t is not None and t.editing:
            t.text.textCursor().insertText(token)
            return
        if t is not None:
            c = QTextCursor(t.text.document())
            c.movePosition(QTextCursor.End)
            c.insertText((" " if t.plain_text().strip() else "") + token)
            self.commit()
            return
        sc = self.scene()
        item = TextFrame(mm2pt(80), mm2pt(15))
        item.text.setPlainText(token)
        item.setPos(sc.margin_rect().topLeft())
        sc.add_frame(item)
        self._select_only(item)
        self.commit()

    def open_merge(self):
        self.commit()
        MergeDialog(self).exec()

    # ----------------------------------------------------------- appunti
    def _selection_payload(self) -> dict:
        sel = self.scene().selected_frames()
        items = [it.to_dict() for it in sel]
        assets = {}

        def walk(lst):
            for d in lst:
                a = d.get("asset")
                if a and a in self.doc.assets:
                    assets[a] = {"ext": self.doc.asset_ext[a],
                                 "data": base64.b64encode(self.doc.assets[a]).decode("ascii")}
                walk(d.get("items", []))
        walk(items)
        return {"items": items, "assets": assets}

    def copy(self):
        if self.scene().editing_item is not None or not self.scene().selected_frames():
            return
        payload = self._selection_payload()
        mime = QMimeData()
        mime.setData(MIME_ITEMS, QByteArray(json.dumps(payload).encode("utf-8")))
        mime.setText("\n\n".join(it.plain_text() for it in self._texts_in(self.scene().selected_frames())))
        QGuiApplication.clipboard().setMimeData(mime)
        self.paste_count = 0

    def cut(self):
        if self.scene().editing_item is not None:
            return
        self.copy()
        self.delete_selected()

    def _insert_payload(self, payload: dict, offset_mm: float):
        for a, info in payload.get("assets", {}).items():
            self.doc.add_asset(base64.b64decode(info["data"]), info["ext"])
        sc = self.scene()
        sc.clearSelection()
        new = []
        for d in renew_ids(payload.get("items", [])):
            d["x"] = d.get("x", 0) + offset_mm
            d["y"] = d.get("y", 0) + offset_mm
            it = item_from_dict(d, self.doc)
            if it is not None:
                sc.add_frame(it)
                it.setSelected(True)
                new.append(it)
        flow.resolve_links(self._all_frames())
        self.commit()

    def paste(self):
        sc = self.scene()
        if sc.editing_item is not None:
            return
        mime = QGuiApplication.clipboard().mimeData()
        if mime.hasFormat(MIME_ITEMS):
            self.paste_count += 1
            payload = json.loads(bytes(mime.data(MIME_ITEMS)).decode("utf-8"))
            self._insert_payload(payload, 5 * self.paste_count)
        elif mime.hasImage():
            img = QImage(mime.imageData())
            if not img.isNull():
                asset = self.doc.add_asset(self._png_bytes(img), "png")
                self.add_image_asset(asset, sc.page_rect().center())
        elif mime.hasText() and mime.text().strip():
            item = TextFrame(mm2pt(100), mm2pt(40))
            item.text.setPlainText(mime.text())
            item.setPos(sc.margin_rect().topLeft())
            sc.add_frame(item)
            self._select_only(item)
            self.commit()

    def duplicate(self):
        if self.scene().editing_item is not None or not self.scene().selected_frames():
            return
        self._insert_payload(self._selection_payload(), 5)

    # ================================================================== pagine
    def _page_props_changed(self):
        self.thumb_timer.start()
        self.area.refresh()

    def add_page(self):
        self._sync_doc()
        ref = self.doc.pages[self.current]
        page = copy.deepcopy({k: v for k, v in ref.items() if k != "items"})
        page["items"] = []
        self.doc.pages.insert(self.current + 1, page)
        self._after_pages_change(self.current + 1)

    def duplicate_page(self):
        self._sync_doc()
        page = copy.deepcopy(self.doc.pages[self.current])
        page["items"] = renew_ids(page["items"])
        self.doc.pages.insert(self.current + 1, page)
        self._after_pages_change(self.current + 1)

    def delete_page(self):
        if len(self.scenes) <= 1:
            return
        if self.scene().frames():
            r = QMessageBox.question(self, APP_NAME, tr("Eliminare la pagina {n} e il suo contenuto?").format(
                n=self.current + 1))
            if r != QMessageBox.Yes:
                return
        for t in self._texts_in(self.scene().frames()):
            flow.remove_from_chain(t)
        self._sync_doc()
        del self.doc.pages[self.current]
        self._after_pages_change(min(self.current, len(self.doc.pages) - 1))

    def move_page(self, delta: int):
        j = self.current + delta
        if not 0 <= j < len(self.scenes):
            return
        self._sync_doc()
        p = self.doc.pages
        p[self.current], p[j] = p[j], p[self.current]
        self._after_pages_change(j)

    def apply_page_to_all(self, props: dict):
        self._sync_doc()
        for p in self.doc.pages:
            p.update(copy.deepcopy(props))
        self._after_pages_change(self.current)

    def _after_pages_change(self, index: int):
        self._rebuild_scenes()
        self.current = index
        self.show_page(index)
        self._refresh_thumbs()
        self.commit()

    def clear_guides(self):
        self.scene().clear_guides()
        self.commit()

    # ============================================================ visualizzazione
    def set_view_opt(self, key: str, value: bool):
        self.view_opts[key] = value
        self.settings.setValue(f"view/{key}", value)
        self.area.set_rulers_visible(self.view_opts["rulers"])
        for sc in self.scenes:
            sc.show_grid = self.view_opts["grid"]
            sc.snap_enabled = self.view_opts["snap"]
            sc.show_margins = self.view_opts["margins"]
            sc.show_guides = self.view_opts["guides"]
            sc.update()

    def set_language(self, code: str):
        self.settings.setValue("ui/language", code)
        QMessageBox.information(self, APP_NAME, "La nuova lingua sarà attiva al prossimo avvio di Charta.\n"
                                "The new language will be used the next time you start Charta.")

    # ===================================================================== aiuto
    def about(self):
        QMessageBox.about(
            self, tr("Informazioni su Charta"),
            f"<h2>{APP_NAME} {__version__}</h2>"
            + tr("<p>Impaginazione libera per volantini, locandine, brochure, menù e attestati: "
                 "un'alternativa open source a Microsoft Publisher.</p>"
                 "<p>Software libero distribuito con licenza GNU GPL versione 3 o successiva. "
                 "Puoi usarlo, studiarlo, modificarlo e condividerlo.</p>"
                 "<p>Un progetto EurekaFoundation.</p>"))

    def shortcuts_help(self):
        rows = [
            ("V T I B R E L", tr("Seleziona, Testo, Immagine, Tabella, Rettangolo, Ellisse, Linea")),
            (tr("Doppio clic"), tr("Modifica il testo / scegli l'immagine")),
            ("Esc", tr("Torna allo strumento Seleziona / deseleziona")),
            (tr("Frecce"), tr("Sposta di 1 mm (Maiusc: 10 mm, Alt: 0,1 mm)")),
            (tr("Maiusc + maniglia"), tr("Ridimensiona mantenendo le proporzioni")),
            (tr("Ctrl + rotellina"), tr("Zoom")),
            (tr("Rotellina premuta"), tr("Scorri la pagina")),
            (tr("Righello → pagina"), tr("Trascina per creare una guida")),
            ("Ctrl+D", tr("Duplica")),
            ("Ctrl+G / Ctrl+Maiusc+G", tr("Raggruppa / separa")),
            ("Ctrl+L", tr("Blocca / sblocca")),
            ("Ctrl+R", tr("Mostra / nascondi i righelli")),
            ("Ctrl+M", tr("Stampa unione")),
            ("Ctrl+0 / Ctrl+1", tr("Adatta pagina / dimensione reale")),
            ("Ctrl+E", tr("Esporta in PDF")),
        ]
        html = "<table cellpadding='3'>" + "".join(
            f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in rows) + "</table>"
        QMessageBox.information(self, tr("Scorciatoie da tastiera"), html)

    # ==================================================================== chiusura
    def closeEvent(self, event):
        if not self.maybe_save():
            event.ignore()
            return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        event.accept()
