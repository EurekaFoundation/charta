"""Modelli pronti. Ogni modello è una funzione che restituisce lo stato di un
documento (stesso formato di document.json), con misure in millimetri.
I testi sono segnaposto da sostituire con un doppio clic."""

from __future__ import annotations

from charta import fonts
from charta.i18n import tr
from charta.document.model import FORMAT_VERSION, new_page

SANS = fonts.css_list(fonts.SANS)
SERIF = fonts.css_list(fonts.SERIF)


# ------------------------------------------------------------------ aiuti
def p(text, size=12, color="#222222", bold=False, italic=False, align="left",
      family=SANS, space_after=0, line=None):
    style = [f"font-family:{family}", f"font-size:{size}pt", f"color:{color}",
             f"margin-top:0px", f"margin-bottom:{space_after}pt"]
    if bold:
        style.append("font-weight:700")
    if italic:
        style.append("font-style:italic")
    if line:
        style.append(f"line-height:{line}%")
    return f'<p align="{align}" style="{";".join(style)}">{text}</p>'


def html(*paragraphs) -> str:
    return "<html><body>" + "".join(paragraphs) + "</body></html>"


def text(x, y, w, h, body, fill=None, stroke=None, stroke_width=1.0, padding=2.0,
         valign="top", rotation=0):
    return {"type": "text", "x": x, "y": y, "w": w, "h": h, "rotation": rotation,
            "opacity": 1.0, "locked": False, "html": body, "fill": fill, "stroke": stroke,
            "stroke_width": stroke_width, "padding": padding, "valign": valign}


def shape(x, y, w, h, kind="rect", fill="#4a90d9", stroke=None, stroke_width=1.0,
          radius=0.0, locked=False):
    return {"type": "shape", "shape": kind, "x": x, "y": y, "w": w, "h": h, "rotation": 0,
            "opacity": 1.0, "locked": locked, "fill": fill, "stroke": stroke,
            "stroke_width": stroke_width, "radius": radius}


def image(x, y, w, h):
    return {"type": "image", "asset": None, "fit": "fill", "x": x, "y": y, "w": w, "h": h,
            "rotation": 0, "opacity": 1.0, "locked": False, "stroke": None, "stroke_width": 1.0}


def state(title, pages) -> dict:
    return {"version": FORMAT_VERSION, "title": title, "pages": pages}


def menu_rows(rows, size=13, color="#3b2f2f"):
    cells = "".join(
        f'<tr><td style="padding-bottom:7pt">{p(tr(name), size, color, family=SERIF)}'
        f'{p(tr(desc), size - 3, "#7a6a5a", italic=True, family=SERIF) if desc else ""}</td>'
        f'<td align="right" valign="top">{p(price, size, color, family=SERIF, align="right")}</td></tr>'
        for name, desc, price in rows)
    return f'<table width="100%" cellspacing="0" cellpadding="0">{cells}</table>'


# ----------------------------------------------------------------- modelli
def blank(width=210.0, height=297.0):
    return state(tr("Senza titolo"), [new_page(width, height)])


def volantino():
    pg = new_page(210, 297, margins=(12, 12, 12, 12))
    pg["items"] = [
        # le fasce che toccano il bordo sbordano di 3 mm: servono per l'abbondanza
        shape(-3, -3, 216, 121, fill="#0f4c81"),
        shape(-3, 118, 216, 4, fill="#f2a900"),
        text(14, 22, 182, 20, html(p(tr("SABATO 14 GIUGNO · ORE 18:00"), 13, "#f2c14e", bold=True))),
        text(14, 36, 182, 52, html(p(tr("Titolo dell'evento"), 46, "#ffffff", bold=True, line=95)),
             valign="middle"),
        text(14, 88, 182, 20, html(p(tr("Un sottotitolo breve che spiega di cosa si tratta"), 15, "#dce8f5"))),
        image(14, 132, 182, 88),
        text(14, 226, 182, 34, html(
            p(tr("Scrivi qui la descrizione dell'evento: il programma, gli ospiti, perché vale la pena "
              "partecipare. Due o tre frasi bastano: un volantino si legge in pochi secondi."),
              12, "#333333", line=130))),
        shape(-3, 266, 216, 34, fill="#f3f5f8"),
        text(14, 270, 120, 23, html(
            p(tr("<b>Dove</b> · Piazza Municipio"), 11, "#0f4c81"),
            p(tr("<b>Info</b> · 000 000 0000 · info@esempio.it"), 11, "#0f4c81")), valign="middle"),
        text(136, 270, 60, 23, html(p(tr("Ingresso libero"), 16, "#0f4c81", bold=True, align="right")),
             valign="middle"),
    ]
    return state(tr("Volantino"), [pg])


