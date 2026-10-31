"""Native Win95 music desk, stepped lyric display and shared reading controls."""
from pathlib import Path
from qt.core import (QAbstractItemView, QCheckBox, QColor, QComboBox, QDialog,
    QFileDialog, QFontMetrics, QHBoxLayout, QHeaderView, QImage, QInputDialog,
    QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPainter, QPlainTextEdit,
    QPushButton, QRect, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
    QTimer, Qt, QVBoxLayout, QWidget)
from theme import pixel_font
from i18n import get_language, register, tr
from lyrics import line_index
from preferences import get_image_mode
from spectrum_ui import PixelSpectrum

MUSIC_HELP = ('音乐：点击音乐按钮或 Ctrl+M 导入本地音频、创建歌单。\n'
              '阅读时会继续播放，也可用阅读器底部的控制条操作。\n'
              '显示歌词支持内嵌歌词与同名 .lrc；关闭后显示 ASCII 音频封面。\n'
              '无封面图可自定义字符画或图片。导入的音频副本保存在 Data/Music。\n'
              '右键时间显示区可关闭或开启像素频谱。')

register({
    '音乐播放器': ('Music player', '音楽プレイヤー'),
    '音乐': ('Music', '音楽'),
    '导入音乐': ('Import music', '音楽を追加'),
    '音频文件 (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav *.wma *.aiff *.aif)':
        ('Audio files (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav *.wma *.aiff *.aif)',
         '音声ファイル (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav *.wma *.aiff *.aif)'),
    '全部音乐': ('All music', 'すべての音楽'),
    '我的歌单': ('My playlists', 'プレイリスト'),
    '新建歌单': ('New playlist', '新規プレイリスト'),
    '歌单名称': ('Playlist name', 'プレイリスト名'),
    '重命名歌单': ('Rename playlist', '名前を変更'),
    '删除歌单': ('Delete playlist', 'プレイリストを削除'),
    '只删除歌单，音乐仍保留在全部音乐中。':
        ('Delete this playlist? Tracks stay in All music.', 'プレイリストだけを削除します。曲はすべての音楽に残ります。'),
    '曲名': ('Title', '曲名'), '歌手': ('Artist', 'アーティスト'),
    '专辑': ('Album', 'アルバム'), '时长': ('Length', '長さ'),
    '播放': ('Play', '再生'), '暂停': ('Pause', '一時停止'),
    '停止': ('Stop', '停止'), '上一首': ('Previous', '前の曲'),
    '下一首': ('Next', '次の曲'), '音量': ('Volume', '音量'),
    '顺序播放': ('In order', '順番に再生'), '随机播放': ('Shuffle', 'シャッフル'),
    '显示歌词': ('Show lyrics', '歌詞を表示'),
    '载入歌词…': ('Load lyrics…', '歌詞を読み込む…'),
    '歌词文件 (*.lrc *.txt)': ('Lyrics (*.lrc *.txt)', '歌詞 (*.lrc *.txt)'),
    '无封面图…': ('No-cover art…', '代替画像…'),
    '加入歌单…': ('Add to playlist…', 'プレイリストに追加…'),
    '移出歌单': ('Remove from playlist', 'リストから外す'),
    '从音乐库移除': ('Remove from library', '音楽ライブラリから削除'),
    '将删除选中音乐的库内副本，原始音频文件保留。':
        ('Remove selected library copies? Original audio files are kept.', '選択した曲のコピーを削除します。元の音声ファイルは保持されます。'),
    '选择歌单': ('Choose playlist', 'プレイリストを選択'),
    '先创建一个歌单。': ('Create a playlist first.', '先にプレイリストを作成してください。'),
    '未选择音乐': ('No track selected', '曲が選択されていません'),
    '导入本地音乐，开始边读边听。': ('Import local music to listen while reading.', '音楽を追加して、読書中に聴けます。'),
    '双击曲目播放 · 音乐在阅读时继续播放':
        ('Double-click a track · Music continues while reading', '曲をダブルクリックで再生 · 読書中も再生を続けます'),
    '同步歌词': ('Synced lyrics', '同期歌詞'),
    '未同步歌词 · 可滚动查看': ('Untimed lyrics · Scroll to read', '時刻なし歌詞 · スクロールできます'),
    '无歌词 · 显示封面': ('No lyrics · Showing artwork', '歌詞なし · 画像を表示'),
    'ASCII 音频封面': ('ASCII album art', 'ASCIIアルバム画像'),
    '自定义占位字符画': ('Custom placeholder art', '代替ASCIIアート'),
    '输入字符画，或选择图片自动转换为 ASCII。':
        ('Enter text art, or choose an image to convert to ASCII.', '文字アートを入力するか、画像をASCIIに変換します。'),
    '字符画文本': ('Text art', '文字アート'),
    '自定义图片': ('Custom image', 'カスタム画像'),
    '选择图片…': ('Choose image…', '画像を選択…'),
    '恢复默认': ('Reset default', '初期値に戻す'),
    '保存': ('Save', '保存'), '取消': ('Cancel', 'キャンセル'),
    '图片 (*.png *.jpg *.jpeg *.webp *.bmp)':
        ('Images (*.png *.jpg *.jpeg *.webp *.bmp)', '画像 (*.png *.jpg *.jpeg *.webp *.bmp)'),
    '最多 40 行、每行 100 个字符。': ('Up to 40 lines and 100 characters per line.', '最大40行、各行100文字まで。'),
    '已停止': ('Stopped', '停止中'), '正在播放': ('Playing', '再生中'),
    '已暂停': ('Paused', '一時停止中'),
    '当前播放': ('NOW PLAYING', '再生中の曲'),
    '向上移动': ('Move up', '上へ移動'), '向下移动': ('Move down', '下へ移動'),
    MUSIC_HELP: (
        'Music: click Music or press Ctrl+M to import local audio and create playlists.\n'
        'Music continues while reading; controls are also at the bottom of the reader.\n'
        'Use Show lyrics for embedded or matching .lrc lyrics; turn it off for ASCII album art.\n'
        'No-cover art lets you supply your own text art or image. Imported music is copied to Data/Music.\n'
        'Right-click the time display to turn the pixel spectrum off or on.',
        '音楽：音楽ボタンまたはCtrl+Mで音声を追加し、プレイリストを作成します。\n'
        '読書中も再生され、閲覧画面の下部で操作できます。\n'
        '「歌詞を表示」で内蔵歌詞や同名の.lrcを表示し、オフにするとASCII画像になります。\n'
        '「代替画像」で文字アートや画像を指定できます。音楽はData/Musicにコピーされます。\n'
        '時間表示を右クリックしてスペクトラムの表示を切り替えられます。'),
    '{count} 首音乐': ('{count} tracks', '{count} 曲'),
    '音乐导入尚未完成，请稍候。': ('Wait for the music import to finish.', '音楽の追加が完了するまでお待ちください。'),
})

