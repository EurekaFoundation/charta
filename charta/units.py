"""Unità di misura e formati pagina.

Internamente la scena lavora in punti tipografici (1 pt = 1/72 di pollice),
che sono anche l'unità nativa del PDF. Nei file e nell'interfaccia si usano
i millimetri, più familiari a chi impagina.
"""

MM = 72.0 / 25.4          # punti in un millimetro
SCREEN_SCALE = 96.0 / 72.0  # zoom 100% = dimensione reale su uno schermo a 96 dpi


def mm2pt(v: float) -> float:
    return v * MM


def pt2mm(v: float) -> float:
    return v / MM


# Formati in millimetri (larghezza, altezza) in orientamento verticale
PAGE_FORMATS = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "Lettera USA": (215.9, 279.4),
    "Biglietto da visita": (85.0, 55.0),
    "Cartolina": (148.0, 105.0),
    "Quadrato 210 × 210": (210.0, 210.0),
}


def format_name_for(w: float, h: float) -> str:
    """Restituisce il nome del formato (anche ruotato) o 'Personalizzato'."""
    for name, (fw, fh) in PAGE_FORMATS.items():
        if (abs(fw - w) < 0.5 and abs(fh - h) < 0.5) or (abs(fw - h) < 0.5 and abs(fh - w) < 0.5):
            return name
    return "Personalizzato"
