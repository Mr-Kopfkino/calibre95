"""Application-owned local audio playback using the bundled Qt/FFmpeg runtime.

No system player is launched. Queue entries are ordinary dictionaries with an
id and an absolute local path. The UI/store owns persistence; this controller
never automatically starts playback on construction or playlist restoration.
"""
from pathlib import Path
import random

from qt.core import QObject, QTimer, QUrl, pyqtSignal
from i18n import register, tr

register({
    '音频播放引擎不可用。': ('The audio playback engine is unavailable.', '音声再生エンジンを利用できません。'),
    '找不到音频文件：{name}': ('Audio file not found: {name}', '音声ファイルが見つかりません：{name}'),
    '无法播放 {name}：{error}': ('Cannot play {name}: {error}', '{name} を再生できません：{error}'),
    '歌单中没有可播放的文件。': ('No playable files remain in this playlist.', 'プレイリストに再生可能なファイルがありません。'),
})


class MusicController(QObject):
    track_changed = pyqtSignal(object)
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    state_changed = pyqtSignal(str)
    error = pyqtSignal(str)
    queue_changed = pyqtSignal()
    volume_changed = pyqtSignal(int)
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        self.current_id = None
        self.position_ms = 0
        self.duration_ms = 0
        self.state = 'stopped'
        self.volume = 45
        self.play_mode = 'order'
        self.available = False
        self.closed = False
        self.player = self.output = None
        self._wants_play = False
        self._loaded_id = None
        self._failed = set()
        self._bag = []
        self._history = []
        self._history_index = -1
        self._generation = 0
        self._advance_generation = 0
        self._advance_reason = None
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._deferred_advance)
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            self.player = QMediaPlayer(self)
            self.output = QAudioOutput(self)
            self.output.setVolume((self.volume/100) ** 2)
            self.player.setAudioOutput(self.output)
            self.available = self.player.isAvailable()
            self.player.positionChanged.connect(self._position)
            self.player.durationChanged.connect(self._duration)
            self.player.playbackStateChanged.connect(self._state)
            self.player.mediaStatusChanged.connect(self._media_status)
            self.player.errorOccurred.connect(self._media_error)
        except (ImportError, RuntimeError):
            self.available = False

    @property
    def track(self):
        return next((item for item in self.queue if item['id'] == self.current_id), None)

    def _emit_state(self, value):
        if self.state != value:
            self.state = value
            self.state_changed.emit(value)

    def _state(self, state):
        if not self.closed:
            self._emit_state({0: 'stopped', 1: 'playing', 2: 'paused'}.get(state.value, 'stopped'))

    def _position(self, value):
        if not self.closed:
            self.position_ms = int(value)
            self.position_changed.emit(self.position_ms)

    def _duration(self, value):
        if not self.closed:
            self.duration_ms = int(value)
            self.duration_changed.emit(self.duration_ms)

    def set_queue(self, entries, current_id=None):
        if self.closed:
            return
        old_track = self.track
        result, seen = [], set()
        for entry in entries:
            item = dict(entry)
            identity = item.get('id')
            if identity is None or identity in seen or not item.get('path'):
                continue
            item['path'] = str(item['path'])
            result.append(item)
            seen.add(identity)
        self.queue = result
        selected = current_id if current_id in seen else self.current_id
        if selected not in seen:
            selected = self.queue[0]['id'] if self.queue else None
        self.current_id = selected
        new_track = self.track
        retain_source = (old_track and new_track and old_track['id'] == new_track['id']
                         and old_track['path'] == new_track['path'])
        if not retain_source:
            self.stop()
            if self.player is not None:
                self.player.setSource(QUrl())
            self._loaded_id = None
            self._duration(0)
        self._failed.intersection_update(seen)
        self._bag = [identity for identity in self._bag if identity in seen and identity != selected]
        old_history_index = self._history_index
        self._history_index = sum(identity in seen for identity in self._history[:old_history_index+1])-1
        self._history = [identity for identity in self._history if identity in seen]
        self.queue_changed.emit()
        self.track_changed.emit(new_track)

    def _select(self, identity, remember=True):
        if not any(item['id'] == identity for item in self.queue):
            return False
        self.current_id = identity
        self._bag = [item for item in self._bag if item != identity]
        if remember and (self._history_index < 0 or self._history[self._history_index] != identity):
            self._history = self._history[:self._history_index+1] + [identity]
            self._history = self._history[-256:]
            self._history_index = len(self._history)-1
        self.track_changed.emit(self.track)
        return True

    def _start(self, identity, remember=True):
        if self.closed or not self._select(identity, remember):
            return
        self._advance_timer.stop()
        self._generation += 1
        self._wants_play = True
        track = self.track
        if not self.available or self.player is None:
            self._wants_play = False
            self._emit_state('stopped')
            self.error.emit(tr('音频播放引擎不可用。'))
            return
        self.player.stop()
        self._position(0)
        self._loaded_id = None
        path = Path(track['path'])
        if not path.is_absolute() or not path.is_file():
            self._duration(0)
            self._fail(tr('找不到音频文件：{name}', name=track.get('title') or path.name))
            return
        self._loaded_id = identity
        source = QUrl.fromLocalFile(str(path))
        # Qt does not emit durationChanged again for an unchanged source. Keep
        # its known duration when restarting the same track after stop/end.
        if self.player.source() != source:
            self._duration(0)
        self.player.setSource(source)
        self.player.play()

    def play_track(self, identity):
        if self.closed:
            return
        self._failed.clear()
        self._start(identity)

    def play(self):
        if self.closed:
            return
        if self.state == 'playing':
            return
        if self.track is None:
            if self.queue:
                self.play_track(self.queue[0]['id'])
            return
        if self.player is not None and self._loaded_id == self.current_id and self.state == 'paused':
            self._wants_play = True
            self.player.play()
        else:
            self.play_track(self.current_id)

    def toggle(self):
        self.pause() if self.state == 'playing' else self.play()

    def pause(self):
        self._wants_play = False
        self._advance_timer.stop()
        if not self.closed and self.player is not None:
            self.player.pause()

    def stop(self):
        self._wants_play = False
        self._advance_timer.stop()
        self._generation += 1
        if not self.closed and self.player is not None:
            self.player.stop()
        self._position(0)
        self._emit_state('stopped')

    def release_source(self):
        """Stop and release the native file handle before deleting local audio.

        QMediaPlayer.stop() keeps its source loaded, including on Windows.
        Queue/catalog edits can then select a surviving track without autoplay.
        """
        if self.closed:
            return
        self.stop()
        if self.player is not None:
            self.player.setSource(QUrl())
        self._loaded_id = None
        self._duration(0)

    def seek(self, milliseconds):
        if not self.closed and self.player is not None and self._loaded_id is not None:
            target = max(0, int(milliseconds))
            if self.duration_ms:
                target = min(target, self.duration_ms)
            self.player.setPosition(target)

    def set_volume(self, value):
        value = min(100, max(0, int(value)))
        if self.closed:
            return
        self.volume = value
        if self.output is not None:
            self.output.setVolume((value/100) ** 2)
        self.volume_changed.emit(value)

    def set_mode(self, value):
        if value not in ('order', 'shuffle'):
            raise ValueError('Unknown playback order')
        if self.closed:
            return
        self.play_mode = value
        self._bag.clear()
        self.mode_changed.emit(value)

    def _candidate(self, automatic=False, failed=False):
        ids = [item['id'] for item in self.queue if item['id'] not in self._failed]
        if not ids:
            return None
        if self.play_mode == 'shuffle':
            self._bag = [identity for identity in self._bag if identity in ids and identity != self.current_id]
            if not self._bag:
                self._bag = [identity for identity in ids if identity != self.current_id]
                random.shuffle(self._bag)
            return self._bag.pop() if self._bag else (ids[0] if not failed else None)
        all_ids = [item['id'] for item in self.queue]
        start = all_ids.index(self.current_id) if self.current_id in all_ids else -1
        for offset in range(1, len(all_ids)+1):
            index = start + offset
            if automatic and index >= len(all_ids):
                return None
            identity = all_ids[index % len(all_ids)]
            if identity in ids:
                return identity
        return None

    def next(self):
        if self.closed:
            return
        self._failed.clear()
        if self.play_mode == 'shuffle' and 0 <= self._history_index < len(self._history)-1:
            self._history_index += 1
            self._start(self._history[self._history_index], False)
            return
        identity = self._candidate()
        if identity is not None:
            self._start(identity)

    def previous(self):
        if self.closed or not self.queue:
            return
        self._failed.clear()
        if self.play_mode == 'shuffle' and self._history_index > 0:
            self._history_index -= 1
            self._start(self._history[self._history_index], False)
        else:
            ids = [item['id'] for item in self.queue]
            index = ids.index(self.current_id) if self.current_id in ids else 0
            self._start(ids[(index-1) % len(ids)])

    def _schedule_advance(self, reason):
        self._advance_reason = reason
        self._advance_generation = self._generation
        self._advance_timer.start(0)

    def _media_status(self, status):
        if self.closed:
            return
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._wants_play:
            self._failed.clear()
            self._schedule_advance('end')

    def _media_error(self, code, text):
        if self.closed or not self._wants_play or self.track is None:
            return
        self._fail(tr('无法播放 {name}：{error}', name=self.track.get('title') or Path(self.track['path']).name,
                      error=text))

    def _fail(self, text):
        if self.current_id in self._failed:
            return
        self._failed.add(self.current_id)
        self.error.emit(text)
        self._schedule_advance('failed')

    def _deferred_advance(self):
        if self.closed or not self._wants_play or self._advance_generation != self._generation:
            return
        identity = self._candidate(automatic=True, failed=self._advance_reason == 'failed')
        if identity is None:
            exhausted = self._advance_reason == 'failed'
            self.stop()
            if exhausted:
                self.error.emit(tr('歌单中没有可播放的文件。'))
        else:
            self._start(identity)

    def shutdown(self):
        """Idempotent; call before deleting QApplication and its audio devices."""
        if self.closed:
            return
        self.stop()
        self.closed = True
        if self.player is not None:
            self.player.setSource(QUrl())
            self.player.setAudioOutput(None)
            self.player.deleteLater()
            self.player = None
        if self.output is not None:
            self.output.deleteLater()
            self.output = None
        self.queue.clear()
        self._bag.clear()
        self._history.clear()
        self.current_id = None
        self.available = False
