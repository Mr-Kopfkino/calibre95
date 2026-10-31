"""Small, unlabelled pixel spectrum: decoration beside the player's clock."""
import math
from qt.core import QColor, QEvent, QPainter, QSizePolicy, Qt, QWidget
from i18n import register, tr

register({
    '像素频谱': ('Pixel spectrum', 'ピクセルスペクトラム'),
    '显示像素频谱': ('Show pixel spectrum', 'ピクセルスペクトラムを表示'),
    '右键可关闭或开启像素频谱': ('Right-click to turn the pixel spectrum off or on',
                                '右クリックでスペクトラムの表示を切り替えます'),
})


class PixelSpectrum(QWidget):
    """Integer rectangles only; no timer, gradients, blur, text or GPU surface.

    The shared analysis session provides at most 20 frames per second. Hidden
    views unsubscribe, including a minimized parent window; integer quantizing
    avoids repainting a frame when its visible pixels would be unchanged.
    """
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.token = id(self)
        self.levels = ()
        self.enabled = True
        self._subscribed = False
        self._watched_window = None
        self.paint_count = 0
        self.setFixedHeight(38)
        self.setMinimumWidth(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(tr('像素频谱'))
        self.setToolTip(tr('右键可关闭或开启像素频谱'))
        self.session.levels_changed.connect(self.set_levels)
        # Capture only session/token: the Qt destroyed signal must not form a
        # cycle retaining this widget, or leave an invisible consumer running.
        session_ref, token = self.session, self.token
        self.destroyed.connect(lambda: session_ref.set_visible(token, False))

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.setVisible(self.enabled)
        self.sync_visibility()

    def set_levels(self, levels):
        if not self._subscribed:
            return
        pixels = tuple(min(8, max(0, int(float(value)*8+.5)))
                       if math.isfinite(float(value)) else 0 for value in levels)
        if pixels != self.levels:
            self.levels = pixels
            self.update()

    def sync_visibility(self):
        window = self.window()
        active = bool(self.enabled and self.isVisible() and window.isVisible()
                      and not window.isMinimized())
        if active != self._subscribed:
            self._subscribed = active
            self.session.set_visible(self.token, active)
        if not active and self.levels:
            self.levels = ()
            self.update()

    def showEvent(self, event):
        super().showEvent(event)
        window = self.window()
        if window is not self._watched_window:
            if self._watched_window is not None:
                self._watched_window.removeEventFilter(self)
            self._watched_window = window
            window.installEventFilter(self)
        self.sync_visibility()

    def hideEvent(self, event):
        self.sync_visibility()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.Show,
                            QEvent.Type.Hide, QEvent.Type.Close):
            self.sync_visibility()
        return False

    def paintEvent(self, event):
        self.paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor('#080c08'))
        count = len(self.levels) or 18
        pitch = max(3, (self.width()-12)//count)
        bar_width = max(1, pitch-2)
        left = (self.width()-(count*pitch-2))//2
        base = self.height()-5
        dark, green = QColor('#123a19'), QColor('#60d878')
        # One dim baseline is enough to show the meter when no music is playing.
        for bar in range(count):
            x = left+bar*pitch
            painter.fillRect(x, base, bar_width, 2, dark)
            steps = self.levels[bar] if bar < len(self.levels) else 0
            for row in range(steps):
                painter.fillRect(x, base-1-row*4, bar_width, 3, green)
        painter.end()