DEFAULT_ART = r'''     __________________
    |  CALIBRE 95      |
    |  .------------.  |
    |  |  o      o  |  |
    |  |    ____    |  |
    |  '------------'  |
    |  [<<] [>] [>>]   |
    |__________________|
           MUSIC'''


def time_text(value):
    seconds = max(0, int(value or 0)//1000)
    return f'{seconds//60:02d}:{seconds%60:02d}'


def alert(parent, text, question=False):
    box = QMessageBox(parent)
    box.setWindowTitle(tr('音乐播放器'))
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(str(text))
    yes = box.addButton(tr('确定'), QMessageBox.ButtonRole.AcceptRole)
    if question:
        no = box.addButton(tr('取消'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no)
    box.exec()
    answer = box.clickedButton() is yes
    box.deleteLater()
    return answer


class PixelTicker(QWidget):
    """Fixed-pixel marquee, inspired by classic LCD/Winamp text displays."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ''
        self.offset = self.ticks = 0
        self.setMinimumHeight(27)
        self.setMinimumWidth(80)
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.step)

    def set_text(self, text):
        text = '  /  '.join(str(text or '').splitlines())
        if self.text != text:
            self.text = text
            self.offset = self.ticks = 0
            self.setToolTip(text)
            self.update()
        self.sync_timer()

    def sync_timer(self):
        if self.isVisible() and QFontMetrics(pixel_font()).horizontalAdvance(self.text) > self.width()-12:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def step(self):
        self.ticks += 1
        if self.ticks > 5:
            self.offset += 4
            total = QFontMetrics(pixel_font()).horizontalAdvance(self.text + '   ***   ')
            if self.offset >= total:
                self.offset = self.ticks = 0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#101810'))
        painter.setPen(QColor('#80ff80'))
        painter.setFont(pixel_font())
        painter.setClipRect(self.rect().adjusted(5, 2, -5, -2))
        metrics = QFontMetrics(painter.font())
        baseline = (self.height()-metrics.height())//2 + metrics.ascent()
        painter.drawText(6-self.offset, baseline, self.text)
        if self.offset:
            length = metrics.horizontalAdvance(self.text + '   ***   ')
            painter.drawText(6-self.offset+length, baseline, self.text)

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_timer()


class LyricsCanvas(QWidget):
    """No blur: clipped pixel text moves in integer steps to the active line."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = {'lines': [], 'timed': False}
        self.current_index = -1
        self.offset = self.target = 0
        self.horizontal = self.ticks = 0
        self.line_height = 28
        self._layout_cache = None
        self.position_ms = 0
        self.setMinimumHeight(180)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.animate)

    def set_document(self, document):
        self.document = document or {'lines': [], 'timed': False}
        self._layout_cache = None
        self.current_index = -1
        self.offset = self.target = self.horizontal = self.ticks = 0
        self.update()
        if self.isVisible():
            self.timer.start()

    def set_position(self, position):
        self.position_ms = position
        if not self.document.get('timed'):
            return
        index = line_index(self.document, position)
        if index != self.current_index:
            self.current_index = index
            rows = self.display_rows()
            self.target = rows[max(0, index)]['center']-rows[0]['center'] if rows else 0
            self.horizontal = self.ticks = 0
            self.update()

    def display_rows(self):
        """Keep translations together; wrap untimed lyrics without losing text."""
        width = max(16, self.width()-24)
        key = (width, get_language())
        if self._layout_cache is not None and self._layout_cache[0] == key:
            return self._layout_cache[1]
        rows, top = [], 0
        metrics = QFontMetrics(pixel_font(16, get_language()))
        timed = self.document.get('timed')
        for entry in self.document.get('lines', []):
            parts = str(entry.get('text', '')).splitlines() or ['']
            if not timed:
                wrapped = []
                for part in parts:
                    line, advance = '', 0
                    for char in part:
                        size = metrics.horizontalAdvance(char)
                        if line and advance+size > width:
                            wrapped.append(line)
                            line, advance = '', 0
                        line += char
                        advance += size
                    wrapped.append(line)
                for part in wrapped:
                    rows.append({'parts': [part], 'center': top+self.line_height//2,
                                 'height': self.line_height})
                    top += self.line_height
            else:
                height = len(parts)*self.line_height
                rows.append({'parts': parts, 'center': top+height//2, 'height': height})
                top += height
        self._layout_cache = (key, rows)
        return rows

    def animate(self):
        delta = self.target-self.offset
        if delta:
            step = min(abs(delta), max(2, int(abs(delta)/10)*2))
            self.offset += step if delta > 0 else -step
        self.ticks += 1
        if self.ticks > 16 and self.ticks % 2 == 0:
            self.horizontal += 2
        if delta or self.current_index >= 0:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#101810'))
        painter.setFont(pixel_font(16, get_language()))
        painter.setClipRect(self.rect().adjusted(6, 2, -6, -2))
        metrics = QFontMetrics(painter.font())
        rows = self.display_rows()
        timed = self.document.get('timed')
        origin = self.height()//2-rows[0]['center'] if timed and rows else 8
        for index, row in enumerate(rows):
            y = origin + row['center']-self.offset
            top = y-row['height']//2
            if top+row['height'] < 0 or top > self.height():
                continue
            current = timed and index == self.current_index
            if current:
                painter.fillRect(QRect(4, top, self.width()-8, row['height']), QColor('#000080'))
            painter.setPen(QColor('#ffff8a' if current else '#7fac8d'))
            for part, text in enumerate(row['parts']):
                text = text or '...'
                baseline = top+part*self.line_height+self.line_height//2+metrics.ascent()-metrics.height()//2
                width = metrics.horizontalAdvance(text)
                if current and width > self.width()-24:
                    span = width + 48
                    shift = self.horizontal % span
                    painter.drawText(12-shift, baseline, text)
                    painter.drawText(12-shift+span, baseline, text)
                else:
                    text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, self.width()-24)
                    painter.drawText((self.width()-metrics.horizontalAdvance(text))//2, baseline, text)

    def wheelEvent(self, event):
        if not self.document.get('timed'):
            maximum = max(0, len(self.display_rows())*self.line_height-self.height()+16)
            self.target = min(maximum, max(0, self.target-round(event.angleDelta().y()/120)*self.line_height*2))
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_cache = None
        if not self.document.get('timed'):
            maximum = max(0, len(self.display_rows())*self.line_height-self.height()+16)
            self.target = min(maximum, self.target)

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


class ArtworkCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.text = DEFAULT_ART
        self.image = None
        self.setMinimumHeight(180)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.render)

    def set_content(self, data=None, text=None):
        self.data = data
        self.text = text or DEFAULT_ART
        self.image = None
        self.timer.start(0)

    def render(self):
        width, height = max(1, self.width()-12), max(1, self.height()-12)
        self.image = None
        if self.data:
            try:
                from ascii_art import render_ascii
                self.image = render_ascii(self.data, width, height, mode=get_image_mode())
            except (ValueError, OSError, TypeError):
                pass
        if self.image is None:
            lines = (self.text or DEFAULT_ART).splitlines()[:40]
            lines = [line[:100] for line in lines] or [' ']
            font = pixel_font(16)
            metrics = QFontMetrics(font)
            source = QImage(max(1, max(metrics.horizontalAdvance(x) for x in lines)+16),
                            len(lines)*16+16, QImage.Format.Format_RGB32)
            source.fill(QColor('#ffffff'))
            painter = QPainter(source)
            painter.setFont(font)
            painter.setPen(QColor('#000080'))
            for i, line in enumerate(lines):
                painter.drawText(8, 8+metrics.ascent()+i*16, line)
            painter.end()
            self.image = source.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.FastTransformation)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('white'))
        if self.image is not None:
            painter.drawImage((self.width()-self.image.width())//2,
                              (self.height()-self.image.height())//2, self.image)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start(0)


class PlaceholderDialog(QDialog):
    def __init__(self, service, parent):
        super().__init__(parent)
        self.service = service
        self.image_path = None
        self.setWindowTitle(tr('自定义占位字符画'))
        self.resize(630, 530)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr('输入字符画，或选择图片自动转换为 ASCII。')))
        self.kind = QComboBox()
        self.kind.addItem(tr('字符画文本'), 'text')
        self.kind.addItem(tr('自定义图片'), 'image')
        self.kind.setCurrentIndex(max(0, self.kind.findData(service.settings().get('placeholder_kind', 'text'))))
        layout.addWidget(self.kind)
        self.text = QPlainTextEdit(service.settings().get('placeholder_text') or DEFAULT_ART)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text, 1)
        row = QHBoxLayout()
        choose = QPushButton(tr('选择图片…'))
        choose.clicked.connect(self.choose_image)
        reset = QPushButton(tr('恢复默认'))
        reset.clicked.connect(self.reset)
        row.addWidget(choose)
        row.addWidget(reset)
        layout.addLayout(row)
        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        row = QHBoxLayout()
        row.addStretch()
        save = QPushButton(tr('保存'))
        save.clicked.connect(self.save)
        cancel = QPushButton(tr('取消'))
        cancel.clicked.connect(self.reject)
        row.addWidget(save)
        row.addWidget(cancel)
        layout.addLayout(row)

    def reset(self):
        self.kind.setCurrentIndex(0)
        self.text.setPlainText(DEFAULT_ART)
        self.image_path = None
        self.file_label.clear()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('选择图片…'), '',
            tr('图片 (*.png *.jpg *.jpeg *.webp *.bmp)'), options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self.image_path = path
            self.file_label.setText(Path(path).name)
            self.kind.setCurrentIndex(1)

    def save(self):
        text = self.text.toPlainText()
        if len(text.splitlines()) > 40 or any(len(x) > 100 for x in text.splitlines()):
            alert(self, tr('最多 40 行、每行 100 个字符。'))
            return
        try:
            if self.image_path:
                self.service.store.set_placeholder_image(self.image_path)
                self.service.set_preferences(placeholder_image=self.service.store.settings().get('placeholder_image'))
            self.service.set_preferences(placeholder_kind=self.kind.currentData(),
                                         placeholder_text=text or DEFAULT_ART)
            self.service.flush_preferences()
            self.accept()
        except (OSError, ValueError) as error:
            alert(self, error)


