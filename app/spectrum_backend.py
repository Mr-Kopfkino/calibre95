"""On-demand CAVA analysis of only the music file currently being played.

The bundled Qt 6.7 player cannot expose output buffers. A single bounded native
FFmpeg reader therefore samples the same local file at the player's position.
It never emits audio or records microphones/system audio. Hidden/paused/off
views close the decoder and leave the worker asleep on a condition variable.
"""
import ctypes
import os
from pathlib import Path
import threading
import time

from qt.core import QObject, QThread, QTimer, pyqtSignal

ROOT = Path(__file__).resolve().parents[1]
BARS = 18
RATE = 22050
SAMPLES = 1102


class NativeSpectrum:
    """Worker-thread-only native handles, with pinned public ABI declarations."""
    def __init__(self):
        binaries = ROOT / 'runtime/app/bin'
        self.directory = os.add_dll_directory(str(binaries)) if os.name == 'nt' else None
        self.avutil = ctypes.CDLL(str(binaries / 'avutil-58.dll'))
        self.pcm = ctypes.CDLL(str(ROOT / 'app/native/pcm95.dll'))
        self.cava = ctypes.CDLL(str(ROOT / 'app/native/cava95.dll'))
        pointer = ctypes.c_void_p
        floats = ctypes.POINTER(ctypes.c_float)
        self.pcm.c95_pcm_open.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        self.pcm.c95_pcm_open.restype = pointer
        self.pcm.c95_pcm_read.argtypes = [pointer, ctypes.c_int64, floats, ctypes.c_int]
        self.pcm.c95_pcm_read.restype = ctypes.c_int
        for name in ('c95_pcm_cancel', 'c95_pcm_close'):
            getattr(self.pcm, name).argtypes = [pointer]
            getattr(self.pcm, name).restype = None
        for name in ('c95_pcm_frames', 'c95_pcm_seeks'):
            getattr(self.pcm, name).argtypes = [pointer]
            getattr(self.pcm, name).restype = ctypes.c_uint64
        self.pcm.c95_pcm_error.argtypes = []
        self.pcm.c95_pcm_error.restype = ctypes.c_char_p
        self.cava.c95_cava_create.argtypes = [ctypes.c_int, ctypes.c_int]
        self.cava.c95_cava_create.restype = pointer
        self.cava.c95_cava_process.argtypes = [pointer, floats, ctypes.c_int, floats]
        self.cava.c95_cava_process.restype = ctypes.c_int
        self.cava.c95_cava_reset.argtypes = [pointer]
        self.cava.c95_cava_reset.restype = ctypes.c_int
        self.cava.c95_cava_destroy.argtypes = [pointer]
        self.cava.c95_cava_destroy.restype = None
        self.analyzer = self.cava.c95_cava_create(BARS, RATE)
        if not self.analyzer:
            raise RuntimeError('CAVA initialization failed')
        self.reader = None
        self.path = None
        self.position = None
        self.pcm_samples = (ctypes.c_float * SAMPLES)()
        self.bars = (ctypes.c_float * BARS)()

    def close_source(self):
        if self.reader:
            self.pcm.c95_pcm_close(self.reader)
            self.reader = None
        self.path = self.position = None
        if self.analyzer:
            self.cava.c95_cava_reset(self.analyzer)

    def analyze(self, path, position):
        if path != self.path:
            self.close_source()
            self.reader = self.pcm.c95_pcm_open(str(ROOT / 'runtime/app/bin'), path)
            if not self.reader:
                error = self.pcm.c95_pcm_error()
                raise RuntimeError(error.decode('utf-8', 'replace') if error else 'Audio analysis could not open file')
            self.path = path
        if self.position is not None and abs(position-self.position-50) > 300:
            self.cava.c95_cava_reset(self.analyzer)
        self.position = position
        received = self.pcm.c95_pcm_read(self.reader, int(position), self.pcm_samples, SAMPLES)
        if received < 0:
            raise RuntimeError('Audio analysis seek/decode failed')
        if self.cava.c95_cava_process(self.analyzer, self.pcm_samples, SAMPLES, self.bars):
            raise RuntimeError('CAVA analysis failed')
        return list(self.bars), received, int(self.pcm.c95_pcm_frames(self.reader)), int(self.pcm.c95_pcm_seeks(self.reader))

    def close(self):
        self.close_source()
        if self.analyzer:
            self.cava.c95_cava_destroy(self.analyzer)
            self.analyzer = None
        if self.directory:
            self.directory.close()
            self.directory = None


