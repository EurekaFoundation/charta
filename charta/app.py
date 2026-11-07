"""Avvio dell'applicazione."""

import sys

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("EurekaFoundation")
    app.setStyle("Fusion")
    opener = FileOpenFilter(app)
    app.installEventFilter(opener)

    from PySide6.QtCore import QLocale, QSettings
    from charta.i18n import set_language
    set_language(QSettings().value("ui/language", "") or QLocale.system().name())

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
    else:
        def start():
            if opener.pending:
                win.open_path(opener.pending.pop(0))
                return
            if opener.opened:
                return
            dlg = NewDocumentDialog(win)
            if dlg.exec():
                doc = Document()
                doc.set_state(dlg.state())
                win.load_document(doc)
        # breve attesa: su macOS l'evento FileOpen arriva subito dopo l'avvio
        QTimer.singleShot(300, start)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