def locandina():
    pg = new_page(297, 420, margins=(15, 15, 15, 15))
    pg["background"] = "#1d1d1f"
    pg["items"] = [
        image(-3, -3, 303, 253),
        shape(-3, 250, 303, 6, fill="#e4572e"),
        text(18, 270, 261, 30, html(p(tr("FESTIVAL · CONCERTO · MOSTRA"), 16, "#e4572e", bold=True))),
        text(18, 296, 261, 62, html(p(tr("Il grande titolo della serata"), 58, "#ffffff", bold=True, line=92)),
             valign="top"),
        text(18, 362, 170, 40, html(
            p(tr("Venerdì 20 settembre"), 20, "#ffffff", bold=True),
            p(tr("Teatro comunale · ore 21:00"), 16, "#c9c9c9"))),
        text(190, 362, 89, 40, html(p(tr("Ingresso<br/>gratuito"), 20, "#e4572e", bold=True, align="right")),
             valign="middle"),
    ]
    return state(tr("Locandina"), [pg])


def menu():
    pg = new_page(210, 297, margins=(15, 18, 15, 18))
    pg["background"] = "#fbf7f0"
    border = "#8a6d3b"
    sections = [
        ("Antipasti", [("Tagliere di salumi e formaggi locali", "con miele e confetture", "€ 12"),
                       ("Bruschette miste", "pomodoro, olive, peperoni", "€ 7"),
                       ("Verdure grigliate", "con olio extravergine del territorio", "€ 6")]),
        ("Primi", [("Fileja al ragù di capra", "pasta fresca fatta a mano", "€ 11"),
                   ("Risotto ai funghi porcini", "mantecato al pecorino", "€ 12"),
                   ("Pasta e fagioli", "ricetta della tradizione", "€ 9")]),
        ("Secondi", [("Grigliata di carne mista", "con patate al forno", "€ 15"),
                     ("Baccalà fritto", "con peperoni cruschi", "€ 14"),
                     ("Melanzane alla parmigiana", "piatto vegetariano", "€ 10")]),
        ("Dolci", [("Tiramisù della casa", "", "€ 5"), ("Crostata alla frutta", "", "€ 5"),
                   ("Gelato artigianale", "chiedi i gusti del giorno", "€ 4")]),
    ]
    body = []
    for title, rows in sections:
        body.append(p(tr(title), 21, border, bold=True, family=SERIF, align="center", space_after=8))
        body.append(menu_rows(rows))
        body.append(p(tr("&nbsp;"), 12))
    pg["items"] = [
        shape(10, 10, 190, 277, fill=None, stroke=border, stroke_width=1.5, locked=True),
        shape(13, 13, 184, 271, fill=None, stroke=border, stroke_width=0.5, locked=True),
        text(25, 22, 160, 22, html(p(tr("Menù"), 40, border, italic=True, family=SERIF, align="center")),
             valign="middle"),
        text(25, 44, 160, 10, html(p(tr("NOME DEL RISTORANTE"), 11, "#7a6a5a", align="center", family=SERIF))),
        shape(85, 57, 40, 1, kind="line", fill=None, stroke=border, stroke_width=1),
        text(28, 66, 154, 196, html(*body)),
        text(25, 266, 160, 12, html(p(tr("Coperto € 2 · Chiedi al personale per informazioni sugli allergeni"),
                                      8.5, "#7a6a5a", italic=True, align="center", family=SERIF)),
             valign="middle"),
    ]
    return state(tr("Menù"), [pg])


def biglietto():
    pg = new_page(85, 55, margins=(4, 4, 4, 4))
    pg["items"] = [
        shape(-3, -3, 9, 61, fill="#0f766e"),
        text(11, 8, 70, 12, html(p(tr("Nome Cognome"), 14, "#111111", bold=True))),
        text(11, 19, 70, 8, html(p(tr("Ruolo o professione"), 8.5, "#0f766e"))),
        shape(13, 29, 20, 0.8, kind="line", fill=None, stroke="#0f766e", stroke_width=0.8),
        text(11, 33, 70, 18, html(
            p(tr("000 000 0000"), 7.5, "#333333"),
            p(tr("nome@esempio.it"), 7.5, "#333333"),
            p(tr("www.esempio.it"), 7.5, "#333333"))),
    ]
    return state(tr("Biglietto da visita"), [pg])


