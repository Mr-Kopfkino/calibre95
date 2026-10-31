"""Windows 98 chrome and a bundled, consistently pixelated text system."""
from pathlib import Path
from PyQt6 import sip
from qt.core import (QApplication, QFont, QFontDatabase, QPalette, QColor, QPixmap,
                     QPainter, QIcon, Qt, QRect, QWidget, QHBoxLayout, QVBoxLayout,
                     QLabel, QPushButton, QObject, QEvent, QDialog, QMainWindow, QMenu)

ROOT = Path(__file__).resolve().parents[1]
FAMILY = 'Unifont'
FAMILIES = {}

class RaisedWindowBorder(QWidget):
    """Crisp Win95 bevel above the contents, without intercepting input."""
    def __init__(self, window):
        super().__init__(window)
        self.setObjectName('retroWindowBorder')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(window.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Outer black contour, inner grey shadow, and a bright upper-left lip.
        for inset, (light, shadow) in enumerate([
            ('#dfdfdf', '#000000'),
            ('#ffffff', '#808080'),
            ('#dfdfdf', '#404040'),
            ('#c0c0c0', '#c0c0c0'),
        ]):
            rect = self.rect().adjusted(inset, inset, -inset, -inset)
            painter.setPen(QColor(light))
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
            painter.setPen(QColor(shadow))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.end()

class TitleBar(QWidget):
    def __init__(self, window, title=None, controls=True):
        super().__init__(window)
        self.window=window
        self.drag_pos=None
        self.setObjectName('retroTitleBar')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet('#retroTitleBar { background: #000080; color: white; } QLabel { color: white; }')
        layout=QHBoxLayout(self); layout.setContentsMargins(8,4,5,4); layout.setSpacing(5)
        logo=QLabel(); logo.setPixmap(icon().pixmap(22,22)); layout.addWidget(logo)
        self.label=QLabel(title or window.windowTitle()); self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.label,1)
        if controls:
            for caption,callback in [('_',window.showMinimized),('□',self.maximize)]:
                button=QPushButton(caption); button.setFixedSize(27,25); button.setStyleSheet('padding: 0; color: black;'); button.clicked.connect(callback); layout.addWidget(button)
        close=QPushButton('×'); close.setFixedSize(27,25); close.setStyleSheet('padding: 0; color: black;'); close.clicked.connect(window.close); layout.addWidget(close)
        window.windowTitleChanged.connect(self.label.setText)
    def maximize(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.drag_pos=event.globalPosition().toPoint()-self.window.frameGeometry().topLeft();event.accept()
    def mouseMoveEvent(self,event):
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton and not self.window.isMaximized():self.window.move(event.globalPosition().toPoint()-self.drag_pos);event.accept()
    def mouseReleaseEvent(self,event): self.drag_pos=None
    def mouseDoubleClickEvent(self,event):
        if not isinstance(self.window,QDialog):self.maximize()

class DialogChrome(QObject):
    shutting_down = False

    def eventFilter(self,obj,event):
        if self.shutting_down or sip.isdeleted(obj):
            return False
        if event.type()==QEvent.Type.Polish and isinstance(obj,QDialog) and not obj.property('retroDecorated') and obj.layout():
            obj.setProperty('retroDecorated',True)
            obj.setWindowFlag(Qt.WindowType.FramelessWindowHint,True)
            # Qt's standard dialogs keep and resize their own layout. Moving it
            # into a child widget breaks QMessageBox's updateSize() calculations
            # (and QInputDialog's dynamic layout), clipping the message text.
            # A layout menu widget provides native top chrome while leaving the
            # original layout and Qt's automatic sizing intact.
            layout = obj.layout()
            layout.setMenuBar(TitleBar(obj, controls=False))
            obj.setContentsMargins(6, 6, 6, 6)
            obj.setSizeGripEnabled(True)
        if isinstance(obj, (QDialog, QMainWindow, QMenu)):
            if event.type() == QEvent.Type.Polish and not hasattr(obj, '_retro_border'):
                if isinstance(obj, QMainWindow):
                    obj.setContentsMargins(4, 4, 4, 4)
                obj._retro_border = RaisedWindowBorder(obj)
                obj._retro_border.show()
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
                border = getattr(obj, '_retro_border', None)
                if border is not None and not sip.isdeleted(border):
                    border.setGeometry(obj.rect())
                    border.raise_()
        return False

def pixel_font(size=16, language=None):
    f = QFont(FAMILIES.get('ja' if language and language.startswith('ja') else 'zh', FAMILY) if language else FAMILY)
    f.setPixelSize(size)
    f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return f

def apply_theme(app, language='zh'):
    global FAMILY
    for key, filename in [('zh','unifont.otf'),('ja','unifont-jp.otf')]:
        if key not in FAMILIES:
            font_id = QFontDatabase.addApplicationFont(str(ROOT / 'assets' / filename))
            if font_id < 0:
                if key == 'ja' and language != 'ja': continue
                raise RuntimeError('像素字体文件无法加载：'+filename)
            FAMILIES[key] = QFontDatabase.applicationFontFamilies(font_id)[0]
    FAMILY = FAMILIES.get(language,FAMILIES['zh'])
    # Replacing the native style while closed dialogs await deferred deletion
    # can leave widgets referencing a style Qt has already destroyed. Language
    # changes only need new fonts/text; keep the original native style alive.
    if not getattr(app, '_retro_style_initialized', False):
        app.setStyle('Fusion')
        app._retro_style_initialized = True
    app.setFont(pixel_font())
    p = QPalette()
    # Reference installer background sampled at RGB (192, 192, 192).
    for role, color in [('Window','#c0c0c0'),('WindowText','#171717'),('Base','#ffffff'),
                        ('AlternateBase','#f0f0f0'),('Text','#171717'),('Button','#c0c0c0'),
                        ('ButtonText','#171717'),('Highlight','#000080'),('HighlightedText','#ffffff'),
                        ('Light','#ffffff'),('Midlight','#dedede'),('Dark','#555555')]:
        p.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    app.setPalette(p)
    if not hasattr(app,'retro_chrome'):
        app.retro_chrome=DialogChrome(app); app.installEventFilter(app.retro_chrome)
    app.setStyleSheet('''
        QWidget { font-family: "%s"; font-size: 16px; }
        QMainWindow, QDialog { background: #c0c0c0; }
        QLabel { background: transparent; }
        QToolTip { background: #ffffff; color: black; border: 1px solid black; padding: 4px; }
        QPushButton { background: #c0c0c0; border: 2px solid;
                      border-top-color: #ffffff; border-left-color: #ffffff;
                      border-bottom-color: #404040; border-right-color: #404040;
                      padding: 6px 13px; min-height: 20px; }
        QPushButton:pressed, QPushButton:checked {
                      border-top-color: #404040; border-left-color: #404040;
                      border-bottom-color: #ffffff; border-right-color: #ffffff; }
        QPushButton:disabled { color: #777777; }
        QPushButton:focus { outline: 1px dotted #000080; }
        QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox, QDoubleSpinBox,
        QListView, QTreeView, QTableView { background: #ffffff; color: #171717;
            border: 2px solid; border-top-color: #404040; border-left-color: #404040;
            border-bottom-color: #ffffff; border-right-color: #ffffff;
            selection-background-color: #000080; selection-color: white; }
        QLineEdit { padding: 5px 6px; }
        QComboBox { padding: 4px 8px; min-height: 22px; }
        QComboBox QAbstractItemView { background: #ffffff; padding: 2px; border: 2px solid;
            border-top-color: #ffffff; border-left-color: #ffffff;
            border-bottom-color: #000000; border-right-color: #000000;
            selection-background-color: #000080; selection-color: #ffffff; }
        QHeaderView::section { background: #c0c0c0; border: 1px outset #eeeeee; padding: 8px 6px; }
        QTableWidget { gridline-color: #dfdfdf; }
        QTableWidget::item { padding: 6px; }
        QListWidget::item { padding: 4px; }
        QListWidget::item:selected { background: #000080; color: white; }
        QMenuBar { padding: 2px; border-bottom: 1px solid #808080; }
        QMenuBar::item { padding: 5px 10px; }
        QMenuBar::item:selected, QMenu::item:selected { background: #000080; color: white; }
        QMenu { background: #c0c0c0; border: 4px solid #c0c0c0; padding: 2px; }
        QMenu::item { padding: 6px 24px; }
        QStatusBar { border-top: 1px solid #888888; }
        QStatusBar::item { border: 1px inset #eeeeee; }
        QProgressBar { border: 2px inset #eeeeee; background: #ffffff; text-align: center; }
        QProgressBar::chunk { background: #000080; width: 12px; margin: 1px; }
        QTabBar::tab { background: #c0c0c0; border: 2px outset #eeeeee; padding: 7px 16px; }
        QTabBar::tab:selected { background: #e2e2e2; }
        QGroupBox { border: 2px groove #eeeeee; margin-top: 15px; padding-top: 15px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QSplitter::handle { background: #c0c0c0; }
        QScrollBar { background: #d3d3d3; }
        QScrollBar::handle { background: #c0c0c0; border: 2px outset #eeeeee; min-height: 24px; min-width: 24px; }
    ''' % FAMILY)

def icon(kind='book', size=32):
    """Small original pixel icons; integer coordinates and nearest-neighbor scaling."""
    pm = QPixmap(32,32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    def box(x,y,w,h,c): p.fillRect(x,y,w,h,QColor(c))
    if kind in ('folder','import'):
        box(2,8,12,5,'#171717'); box(3,9,10,4,'#ffff9b')
        box(2,12,27,17,'#171717'); box(3,13,25,14,'#d8ac4c'); box(4,14,23,2,'#ffffad')
        box(5,17,25,12,'#171717'); box(6,18,23,10,'#f1d47a')
    else:
        box(6,3,21,27,'#171717'); box(7,4,19,25,'#247b7b')
        box(9,5,2,22,'#7cd3cb'); box(12,7,12,2,'#ffffd5')
        box(12,11,9,1,'#ffffd5'); box(8,25,17,3,'#eee6cc')
    if kind in ('import','add'):
        box(18,19,14,5,'#f7fff7'); box(22,15,5,14,'#f7fff7'); box(19,20,12,3,'#006b36'); box(23,16,3,12,'#006b36')
    if kind == 'delete':
        for i in range(10):
            box(18+i,17+i,3,3,'#a40000'); box(27-i,17+i,3,3,'#a40000')
    if kind in ('edit','metadata'):
        for i in range(14): box(13+i,26-i,4,4,'#161616'); box(14+i,26-i,2,2,'#ffcc32')
    if kind == 'convert':
        box(17,18,14,3,'#ffff8a'); box(26,15,3,9,'#ffff8a'); box(19,25,13,3,'#80ffff')
    p.end()
    return QIcon(pm.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation))

def cover_pixmap(book, w=156, h=208):
    pm = QPixmap()
    if book.get('cover') and pm.loadFromData(book['cover']):
        return pm.scaled(w,h,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)
    pm = QPixmap(w,h); pm.fill(QColor('#0c5a5a'))
    p = QPainter(pm); p.setFont(pixel_font())
    p.fillRect(8,0,3,h,QColor('#97c4b5')); p.setPen(QColor('#f6edc8'))
    p.drawRect(20,16,w-34,h-32)
    p.drawText(QRect(29,35,w-52,h-70),Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,book.get('title','未命名'))
    p.end(); return pm
