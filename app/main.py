"""calibre95 — local, single-user calibre desktop."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
DATA = Path(os.environ.get('RETROREADER_DATA_DIR', ROOT / 'Data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
os.environ['CALIBRE_CONFIG_DIRECTORY'] = str(DATA / 'config')
import shutil
import traceback
from datetime import datetime, timezone, timedelta
from qt.core import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSplitter, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QStackedWidget, QFrame, QSize, Qt, QDialog, QFormLayout, QDialogButtonBox, QComboBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit, QFileDialog, QMessageBox, QProgressBar, QThread, pyqtSignal, QAction, QTimer, QLockFile, QIcon, QInputDialog, QTextDocument
from theme import apply_theme, icon, cover_pixmap, pixel_font, TitleBar
from qt.core import QMenuBar, QPixmap
from qt.core import QStyledItemDelegate, QStyle
QApplication.setLibraryPaths([str(ROOT / 'runtime/app/plugins')])
from library import LibraryStore
from i18n import tr, get_language, set_language, load_language, LANGUAGES, install_qt_translator, register
from preferences import get_image_mode, set_image_mode
from lifecycle import enable_fault_log, shutdown_application
from music_service import get_music_service
from music_ui import MusicBar, MUSIC_HELP

register({
    '打开书籍': ('Open book', '書籍を開く'),
    '正在准备书籍和图片': ('Preparing book and images', '本文と画像を準備中'),
    '双击查看完整字符画封面': ('Double-click for the full ASCII cover', 'ダブルクリックでASCII表紙を拡大'),
    '字符画封面': ('ASCII cover', 'ASCII表紙'),
    '关闭': ('Close', '閉じる'),
    '正在准备可编辑的 EPUB': ('Preparing an editable EPUB', '編集用のEPUBを準備中'),
    '字符画使用说明': (
        'Images: choose Color ASCII or Monochrome ASCII; the shelf and reader share this setting.\nDouble-click the cover in the details panel to enlarge it.\nReading images: Fit window shows the complete image; Fit page width enlarges long artwork for scrolling.\nThe location bar shows the actual library path and follows the application folder when moved.',
        '画像表示：カラーASCII／白黒ASCIIを選択できます。書庫とリーダーで設定を共有します。\n詳細欄の表紙をダブルクリックすると拡大表示できます。\n画像の倍率：ウィンドウに合わせると全体を表示、ページ幅に合わせると縦長画像を拡大してスクロールできます。\n場所欄には実際の書庫パスが表示され、アプリの移動先に追従します。'),
})

def shelf_cover(book, width=168, height=224, mode='color'):
    if book.get('cover'):
        from ascii_art import render_ascii
        try:
            return QPixmap.fromImage(render_ascii(book['cover'], width, height, mode=mode))
        except (ValueError, OSError):
            # A damaged cover should not prevent opening the rest of the library.
            book = dict(book, cover=None)
    return cover_pixmap(book, width, height)

class CoverLabel(QLabel):
    activated = pyqtSignal()
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseDoubleClickEvent(event)


class BookItemDelegate(QStyledItemDelegate):
    """Only selected books get a highlight; hovering is not a selection."""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_MouseOver
        if not option.state & QStyle.StateFlag.State_Selected:
            option.state &= ~QStyle.StateFlag.State_HasFocus


class ClearableBookView:
    def clear_book_selection(self):
        self.selectionModel().clear()

    def mousePressEvent(self, event):
        empty = not self.indexAt(event.position().toPoint()).isValid()
        super().mousePressEvent(event)
        if empty and event.button() == Qt.MouseButton.LeftButton:
            self.clear_book_selection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear_book_selection()
            event.accept()
            return
        super().keyPressEvent(event)


class BookShelf(ClearableBookView, QListWidget):
    pass


class BookTable(ClearableBookView, QTableWidget):
    pass

from image_viewer import AsciiImageDialog

class AsciiCoverDialog(AsciiImageDialog):
    def __init__(self, book, parent=None):
        self.book = book
        super().__init__(book.get('cover'), parent,
                         title=tr('字符画封面') + ' — ' + book['title'],
                         empty_text=book['title'])

def plain(value):
    doc = QTextDocument()
    doc.setHtml(value or '')
    return doc.toPlainText()

def message(parent, title, text, question=False):
    box = QMessageBox(parent)
    box.setWindowTitle(tr(title))
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(tr(text))
    box.setIcon(QMessageBox.Icon.Question if question else QMessageBox.Icon.Information)
    if question:
        yes = box.addButton(tr('确定'), QMessageBox.ButtonRole.AcceptRole)
        no = box.addButton(tr('取消'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no)
        box.exec()
        accepted = box.clickedButton() == yes
        box.deleteLater()
        return accepted
    box.addButton(tr('确定'), QMessageBox.ButtonRole.AcceptRole)
    box.exec()
    box.deleteLater()

class Job(QThread):
    result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception:
            self.failed.emit(traceback.format_exc())

class MetadataDialog(QDialog):

    def __init__(self, book, parent):
        super().__init__(parent)
        self.setWindowTitle(tr('编辑元数据 — ') + book['title'])
        self.resize(590, 650)
        self.cover_path = None
        self.fields = {}
        layout = QVBoxLayout(self)
        heading = QLabel(tr('书籍资料卡 / BOOK PROPERTIES'))
        heading.setObjectName('dialogHeading')
        layout.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(12)
        layout.addLayout(form)
        for key, label, value in [('title', tr('书名'), book['title']), ('authors', tr('作者（用 & 分隔）'), ' & '.join(book['authors'])), ('publisher', tr('出版社'), book.get('publisher', '')), ('series', tr('丛书'), book.get('series', '')), ('tags', tr('标签（用逗号分隔）'), ', '.join(book.get('tags', []))), ('languages', tr('语言代码'), ', '.join(book.get('languages', []))), ('isbn', 'ISBN', book.get('isbn', ''))]:
            field = QLineEdit(value or '')
            self.fields[key] = field
            form.addRow(label.replace('&', '&&'), field)
        self.series_index = QDoubleSpinBox()
        self.series_index.setRange(0, 999999)
        self.series_index.setValue(book.get('series_index') if book.get('series_index') is not None else 1)
        form.addRow(tr('丛书序号'), self.series_index)
        self.rating = QSpinBox()
        self.rating.setRange(0, 5)
        self.rating.setValue(int(book.get('rating', 0) or 0) // 2)
        form.addRow(tr('评分（0–5）'), self.rating)
        self.comments = QPlainTextEdit(plain(book.get('comments')))
        self.comments.setMinimumHeight(100)
        form.addRow(tr('内容简介'), self.comments)
        self.cover_button = QPushButton(tr('更换封面…'))
        self.cover_button.clicked.connect(self.pick_cover)
        layout.addWidget(self.cover_button)
        buttons = QDialogButtonBox()
        save = buttons.addButton(tr('保存资料'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr('取消'), QDialogButtonBox.ButtonRole.RejectRole)
        save.clicked.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def pick_cover(self):
        p, _ = QFileDialog.getOpenFileName(self, tr('选择封面'), '', tr('图片 (*.png *.jpg *.jpeg *.webp)'), options=QFileDialog.Option.DontUseNativeDialog)
        if p:
            self.cover_path = p
            self.cover_button.setText(tr('封面：') + Path(p).name)

    def validate(self):
        if not self.fields['title'].text().strip():
            message(self, tr('请填写书名'), tr('书名不能为空。'))
            return
        self.accept()

    def values(self):
        import html
        v = {k: f.text().strip() for k, f in self.fields.items()}
        v['authors'] = [a.strip() for a in v['authors'].split('&') if a.strip()] or [tr('未知作者')]
        for k in ('tags', 'languages'):
            v[k] = [s.strip() for s in v[k].replace('，', ',').split(',') if s.strip()]
        v.update(series_index=self.series_index.value(), rating=self.rating.value() * 2, comments='<p>' + html.escape(self.comments.toPlainText()).replace('\n', '<br/>') + '</p>')
        if self.cover_path:
            v['cover_path'] = self.cover_path
        return v

class MainWindow(QMainWindow):

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.books = []
        self.visible = []
        self.current_id = None
        self.job = None
        self.mode = '全部藏书'
        self.image_mode = get_image_mode()
        self._replacing = False
        self.music = get_music_service(DATA)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('calibre95')
        self.setWindowIcon(icon())
        self.resize(1240, 800)
        self.setMinimumSize(1000, 680)
        self.setAcceptDrops(True)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(5, 3, 5, 5)
        root.setSpacing(0)
        title = TitleBar(self, 'calibre95')
        tl = title.layout()
        root.addWidget(title)
        self.language_combo = QComboBox()
        self.language_combo.setAccessibleName(tr('语言'))
        self.language_combo.setToolTip(tr('语言'))
        for code, label in LANGUAGES:
            self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex(next((i for i, (code, _) in enumerate(LANGUAGES) if code == get_language())))
        self.language_combo.currentIndexChanged.connect(self.switch_language)
        tl.insertWidget(2, self.language_combo)
        self.actions = {}
        for name, kind, fn, shortcut in [('导入书籍', 'import', self.import_dialog, 'Ctrl+O'), ('阅读书籍', 'book', self.read_book, 'Ctrl+R'), ('编辑元数据', 'metadata', self.edit_metadata, 'Ctrl+E'), ('编辑书籍', 'edit', self.edit_book, 'Ctrl+Shift+E'), ('格式转换', 'convert', self.convert, 'Ctrl+Shift+C'), ('导出文件', 'folder', self.export, 'Ctrl+S'), ('删除书籍', 'delete', self.delete, 'Delete')]:
            a = QAction(icon(kind), tr(name), self)
            a.triggered.connect(fn)
            a.setShortcut(shortcut)
            self.addAction(a)
            self.actions[name] = a
        menu = QMenuBar(central)
        self._menu = menu
        root.addWidget(menu)
        file = menu.addMenu(tr('文件(F)'))
        file.addAction(self.actions['导入书籍'])
        file.addAction(self.actions['导出文件'])
        file.addSeparator()
        file.addAction(tr('退出'), self.close)
        edit = menu.addMenu(tr('书籍(B)'))
        for n in ('阅读书籍', '编辑元数据', '编辑书籍', '格式转换', '删除书籍'):
            edit.addAction(self.actions[n])
        view = menu.addMenu(tr('视图(V)'))
        view.addAction(tr('封面书架'), lambda: self.set_view(0))
        view.addAction(tr('详细列表'), lambda: self.set_view(1))
        refresh_action = QAction(tr('刷新'), self)
        refresh_action.setShortcut('F5')
        refresh_action.triggered.connect(self.refresh)
        view.addAction(refresh_action)
        self.music_action = QAction(tr('音乐播放器'), self)
        self.music_action.setShortcut('Ctrl+M')
        self.music_action.triggered.connect(self.open_music)
        self.addAction(self.music_action)
        view.addAction(self.music_action)
        helpmenu = menu.addMenu(tr('帮助(H)'))
        helpmenu.addAction(tr('使用说明'), self.help)
        helpmenu.addAction(tr('关于旧时书房'), self.about)
        toolbar = QWidget()
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(7, 12, 7, 12)
        bar.setSpacing(8)
        self.toolbuttons = []
        for name, a in self.actions.items():
            b = QPushButton(a.icon(), tr(name))
            b.setIconSize(QSize(23, 23))
            b.setMinimumHeight(39)
            b.clicked.connect(a.trigger)
            a.changed.connect(lambda b=b, a=a: b.setEnabled(a.isEnabled()))
            bar.addWidget(b)
            self.toolbuttons.append(b)
        bar.addStretch()
        self.music_button = QPushButton(tr('音乐'))
        self.music_button.setMinimumHeight(39)
        self.music_button.clicked.connect(self.open_music)
        bar.addWidget(self.music_button)
        root.addWidget(toolbar)
        address = QWidget()
        ar = QHBoxLayout(address)
        ar.setContentsMargins(9, 0, 9, 12)
        ar.addWidget(QLabel(tr('位置(D)')))
        self.library_location = QLineEdit(str(Path(self.store.library_path).resolve()))
        self.library_location.setReadOnly(True)
        self.library_location.setToolTip(self.library_location.text())
        ar.addWidget(self.library_location, 1)
        ar.addWidget(QLabel(tr('图片显示')))
        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItem(tr('彩色字符画'), 'color')
        self.image_mode_combo.addItem(tr('黑白字符画'), 'mono')
        self.image_mode_combo.setCurrentIndex(self.image_mode_combo.findData(self.image_mode))
        self.image_mode_combo.currentIndexChanged.connect(self.change_image_mode)
        ar.addWidget(self.image_mode_combo)
        root.addWidget(address)
        split = QSplitter()
        root.addWidget(split, 1)
        left = QWidget()
        left.setMinimumWidth(172)
        left.setMaximumWidth(230)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 8, 10, 8)
        ll.setSpacing(12)
        ll.addWidget(QLabel(tr('书库目录')))
        self.nav = QListWidget()
        self.nav.setObjectName('navigation')
        self.nav.setStyleSheet('QListWidget { background: #e0e0e0; } QListWidget::item { padding: 10px 6px; }')
        for text in ['全部藏书', '最近添加', '我的收藏', 'EPUB', 'PDF', 'AZW3', 'MOBI', '其他格式']:
            item = QListWidgetItem(icon('folder', 20), tr(text))
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.currentItemChanged.connect(self.filter_changed)
        ll.addWidget(self.nav)
        self.library_count = QLabel()
        ll.addWidget(self.library_count)
        split.addWidget(left)
        middle = QWidget()
        ml = QVBoxLayout(middle)
        ml.setContentsMargins(9, 8, 9, 8)
        ml.setSpacing(12)
        hr = QHBoxLayout()
        self.heading = QLabel(tr('全部藏书'))
        self.heading.setFont(pixel_font(16))
        hr.addWidget(self.heading)
        hr.addStretch()
        self.grid_button = QPushButton(tr('▦ 书架'))
        self.list_button = QPushButton(tr('≡ 列表'))
        for b in (self.grid_button, self.list_button):
            b.setCheckable(True)
            hr.addWidget(b)
        self.grid_button.clicked.connect(lambda: self.set_view(0))
        self.list_button.clicked.connect(lambda: self.set_view(1))
        ml.addLayout(hr)
        sr = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('搜索书名、作者、标签…'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.render)
        sr.addWidget(self.search)
        self.sort = QComboBox()
        self.sort.addItems([tr('最新添加'), tr('书名 A → Z'), tr('作者 A → Z')])
        self.sort.currentIndexChanged.connect(self.render)
        sr.addWidget(self.sort)
        ml.addLayout(sr)
        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)
        self.grid = BookShelf()
        self.grid.setItemDelegate(BookItemDelegate(self.grid))
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setIconSize(QSize(180, 240))
        self.grid.setGridSize(QSize(218, 300))
        self.grid.setSpacing(8)
        self.grid.setWordWrap(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.itemSelectionChanged.connect(self.selection_changed)
        self.grid.itemDoubleClicked.connect(self.read_book)
        self.stack.addWidget(self.grid)
        self.table = BookTable(0, 5)
        self.table.setItemDelegate(BookItemDelegate(self.table))
        self.table.setHorizontalHeaderLabels([tr('书名'), tr('作者'), tr('格式'), tr('标签'), tr('评分')])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 95)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 65)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.itemDoubleClicked.connect(self.read_book)
        self.stack.addWidget(self.table)
        self.empty = QLabel(tr('书架还是空的\n\n点击“导入书籍”，或把文件拖到这里。'))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)
        hint = QLabel(tr('提示：拖入文件即可收藏 · Ctrl + O 导入 · Ctrl + E 编辑资料'))
        hint.setStyleSheet('color: #555555;')
        hint.setWordWrap(True)
        ml.addWidget(hint)
        split.addWidget(middle)
        right = QWidget()
        right.setMinimumWidth(238)
        right.setMaximumWidth(280)
        dl = QVBoxLayout(right)
        dl.setContentsMargins(14, 8, 14, 8)
        dl.setSpacing(11)
        dl.addWidget(QLabel(tr('书籍资料 / DETAILS')))
        self.cover = CoverLabel()
        self.cover.setToolTip(tr('双击查看完整字符画封面'))
        self.cover.activated.connect(self.show_cover)
        self.cover.setFixedHeight(225)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.cover)
        self.book_title = QLabel(tr('选择一本书'))
        self.book_title.setWordWrap(True)
        self.book_title.setTextFormat(Qt.TextFormat.PlainText)
        dl.addWidget(self.book_title)
        self.author = QLabel()
        self.author.setWordWrap(True)
        self.author.setTextFormat(Qt.TextFormat.PlainText)
        dl.addWidget(self.author)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        dl.addWidget(self.details)
        self.description = QPlainTextEdit()
        self.description.setReadOnly(True)
        self.description.setFrameShape(QFrame.Shape.NoFrame)
        self.description.setStyleSheet('background: #e0e0e0; padding: 5px;')
        dl.addWidget(self.description, 1)
        self.favorite = QPushButton(tr('☆ 加入收藏'))
        self.favorite.clicked.connect(self.toggle_favorite)
        dl.addWidget(self.favorite)
        self.detail_edit = QPushButton(tr('编辑这本书的资料'))
        self.detail_edit.clicked.connect(self.edit_metadata)
        dl.addWidget(self.detail_edit)
        split.addWidget(right)
        split.setSizes([180, 770, 250])
        self.status = self.statusBar()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(150)
        self.progress.hide()
        self.status.addPermanentWidget(self.progress)
        self.music_bar = MusicBar(self.music, self, compact=True)
        self.status.addPermanentWidget(self.music_bar)
        self.view_index = 0
        self.set_view(0)
        self.refresh()

    def selected_ids(self):
        if self.stack.currentIndex() == 0:
            return [i.data(Qt.ItemDataRole.UserRole) for i in self.grid.selectedItems()]
        if self.stack.currentIndex() == 1:
            return [self.table.item(i.row(), 0).data(Qt.ItemDataRole.UserRole) for i in self.table.selectionModel().selectedRows()]
        return []

    def open_music(self):
        self.music.show_player(self)

    def current_book(self):
        return next((b for b in self.books if b['id'] == self.current_id), None)

    def filter_changed(self, item, *_):
        if item is None:
            return
        self.mode = item.data(Qt.ItemDataRole.UserRole)
        self.heading.setText(tr(self.mode))
        self.render()

    def refresh(self):
        if self.job and self.job.isRunning():
            return
        self.books = self.store.list_books(include_covers=True)
        self.library_location.setText(str(Path(self.store.library_path).resolve()))
        self.library_location.setToolTip(self.library_location.text())
        self.library_count.setText(tr('{count:03d} 本书籍\nLOCAL DISK / CATALOG', count=len(self.books)))
        self.render()

    def render(self, *_):
        selected = set(self.selected_ids())
        query = self.search.text().strip().casefold()
        books = self.books
        if self.mode == '我的收藏':
            books = [b for b in books if '收藏' in b['tags']]
        elif self.mode == '最近添加':
            threshold = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()

            def recent(b):
                t = b.get('timestamp')
                return (t.timestamp() if hasattr(t, 'timestamp') else datetime.fromisoformat(str(t)).timestamp()) >= threshold
            books = [b for b in books if recent(b)]
        elif self.mode in ('EPUB', 'PDF', 'AZW3', 'MOBI'):
            books = [b for b in books if self.mode in b['formats']]
        elif self.mode == '其他格式':
            books = [b for b in books if any((f not in ('EPUB', 'PDF', 'AZW3', 'MOBI') for f in b['formats']))]
        if query:
            books = [b for b in books if query in ' '.join([b['title'], *b['authors'], *b['tags'], *b['formats']]).casefold()]
        idx = self.sort.currentIndex()
        books = sorted(books, key=lambda b: b['title'].casefold() if idx == 1 else ' '.join(b['authors']).casefold() if idx == 2 else b['id'], reverse=idx == 0)
        self.visible = books
        self.grid.blockSignals(True)
        self.table.blockSignals(True)
        self.grid.clear()
        self.table.selectionModel().clear()
        self.table.setRowCount(len(books))
        for row, b in enumerate(books):
            item = QListWidgetItem(QIcon(shelf_cover(b, 180, 240, self.image_mode)), b['title'] + '\n' + ' / '.join(b['formats']))
            item.setData(Qt.ItemDataRole.UserRole, b['id'])
            item.setToolTip(b['title'] + '\n' + ' / '.join(b['authors']))
            self.grid.addItem(item)
            for col, value in enumerate([b['title'], ' / '.join(b['authors']), ' / '.join(b['formats']), ', '.join(b['tags']), str((b.get('rating') or 0) // 2) + '/5']):
                ti = QTableWidgetItem(value)
                ti.setData(Qt.ItemDataRole.UserRole, b['id'])
                self.table.setItem(row, col, ti)
            self.table.setRowHeight(row, 40)
        self.grid.blockSignals(False)
        self.table.blockSignals(False)
        self.empty.setText(tr('未找到匹配的书籍\n\n尝试清除搜索内容或更换分类。') if self.books else tr('书架还是空的\n\n点击“导入书籍”，或把文件拖到这里。'))
        self.stack.setCurrentIndex(self.view_index if books else 2)
        self.restore_selection(selected)
        self.selection_changed()
        self.status.showMessage(tr('共 {total} 本书籍  |  当前显示 {shown} 本', total=len(self.books), shown=len(books)))

    def set_view(self, index):
        selected = set(self.selected_ids())
        self.view_index = index
        self.grid_button.setChecked(index == 0)
        self.list_button.setChecked(index == 1)
        self.stack.setCurrentIndex(index if self.visible else 2)
        self.restore_selection(selected)
        self.selection_changed()

    def restore_selection(self, ids):
        """Keep both views consistent, including the deliberately empty state."""
        for view in (self.grid, self.table):
            view.blockSignals(True)
            view.selectionModel().clear()
        first = None
        for row, book in enumerate(self.visible):
            if book['id'] in ids:
                self.grid.item(row).setSelected(True)
                for col in range(self.table.columnCount()):
                    self.table.item(row, col).setSelected(True)
                if first is None:
                    first = row
        if first is not None:
            # Set keyboard focus without clearing a multi-book selection.
            from qt.core import QItemSelectionModel
            flags = QItemSelectionModel.SelectionFlag.NoUpdate
            self.grid.selectionModel().setCurrentIndex(self.grid.model().index(first, 0), flags)
            self.table.selectionModel().setCurrentIndex(self.table.model().index(first, 0), flags)
        for view in (self.grid, self.table):
            view.blockSignals(False)

    def selection_changed(self):
        ids = self.selected_ids()
        if not ids:
            self.grid.selectionModel().clearCurrentIndex()
            self.table.selectionModel().clearCurrentIndex()
        self.current_id = ids[0] if ids else None
        b = self.current_book()
        one = len(ids) == 1
        for n, a in self.actions.items():
            a.setEnabled(n == '导入书籍' or (bool(ids) if n == '删除书籍' else one))
        self.favorite.setEnabled(one)
        self.detail_edit.setEnabled(one)
        if not b:
            self.cover.clear()
            self.book_title.setText(tr('选择一本书'))
            self.author.clear()
            self.details.clear()
            self.description.clear()
            return
        self.cover.setPixmap(shelf_cover(b, mode=self.image_mode))
        self.book_title.setText(b['title'])
        self.author.setText(tr('作者  ') + ' / '.join(b['authors']))
        self.details.setText(tr('格式  ') + ' / '.join(b['formats']) + tr('\n标签  ') + (', '.join(b['tags']) or tr('未分类')) + tr('\n评分  ') + str((b.get('rating') or 0) // 2) + ' / 5')
        self.description.setPlainText(plain(b.get('comments')) or tr('暂无简介。可以在“编辑元数据”中添加。'))
        self.favorite.setText(tr('★ 已收藏 · 移出收藏') if '收藏' in b['tags'] else tr('☆ 加入收藏'))

    def run_job(self, title, fn, done=None):
        if self.job:
            return
        self.centralWidget().setEnabled(False)
        self._menu.setEnabled(False)
        for a in self.actions.values():
            a.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status.showMessage(tr(title) + tr('，请稍候…'))
        self.job = Job(fn, self)
        result = {}
        self.job.result.connect(lambda r: result.update(value=r))
        self.job.failed.connect(lambda e: result.update(error=e))

        def finish():
            self.job.deleteLater()
            self.job = None
            self.centralWidget().setEnabled(True)
            self._menu.setEnabled(True)
            self.progress.hide()
            self.refresh()
            if 'error' in result:
                (DATA / 'logs').mkdir(exist_ok=True)
                with (DATA / 'logs/errors.log').open('a', encoding='utf-8') as f:
                    f.write(result['error'] + '\n')
                message(self, tr('操作未完成'), result['error'].strip().splitlines()[-1])
            elif done:
                done(result.get('value'))
            else:
                self.status.showMessage(tr(title) + tr('完成'), 10000)
        self.job.finished.connect(finish)
        self.job.start()

    def import_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr('导入电子书'), '', tr('电子书 (*.epub *.pdf *.azw3 *.mobi *.azw *.txt *.docx *.rtf *.fb2 *.cbz *.cbr *.html *.htmlz *.lit *.lrf *.djvu);;所有文件 (*)'), options=QFileDialog.Option.DontUseNativeDialog)
        if files:
            self.import_files(files)

    def import_files(self, files):

        def done(r):
            text = tr('已导入 {added} 本，跳过 {duplicates} 个重复文件。', added=len(r['added']), duplicates=len(r['duplicates']))
            if r['errors']:
                text += tr('\n\n未能导入：\n') + '\n'.join((Path(e['path']).name + '：' + e['error'] for e in r['errors']))
            message(self, tr('导入结果'), text)
        self.run_job('导入书籍', lambda: self.store.import_books(files), done)

    def edit_metadata(self, *_):
        b = self.current_book()
        if not b:
            return
        d = MetadataDialog(b, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            values = d.values()
            self.run_job(tr('保存元数据'), lambda: self.store.update_metadata(b['id'], values))
        d.deleteLater()

    def toggle_favorite(self):
        b = self.current_book()
        if not b:
            return
        tags = list(b['tags'])
        tags.remove('收藏') if '收藏' in tags else tags.append('收藏')
        self.run_job(tr('更新收藏'), lambda: self.store.update_metadata(b['id'], {'tags': tags}))

    def edit_book(self, *_):
        b = self.current_book()
        if not b:
            return
        fmts = [f for f in b['formats'] if f in ('EPUB', 'AZW3')]
        if not fmts:
            supported = set(self.store.input_formats())
            sources = [f for f in ('MOBI', 'AZW', 'FB2', 'DOCX', 'HTMLZ', 'TXT', 'PDF')
                       if f in b['formats'] and f in supported]
            sources += [f for f in b['formats'] if f in supported and f not in sources]
            if not sources:
                message(self, '编辑书籍', tr('该书没有可用的输入格式。'))
                return
            book_id, source = b['id'], sources[0]
            self.run_job('正在准备可编辑的 EPUB',
                         lambda: self.store.convert_book(book_id, source, 'EPUB', replace=False),
                         lambda result: self.open_book_editor(book_id, 'EPUB'))
            return
        fmt = fmts[0]
        if len(fmts) > 1:
            fmt, ok = QInputDialog.getItem(self, tr('编辑书籍'), tr('选择要编辑的格式'), fmts, 0, False)
            if not ok:
                return
        self.open_book_editor(b['id'], fmt)

    def open_book_editor(self, book_id, fmt):
        d = None
        try:
            from editor import BookEditor
            path = self.store.format_path(book_id, fmt)
            d = BookEditor(path, self)
            d.exec()
            if d.saved_once:
                self.store.add_format(book_id, path, replace=True)
            self.refresh()
        except Exception as e:
            message(self, tr('无法编辑'), str(e))
        finally:
            if d is not None:
                d.deleteLater()

    def read_book(self, *_):
        b = self.current_book()
        if not b:
            return
        preferred = ('EPUB', 'AZW3', 'MOBI', 'AZW', 'PDF', 'TXT')
        supported = set(self.store.input_formats()) | {'EPUB', 'AZW3', 'TXT'}
        fmts = [f for f in preferred if f in b['formats']]
        fmts += [f for f in b['formats'] if f in supported and f not in fmts]
        if not fmts:
            message(self, tr('无法阅读'), tr('此格式暂不支持直接阅读，请转换为 EPUB 后再打开。'))
            return
        fmt = fmts[0]
        if len(fmts) > 1:
            fmt, ok = QInputDialog.getItem(self, tr('阅读书籍'), tr('选择要阅读的格式'), fmts, 0, False)
            if not ok:
                return
        from reader import BookReader, ReaderDocument
        path = self.store.format_path(b['id'], fmt)
        language = get_language()
        def opened(document):
            reader = None
            try:
                reader = BookReader(path, self, language=language, book_id=b['id'],
                                    image_mode=self.image_mode, document=document, music_service=self.music)
                reader.exec()
            except Exception as error:
                message(self, tr('无法阅读'), str(error))
            finally:
                document.close()
                if reader is not None:
                    reader.deleteLater()
                self.sync_image_mode()
        self.run_job(tr('正在准备书籍和图片'), lambda: ReaderDocument(path, language), opened)

    def change_image_mode(self, index):
        mode = self.image_mode_combo.itemData(index)
        try:
            set_image_mode(mode)
        except OSError as error:
            message(self, tr('无法保存显示设置'), str(error))
            self.image_mode_combo.blockSignals(True)
            self.image_mode_combo.setCurrentIndex(self.image_mode_combo.findData(self.image_mode))
            self.image_mode_combo.blockSignals(False)
            return
        self.image_mode = mode
        self.music.preferences_changed.emit()
        self.render()

    def sync_image_mode(self):
        self.image_mode = get_image_mode()
        self.image_mode_combo.blockSignals(True)
        self.image_mode_combo.setCurrentIndex(self.image_mode_combo.findData(self.image_mode))
        self.image_mode_combo.blockSignals(False)
        self.render()

    def show_cover(self):
        book = self.current_book()
        if not book:
            return
        dialog = AsciiCoverDialog(book, self)
        dialog.exec()
        dialog.redraw_timer.stop()
        dialog.deleteLater()
        self.sync_image_mode()

    def convert(self):
        b = self.current_book()
        if not b:
            return
        d = QDialog(self)
        d.setWindowTitle(tr('格式转换'))
        d.resize(450, 270)
        l = QVBoxLayout(d)
        title = QLabel(b['title'])
        title.setWordWrap(True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        l.addWidget(title)
        f = QFormLayout()
        src = QComboBox()
        src.addItems([x for x in b['formats'] if x in self.store.input_formats()])
        dst = QComboBox()
        dst.addItems(self.store.output_formats())
        dst.setCurrentText('EPUB')
        f.addRow(tr('源格式'), src)
        f.addRow(tr('目标格式'), dst)
        l.addLayout(f)
        note = QLabel(tr('转换结果保存在同一本书中。\n源格式将保留，转换期间请勿关闭软件。'))
        note.setWordWrap(True)
        l.addWidget(note)
        buttons = QDialogButtonBox()
        buttons.addButton(tr('开始转换'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr('取消'), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(d.accept)
        buttons.rejected.connect(d.reject)
        l.addWidget(buttons)
        if d.exec() != QDialog.DialogCode.Accepted:
            d.deleteLater()
            return
        source, target = (src.currentText(), dst.currentText())
        d.deleteLater()
        if not source:
            message(self, tr('不支持转换'), tr('该书没有可用的输入格式。'))
            return
        if source == target:
            message(self, tr('请选择不同格式'), tr('源格式与目标格式不能相同。'))
            return
        replace = target in b['formats']
        if replace and (not message(self, tr('替换已有格式'), tr('此书已有 {format} 格式。确认用新转换结果替换？', format=target), True)):
            return
        self.run_job(tr('转换为 ') + target, lambda: self.store.convert_book(b['id'], source, target, replace=replace), lambda r: message(self, tr('转换完成'), tr('已生成 {format}，可以通过“导出文件”保存副本。', format=target)))

    def export(self):
        b = self.current_book()
        if not b:
            return
        fmt, ok = QInputDialog.getItem(self, tr('导出文件'), tr('选择格式'), b['formats'], 0, False)
        if not ok:
            return
        import re
        safe = re.sub('[<>:"/\\\\|?*\\x00-\\x1f]', '_', b['title']).strip('. ') or 'book'
        dest, _ = QFileDialog.getSaveFileName(self, tr('导出书籍'), safe + '.' + fmt.lower(), f'{fmt} (*.{fmt.lower()})', options=QFileDialog.Option.DontUseNativeDialog)
        if dest:
            source = self.store.format_path(b['id'], fmt)
            if Path(source).resolve() == Path(dest).resolve():
                return
            self.run_job(tr('导出书籍'), lambda: self.store.export_format(b['id'], fmt, dest, replace=True))

    def delete(self):
        ids = self.selected_ids()
        if not ids:
            return
        if message(self, tr('删除书籍'), tr('将从书库移除选中的 {count} 本书及其全部格式。\n导入前的原始文件不受影响。\n\n确认删除？', count=len(ids)), True):
            self.run_job('删除书籍', lambda: self.store.remove_books(ids))

    def dragEnterEvent(self, e):
        if not self.job and e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]
        if files and (not self.job):
            self.import_files(files)
            e.acceptProposedAction()

    def help(self):
        image_help = ('图片显示：彩色字符画与黑白字符画可切换，书库和阅读器共用设置。\n'
                      '双击右侧资料栏的封面可放大查看。\n'
                      '阅读缩放：适合窗口可查看整图；适合页宽可放大长图并滚动查看。\n'
                      '位置栏显示实际书库地址，随整个软件文件夹的移动自动更新。')
        if get_language() != 'zh_CN':
            image_help = tr('字符画使用说明')
        message(self, tr('使用说明'), tr('使用说明正文') + '\n\n' + image_help + '\n\n' + tr(MUSIC_HELP))

    def about(self):
        message(self, tr('关于旧时书房'), tr('关于正文'))

    def switch_language(self, index):
        if self.job:
            return
        code = self.language_combo.itemData(index)
        if code == get_language():
            return
        old_language = get_language()
        selected = set(self.selected_ids())
        try:
            set_language(code)
            self.music.close_windows()
            app = QApplication.instance()
            apply_theme(app, get_language())
            install_qt_translator(app)
            replacement = MainWindow(self.store)
            replacement.setGeometry(self.geometry())
            replacement.search.setText(self.search.text())
            replacement.sort.setCurrentIndex(self.sort.currentIndex())
            replacement.nav.setCurrentRow(self.nav.currentRow())
            replacement.set_view(self.view_index)
            replacement.render()
            replacement.restore_selection(selected)
            replacement.selection_changed()
            app._main_window = replacement
            if self.isMaximized():
                replacement.showMaximized()
            else:
                replacement.show()
            self._replacing = True
            self.close()
            self.deleteLater()
        except Exception as error:
            set_language(old_language)
            apply_theme(QApplication.instance(), get_language())
            install_qt_translator(QApplication.instance())
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(next((i for i, (c, _) in enumerate(LANGUAGES) if c == old_language)))
            self.language_combo.blockSignals(False)
            message(self, tr('无法切换语言'), str(error))

    def closeEvent(self, e):
        if not self._replacing and (self.job or self.music.job):
            message(self, tr('任务正在进行'), tr('请等待当前任务完成后再退出。'))
            e.ignore()
            return
        if not self._replacing:
            self.store.close()
        e.accept()

def main():
    load_language(DATA)
    enable_fault_log(DATA)
    QApplication.setLibraryPaths([str(ROOT / 'runtime/app/plugins')])
    app = QApplication(sys.argv)
    app.setApplicationName('calibre95')
    lock = QLockFile(str(DATA / 'library.lock'))
    lock.setStaleLockTime(0)
    store = None
    window = None
    try:
        apply_theme(app, get_language())
        install_qt_translator(app)
        if not lock.tryLock(100):
            message(None, tr('书库已打开'), tr('这个书库已在另一个窗口中打开。'))
            return 0
        store = LibraryStore(DATA / 'Library', ROOT / 'runtime')
        # Public release starts with an empty user-managed library.
        window = MainWindow(store)
        app._main_window = window
        window.show()
        return app.exec()
    except Exception:
        (DATA / 'logs').mkdir(exist_ok=True)
        (DATA / 'logs/startup-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        message(None, tr('启动失败'), tr('请检查 Data/logs/startup-error.log。\n') + traceback.format_exc().strip().splitlines()[-1])
        return 1
    finally:
        window = None
        try:
            shutdown_application(app, store)
        finally:
            lock.unlock()
if __name__ == '__main__':
    sys.exit(main())
