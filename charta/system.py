"""Aiuti per lanciare programmi esterni (LibreOffice, Ghostscript)."""

import os
import sys


def external_env() -> dict:
    """Ambiente per i programmi esterni. Nella versione installabile
    (PyInstaller) il percorso delle librerie punta a quelle incluse in
    Charta: lo riportiamo a quello del sistema, altrimenti LibreOffice o
    Ghostscript potrebbero caricare librerie sbagliate e non partire."""
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            orig = env.pop(var + "_ORIG", None)
            if orig is not None:
                env[var] = orig
            else:
                env.pop(var, None)
    return env
