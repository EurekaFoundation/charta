"""Pannello Proprietà: pagina, posizione, testo, collegamenti, tabella,
aspetto, immagine, disposizione."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextBlockFormat, QTextCharFormat
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFontComboBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QToolButton,
                               QVBoxLayout, QWidget)

from charta.i18n import tr
from charta.items import GroupFrame, ImageFrame, ShapeFrame, TextFrame
from charta.items import table as tables
from charta.items.image import FIT_MODES
from charta.ui.widgets import ColorButton, mm_spin
from charta.units import PAGE_FORMATS, format_name_for, mm2pt, pt2mm


def tool(text: str, tip: str, checkable=False) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setMinimumWidth(26)
    return b


class PropertiesPanel(QScrollArea):
    changed = Signal()            # modifica che va registrata (annulla/ripeti)
    page_changed = Signal()       # cambiate le proprietà della pagina
    apply_page_to_all = Signal(dict)
    replace_image = Signal(object)
    link_requested = Signal(object)
    unlink_requested = Signal(object)
    insert_table_requested = Signal(object)
    group_requested = Signal()
    ungroup_requested = Signal()
    insert_field = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self._updating = False
        self.setWidgetResizable(True)
        self.setMinimumWidth(300)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(8, 8, 8, 8)
        self.lay.setSpacing(10)
        self._build_page()
        self._build_geometry()
        self._build_text()
        self._build_table()
        self._build_look()
        self._build_image()
        self._build_arrange()
        self.hint = QLabel(tr("Doppio clic su una cornice di testo per scrivere.\n"
                              "Seleziona una parte del testo per formattare solo quella."))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: palette(mid); font-size: 11px;")
        self.lay.addWidget(self.hint)
        self.lay.addStretch(1)
        self.setWidget(body)
        self.set_merge_fields([])

    # =============================================================== costruzione
    def _group(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        g = QGroupBox(title)
        f = QFormLayout(g)
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.lay.addWidget(g)
        return g, f

    def _build_page(self):
        self.grp_page, f = self._group(tr("Pagina"))
        self.page_format = QComboBox()
        for name in PAGE_FORMATS:
            self.page_format.addItem(tr(name), name)
        self.page_format.addItem(tr("Personalizzato"), "Personalizzato")
        self.page_format.currentIndexChanged.connect(self._on_format)
        f.addRow(tr("Formato"), self.page_format)
        self.page_w = mm_spin(10, 5000)
        self.page_h = mm_spin(10, 5000)
        for s in (self.page_w, self.page_h):
            s.valueChanged.connect(self._on_page_size)
        f.addRow(tr("Larghezza"), self.page_w)
        f.addRow(tr("Altezza"), self.page_h)
        row = QHBoxLayout()
        self.btn_portrait = QPushButton(tr("Verticale"))
        self.btn_landscape = QPushButton(tr("Orizzontale"))
        for b in (self.btn_portrait, self.btn_landscape):
            b.setCheckable(True)
            row.addWidget(b)
        grp = QButtonGroup(self)
        grp.addButton(self.btn_portrait)
        grp.addButton(self.btn_landscape)
        self.btn_portrait.clicked.connect(lambda: self._set_orientation(False))
        self.btn_landscape.clicked.connect(lambda: self._set_orientation(True))
        f.addRow(tr("Orientamento"), row)
        grid = QGridLayout()
        self.margin_spins = []
        for i, name in enumerate((tr("Alto"), tr("Destra"), tr("Basso"), tr("Sinistra"))):
            s = mm_spin(0, 500)
            s.valueChanged.connect(self._on_margins)
            self.margin_spins.append(s)
            grid.addWidget(QLabel(name), i // 2, (i % 2) * 2)
            grid.addWidget(s, i // 2, (i % 2) * 2 + 1)
        f.addRow(QLabel(tr("Margini")))
        f.addRow(grid)
        self.page_bg = ColorButton(tr("Colore di sfondo"), allow_none=False)
        self.page_bg.color_changed.connect(self._on_page_bg)
        f.addRow(tr("Sfondo"), self.page_bg)
        b = QPushButton(tr("Applica a tutte le pagine"))
        b.clicked.connect(lambda: self.apply_page_to_all.emit(self.scene.page_props()) if self.scene else None)
        f.addRow(b)
        info = QLabel(tr("Trascina dai righelli per aggiungere guide; trascina una guida "
                         "sul righello per toglierla."))
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid); font-size: 11px;")
        f.addRow(info)

    def _build_geometry(self):
        self.grp_geom, f = self._group(tr("Posizione e dimensioni"))
        self.gx, self.gy = mm_spin(), mm_spin()
        self.gw, self.gh = mm_spin(1, 5000), mm_spin(1, 5000)
        for s in (self.gx, self.gy, self.gw, self.gh):
            s.valueChanged.connect(self._on_geometry)
        f.addRow("X", self.gx)
        f.addRow("Y", self.gy)
        f.addRow(tr("Larghezza"), self.gw)
        f.addRow(tr("Altezza"), self.gh)
        self.grot = mm_spin(-360, 360, 1, "°", 5)
        self.grot.valueChanged.connect(self._on_rotation)
        f.addRow(tr("Rotazione"), self.grot)
        self.gop = mm_spin(0, 100, 0, " %", 5)
        self.gop.valueChanged.connect(self._on_opacity)
        f.addRow(tr("Opacità"), self.gop)
        self.glock = QCheckBox(tr("Blocca (non si sposta per sbaglio)"))
        self.glock.toggled.connect(self._on_lock)
        f.addRow(self.glock)

    def _build_text(self):
        self.grp_text, f = self._group(tr("Testo"))
        self.t_font = QFontComboBox()
        self.t_font.currentFontChanged.connect(self._on_font)
        f.addRow(tr("Carattere"), self.t_font)
        self.t_size = mm_spin(4, 400, 1, " pt", 1)
        self.t_size.valueChanged.connect(self._on_size)
        f.addRow(tr("Dimensione"), self.t_size)
        row = QHBoxLayout()
        self.t_bold = tool(tr("G"), tr("Grassetto"), True)
        self.t_bold.setStyleSheet("font-weight: bold;")
        self.t_italic = tool(tr("C"), tr("Corsivo"), True)
        self.t_italic.setStyleSheet("font-style: italic;")
        self.t_under = tool(tr("S"), tr("Sottolineato"), True)
        self.t_under.setStyleSheet("text-decoration: underline;")
        self.t_bold.toggled.connect(self._on_bold)
        self.t_italic.toggled.connect(self._on_italic)
        self.t_under.toggled.connect(self._on_underline)
        self.t_color = ColorButton(tr("Colore del testo"), allow_none=False)
        self.t_color.color_changed.connect(self._on_text_color)
        for w in (self.t_bold, self.t_italic, self.t_under, self.t_color):
            row.addWidget(w)
        row.addStretch(1)
        f.addRow(tr("Stile"), row)
        row = QHBoxLayout()
        self.t_align = {}
        for key, txt, tip in (("left", "⯇", tr("Allinea a sinistra")), ("center", "≡", tr("Centra")),
                              ("right", "⯈", tr("Allinea a destra")), ("justify", "☰", tr("Giustifica"))):
            b = tool(txt, tip, True)
            b.clicked.connect(lambda _=False, k=key: self._on_align(k))
            self.t_align[key] = b
            row.addWidget(b)
        row.addStretch(1)
        f.addRow(tr("Allineamento"), row)
        self.t_valign = QComboBox()
        self.t_valign.addItem(tr("In alto"), "top")
        self.t_valign.addItem(tr("Al centro"), "middle")
        self.t_valign.addItem(tr("In basso"), "bottom")
        self.t_valign.currentIndexChanged.connect(self._on_valign)
        f.addRow(tr("In verticale"), self.t_valign)
        self.t_line = mm_spin(50, 400, 0, " %", 10)
        self.t_line.valueChanged.connect(self._on_line)
        f.addRow(tr("Interlinea"), self.t_line)
        self.t_pad = mm_spin(0, 100, 1, " mm", 0.5)
        self.t_pad.valueChanged.connect(self._on_padding)
        f.addRow(tr("Spazio interno"), self.t_pad)

        # testo che scorre tra cornici
        row = QHBoxLayout()
        self.btn_link = QPushButton(tr("Collega a…"))
        self.btn_link.setToolTip(tr("Il testo che non entra continua in un'altra cornice: "
                                    "clicca questo pulsante e poi la cornice di destinazione"))
        self.btn_link.clicked.connect(lambda: self.link_requested.emit(self._single()))
        self.btn_unlink = QPushButton(tr("Scollega"))
        self.btn_unlink.setToolTip(tr("Interrompe il collegamento con la cornice successiva"))
        self.btn_unlink.clicked.connect(lambda: self.unlink_requested.emit(self._single()))
        row.addWidget(self.btn_link)
        row.addWidget(self.btn_unlink)
        f.addRow(tr("Scorrimento"), row)
        self.link_info = QLabel()
        self.link_info.setWordWrap(True)
        self.link_info.setStyleSheet("color: palette(mid); font-size: 11px;")
        f.addRow(self.link_info)

        b = QPushButton(tr("Inserisci tabella…"))
        b.clicked.connect(lambda: self.insert_table_requested.emit(self._single()))
        f.addRow(b)
        self.t_field = QComboBox()
        self.t_field.activated.connect(self._on_field)
        self.t_field_label = QLabel(tr("Campo"))
        f.addRow(self.t_field_label, self.t_field)
        self.text_form = f

    def _build_table(self):
        self.grp_table, f = self._group(tr("Tabella"))
        grid = QGridLayout()
        btns = (
            (tr("Riga sopra"), lambda t: tables.insert_row(t, below=False)),
            (tr("Riga sotto"), lambda t: tables.insert_row(t, below=True)),
            (tr("Colonna a sinistra"), lambda t: tables.insert_column(t, right=False)),
            (tr("Colonna a destra"), lambda t: tables.insert_column(t, right=True)),
            (tr("Elimina riga"), tables.remove_row),
            (tr("Elimina colonna"), tables.remove_column),
            (tr("Unisci celle"), tables.merge_cells),
            (tr("Dividi cella"), tables.split_cell),
        )
        for i, (label, fn) in enumerate(btns):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, fn=fn: self._table_op(fn))
            grid.addWidget(b, i // 2, i % 2)
        f.addRow(grid)
        self.tb_cell = ColorButton(tr("Colore della cella"))
        self.tb_cell.color_changed.connect(lambda c: self._table_op(lambda t: tables.set_cell_background(t, c)))
        f.addRow(tr("Sfondo cella"), self.tb_cell)
        row = QHBoxLayout()
        self.tb_border = ColorButton(tr("Colore dei bordi"), allow_none=False)
        self.tb_border.color_changed.connect(lambda c: self._table_op(lambda t: tables.set_table_border(t, color=c)))
        self.tb_border_w = mm_spin(0, 10, 2, " pt", 0.25)
        self.tb_border_w.valueChanged.connect(
            lambda v: None if self._updating else self._table_op(lambda t: tables.set_table_border(t, width=v)))
        row.addWidget(self.tb_border)
        row.addWidget(self.tb_border_w, 1)
        f.addRow(tr("Bordi"), row)
        self.tb_pad = mm_spin(0, 30, 1, " pt", 1)
        self.tb_pad.valueChanged.connect(
            lambda v: None if self._updating else self._table_op(lambda t: tables.set_table_border(t, padding=v)))
        f.addRow(tr("Spazio celle"), self.tb_pad)
        info = QLabel(tr("Le operazioni valgono per la cella dove si trova il cursore "
                         "(per unire, seleziona più celle)."))
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(mid); font-size: 11px;")
        f.addRow(info)

    def _build_look(self):
        self.grp_look, f = self._group(tr("Aspetto"))
        self.l_fill = ColorButton(tr("Riempimento"))
        self.l_fill.color_changed.connect(self._on_fill)
        self.l_fill_row = f.rowCount()
        f.addRow(tr("Riempimento"), self.l_fill)
        row = QHBoxLayout()
        self.l_stroke = ColorButton(tr("Colore del bordo"))
        self.l_stroke.color_changed.connect(self._on_stroke)
        self.l_stroke_w = mm_spin(0, 100, 2, " pt", 0.25)
        self.l_stroke_w.valueChanged.connect(self._on_stroke_w)
        row.addWidget(self.l_stroke)
        row.addWidget(self.l_stroke_w, 1)
        self.l_stroke_row = f.rowCount()
        f.addRow(tr("Bordo"), row)
        self.l_radius = mm_spin(0, 500, 1, " mm", 0.5)
        self.l_radius.valueChanged.connect(self._on_radius)
        self.l_radius_row = f.rowCount()
        f.addRow(tr("Angoli"), self.l_radius)
        self.look_form = f

    def _build_image(self):
        self.grp_image, f = self._group(tr("Immagine"))
        self.i_fit = QComboBox()
        for k, v in FIT_MODES.items():
            self.i_fit.addItem(tr(v), k)
        self.i_fit.currentIndexChanged.connect(self._on_fit)
        f.addRow(tr("Adattamento"), self.i_fit)
        b = QPushButton(tr("Sostituisci immagine…"))
        b.clicked.connect(lambda: self.replace_image.emit(self._single()) if self._single() else None)
        f.addRow(b)
        b = QPushButton(tr("Proporzioni originali"))
        b.setToolTip(tr("Ridimensiona la cornice secondo le proporzioni dell'immagine"))
        b.clicked.connect(self._on_natural)
        f.addRow(b)

    def _build_arrange(self):
        self.grp_arr = QGroupBox(tr("Disponi"))
        v = QVBoxLayout(self.grp_arr)
        row = QHBoxLayout()
        for txt, tip, fn in (("⤒", tr("Porta in primo piano"), self.bring_front),
                             ("↑", tr("Porta avanti"), self.bring_forward),
                             ("↓", tr("Porta indietro"), self.send_backward),
                             ("⤓", tr("Porta sullo sfondo"), self.send_back)):
            b = tool(txt, tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.align_label = QLabel()
        self.align_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        v.addWidget(self.align_label)
        row = QHBoxLayout()
        for key, txt, tip in (("l", "⇤", tr("Allinea a sinistra")), ("hc", "↔", tr("Centra in orizzontale")),
                              ("r", "⇥", tr("Allinea a destra")), ("t", "⤒", tr("Allinea in alto")),
                              ("vc", "↕", tr("Centra in verticale")), ("b", "⤓", tr("Allinea in basso"))):
            b = tool(txt, tip)
            b.clicked.connect(lambda _=False, k=key: self.align(k))
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        row = QHBoxLayout()
        self.btn_dist_h = QPushButton(tr("Distribuisci ↔"))
        self.btn_dist_v = QPushButton(tr("Distribuisci ↕"))
        for b in (self.btn_dist_h, self.btn_dist_v):
            b.setToolTip(tr("Spazia in modo uguale (almeno 3 oggetti)"))
        self.btn_dist_h.clicked.connect(lambda: self.distribute("h"))
        self.btn_dist_v.clicked.connect(lambda: self.distribute("v"))
        row.addWidget(self.btn_dist_h)
        row.addWidget(self.btn_dist_v)
        v.addLayout(row)
        row = QHBoxLayout()
        self.btn_group = QPushButton(tr("Raggruppa"))
        self.btn_ungroup = QPushButton(tr("Separa"))
        self.btn_group.clicked.connect(self.group_requested.emit)
        self.btn_ungroup.clicked.connect(self.ungroup_requested.emit)
        row.addWidget(self.btn_group)
        row.addWidget(self.btn_ungroup)
        v.addLayout(row)
        self.lay.addWidget(self.grp_arr)

    # ============================================================== aggiornamento
    def set_scene(self, scene):
        self.scene = scene
        self.refresh()

    def set_merge_fields(self, fields: list[str]):
        self.t_field.clear()
        self.t_field.addItem(tr("Inserisci un campo…"), None)
        for f in fields:
            self.t_field.addItem(f, f)
        self.text_form.setRowVisible(self.t_field_label, bool(fields))

    def _sel(self):
        return self.scene.selected_frames() if self.scene else []

    def _single(self):
        s = self._sel()
        return s[0] if len(s) == 1 else None

    def refresh(self):
        if self.scene is None:
            return
        self._updating = True
        blockers = [QSignalBlocker(w) for w in self.findChildren(QWidget)]
        try:
            self._refresh()
        finally:
            for b in blockers:
                b.unblock()
            self._updating = False

    def _refresh(self):
        sel = self._sel()
        one = sel[0] if len(sel) == 1 else None
        is_text = isinstance(one, TextFrame)
        self.grp_page.setVisible(not sel)
        self.grp_geom.setVisible(one is not None)
        self.grp_text.setVisible(is_text)
        self.grp_table.setVisible(is_text and bool(tables.tables(one.text.document())))
        self.grp_image.setVisible(isinstance(one, ImageFrame))
        self.grp_look.setVisible(bool(sel) and not (one is not None and isinstance(one, GroupFrame)))
        self.grp_arr.setVisible(bool(sel))
        self.hint.setVisible(not sel or is_text)
        self.btn_group.setEnabled(len(sel) >= 2)
        self.btn_ungroup.setEnabled(any(isinstance(s, GroupFrame) for s in sel))
        if not sel:
            self._refresh_page()
            return
        self.align_label.setText(tr("Allinea rispetto ai margini della pagina") if one
                                 else tr("Allinea rispetto alla selezione"))
        self.btn_dist_h.setEnabled(len(sel) >= 3)
        self.btn_dist_v.setEnabled(len(sel) >= 3)
        if one is not None:
            self.gx.setValue(pt2mm(one.pos().x()))
            self.gy.setValue(pt2mm(one.pos().y()))
            self.gw.setValue(pt2mm(one.width()))
            self.gh.setValue(pt2mm(one.height()))
            self.grot.setValue(one.rotation())
            self.gop.setValue(one.opacity() * 100)
            self.glock.setChecked(one.locked)
        ref = next((s for s in sel if hasattr(s, "stroke")), None)
        if ref is not None:
            has_fill = hasattr(ref, "fill") and not (isinstance(ref, ShapeFrame) and ref.shape_kind == "line")
            self.look_form.setRowVisible(self.l_fill_row, has_fill)
            if has_fill:
                self.l_fill.set_color(ref.fill)
            self.l_stroke.set_color(ref.stroke)
            self.l_stroke_w.setValue(ref.stroke_width)
        show_r = isinstance(one, ShapeFrame) and one.shape_kind == "rect"
        self.look_form.setRowVisible(self.l_radius_row, show_r)
        if show_r:
            self.l_radius.setValue(pt2mm(one.radius))
        if is_text:
            self._refresh_text(one)
        if isinstance(one, ImageFrame):
            self.i_fit.setCurrentIndex(self.i_fit.findData(one.fit))

    def _refresh_text(self, one: TextFrame):
        cf = one.char_format()
        fams = cf.fontFamilies()
        fam = fams[0] if fams else (cf.font().family() or one.text.document().defaultFont().family())
        self.t_font.setCurrentFont(QFont(fam))
        size = cf.fontPointSize() or one.text.document().defaultFont().pointSizeF()
        self.t_size.setValue(size)
        self.t_bold.setChecked(cf.fontWeight() >= QFont.DemiBold)
        self.t_italic.setChecked(cf.fontItalic())
        self.t_under.setChecked(cf.fontUnderline())
        fg = cf.foreground().color() if cf.hasProperty(QTextCharFormat.ForegroundBrush) else QColor("black")
        self.t_color.set_color(fg)
        bf = one.block_format()
        al = bf.alignment()
        key = "left"
        if al & Qt.AlignHCenter:
            key = "center"
        elif al & Qt.AlignRight:
            key = "right"
        elif al & Qt.AlignJustify:
            key = "justify"
        for k, b in self.t_align.items():
            b.setChecked(k == key)
        lh = bf.lineHeight() if bf.lineHeightType() == QTextBlockFormat.ProportionalHeight else 100
        self.t_line.setValue(lh or 100)
        self.t_valign.setCurrentIndex(self.t_valign.findData(one.valign))
        self.t_pad.setValue(pt2mm(one.padding))
        self.btn_link.setEnabled(one.next is None)
        self.btn_unlink.setEnabled(one.next is not None)
        if one.prev is not None and one.next is not None:
            msg = tr("Il testo arriva dalla cornice precedente e continua nella successiva.")
        elif one.next is not None:
            msg = tr("Il testo continua in un'altra cornice.")
        elif one.prev is not None:
            msg = tr("Il testo arriva da un'altra cornice.")
        elif one.overflowing():
            msg = tr("Il testo non entra: ingrandisci la cornice o collegala a un'altra.")
        else:
            msg = ""
        self.link_info.setText(msg)
        self.link_info.setVisible(bool(msg))
        ts = tables.tables(one.text.document())
        if ts:
            fmt = ts[0].format()
            self.tb_border.set_color(fmt.borderBrush().color())
            self.tb_border_w.setValue(fmt.border())
            self.tb_pad.setValue(fmt.cellPadding())

    def _refresh_page(self):
        sc = self.scene
        w, h = pt2mm(sc.page_w), pt2mm(sc.page_h)
        self.page_format.setCurrentIndex(self.page_format.findData(format_name_for(w, h)))
        self.page_w.setValue(w)
        self.page_h.setValue(h)
        self.btn_landscape.setChecked(w > h)
        self.btn_portrait.setChecked(w <= h)
        for s, m in zip(self.margin_spins, sc.margins):
            s.setValue(pt2mm(m))
        self.page_bg.set_color(sc.background)

    def _done(self):
        if self.scene is not None:
            self.scene.update()
        self.changed.emit()

    # ================================================================== pagina
    def _apply_page(self, d: dict):
        self.scene.set_page_props(d)
        self.page_changed.emit()
        self._done()

    def _on_format(self):
        name = self.page_format.currentData()
        if self._updating or name not in PAGE_FORMATS:
            return
        w, h = PAGE_FORMATS[name]
        if self.btn_landscape.isChecked():
            w, h = h, w
        d = self.scene.page_props()
        d["width"], d["height"] = w, h
        self._apply_page(d)
        self.refresh()

    def _on_page_size(self):
        if self._updating:
            return
        d = self.scene.page_props()
        d["width"], d["height"] = self.page_w.value(), self.page_h.value()
        self._apply_page(d)
        self.refresh()

    def _set_orientation(self, landscape: bool):
        d = self.scene.page_props()
        w, h = d["width"], d["height"]
        if (w > h) != landscape:
            d["width"], d["height"] = h, w
            self._apply_page(d)
        self.refresh()

    def _on_margins(self):
        if self._updating:
            return
        d = self.scene.page_props()
        d["margins"] = [s.value() for s in self.margin_spins]
        self._apply_page(d)

    def _on_page_bg(self, c):
        d = self.scene.page_props()
        d["background"] = c.name()
        self._apply_page(d)

    # ================================================================ geometria
    def _on_geometry(self):
        one = self._single()
        if self._updating or one is None:
            return
        one.setPos(mm2pt(self.gx.value()), mm2pt(self.gy.value()))
        one.resize_to(mm2pt(self.gw.value()), mm2pt(self.gh.value()))
        self._done()

    def _on_rotation(self, v):
        one = self._single()
        if self._updating or one is None:
            return
        one.setRotation(v)
        self._done()

    def _on_opacity(self, v):
        one = self._single()
        if self._updating or one is None:
            return
        one.setOpacity(v / 100)
        self._done()

    def _on_lock(self, v):
        one = self._single()
        if self._updating or one is None:
            return
        one.set_locked(v)
        self._done()

    # ==================================================================== testo
    def _text(self):
        one = self._single()
        return one if isinstance(one, TextFrame) else None

    def _char(self, fmt: QTextCharFormat):
        t = self._text()
        if self._updating or t is None:
            return
        t.merge_char_format(fmt)
        self._done()

    def _on_font(self, font: QFont):
        f = QTextCharFormat()
        f.setFontFamilies([font.family()])
        self._char(f)

    def _on_size(self, v):
        f = QTextCharFormat()
        f.setFontPointSize(v)
        self._char(f)

    def _on_bold(self, v):
        f = QTextCharFormat()
        f.setFontWeight(QFont.Bold if v else QFont.Normal)
        self._char(f)

    def _on_italic(self, v):
        f = QTextCharFormat()
        f.setFontItalic(v)
        self._char(f)

    def _on_underline(self, v):
        f = QTextCharFormat()
        f.setFontUnderline(v)
        self._char(f)

    def _on_text_color(self, c):
        f = QTextCharFormat()
        f.setForeground(c)
        self._char(f)

    def _on_align(self, key):
        t = self._text()
        if t is None:
            return
        al = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter,
              "right": Qt.AlignRight, "justify": Qt.AlignJustify}[key]
        bf = QTextBlockFormat()
        bf.setAlignment(al)
        t.merge_block_format(bf)
        for k, b in self.t_align.items():
            b.setChecked(k == key)
        self._done()

    def _on_line(self, v):
        t = self._text()
        if self._updating or t is None:
            return
        bf = QTextBlockFormat()
        bf.setLineHeight(v, QTextBlockFormat.ProportionalHeight)
        t.merge_block_format(bf)
        self._done()

    def _on_valign(self):
        t = self._text()
        if self._updating or t is None:
            return
        t.set_valign(self.t_valign.currentData())
        self._done()

    def _on_padding(self, v):
        t = self._text()
        if self._updating or t is None:
            return
        t.set_padding(mm2pt(v))
        self._done()

    def _on_field(self, idx):
        name = self.t_field.itemData(idx)
        self.t_field.setCurrentIndex(0)
        if name:
            self.insert_field.emit(name)

    def _table_op(self, fn):
        t = self._text()
        if t is None:
            return
        fn(t)
        t.layout_text()
        self.refresh()
        self._done()

    # ================================================================== aspetto
    def _on_fill(self, c):
        for it in self._sel():
            if hasattr(it, "fill"):
                it.fill = QColor(c)
                it.update()
        self._done()

    def _on_stroke(self, c):
        for it in self._sel():
            if not hasattr(it, "stroke"):
                continue
            it.prepareGeometryChange()
            it.stroke = QColor(c)
            if c.alpha() and it.stroke_width == 0:
                it.stroke_width = 1.0
            it.update()
        self.refresh()
        self._done()

    def _on_stroke_w(self, v):
        if self._updating:
            return
        for it in self._sel():
            if not hasattr(it, "stroke"):
                continue
            it.prepareGeometryChange()
            it.stroke_width = v
            if v > 0 and it.stroke.alpha() == 0:
                it.stroke = QColor("black")
            it.update()
        self.refresh()
        self._done()

    def _on_radius(self, v):
        one = self._single()
        if self._updating or not isinstance(one, ShapeFrame):
            return
        one.radius = mm2pt(v)
        one.update()
        self._done()

    # ================================================================= immagine
    def _on_fit(self):
        one = self._single()
        if self._updating or not isinstance(one, ImageFrame):
            return
        one.fit = self.i_fit.currentData()
        one.update()
        self._done()

    def _on_natural(self):
        one = self._single()
        if not isinstance(one, ImageFrame) or not one.has_image():
            return
        one.resize_to(one.width(), one.width() / one.natural_aspect())
        self.refresh()
        self._done()

    # ================================================================== disponi
    def bring_front(self):
        fr = self.scene.frames()
        top = fr[-1].zValue() if fr else 0
        for i, it in enumerate(sorted(self._sel(), key=lambda x: x.zValue())):
            it.setZValue(top + 1 + i)
        self.scene.normalize_z()
        self._done()

    def send_back(self):
        fr = self.scene.frames()
        bottom = fr[0].zValue() if fr else 0
        sel = sorted(self._sel(), key=lambda x: x.zValue())
        for i, it in enumerate(sel):
            it.setZValue(bottom - len(sel) + i)
        self.scene.normalize_z()
        self._done()

    def _step(self, direction: int):
        self.scene.normalize_z()
        fr = self.scene.frames()
        sel = set(self._sel())
        order = fr if direction < 0 else list(reversed(fr))
        for i, it in enumerate(order):
            if it in sel and i > 0 and order[i - 1] not in sel:
                a, b = it.zValue(), order[i - 1].zValue()
                it.setZValue(b)
                order[i - 1].setZValue(a)
                order[i - 1], order[i] = order[i], order[i - 1]
        self.scene.normalize_z()
        self._done()

    def bring_forward(self):
        self._step(+1)

    def send_backward(self):
        self._step(-1)

    def align(self, key: str):
        sel = [it for it in self._sel() if not it.locked]
        if not sel:
            return
        rects = {it: it.mapRectToScene(it.rect()) for it in sel}
        if len(self._sel()) == 1:
            ref = self.scene.margin_rect()
        else:
            ref = None
            for r in rects.values():
                ref = r if ref is None else ref.united(r)
        for it, r in rects.items():
            dx = dy = 0.0
            if key == "l":
                dx = ref.left() - r.left()
            elif key == "r":
                dx = ref.right() - r.right()
            elif key == "hc":
                dx = ref.center().x() - r.center().x()
            elif key == "t":
                dy = ref.top() - r.top()
            elif key == "b":
                dy = ref.bottom() - r.bottom()
            elif key == "vc":
                dy = ref.center().y() - r.center().y()
            it.moveBy(dx, dy)
        self.refresh()
        self._done()

    def distribute(self, axis: str):
        sel = [it for it in self._sel() if not it.locked]
        if len(sel) < 3:
            return
        rects = {it: it.mapRectToScene(it.rect()) for it in sel}
        if axis == "h":
            sel.sort(key=lambda it: rects[it].left())
            start, end = rects[sel[0]].left(), rects[sel[-1]].right()
            total = sum(rects[it].width() for it in sel)
            gap = (end - start - total) / (len(sel) - 1)
            x = start
            for it in sel:
                it.moveBy(x - rects[it].left(), 0)
                x += rects[it].width() + gap
        else:
            sel.sort(key=lambda it: rects[it].top())
            start, end = rects[sel[0]].top(), rects[sel[-1]].bottom()
            total = sum(rects[it].height() for it in sel)
            gap = (end - start - total) / (len(sel) - 1)
            y = start
            for it in sel:
                it.moveBy(0, y - rects[it].top())
                y += rects[it].height() + gap
        self._done()
