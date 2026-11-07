"""Importazione dei file Microsoft Publisher (.pub).

Charta non legge direttamente il formato binario di Publisher: usa
LibreOffice (gratuito, con la libreria libmspub) per convertirlo in un
disegno OpenDocument, poi lo trasforma in oggetti Charta modificabili."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile

from charta.i18n import tr
from charta.system import external_env
from charta.importers.odg import ImportError_, import_odg


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    candidates = []
    if sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates += glob.glob(os.path.join(base, "LibreOffice*", "program", "soffice.exe"))
    elif sys.platform == "darwin":
        candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    else:
        candidates += ["/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice",
                       "/opt/libreoffice/program/soffice", "/snap/bin/libreoffice"]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def convert_to_odg(path: str, out_dir: str, timeout: int = 180) -> str:
    soffice = find_libreoffice()
    if soffice is None:
        raise ImportError_(tr(
            "Per aprire i file di Publisher serve LibreOffice (gratuito): "
            "installalo da libreoffice.org e riprova."))
    # profilo separato: funziona anche se LibreOffice è già aperto
    profile = tempfile.mkdtemp(prefix="charta-lo-")
    try:
        url = "file:///" + profile.replace("\\", "/").lstrip("/")
        cmd = [soffice, f"-env:UserInstallation={url}", "--headless", "--norestore",
               "--convert-to", "odg", "--outdir", out_dir, path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               env=external_env(),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired as e:
            raise ImportError_(tr("LibreOffice non ha risposto in tempo.")) from e
        out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".odg")
        if not os.path.exists(out):
            raise ImportError_(tr("LibreOffice non è riuscito a convertire il file.") + "\n"
                               + (r.stderr or r.stdout or "")[-500:])
        return out
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def import_publisher(path: str):
    tmp = tempfile.mkdtemp(prefix="charta-pub-")
    try:
        odg = convert_to_odg(path, tmp)
        doc, report = import_odg(odg)
        doc.title = os.path.splitext(os.path.basename(path))[0]
        return doc, report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def import_file(path: str):
    """Importa .pub, .odg o .fodg; per altri formati di disegno (es. .vsd di
    Visio, .cdr) prova comunque la conversione con LibreOffice."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".odg", ".fodg"):
        return import_odg(path)
    return import_publisher(path)