class MusicBar(QWidget):
    def __init__(self, service, owner, compact=False):
        super().__init__(owner)
        self.service, self.owner = service, owner
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(3)
        open_button = QPushButton(tr('音乐'))
        open_button.setToolTip(tr('音乐播放器'))
        open_button.clicked.connect(self.open_player)
        row.addWidget(open_button)
        self.previous = QPushButton('|<')
        self.previous.setToolTip(tr('上一首'))
        self.previous.clicked.connect(service.controller.previous)
        self.play = QPushButton('>')
        self.play.setToolTip(tr('播放'))
        self.play.clicked.connect(service.controller.toggle)
        self.next = QPushButton('>|')
        self.next.setToolTip(tr('下一首'))
        self.next.clicked.connect(service.controller.next)
        for button in (self.previous, self.play, self.next):
            button.setFixedWidth(37)
            button.setStyleSheet('padding:2px; min-height:18px;')
            row.addWidget(button)
        self.ticker = PixelTicker()
        row.addWidget(self.ticker, 1)
        if compact:
            self.setFixedWidth(390)
            open_button.setStyleSheet('padding:2px 5px; min-height:18px;')
        else:
            self.clock = QLabel('00:00')
            row.addWidget(self.clock)
        service.track_changed.connect(self.refresh)
        service.preferences_changed.connect(self.refresh)
        service.controller.state_changed.connect(self.refresh)
        service.controller.position_changed.connect(self.position)
        self.refresh()

    def open_player(self):
        self.service.show_player(self.owner)

    def refresh(self, *_):
        c = self.service.controller
        self.play.setText('||' if c.state == 'playing' else '>')
        self.play.setToolTip(tr('暂停') if c.state == 'playing' else tr('播放'))
        self.position(c.position_ms)

    def position(self, position):
        track = self.service.current
        text = tr('导入本地音乐，开始边读边听。')
        if track:
            text = track['title'] + ('  -  ' + track.get('artist', '') if track.get('artist') else '')
            lyric = track.get('lyrics') or {}
            index = line_index(lyric, position) if lyric.get('timed') else -1
            if self.service.settings().get('show_lyrics', True) and index >= 0:
                text = lyric['lines'][index]['text'] or '...'
        self.ticker.set_text(text)
        if hasattr(self, 'clock'):
            self.clock.setText(time_text(position))


