"""One music session for the application, shared by library and reader windows."""
from pathlib import Path
from PyQt6 import sip
from qt.core import QApplication, QObject, QThread, QTimer, pyqtSignal
from music_engine import MusicController
from music_store import MusicStore
from spectrum_backend import SpectrumSession
from i18n import register, tr

register({
    '正在导入音乐…': ('Importing music…', '音楽を追加中…'),
    '已导入 {count} 首音乐': ('Imported {count} tracks', '{count} 曲を追加しました'),
    '音乐导入尚未完成，请稍候。': ('Wait for the music import to finish.', '音楽の追加が完了するまでお待ちください。'),
})


class MusicImport(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, store, paths, playlist, parent):
        super().__init__(parent)
        self.store, self.paths, self.playlist = store, paths, playlist

    def run(self):
        try:
            self.result.emit(self.store.import_files(self.paths, self.playlist))
        except Exception as error:
            self.failed.emit(str(error))


class MusicService(QObject):
    library_changed = pyqtSignal()
    preferences_changed = pyqtSignal()
    track_changed = pyqtSignal(object)
    notice = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)

    def __init__(self, data_dir, parent=None):
        super().__init__(parent)
        self.store = MusicStore(data_dir)
        self.preferences = self.store.settings()
        self.controller = MusicController(self)
        self.spectrum = SpectrumSession(self.controller, self)
        self.spectrum.set_enabled(self.preferences.get('show_spectrum', True))
        self.current = None
        self.job = None
        self.closed = False
        self.windows = []
        self._pending = {}
        self._import_result = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(200)
        self._save_timer.timeout.connect(self.flush_preferences)
        self.controller.track_changed.connect(self._track_changed)
        self.controller.error.connect(self.notice)
        self.controller.volume_changed.connect(self._volume_changed)
        self.controller.mode_changed.connect(self._mode_changed)
        self.controller.set_volume(self.preferences.get('volume', 45))
        self.controller.set_mode(self.preferences.get('play_mode', 'order'))
        self.active_playlist = self.preferences.get('active_playlist')
        self.refresh_queue(self.preferences.get('last_track'))

    def settings(self):
        return dict(self.preferences)

    def set_preferences(self, **values):
        if self.closed:
            return
        self.preferences.update(values)
        if 'show_spectrum' in values:
            self.spectrum.set_enabled(bool(values['show_spectrum']))
        self._pending.update(values)
        self._save_timer.start()
        self.preferences_changed.emit()

    def flush_preferences(self):
        if not self._pending:
            return
        if self.job is not None and not self.closed:
            # A batch import may hold the catalog lock. Do not block the GUI
            # timer on filesystem work; save after its finished signal instead.
            self._save_timer.start()
            return
        values = dict(self._pending)
        try:
            self.store.update_settings(**values)
        except OSError as error:
            if not self.closed:
                self.notice.emit(str(error))
            return
        self._pending.clear()

    def _volume_changed(self, value):
        self.set_preferences(volume=value)

    def _mode_changed(self, value):
        self.set_preferences(play_mode=value)

    def _track_changed(self, track):
        if self.closed:
            return
        self.current = self.store.get_track(track['id']) if track else None
        self.set_preferences(last_track=track['id'] if track else None)
        self.track_changed.emit(self.current)

    def refresh_queue(self, selected=None):
        if self.closed:
            return
        known = {p['id'] for p in self.store.playlists()}
        if self.active_playlist not in known:
            self.active_playlist = None
            if self.preferences.get('active_playlist') is not None:
                self.set_preferences(active_playlist=None)
        self.controller.set_queue(self.store.tracks(self.active_playlist), selected)

    def play_track(self, identity, playlist=None):
        if self.closed:
            return
        self.active_playlist = playlist
        self.refresh_queue(identity)
        self.set_preferences(active_playlist=playlist)
        self.controller.play_track(identity)

    def changed(self):
        if self.closed:
            return
        self.refresh_queue(self.controller.current_id)
        self.library_changed.emit()

    def refresh_track(self):
        if self.closed:
            return
        self._track_changed(self.controller.track)
        self.library_changed.emit()

    def import_files(self, paths, playlist=None):
        if self.closed or self.job or not paths:
            return
        self.notice.emit(tr('正在导入音乐…'))
        self.busy_changed.emit(True)
        self._import_result = None
        self.job = MusicImport(self.store, list(paths), playlist, self)
        self.job.result.connect(self._imported)
        self.job.failed.connect(self._import_failed)
        self.job.finished.connect(self._import_finished)
        self.job.start()

    def _imported(self, result):
        if not self.closed:
            self._import_result = result

    def _import_failed(self, text):
        if not self.closed:
            self.notice.emit(text)

    def _import_finished(self):
        # shutdown may have waited for this worker before Qt delivers its
        # queued result/finished signals. Never revive a closed music session.
        if self.closed or self.job is None:
            return
        job, self.job = self.job, None
        job.deleteLater()
        self.changed()
        result = self._import_result
        self._import_result = None
        if result is not None:
            text = tr('已导入 {count} 首音乐', count=len(result['added']))
            if result.get('errors'):
                text += '\n' + '\n'.join(Path(x['path']).name + ': ' + x['error'] for x in result['errors'])
            self.notice.emit(text)
        self.busy_changed.emit(False)
        self.flush_preferences()

    def remove_tracks(self, identities, playlist=None):
        if self.closed:
            return
        identities = set(identities)
        if not identities:
            return
        try:
            if playlist:
                self.store.remove_from_playlist(playlist, identities)
            else:
                # The optional analyser has its own bounded decoder. Release
                # its file handle before removing managed Windows audio files.
                self.spectrum.release_source()
                # stop() alone leaves Qt's source/file handle alive. Also
                # inspect the actual source: a failed subsequent load may
                # leave the previous file loaded while current_id changes.
                source = self.controller.player.source().toLocalFile() if self.controller.player else ''
                paths = {Path(t['path']) for t in self.store.tracks() if t['id'] in identities}
                if self.controller.current_id in identities or (source and Path(source) in paths):
                    self.controller.release_source()
                for identity in identities:
                    self.store.remove_track(identity)
        finally:
            # A multi-track operation can partially succeed before an IO
            # error. Always reconcile the displayed list and playback queue.
            self.changed()

    def show_player(self, owner):
        if self.closed:
            return None
        from music_ui import MusicDialog
        self.windows = [w for w in self.windows if not sip.isdeleted(w)]
        for window in self.windows:
            if window.parentWidget() is owner:
                window.show()
                window.raise_()
                window.activateWindow()
                return window
        window = MusicDialog(self, owner)
        self.windows.append(window)
        window.show()
        window.raise_()
        return window

    def close_windows(self):
        for window in self.windows:
            if not sip.isdeleted(window):
                window.close()
        self.windows.clear()

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self._save_timer.stop()
        self.spectrum.shutdown()
        self.controller.shutdown()
        self.close_windows()
        job, self.job = self.job, None
        if job is not None:
            job.wait()
            job.deleteLater()
        self._import_result = None
        self.flush_preferences()
        self.store.close()


def get_music_service(data_dir):
    app = QApplication.instance()
    service = getattr(app, '_music_service', None)
    if service is None:
        service = MusicService(data_dir, app)
        app._music_service = service
    return service
