"""Avvio dell'applicazione."""

import sys

from PySide6.QtCore import QEvent, QLocale, QObject, QSettings, QTimer

from eureka_core import EurekaApp

from charta import APP_NAME, __version__


class FileOpenFilter(QObject):
    """Su macOS il doppio clic su un file .charta non passa il percorso sulla
    riga di comando ma con un evento FileOpen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.window = None
        self.pending = []
        self.opened = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FileOpen:
            path = event.file()
            self.opened = True
            if self.window is not None:
                self.window.open_document(path)
            else:
                self.pending.append(path)
            return True
        return False


def ui_language(app: EurekaApp) -> str:
    """Lingua dell'interfaccia, scelta per tutta Eureka Suite."""
    lang = app.settings.suite.get("language", "system")
    return QLocale.system().name() if lang == "system" else lang


def migrate_old_settings(app: EurekaApp) -> None:
    """Una sola volta: la lingua scelta in Charta 0.3 diventa quella della suite
    (se nella suite non ne è già stata scelta una)."""
    if app.settings.app.get("migrated_from_qsettings"):
        return
    from charta.i18n import LANGUAGES
    old = QSettings().value("ui/language", "")
    if old in LANGUAGES and app.settings.suite.get("language") == "system":
        app.set_language(old)
    app.settings.app["migrated_from_qsettings"] = True
    app.settings.save()


def create_app(argv=None) -> EurekaApp:
    """Crea l'applicazione con tema, impostazioni e lingua di Eureka Suite."""
    app = EurekaApp("charta", version=__version__, argv=argv)
    # Le impostazioni proprie di Charta (file recenti, vista, finestra) restano
    # in QSettings: teniamo lo stesso nome di organizzazione per non perderle.
    app.setOrganizationName("EurekaFoundation")
    app.setApplicationName(APP_NAME)
    migrate_old_settings(app)

    from charta.i18n import set_language
    set_language(ui_language(app))
    return app


def main():
    app = create_app()
    opener = FileOpenFilter(app)
    app.installEventFilter(opener)

    # import dopo la creazione dell'applicazione: servono i font di sistema
    from charta.document.model import Document
    from charta.ui.dialogs import NewDocumentDialog
    from charta.ui.icons import app_icon
    from charta.ui.main_window import MainWindow

    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    opener.window = win

    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        win.open_path(files[0])
        app.check_updates_later(win)
    else:
        def start():
            # il controllo aggiornamenti parte solo dopo la finestra iniziale,
            # così i due avvisi non si sovrappongono
            if opener.pending:
                win.open_path(opener.pending.pop(0))
            elif not opener.opened:
                dlg = NewDocumentDialog(win)
                if dlg.exec():
                    doc = Document()
                    doc.set_state(dlg.state())
                    win.load_document(doc)
            app.check_updates_later(win)
        # breve attesa: su macOS l'evento FileOpen arriva subito dopo l'avvio
        QTimer.singleShot(300, start)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
