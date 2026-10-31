"""Release Qt windows and callbacks before Python tears down application modules."""
import faulthandler
import gc
from datetime import datetime
from pathlib import Path

from PyQt6 import sip
from qt.core import QApplication, QCoreApplication, QEvent, QTimer

_fault_stream = None


def enable_fault_log(data_directory):
    """Keep a native-crash traceback in addition to the launcher's exit status."""
    global _fault_stream
    if _fault_stream is not None:
        return
    log = Path(data_directory) / 'logs' / 'native-fault.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    _fault_stream = log.open('a', encoding='utf-8', buffering=1)
    _fault_stream.write('\nApplication started: ' + datetime.now().isoformat() + '\n')
    faulthandler.enable(file=_fault_stream, all_threads=True)


def shutdown_application(app, store=None):
    """Run after the event loop exits, while Qt and Python callbacks still exist.

    Dialogs/title bars reference their owning windows and Python signal slots.
    Leaving those cycles for interpreter shutdown can destroy native windows
    after QApplication or a Python event filter has already been destroyed.
    Drain deferred deletion explicitly and delete QApplication last.
    """
    if app is None or sip.isdeleted(app) or getattr(app, '_retro_shutting_down', False):
        return
    music = getattr(app, '_music_service', None)
    if music is not None and not sip.isdeleted(music):
        music.shutdown()
    app._retro_shutting_down = True
    chrome = getattr(app, 'retro_chrome', None)
    if chrome is not None and not sip.isdeleted(chrome):
        chrome.shutting_down = True
        app.removeEventFilter(chrome)

    # No UI work should be delivered between deleting a window and its wrappers.
    for timer in app.findChildren(QTimer):
        if not sip.isdeleted(timer):
            timer.stop()
    windows = list(QApplication.topLevelWidgets())
    for window in windows:
        if not sip.isdeleted(window):
            for timer in window.findChildren(QTimer):
                if not sip.isdeleted(timer):
                    timer.stop()
            window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    windows.clear()
    window = timer = None
    app._main_window = None

    translator = getattr(app, '_retro_translator', None)
    if translator is not None and not sip.isdeleted(translator):
        app.removeTranslator(translator)
    app._retro_translator = None
    # Finalized Qt wrappers are safe to collect while the application is alive.
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    if store is not None:
        store.close()
    sip.delete(app)
    gc.collect()