class MusicDialog(QDialog):
    def __init__(self, service, parent):
        super().__init__(parent)
        self.service = service
        self.view_playlist = service.active_playlist
        self._reloading = False
        self._display_key = None
        self.setWindowTitle('calibre95 · ' + tr('音乐播放器'))
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setSizeGripEnabled(True)
        self.resize(1010, 670)
        self.setMinimumSize(810, 570)
        self.setAcceptDrops(True)
        self.setStyleSheet('''
            QSlider::groove:horizontal {height:6px; background:#808080;
                border:1px solid; border-top-color:#404040; border-left-color:#404040;
                border-bottom-color:white; border-right-color:white;}
            QSlider::handle:horizontal {width:12px; margin:-5px 0; background:#c0c0c0;
                border:2px solid; border-top-color:white; border-left-color:white;
                border-bottom-color:#404040; border-right-color:#404040;}
            QSlider::sub-page:horizontal {background:#000080;}
        ''')
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        tools = QHBoxLayout()
        self.import_button = QPushButton(tr('导入音乐'))
        self.import_button.clicked.connect(self.import_dialog)
        tools.addWidget(self.import_button)
        lyric_button = QPushButton(tr('载入歌词…'))
        lyric_button.clicked.connect(self.load_lyrics)
        tools.addWidget(lyric_button)
        placeholder = QPushButton(tr('无封面图…'))
        placeholder.clicked.connect(self.edit_placeholder)
        tools.addWidget(placeholder)
        tools.addStretch()
        self.show_lyrics = QCheckBox(tr('显示歌词'))
        self.show_lyrics.setChecked(service.settings().get('show_lyrics', True))
        self.show_lyrics.toggled.connect(self.lyrics_toggled)
        tools.addWidget(self.show_lyrics)
        self.play_mode = QComboBox()
        self.play_mode.addItem(tr('顺序播放'), 'order')
        self.play_mode.addItem(tr('随机播放'), 'shuffle')
        self.play_mode.currentIndexChanged.connect(self.mode_changed)
        tools.addWidget(self.play_mode)
        layout.addLayout(tools)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(QLabel(tr('我的歌单')))
        self.playlists = QListWidget()
        self.playlists.setMinimumWidth(145)
        self.playlists.currentItemChanged.connect(self.select_playlist)
        side_layout.addWidget(self.playlists, 1)
        playlist_buttons = QHBoxLayout()
        for label, tooltip, callback in (('+', '新建歌单', self.new_playlist),
                                        ('...', '重命名歌单', self.rename_playlist),
                                        ('X', '删除歌单', self.delete_playlist)):
            button = QPushButton(label)
            button.setStyleSheet('padding:4px;')
            button.setToolTip(tr(tooltip))
            button.clicked.connect(callback)
            playlist_buttons.addWidget(button)
        side_layout.addLayout(playlist_buttons)
        splitter.addWidget(side)
        desk = QWidget()
        desk_layout = QVBoxLayout(desk)
        desk_layout.setContentsMargins(3, 0, 0, 0)
        display_row = QHBoxLayout()
        screen = QWidget()
        screen.setStyleSheet('QWidget#musicScreen {border:2px solid; border-top-color:#404040; border-left-color:#404040; border-right-color:white; border-bottom-color:white;}')
        screen.setObjectName('musicScreen')
        screen_layout = QVBoxLayout(screen)
        screen_layout.setContentsMargins(3, 3, 3, 3)
        screen_layout.setSpacing(0)
        self.lyrics = LyricsCanvas()
        self.artwork = ArtworkCanvas()
        screen_layout.addWidget(self.lyrics)
        screen_layout.addWidget(self.artwork)
        self.display_caption = QLabel()
        screen_layout.addWidget(self.display_caption)
        display_row.addWidget(screen, 1)
        info = QWidget()
        info.setFixedWidth(202)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        caption = QLabel(tr('当前播放'))
        caption.setStyleSheet('background:#000080;color:white;padding:5px;')
        info_layout.addWidget(caption)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(48)
        info_layout.addWidget(self.title)
        self.artist = QLabel()
        self.artist.setWordWrap(True)
        self.artist.setMaximumHeight(32)
        info_layout.addWidget(self.artist)
        self.album = QLabel()
        self.album.setWordWrap(True)
        self.album.setMaximumHeight(32)
        info_layout.addWidget(self.album)
        for label in (self.title, self.artist, self.album):
            label.setTextFormat(Qt.TextFormat.PlainText)
        self.lcd = QLabel('00:00')
        self.lcd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lcd.setFont(pixel_font(32))
        self.lcd.setStyleSheet('background:#080c08;color:#80ff80;font-size:32px;padding:4px;border:0;')
        self.meter = QWidget()
        self.meter.setObjectName('musicMeter')
        self.meter.setStyleSheet('QWidget#musicMeter {background:#080c08;border:2px solid;'
            'border-top-color:#404040;border-left-color:#404040;'
            'border-bottom-color:white;border-right-color:white;}')
        meter_layout = QVBoxLayout(self.meter)
        meter_layout.setContentsMargins(2, 2, 2, 2)
        meter_layout.setSpacing(0)
        meter_layout.addWidget(self.lcd)
        self.spectrum = PixelSpectrum(service.spectrum, self.meter)
        meter_layout.addWidget(self.spectrum)
        for display in (self.lcd, self.spectrum):
            display.setToolTip(tr('右键可关闭或开启像素频谱'))
            display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            display.customContextMenuRequested.connect(self.spectrum_menu)
        info_layout.addWidget(self.meter)
        self.state_label = QLabel()
        info_layout.addWidget(self.state_label)
        info_layout.addStretch()
        display_row.addWidget(info)
        desk_layout.addLayout(display_row)
        controls = QHBoxLayout()
        self.play_button = None
        for text, tooltip, callback in (('|<', '上一首', service.controller.previous),
                ('>', '播放', self.play_selected), ('[]', '停止', service.controller.stop),
                ('>|', '下一首', service.controller.next)):
            button = QPushButton(text)
            button.setToolTip(tr(tooltip))
            button.setFixedWidth(48)
            button.setStyleSheet('padding:5px;')
            button.clicked.connect(callback)
            controls.addWidget(button)
            if text == '>':
                self.play_button = button
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderReleased.connect(self.seek_released)
        self.seek.valueChanged.connect(self.seek_changed)
        controls.addWidget(self.seek, 1)
        self.duration = QLabel('00:00')
        controls.addWidget(self.duration)
        controls.addWidget(QLabel(tr('音量')))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(78)
        self.volume.valueChanged.connect(service.controller.set_volume)
        controls.addWidget(self.volume)
        desk_layout.addLayout(controls)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr('曲名'), tr('歌手'), tr('专辑'), tr('时长')])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 145)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 72)
        self.table.cellDoubleClicked.connect(self.play_row)
        self.table.setMinimumHeight(120)
        desk_layout.addWidget(self.table, 1)
        track_tools = QHBoxLayout()
        add = QPushButton(tr('加入歌单…'))
        add.clicked.connect(self.add_to_playlist)
        track_tools.addWidget(add)
        self.remove_button = QPushButton(tr('移出歌单'))
        self.remove_button.clicked.connect(self.remove_tracks)
        track_tools.addWidget(self.remove_button)
        for text, delta in (('↑', -1), ('↓', 1)):
            button = QPushButton(text)
            button.setFixedWidth(40)
            button.setStyleSheet('padding:4px;')
            button.setToolTip(tr('向上移动' if delta < 0 else '向下移动'))
            button.clicked.connect(lambda checked=False, step=delta: self.move_track(step))
            track_tools.addWidget(button)
        track_tools.addStretch()
        desk_layout.addLayout(track_tools)
        splitter.addWidget(desk)
        splitter.setSizes([155, 820])
        layout.addWidget(splitter, 1)
        self.status = QLabel(tr('双击曲目播放 · 音乐在阅读时继续播放'))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        service.library_changed.connect(self.reload)
        service.track_changed.connect(self.track_changed)
        service.preferences_changed.connect(self.preferences_changed)
        service.notice.connect(self.notice)
        service.busy_changed.connect(self.busy)
        service.controller.position_changed.connect(self.position_changed)
        service.controller.duration_changed.connect(self.duration_changed)
        service.controller.state_changed.connect(self.state_changed)
        self.reload()
        self.preferences_changed()
        self.track_changed(service.current)
        self.busy(service.job is not None)

    def notice(self, text):
        self.status.setText(str(text).splitlines()[0])
        self.status.setToolTip(str(text))

    def busy(self, value):
        self.import_button.setEnabled(not value)

    def selected_ids(self):
        return [self.table.item(i.row(), 0).data(Qt.ItemDataRole.UserRole)
                for i in self.table.selectionModel().selectedRows()]

    def reload(self, *_):
        selected = self.selected_ids()
        self._reloading = True
        self.playlists.clear()
        items = [{'id': None, 'name': tr('全部音乐')}] + self.service.store.playlists()
        if self.view_playlist not in {p['id'] for p in items}:
            self.view_playlist = None
        for index, entry in enumerate(items):
            item = QListWidgetItem(entry['name'])
            item.setData(Qt.ItemDataRole.UserRole, entry['id'])
            self.playlists.addItem(item)
            if entry['id'] == self.view_playlist:
                self.playlists.setCurrentRow(index)
        self._reloading = False
        self.reload_tracks(selected)

    def reload_tracks(self, selected=None):
        tracks = self.service.store.tracks(self.view_playlist)
        self.table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            values = [track['title'], track.get('artist', ''), track.get('album', ''), time_text(track.get('duration_ms', 0))]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, track['id'])
                item.setToolTip(str(value))
                if track['id'] == self.service.controller.current_id:
                    item.setForeground(QColor('#000080'))
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 29)
            if selected and track['id'] in selected:
                self.table.selectRow(row)
        self.remove_button.setText(tr('移出歌单') if self.view_playlist else tr('从音乐库移除'))
        self.notice(tr('{count} 首音乐', count=len(tracks)))

    def select_playlist(self, item, previous):
        if not self._reloading and item is not None:
            self.view_playlist = item.data(Qt.ItemDataRole.UserRole)
            self.reload_tracks()

    def import_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr('导入音乐'), '',
            tr('音频文件 (*.mp3 *.flac *.m4a *.aac *.ogg *.opus *.wav *.wma *.aiff *.aif)'),
            options=QFileDialog.Option.DontUseNativeDialog)
        self.service.import_files(files, self.view_playlist)

    def new_playlist(self):
        name, ok = QInputDialog.getText(self, tr('新建歌单'), tr('歌单名称'))
        if ok and name.strip():
            try:
                self.view_playlist = self.service.store.create_playlist(name)
                self.reload()
            except (ValueError, OSError) as error:
                alert(self, error)

    def rename_playlist(self):
        if not self.view_playlist:
            return
        name, ok = QInputDialog.getText(self, tr('重命名歌单'), tr('歌单名称'),
                                      text=self.playlists.currentItem().text())
        if ok and name.strip():
            try:
                self.service.store.rename_playlist(self.view_playlist, name)
                self.reload()
            except (ValueError, OSError) as error:
                alert(self, error)

    def delete_playlist(self):
        if self.view_playlist and alert(self, tr('只删除歌单，音乐仍保留在全部音乐中。'), True):
            try:
                self.service.store.delete_playlist(self.view_playlist)
                self.view_playlist = None
                self.service.changed()
            except (ValueError, OSError) as error:
                alert(self, error)

    def add_to_playlist(self):
        ids = self.selected_ids()
        if not ids:
            return
        lists = self.service.store.playlists()
        if not lists:
            alert(self, tr('先创建一个歌单。'))
            return
        labels = [f'{index+1:02d}  {p["name"]}' for index, p in enumerate(lists)]
        name, ok = QInputDialog.getItem(self, tr('加入歌单…'), tr('选择歌单'), labels, 0, False)
        if ok:
            try:
                self.service.store.add_to_playlist(lists[labels.index(name)]['id'], ids)
                self.service.changed()
            except (ValueError, OSError) as error:
                alert(self, error)

    def remove_tracks(self):
        ids = self.selected_ids()
        if not ids:
            return
        if not self.view_playlist and not alert(self, tr('将删除选中音乐的库内副本，原始音频文件保留。'), True):
            return
        try:
            self.service.remove_tracks(ids, self.view_playlist)
        except (ValueError, OSError) as error:
            alert(self, error)

    def move_track(self, delta):
        ids = self.selected_ids()
        if not self.view_playlist or len(ids) != 1:
            return
        order = [t['id'] for t in self.service.store.tracks(self.view_playlist)]
        index = order.index(ids[0])
        target = index+delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            try:
                self.service.store.reorder_playlist(self.view_playlist, order)
                self.service.changed()
                self.reload_tracks(ids)
            except (ValueError, OSError) as error:
                alert(self, error)

    def play_row(self, row, *_):
        self.service.play_track(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole), self.view_playlist)

    def play_selected(self):
        ids = self.selected_ids()
        if self.service.controller.state != 'playing' and ids and ids[0] != self.service.controller.current_id:
            self.service.play_track(ids[0], self.view_playlist)
        else:
            self.service.controller.toggle()

    def seek_released(self):
        self.service.controller.seek(self.seek.value())

    def seek_changed(self, value):
        if not self.seek.isSliderDown():
            self.service.controller.seek(value)

    def mode_changed(self, index):
        self.service.controller.set_mode(self.play_mode.itemData(index))

    def lyrics_toggled(self, value):
        self.service.set_preferences(show_lyrics=value)

    def preferences_changed(self):
        prefs = self.service.settings()
        self.spectrum.set_enabled(prefs.get('show_spectrum', True))
        for widget, value in ((self.show_lyrics, prefs.get('show_lyrics', True)),):
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        self.play_mode.blockSignals(True)
        self.play_mode.setCurrentIndex(max(0, self.play_mode.findData(self.service.controller.play_mode)))
        self.play_mode.blockSignals(False)
        self.volume.blockSignals(True)
        self.volume.setValue(self.service.controller.volume)
        self.volume.blockSignals(False)
        self.update_display()

    def spectrum_menu(self, point):
        menu = QMenu(self)
        action = menu.addAction(tr('显示像素频谱'))
        action.setCheckable(True)
        action.setChecked(self.service.settings().get('show_spectrum', True))
        sender = self.sender()
        if menu.exec(sender.mapToGlobal(point)) is action:
            self.service.set_preferences(show_spectrum=action.isChecked())
        menu.deleteLater()

    def track_changed(self, track):
        self.title.setText(track['title'] if track else tr('未选择音乐'))
        self.artist.setText(track.get('artist', '') if track else '')
        self.album.setText(track.get('album', '') if track else '')
        self.lyrics.set_document(track.get('lyrics') if track else None)
        self._display_key = None
        self.update_display()
        self.duration_changed(self.service.controller.duration_ms)
        self.position_changed(self.service.controller.position_ms)
        self.state_changed(self.service.controller.state)
        for row in range(self.table.rowCount()):
            current = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == self.service.controller.current_id
            for column in range(self.table.columnCount()):
                self.table.item(row, column).setForeground(QColor('#000080' if current else '#000000'))

    def update_display(self):
        track = self.service.current or {}
        prefs = self.service.settings()
        doc = track.get('lyrics') or {}
        lyric_visible = bool(prefs.get('show_lyrics', True) and doc.get('lines'))
        self.lyrics.setVisible(lyric_visible)
        self.artwork.setVisible(not lyric_visible)
        if lyric_visible:
            self.display_caption.setText(tr('同步歌词') if doc.get('timed') else tr('未同步歌词 · 可滚动查看'))
            self.lyrics.set_position(self.service.controller.position_ms)
        else:
            self.display_caption.setText(tr('无歌词 · 显示封面') if prefs.get('show_lyrics', True) else tr('ASCII 音频封面'))
            key = (track.get('id'), prefs.get('placeholder_kind'), prefs.get('placeholder_text'),
                   prefs.get('placeholder_image'), get_image_mode())
            if key != self._display_key:
                data = track.get('cover')
                if not data and prefs.get('placeholder_kind') == 'image':
                    data = self.service.store.placeholder_image()
                self.artwork.set_content(data, prefs.get('placeholder_text') or DEFAULT_ART)
                self._display_key = key

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(min(position, self.seek.maximum()))
            self.seek.blockSignals(False)
        self.lcd.setText(time_text(position))
        self.lyrics.set_position(position)

    def duration_changed(self, duration):
        self.seek.blockSignals(True)
        self.seek.setRange(0, min(max(0, duration), 2147483647))
        self.seek.blockSignals(False)
        self.duration.setText(time_text(duration))

    def state_changed(self, state):
        self.play_button.setText('||' if state == 'playing' else '>')
        self.play_button.setToolTip(tr('暂停') if state == 'playing' else tr('播放'))
        self.state_label.setText(tr({'playing': '正在播放', 'paused': '已暂停'}.get(state, '已停止')))

    def load_lyrics(self):
        ids = self.selected_ids()
        identity = ids[0] if ids else self.service.controller.current_id
        if not identity:
            return
        path, _ = QFileDialog.getOpenFileName(self, tr('载入歌词…'), '', tr('歌词文件 (*.lrc *.txt)'),
                                             options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            try:
                self.service.store.set_track_lyrics(identity, path)
                self.service.refresh_track()
            except (ValueError, OSError) as error:
                alert(self, error)

    def edit_placeholder(self):
        dialog = PlaceholderDialog(self.service, self)
        dialog.exec()
        dialog.deleteLater()
        self._display_key = None
        self.update_display()

    def dragEnterEvent(self, event):
        if not self.service.job and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if not self.service.job:
            self.service.import_files(paths, self.view_playlist)
            event.acceptProposedAction()
