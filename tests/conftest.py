import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_exit_status = 0


@pytest.fixture(scope="session")
def app():
    from PySide6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    a.setOrganizationName("EurekaFoundation")
    a.setApplicationName("Charta-test")
    return a


@pytest.fixture
def window(app):
    from charta.ui.main_window import MainWindow
    w = MainWindow()
    w.resize(1300, 850)
    w.show()
    app.processEvents()
    yield w
    w.commit()
    w.saved_state = w.history.current()  # niente richiesta "salvare le modifiche?"
    w.close()
    w.deleteLater()
    app.processEvents()


def pytest_sessionfinish(session, exitstatus):
    global _exit_status
    _exit_status = int(exitstatus)


def pytest_unconfigure(config):
    # Alla chiusura di Python, PySide distrugge gli oggetti Qt in ordine
    # casuale e su alcuni sistemi (come i server di GitHub Actions) il processo
    # va in crash dopo che i test sono già passati. Usciamo subito, con il
    # risultato reale dei test, dopo aver scritto tutto l'output.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_exit_status)