class SpectrumWorker(QThread):
    result = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, parent):
        super().__init__(parent)
        self.condition = threading.Condition()
        self.pending = None
        self.stopping = False
        self.close_requested = False
        self.released = threading.Event()
        self.released.set()
        self.stats = {'source_open': False, 'busy': False, 'frames': 0,
                      'decoded_frames': 0, 'seeks': 0, 'cpu_ms': 0.0,
                      'samples': 0, 'dropped': 0}

    def submit(self, generation, path, position):
        with self.condition:
            if self.stopping:
                return
            if self.pending is not None:
                self.stats['dropped'] += 1
            self.pending = (generation, path, position)
            self.condition.notify()

    def release(self, wait=False):
        with self.condition:
            self.pending = None
            self.close_requested = True
            if self.isRunning():
                self.released.clear()
                self.condition.notify()
        # A local-file read has a native deadline. If opening a file, its probe
        # has a separate bounded deadline; wait until every handle is released.
        if wait and self.isRunning() and not self.released.wait(3.0):
            raise OSError('Audio visualization did not release its file in time')

    def snapshot(self):
        with self.condition:
            return dict(self.stats)

    def run(self):
        native = None
        try:
            while True:
                with self.condition:
                    while self.pending is None and not self.close_requested and not self.stopping:
                        self.condition.wait()
                    if self.close_requested or self.stopping:
                        if native:
                            native.close_source()
                        self.stats['source_open'] = self.stats['busy'] = False
                        self.close_requested = False
                        self.released.set()
                    if self.stopping:
                        break
                    request, self.pending = self.pending, None
                    if request is None:
                        continue
                    self.stats['busy'] = True
                generation, path, position = request
                started = time.thread_time()
                try:
                    if native is None:
                        native = NativeSpectrum()
                    levels, received, decoded, seeks = native.analyze(path, position)
                    with self.condition:
                        self.stats['frames'] += 1
                        self.stats['samples'] += received
                        self.stats['decoded_frames'] = decoded
                        self.stats['seeks'] = seeks
                        self.stats['source_open'] = True
                    self.result.emit(generation, levels)
                except Exception as error:
                    if native:
                        native.close_source()
                    with self.condition:
                        self.stats['source_open'] = False
                    self.failed.emit(generation, str(error))
                finally:
                    with self.condition:
                        self.stats['busy'] = False
                        self.stats['cpu_ms'] += (time.thread_time()-started)*1000
        finally:
            if native:
                native.close()
            with self.condition:
                self.stats['source_open'] = self.stats['busy'] = False
                self.released.set()

    def shutdown(self):
        with self.condition:
            self.stopping = True
            self.pending = None
            self.condition.notify()
        if self.isRunning():
            self.wait()


class SpectrumSession(QObject):
    levels_changed = pyqtSignal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.enabled = True
        self.closed = False
        self.available = True
        self.last_error = ''
        self.active = False
        self.visible = set()
        self.generation = 0
        self.failed_path = None
        self.worker = SpectrumWorker(self)
        self.worker.result.connect(self._result)
        self.worker.failed.connect(self._failed)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        controller.state_changed.connect(self._sync)
        controller.track_changed.connect(self._track_changed)

    def set_visible(self, token, visible):
        if self.closed:
            return
        self.visible.add(token) if visible else self.visible.discard(token)
        self._sync()

    def set_enabled(self, enabled):
        if self.closed:
            return
        self.enabled = bool(enabled)
        if self.enabled:
            self.failed_path = None
            self.available = True
        self._sync()

    def _track_changed(self, *_):
        track = self.controller.track
        if track is None or track['path'] != self.failed_path:
            self.failed_path = None
            self.available = True
        self.generation += 1
        self.levels_changed.emit([0.0]*BARS)
        self._sync()

    def _sync(self, *_):
        track = self.controller.track
        active = bool(not self.closed and self.enabled and self.visible and
                      self.controller.state == 'playing' and track and
                      track['path'] != self.failed_path)
        if active == self.active:
            return
        self.active = active
        self.generation += 1
        if active:
            if not self.worker.isRunning():
                self.worker.start()
            self.timer.start()
            self._tick()
        else:
            self.timer.stop()
            self.worker.release()
            self.levels_changed.emit([0.0]*BARS)

    def _tick(self):
        track = self.controller.track
        if not self.active or not track:
            return
        # Read Qt on its GUI thread; position_changed can be much less frequent
        # than painting. The worker receives only immutable primitives.
        player = self.controller.player
        position = int(player.position()) if player is not None else self.controller.position_ms
        self.worker.submit(self.generation, track['path'], position)

    def _result(self, generation, levels):
        if not self.closed and self.active and generation == self.generation:
            self.levels_changed.emit(levels)

    def _failed(self, generation, error):
        if self.closed or generation != self.generation:
            return
        self.last_error = error
        self.available = False
        track = self.controller.track
        self.failed_path = track['path'] if track else None
        self._sync()

    def release_source(self):
        if self.closed:
            return
        self.generation += 1
        self.worker.release(wait=True)
        self.levels_changed.emit([0.0]*BARS)

    def snapshot(self):
        result = self.worker.snapshot()
        result.update(active=self.active, available=self.available, last_error=self.last_error,
                      worker_running=self.worker.isRunning(), timer_active=self.timer.isActive(),
                      analysed_frames=result['frames'], decoder_open=result['source_open'])
        return result

    metrics = snapshot

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.active = False
        self.timer.stop()
        self.visible.clear()
        self.generation += 1
        self.worker.shutdown()