def attestato():
    pg = new_page(297, 210, margins=(15, 15, 15, 15))
    gold = "#a67c00"
    pg["items"] = [
        shape(8, 8, 281, 194, fill=None, stroke=gold, stroke_width=3, locked=True),
        shape(13, 13, 271, 184, fill=None, stroke=gold, stroke_width=0.8, locked=True),
        text(30, 26, 237, 16, html(p(tr("NOME DELL'ENTE O DELLA SCUOLA"), 12, "#555555", align="center")),
             valign="middle"),
        text(30, 46, 237, 28, html(p(tr("Attestato di partecipazione"), 34, gold, italic=True,
                                     family=SERIF, align="center")), valign="middle"),
        text(30, 80, 237, 10, html(p(tr("si conferisce a"), 12, "#555555", italic=True, family=SERIF,
                                     align="center"))),
        text(30, 92, 237, 22, html(p(tr("Nome Cognome"), 30, "#1d1d1f", bold=True, family=SERIF,
                                     align="center")), valign="middle"),
        text(45, 118, 207, 24, html(p(
            tr("per aver partecipato al corso «Titolo del corso», della durata di 25 ore, "
               "svoltosi da ottobre a dicembre 2026."), 12.5, "#333333", family=SERIF,
            align="center", line=135))),
        shape(40, 172, 70, 0.6, kind="line", fill=None, stroke="#333333", stroke_width=0.6),
        text(40, 174, 70, 9, html(p(tr("Luogo e data"), 9, "#555555", align="center"))),
        shape(187, 172, 70, 0.6, kind="line", fill=None, stroke="#333333", stroke_width=0.6),
        text(187, 174, 70, 9, html(p(tr("Firma"), 9, "#555555", align="center"))),
    ]
    return state(tr("Attestato"), [pg])


def brochure():
    col = 297 / 3
    m = 10
    green = "#2f6b3a"
    outside = new_page(297, 210, margins=(m, m, m, m))
    outside["items"] = [
        # anta interna ripiegata (sinistra)
        text(m, 18, col - 2 * m, 170, html(
            p(tr("Chi siamo"), 16, green, bold=True, space_after=6),
            p(tr("Racconta in poche righe la tua attività, la tua associazione o il tuo progetto. "
              "Questa anta è la prima che si vede quando si apre la brochure."), 10.5, "#333333", line=135))),
        # retro (centro)
        text(col + m, 120, col - 2 * m, 70, html(
            p(tr("Contatti"), 14, green, bold=True, space_after=4),
            p(tr("Via Esempio 1, 00000 Città"), 10, "#333333"),
            p(tr("000 000 0000"), 10, "#333333"),
            p(tr("info@esempio.it · www.esempio.it"), 10, "#333333")), valign="bottom"),
        # copertina (destra)
        shape(2 * col, -3, col + 3, 216, fill=green),
        image(2 * col + m, 25, col - 2 * m, 85),
        text(2 * col + m, 120, col - 2 * m, 50, html(
            p(tr("Titolo della brochure"), 26, "#ffffff", bold=True, line=95)), valign="bottom"),
        text(2 * col + m, 172, col - 2 * m, 20, html(p(tr("Sottotitolo o slogan"), 12, "#d8ecd9"))),
    ]
    inside = new_page(297, 210, margins=(m, m, m, m))
    inside["items"] = []
    titles = ["Cosa facciamo", "Come lavoriamo", "Perché sceglierci"]
    for i, t in enumerate(titles):
        x = i * col + m
        inside["items"] += [
            text(x, 15, col - 2 * m, 14, html(p(tr(t), 16, green, bold=True))),
            shape(x, 30, 18, 1.2, kind="line", fill=None, stroke=green, stroke_width=1.2),
            image(x, 36, col - 2 * m, 50),
            text(x, 92, col - 2 * m, 105, html(p(
                tr("Testo del paragrafo. Spiega un aspetto importante con frasi brevi e chiare. "
                   "Puoi aggiungere un elenco, un dato o una citazione per rendere la pagina più viva."),
                10.5, "#333333", line=135))),
        ]
    return state(tr("Brochure a tre ante"), [outside, inside])


TEMPLATES = [
    ("blank", "Pagina vuota", blank),
    ("volantino", "Volantino A4", volantino),
    ("locandina", "Locandina A3", locandina),
    ("menu", "Menù A4", menu),
    ("biglietto", "Biglietto da visita", biglietto),
    ("attestato", "Attestato A4", attestato),
    ("brochure", "Brochure a tre ante", brochure),
]
