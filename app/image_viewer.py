"""Shared, resizable ASCII detail view; zoom always starts from the source bytes."""
from qt.core import (QComboBox, QDialog, QEvent, QHBoxLayout, QLabel, QPixmap,
                     QPushButton, QScrollArea, QTimer, Qt, QVBoxLayout)
from i18n import register, tr
from preferences import get_image_mode, set_image_mode

register({
    '字符画细节': ('ASCII image details', 'ASCII画像の詳細'),
    '适合窗口': ('Fit window', 'ウィンドウに合わせる'),
    '缩放': ('Zoom', '倍率'),
    '100%（原始尺寸）': ('100% (original size)', '100%（元のサイズ）'),
    '拖动右下角可调整窗口；放大后可滚动查看整图。':
        ('Drag the bottom-right corner to resize; scroll to inspect the enlarged image.',
         '右下隅をドラッグしてサイズ変更。拡大後はスクロールして全体を確認できます。'),
    '图片不可用': ('Image unavailable', '画像を利用できません'),
    '显示尺寸：{width} × {height}': ('Display size: {width} × {height}', '表示サイズ：{width} × {height}'),
    '关闭': ('Close', '閉じる'),
})


class AsciiImageDialog(QDialog):
    def __init__(self, data, parent=None, title=None, empty_text=None):
        super().__init__(parent)
        self.data = data
        self.empty_text = empty_text
        self.cleaned = False
        self.source_size = None
        self.source_error = None
        if data:
            try:
                # Uses the same bounded raster/SVG decoder as normal reading.
                from ascii_art import _decode
                self.source_size = _decode(data).size
            except (ValueError, OSError, TypeError) as error:
                self.source_error = str(error)
        self.setWindowTitle(title or tr('字符画细节'))
        self.resize(680, 780)
        self.setMinimumSize(360, 360)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem(tr('彩色字符画'), 'color')
        self.mode.addItem(tr('黑白字符画'), 'mono')
        self.mode.setCurrentIndex(self.mode.findData(get_image_mode()))
        controls.addWidget(self.mode)
        controls.addWidget(QLabel(tr('缩放')))
        self.zoom = QComboBox()
        self.zoom.addItem(tr('适合窗口'), 'fit')
        self.zoom.addItem(tr('100%（原始尺寸）'), 1.0)
        self.zoom.addItem('150%', 1.5)
        self.zoom.addItem('200%', 2.0)
        controls.addWidget(self.zoom)
        controls.addStretch()
        layout.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setStyleSheet('QScrollArea { background: white; }')
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet('background:white;')
        self.scroll.setWidget(self.preview)
        self.scroll.viewport().installEventFilter(self)
        layout.addWidget(self.scroll, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        hint = QLabel(tr('拖动右下角可调整窗口；放大后可滚动查看整图。'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        close = QPushButton(tr('关闭'))
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(90)
        self.redraw_timer.timeout.connect(self.redraw)
        self.restore_timer = QTimer(self)
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self.restore_scroll)
        self._position = (0.5, 0.5)
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.zoom.currentIndexChanged.connect(self.redraw)
        self.finished.connect(self.cleanup)
        self.redraw_timer.start(0)

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.Resize and not self.cleaned
                and watched is self.scroll.viewport() and self.zoom.currentData() == 'fit'
                and hasattr(self, 'redraw_timer')):
            self.redraw_timer.start()
        return super().eventFilter(watched, event)

    def change_mode(self, *_):
        try:
            set_image_mode(self.mode.currentData())
        except OSError as error:
            self.mode.blockSignals(True)
            self.mode.setCurrentIndex(self.mode.findData(get_image_mode()))
            self.mode.blockSignals(False)
            self.status.setText(tr('无法保存显示设置') + ': ' + str(error))
            return
        self.redraw()

    def redraw(self, *_):
        if self.cleaned:
            return
        self.redraw_timer.stop()
        bars = (self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar())
        self._position = tuple(bar.value()/bar.maximum() if bar.maximum() else .5 for bar in bars)
        if not self.source_size:
            self.preview.clear()
            self.preview.setText(self.empty_text or tr('图片不可用'))
            self.preview.setFixedSize(max(1, self.scroll.viewport().width()-4),
                                      max(1, self.scroll.viewport().height()-4))
            self.zoom.setEnabled(False)
            self.status.setText(self.source_error or '')
            return
        value = self.zoom.currentData()
        if value == 'fit':
            width = max(16, self.scroll.viewport().width()-4)
            height = max(16, self.scroll.viewport().height()-4)
        else:
            width = max(1, round(self.source_size[0]*value))
            height = max(1, round(self.source_size[1]*value))
        try:
            from ascii_art import render_ascii
            image = render_ascii(self.data, width, height, mode=self.mode.currentData())
            self.preview.setPixmap(QPixmap.fromImage(image))
            self.preview.setFixedSize(image.size())
            self.status.setText(tr('显示尺寸：{width} × {height}', width=image.width(), height=image.height()))
            self.restore_timer.start(0)
        except (ValueError, OSError, TypeError) as error:
            self.preview.clear()
            self.preview.setText(tr('图片不可用'))
            self.status.setText(str(error))

    def restore_scroll(self):
        if not self.cleaned:
            for bar, ratio in zip((self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()), self._position):
                bar.setValue(round(bar.maximum()*ratio))

    def cleanup(self, *_):
        if self.cleaned:
            return
        self.cleaned = True
        self.redraw_timer.stop()
        self.restore_timer.stop()
        self.scroll.viewport().removeEventFilter(self)
        self.data = None
