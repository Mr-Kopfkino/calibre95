"""A small, local EPUB/AZW3 source editor backed by calibre's containers.

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import re
import shutil
import tempfile
from pathlib import Path
from i18n import tr, register

from calibre.ebooks.chardet import replace_encoding_declarations
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.check.base import ERROR
from calibre.ebooks.oeb.polish.check.parsing import check_xml_parsing
from calibre.ebooks.oeb.polish.container import get_container
from qt.core import (
    QColor, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QShortcut, QKeySequence,
    QSplitter, QSyntaxHighlighter, QTextCharFormat, QTabWidget, QThread,
    Qt, QVBoxLayout, QWidget, pyqtSignal,
)

register({
    '内容编辑支持 EPUB 和 AZW3，请先将书籍转换为这两种格式。':
        ('Editing supports EPUB and AZW3. Convert the book first.', 'EPUBとAZW3を編集できます。先に本を変換してください。'),
    '加载期间书籍被其他程序修改，请重新打开。':
        ('The book changed while loading. Please reopen it.', '読み込み中に本が変更されました。開き直してください。'),
    '请先修复以下标记错误：\n\n': ('Fix these markup errors first:\n\n', '先に次の構文エラーを修正してください：\n\n'),
    '书籍已被其他程序修改。请关闭编辑器后重新打开，以免覆盖外部更改。':
        ('Another program changed this book. Close and reopen the editor before saving.', '別のプログラムが本を変更しました。編集画面を閉じてから開き直してください。'),
    '保存期间书籍被其他程序修改，本次保存已取消。':
        ('The book changed during saving. This save was canceled.', '保存中に本が変更されたため、保存を中止しました。'),
    '保存后的书籍缺少章节：{name}': ('Saved book is missing a chapter: {name}', '保存した本に章がありません：{name}'),
    '，第 {line} 行': (', line {line}', '、{line} 行目'),
    '编辑书籍 — ': ('Edit book — ', '書籍編集 — '),
    'BOOK EDITOR  /  书籍内容编辑': ('BOOK EDITOR  /  Content editor', 'BOOK EDITOR  /  本文編集'),
    '编辑章节与样式；切换文件保留草稿。保存时校验标记，并保留上一版本备份。':
        ('Edit chapters and styles. Drafts survive file switches. Saves validate markup and keep a previous-version backup.',
         '章とスタイルを編集します。ファイルを切り替えても下書きは残ります。保存時に構文を検証し、前の版を保管します。'),
    '保存书籍 (Ctrl+S)': ('Save book (Ctrl+S)', '本を保存 (Ctrl+S)'),
    '检查标记': ('Check markup', '構文を検証'), '撤销': ('Undo', '元に戻す'), '重做': ('Redo', 'やり直す'),
    '查找当前文件…': ('Find in this file…', 'このファイルで検索…'), '查找': ('Find', '検索'),
    '书内文件': ('Book files', '本のファイル'), '选择左侧文件以开始编辑': ('Select a file to begin editing', '左側で編集するファイルを選択'),
    '源码编辑': ('Source', 'ソース編集'), '正文预览': ('Text preview', '本文プレビュー'),
    '选择 HTML 章节，查看正文预览。': ('Select an HTML chapter to preview its text.', 'HTMLの章を選択すると本文を確認できます。'),
    '就绪': ('Ready', '準備完了'), '关闭': ('Close', '閉じる'),
    'EPUB / AZW3 · 本地编辑 · UTF-8': ('EPUB / AZW3 · Local editing · UTF-8', 'EPUB / AZW3・ローカル編集・UTF-8'),
    '无法打开文件': ('Cannot open file', 'ファイルを開けません'),
    '无法解析此章节预览：': ('Cannot preview this chapter: ', 'この章をプレビューできません：'),
    '这是样式或结构文件，请在「源码编辑」中查看。':
        ('This is a style or structure file. Open the Source tab to view it.', 'スタイルまたは構造ファイルです。ソース編集タブで確認してください。'),
    '行 {line}，列 {column}': ('Line {line}, column {column}', '{line} 行・{column} 列'),
    '{count} 个文件有未保存修改': ('{count} files with unsaved changes', '{count} ファイルに未保存の変更'),
    '已保存': ('Saved', '保存済み'), '没有找到：': ('Not found: ', '見つかりません：'),
    '标记检查': ('Markup check', '構文の検証'),
    '修改过的 HTML / XML 标记检查通过。\n此项检查不包含完整 EPUB 规范和 CSS 校验。':
        ('Changed HTML / XML markup passed.\nThis does not perform full EPUB or CSS validation.', '変更したHTML / XMLの構文検証に成功しました。\nEPUB全仕様とCSSの検証は含まれません。'),
    '无法保存': ('Cannot save', '保存できません'),
    '正在校验并保存书籍，请稍候…': ('Validating and saving. Please wait…', '検証して保存しています。お待ちください…'),
    '保存失败': ('Save failed', '保存に失敗しました'),
    '\n\n编辑草稿仍保留在此窗口中。若已生成备份，可通过 .retro-backup 文件恢复上一版本。':
        ('\n\nDrafts remain in this window. If a .retro-backup file exists, it contains the previous version.',
         '\n\n下書きはこの画面に残っています。.retro-backupファイルがあれば前の版を復元できます。'),
    '保存修改': ('Save changes', '変更を保存'),
    '书籍中有未保存的修改，是否保存后关闭？': ('Save changes to the book before closing?', '閉じる前に本の変更を保存しますか？'),
    '保存': ('Save', '保存'), '放弃修改': ('Discard', '変更を破棄'), '取消': ('Cancel', 'キャンセル'), '确定': ('OK', 'OK'),
})


class EditorSession:
    """Unpack into an owned temporary directory; never edit the input in-place."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        if self.path.suffix.lower() not in {'.epub', '.azw3'}:
            raise ValueError(tr('内容编辑支持 EPUB 和 AZW3，请先将书籍转换为这两种格式。'))
        self.expected_stat = self._stat()
        self.temp = tempfile.TemporaryDirectory(prefix='retro-editor-')
        try:
            self.container = get_container(str(self.path), tdir=self.temp.name)
            if self._stat() != self.expected_stat:
                raise RuntimeError(tr('加载期间书籍被其他程序修改，请重新打开。'))
        except BaseException:
            self.temp.cleanup()
            raise
        self.original = {}
        self.pending = {}
        self.names = sorted(
            name for name, mime in self.container.mime_map.items()
            if mime in OEB_DOCS or mime in OEB_STYLES or mime == 'text/plain'
            or mime.endswith(('+xml', '/xml'))
        )

    def _stat(self):
        value = self.path.stat()
        return value.st_size, value.st_mtime_ns

    def read(self, name):
        if name not in self.original:
            value = self.container.raw_data(name, normalize_to_nfc=False)
            if not isinstance(value, str):
                value = value.decode('utf-8')
            # QTextDocument uses LF internally. Normalizing here avoids false edits.
            self.original[name] = value.replace('\r\n', '\n').replace('\r', '\n')
        return self.pending.get(name, self.original[name])

    def update(self, name, text):
        self.read(name)
        if text == self.original[name]:
            self.pending.pop(name, None)
        else:
            self.pending[name] = text

    def validate(self):
        """Check changed markup using the same parser as calibre's book checker."""
        problems = []
        for name, text in self.pending.items():
            mime = self.container.mime_map[name]
            if mime in OEB_DOCS or mime.endswith(('+xml', '/xml')):
                normalized, _ = replace_encoding_declarations(text)
                for error in check_xml_parsing(name, mime, normalized.encode('utf-8')):
                    if error.level >= ERROR:
                        where = tr('，第 {line} 行', line=error.line) if error.line else ''
                        problems.append(f'{name}{where}\n{error.msg}')
        return problems

    def save(self):
        if not self.pending:
            return False
        problems = self.validate()
        if problems:
            raise ValueError(tr('请先修复以下标记错误：\n\n') + '\n\n'.join(problems[:12]))
        if self._stat() != self.expected_stat:
            raise RuntimeError(tr('书籍已被其他程序修改。请关闭编辑器后重新打开，以免覆盖外部更改。'))
        output = backup_temp = working_temp = None
        try:
            # Never mutate the browsing snapshot: a failed save followed by a
            # reverted draft must not resurrect that discarded draft on retry.
            working_temp = tempfile.TemporaryDirectory(prefix='retro-edit-save-')
            candidate = get_container(str(self.path), tdir=working_temp.name)
            for name, text in self.pending.items():
                text, _ = replace_encoding_declarations(text)
                with candidate.open(name, 'wb') as stream:
                    stream.write(text.encode('utf-8'))
            fd, output = tempfile.mkstemp(
                prefix='.retro-save-', suffix=self.path.suffix, dir=str(self.path.parent))
            os.close(fd)
            candidate.commit(outpath=output)
            # Re-open the complete result before replacing a user's book.
            with tempfile.TemporaryDirectory(prefix='retro-verify-') as verify_dir:
                verified = get_container(output, tdir=verify_dir)
                for name, _ in verified.spine_names:
                    if name not in verified.name_path_map or not Path(verified.name_path_map[name]).is_file():
                        raise ValueError(tr('保存后的书籍缺少章节：{name}', name=name))
                del verified
            if self._stat() != self.expected_stat:
                raise RuntimeError(tr('保存期间书籍被其他程序修改，本次保存已取消。'))
            fd, backup_temp = tempfile.mkstemp(prefix='.retro-backup-', dir=str(self.path.parent))
            os.close(fd)
            shutil.copy2(self.path, backup_temp)
            # This backup always contains the immediately previous saved version.
            os.replace(backup_temp, str(self.path) + '.retro-backup')
            backup_temp = None
            os.replace(output, self.path)
            output = None
            self.expected_stat = self._stat()
            old_temp = self.temp
            self.temp, working_temp = working_temp, None
            self.container = candidate
            self.container.path_to_ebook = str(self.path)
            try:
                old_temp.cleanup()
            except OSError:
                pass
            self.original.update(self.pending)
            self.pending.clear()
            return True
        finally:
            if working_temp is not None:
                working_temp.cleanup()
            for staged in (output, backup_temp):
                if staged and os.path.exists(staged):
                    os.unlink(staged)

    def close(self):
        self.container = None
        self.temp.cleanup()


class SourceHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []
        for pattern, color in (
            (r'</?[\w:.-]+|/?>', '#000080'),
            (r'\b[\w:-]+(?=\s*=)', '#800080'),
            (r'"[^"\n]*"|\x27[^\x27\n]*\x27', '#008000'),
            (r'&[\w#]+;', '#804000'),
            (r'<!--.*?-->', '#808080'),
        ):
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            self.rules.append((re.compile(pattern), style))

    def highlightBlock(self, text):
        # Build a map only for non-BMP text; repeatedly encoding prefixes is
        # quadratic on the long, minified HTML lines commonly found in e-books.
        positions = None
        if any(ord(character) > 0xffff for character in text):
            positions = [0]
            for character in text:
                positions.append(positions[-1] + (2 if ord(character) > 0xffff else 1))
        for pattern, style in self.rules:
            for match in pattern.finditer(text):
                # Qt positions count UTF-16 code units, unlike Python indices.
                start = positions[match.start()] if positions else match.start()
                end = positions[match.end()] if positions else match.end()
                size = end - start
                self.setFormat(start, size, style)


class SaveWorker(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, session, parent):
        super().__init__(parent)
        self.session = session

    def run(self):
        try:
            self.session.save()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit()


class BookEditor(QDialog):
    """Modal content editor. ``saved`` emits the updated book's absolute path."""

    saved = pyqtSignal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.session = EditorSession(path)
        self.current_name = None
        self.saved_once = False
        self.worker = None
        self.busy = False
        self.close_after_save = False
        self.setWindowTitle(tr('编辑书籍 — ') + Path(path).name)
        self.setMinimumSize(760, 500)
        self.resize(1060, 730)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        outer = QVBoxLayout(self)
        self.body = QWidget(self)
        outer.addWidget(self.body)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(0, 0, 0, 0)
        banner = QLabel(tr('BOOK EDITOR  /  书籍内容编辑'))
        banner.setStyleSheet('background:#000080; color:white; padding:9px; font-weight:bold;')
        layout.addWidget(banner)
        hint = QLabel(tr('编辑章节与样式；切换文件保留草稿。保存时校验标记，并保留上一版本备份。'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        toolbar = QHBoxLayout()
        self.save_button = QPushButton(tr('保存书籍 (Ctrl+S)'))
        self.save_button.clicked.connect(self.save_book)
        toolbar.addWidget(self.save_button)
        check = QPushButton(tr('检查标记'))
        check.clicked.connect(self.check_markup)
        toolbar.addWidget(check)
        undo = QPushButton(tr('撤销'))
        redo = QPushButton(tr('重做'))
        toolbar.addWidget(undo)
        toolbar.addWidget(redo)
        toolbar.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('查找当前文件…'))
        self.search.returnPressed.connect(self.find_next)
        toolbar.addWidget(self.search)
        find = QPushButton(tr('查找'))
        find.clicked.connect(self.find_next)
        toolbar.addWidget(find)
        layout.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel(tr('书内文件')))
        self.files = QListWidget()
        self.files.addItems(self.session.names)
        self.files.currentTextChanged.connect(self.select_file)
        left_layout.addWidget(self.files)
        splitter.addWidget(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.filename_label = QLabel(tr('选择左侧文件以开始编辑'))
        right_layout.addWidget(self.filename_label)
        self.text = QPlainTextEdit()
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setStyleSheet('QPlainTextEdit { background:#ffffff; color:#202020; }')
        self.highlighter = SourceHighlighter(self.text.document())
        self.text.textChanged.connect(self.text_changed)
        self.text.cursorPositionChanged.connect(self.update_status)
        undo.clicked.connect(self.text.undo)
        redo.clicked.connect(self.text.redo)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.text, tr('源码编辑'))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet('QPlainTextEdit { background:#ffffff; color:#202020; padding:12px; }')
        self.preview.setPlaceholderText(tr('选择 HTML 章节，查看正文预览。'))
        self.tabs.addTab(self.preview, tr('正文预览'))
        self.tabs.currentChanged.connect(self.update_preview)
        right_layout.addWidget(self.tabs)
        splitter.addWidget(right)
        splitter.setSizes([235, 780])
        layout.addWidget(splitter, 1)
        self.status = QLabel(tr('就绪'))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel(tr('EPUB / AZW3 · 本地编辑 · UTF-8')))
        bottom.addStretch()
        close = QPushButton(tr('关闭'))
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self.save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        self.save_shortcut.activated.connect(self.save_book)
        self.find_shortcut = QShortcut(QKeySequence('Ctrl+F'), self)
        self.find_shortcut.activated.connect(self.search.setFocus)
        self.finished.connect(self.cleanup)
        if self.session.names:
            first_chapter = next((name for name, _ in self.session.container.spine_names
                                  if name in self.session.names), self.session.names[0])
            self.files.setCurrentRow(self.session.names.index(first_chapter))
        else:
            self.text.setReadOnly(True)
        self.update_status()

    def cleanup(self, *_):
        self.session.close()

    def notice(self, title, message, icon=QMessageBox.Icon.Warning):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(message)
        box.setIcon(icon)
        box.addButton(tr('确定'), QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    def select_file(self, name):
        if not name or self.busy:
            return
        if self.current_name:
            self.session.update(self.current_name, self.text.toPlainText())
        try:
            value = self.session.read(name)
        except Exception as error:
            self.notice(tr('无法打开文件'), str(error))
            self.files.blockSignals(True)
            if self.current_name:
                self.files.setCurrentRow(self.session.names.index(self.current_name))
            self.files.blockSignals(False)
            return
        self.current_name = name
        self.text.blockSignals(True)
        self.text.setPlainText(value)
        self.text.blockSignals(False)
        self.filename_label.setText(name)
        self.update_status()
        self.update_preview()

    def text_changed(self):
        if self.current_name:
            self.session.update(self.current_name, self.text.toPlainText())
        self.update_status()
        self.update_preview()

    def update_preview(self, *_):
        if self.tabs.currentIndex() != 1 or not self.current_name:
            return
        mime = self.session.container.mime_map[self.current_name]
        raw = self.text.toPlainText()
        if mime in OEB_DOCS:
            try:
                # Extract text only. Book styles, scripts, fonts, images and URLs
                # are never sent to a renderer; the application pixel font wins.
                from lxml import html
                raw = re.sub(r'<\?xml\s[^>]*\?>', '', raw, count=1, flags=re.IGNORECASE)
                raw = re.sub(r'(?i)</(?:p|div|h[1-6]|li|section|article)>', '\n\n\\g<0>', raw)
                raw = re.sub(r'(?i)<br\s*/?>', '\n', raw)
                root = html.document_fromstring(raw)
                for node in root.xpath('//script|//style|//head'):
                    node.drop_tree()
                raw = root.text_content()
                raw = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', raw).strip()
            except Exception as error:
                raw = tr('无法解析此章节预览：') + str(error)
        elif mime != 'text/plain':
            raw = tr('这是样式或结构文件，请在「源码编辑」中查看。')
        self.preview.setPlainText(raw)

    def update_status(self):
        if self.busy:
            return
        cursor = self.text.textCursor()
        count = len(self.session.pending)
        location = tr('行 {line}，列 {column}', line=cursor.blockNumber() + 1, column=cursor.positionInBlock() + 1)
        state = tr('{count} 个文件有未保存修改', count=count) if count else tr('已保存')
        self.status.setText(location + '    |    ' + state)
        self.save_button.setEnabled(bool(count))
        self.setWindowTitle(('● ' if count else '') + tr('编辑书籍 — ') + self.session.path.name)

    def find_next(self):
        value = self.search.text()
        if not value:
            return
        if not self.text.find(value):
            cursor = self.text.textCursor()
            previous = cursor.position()
            cursor.setPosition(0)
            self.text.setTextCursor(cursor)
            if not self.text.find(value):
                cursor.setPosition(previous)
                self.text.setTextCursor(cursor)
                self.status.setText(tr('没有找到：') + value)

    def check_markup(self):
        problems = self.session.validate()
        if problems:
            self.notice(tr('标记检查'), '\n\n'.join(problems[:12]))
        else:
            self.notice(tr('标记检查'), tr('修改过的 HTML / XML 标记检查通过。\n此项检查不包含完整 EPUB 规范和 CSS 校验。'), QMessageBox.Icon.Information)

    def save_book(self):
        if self.busy or not self.session.pending:
            return
        problems = self.session.validate()
        if problems:
            self.notice(tr('无法保存'), '\n\n'.join(problems[:12]))
            self.close_after_save = False
            return
        self.busy = True
        self.body.setEnabled(False)
        self.status.setText(tr('正在校验并保存书籍，请稍候…'))
        self.worker = SaveWorker(self.session, self)
        self.worker.succeeded.connect(self.save_succeeded)
        self.worker.failed.connect(self.save_failed)
        self.worker.finished.connect(self.save_finished)
        self.worker.start()

    def save_succeeded(self):
        self.saved_once = True
        self.saved.emit(str(self.session.path))

    def save_failed(self, message):
        self.close_after_save = False
        self.notice(tr('保存失败'), message + tr('\n\n编辑草稿仍保留在此窗口中。若已生成备份，可通过 .retro-backup 文件恢复上一版本。'))

    def save_finished(self):
        self.busy = False
        self.body.setEnabled(True)
        self.worker.deleteLater()
        self.worker = None
        self.update_status()
        if self.close_after_save:
            self.close_after_save = False
            self.accept()

    def can_close(self):
        if self.busy:
            return False
        if not self.session.pending:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr('保存修改'))
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(tr('书籍中有未保存的修改，是否保存后关闭？'))
        box.setIcon(QMessageBox.Icon.Question)
        save = box.addButton(tr('保存'), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr('放弃修改'), QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton(tr('取消'), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() == save:
            self.close_after_save = True
            self.save_book()
            return False
        return box.clickedButton() == discard

    def closeEvent(self, event):
        if self.can_close():
            event.accept()
            super().reject()
        else:
            event.ignore()

    def reject(self):
        # Escape is equivalent to the title bar's close button.
        if self.can_close():
            super().reject()
