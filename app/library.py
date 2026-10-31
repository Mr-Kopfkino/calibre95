"""The small, local-only calibre library adapter used by RetroReader.

Run with the bundled calibre-debug interpreter.  No network service, devices,
store, news or third-party calibre plugin actions are exposed by this adapter.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile

from calibre.customize.ui import available_input_formats, available_output_formats, can_set_metadata
from calibre.db.legacy import LibraryDatabase
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import string_to_authors
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.utils.localization import canonicalize_lang

try:
    from i18n import tr, register
except ImportError:
    def tr(text, **values):
        return text.format(**values) if values else text
    def register(values):
        pass

register({
    '书库已经关闭。': ('The library is closed.', 'ライブラリは閉じています。'),
    '这本书已经不在书库中，请刷新后重试。': ('This book is no longer in the library. Refresh and try again.', '書籍が見つかりません。更新して再試行してください。'),
    '未找到 {fmt} 格式的文件。': ('The {fmt} file was not found.', '{fmt} ファイルが見つかりません。'),
    '文件为空或不是普通文件。': ('The file is empty or not a regular file.', '空のファイル、または通常のファイルではありません。'),
    '不支持导入这种文件类型：{fmt}': ('This file type cannot be imported: {fmt}', 'このファイル形式は追加できません：{fmt}'),
    'EPUB 文件缺少 META-INF/container.xml。': ('The EPUB is missing META-INF/container.xml.', 'EPUB に META-INF/container.xml がありません。'),
    'DOCX 文件缺少正文。': ('The DOCX has no document body.', 'DOCX に本文がありません。'),
    '电子书压缩包已损坏。': ('The ebook archive is damaged.', '電子書籍の圧縮ファイルが破損しています。'),
    '文件不是有效的 PDF。': ('This is not a valid PDF file.', '有効な PDF ファイルではありません。'),
    '无法将文件写入书库。': ('Could not write the file to the library.', 'ライブラリにファイルを書き込めませんでした。'),
    '书名不能为空。': ('The title cannot be empty.', '書名を入力してください。'),
    '丛书序号应介于 0 和 1000000 之间。': ('The series number must be between 0 and 1000000.', '巻番号は 0 から 1000000 の範囲で入力してください。'),
    '无法识别语言代码：{language}（例如 zh、en、ja）。': ('Unknown language code: {language} (examples: zh, en, ja).', '不明な言語コード：{language}（例：zh、en、ja）。'),
    '评分必须介于 0 和 10 之间。': ('Rating must be between 0 and 10.', '評価は 0 から 10 の範囲で入力してください。'),
    '书库中已经有 {fmt} 格式。': ('The book already has a {fmt} format.', 'この書籍には既に {fmt} 形式があります。'),
    '目标文件已存在，请确认覆盖后重试。': ('The destination already exists. Confirm replacement and try again.', '保存先にファイルがあります。上書きを確認してください。'),
    '请将导出文件保存到书库目录之外。': ('Export outside the library directory.', 'ライブラリの外に書き出してください。'),
    '写入导出文件元数据失败。': ('Could not write metadata to the exported file.', '書き出しファイルにメタデータを書き込めませんでした。'),
    '{fmt} 暂不支持作为转换来源。': ('{fmt} is not supported as a conversion source.', '{fmt} からの変換には対応していません。'),
    '不支持转换为 {fmt}。': ('Conversion to {fmt} is not supported.', '{fmt} への変換には対応していません。'),
    '来源格式与目标格式不能相同。': ('Source and destination formats must be different.', '変換元と変換先の形式を変えてください。'),
    '转换已取消，原文件保持不变。': ('Conversion cancelled. The original file is unchanged.', '変換をキャンセルしました。元のファイルは変更されていません。'),
    '转换超时，原文件保持不变。': ('Conversion timed out. The original file is unchanged.', '変換がタイムアウトしました。元のファイルは変更されていません。'),
    '找不到转换引擎：{path}': ('Conversion engine not found: {path}', '変換エンジンが見つかりません：{path}'),
    '书库中已经有 {fmt} 格式。请确认覆盖后再试。': ('The book already has {fmt}. Confirm replacement and try again.', '書籍には既に {fmt} があります。上書きを確認してください。'),
    '格式转换失败，原文件保持不变。': ('Conversion failed. The original file is unchanged.', '変換に失敗しました。元のファイルは変更されていません。'),
    '转换完成，但 {fmt} 格式已存在；结果未覆盖。': ('Conversion finished, but {fmt} already exists and was not overwritten.', '変換が完了しましたが、{fmt} は既にあるため上書きしませんでした。'),
})


class LibraryError(Exception):
    """An error which can be shown directly in the desktop UI."""

    def __init__(self, message):
        super().__init__(tr(message))


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.digest()


class LibraryStore:
    def __init__(self, library_path, runtime_dir=None):
        self.path = Path(library_path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self.library_path = str(self.path)
        self.runtime_dir = Path(runtime_dir).resolve() if runtime_dir else Path(__file__).resolve().parents[1] / 'runtime'
        self._lock = threading.RLock()
        self._closed = False
        self._db = LibraryDatabase(str(self.path))
        self.db = self._db.new_api

    @staticmethod
    def input_formats():
        return sorted(x.upper() for x in available_input_formats())

    @staticmethod
    def output_formats():
        # OEB is a directory export, not an ebook file that calibre can store.
        return sorted(x.upper() for x in available_output_formats() if x.lower() != 'oeb')

    can_output_formats = output_formats

    @staticmethod
    def import_formats():
        return sorted({x.upper() for x in BOOK_EXTENSIONS} | set(LibraryStore.output_formats()))

    def _check_book(self, book_id):
        if self._closed:
            raise LibraryError('书库已经关闭。')
        if book_id not in self.db.all_book_ids():
            raise LibraryError('这本书已经不在书库中，请刷新后重试。')

    def get_book(self, book_id, include_cover=True):
        with self._lock:
            self._check_book(book_id)
            mi = self.db.get_metadata(book_id)
            stamp = getattr(mi, 'timestamp', None)
            date = getattr(mi, 'pubdate', None)
            return {
                'id': book_id,
                'title': mi.title or '未命名',
                'authors': list(mi.authors or []),
                'tags': list(mi.tags or []),
                'formats': list(self.db.formats(book_id)),
                'publisher': mi.publisher or '',
                'series': mi.series or '',
                'series_index': mi.series_index if mi.series_index is not None else 1.0,
                'comments': mi.comments or '',
                'languages': list(mi.languages or []),
                'rating': mi.rating or 0,
                'isbn': mi.isbn or '',
                'identifiers': mi.get_identifiers(),
                'size': self.db.field_for('size', book_id, 0) or 0,
                'timestamp': stamp.isoformat() if stamp else '',
                'pubdate': date.date().isoformat() if date and date.year > 101 else '',
                'cover': self.db.cover(book_id) if include_cover else None,
            }

    def list_books(self, include_covers=False):
        with self._lock:
            return [self.get_book(book_id, include_covers) for book_id in sorted(self.db.all_book_ids(), reverse=True)]

    def format_path(self, book_id, fmt):
        with self._lock:
            self._check_book(book_id)
            path = self.db.format_abspath(book_id, str(fmt).upper())
            if not path or not Path(path).is_file():
                raise LibraryError(tr('未找到 {fmt} 格式的文件。', fmt=fmt))
            return path

    @staticmethod
    def _validate_file(path):
        path = Path(path).resolve(strict=True)
        if not path.is_file() or not path.stat().st_size:
            raise LibraryError('文件为空或不是普通文件。')
        fmt = path.suffix.lstrip('.').upper()
        if fmt not in LibraryStore.import_formats():
            raise LibraryError(tr('不支持导入这种文件类型：{fmt}', fmt=fmt or '(none)'))
        if fmt in {'EPUB', 'KEPUB', 'DOCX', 'ODT'}:
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    if fmt in {'EPUB', 'KEPUB'} and 'META-INF/container.xml' not in names:
                        raise LibraryError('EPUB 文件缺少 META-INF/container.xml。')
                    if fmt == 'DOCX' and 'word/document.xml' not in names:
                        raise LibraryError('DOCX 文件缺少正文。')
                    if archive.testzip():
                        raise LibraryError('电子书压缩包已损坏。')
            except zipfile.BadZipFile as err:
                raise LibraryError('电子书压缩包已损坏。') from err
        if fmt == 'PDF':
            with path.open('rb') as stream:
                if b'%PDF-' not in stream.read(1024):
                    raise LibraryError('文件不是有效的 PDF。')
        return path, fmt

    def import_books(self, paths):
        result = {'added': [], 'errors': [], 'duplicates': []}
        for raw_path in paths:
            book_id = None
            try:
                path, fmt = self._validate_file(raw_path)
                digest = _sha256(path)
                with self._lock:
                    duplicate = False
                    for existing_id in self.db.all_book_ids():
                        if fmt not in self.db.formats(existing_id):
                            continue
                        existing = self.db.format_abspath(existing_id, fmt)
                        if existing and os.path.getsize(existing) == path.stat().st_size and _sha256(existing) == digest:
                            duplicate = True
                            break
                    if duplicate:
                        result['duplicates'].append(str(path))
                        continue
                    with path.open('rb') as stream:
                        mi = get_metadata(stream, stream_type=fmt.lower(), force_read_metadata=True)
                    if not mi.title or mi.title in ('Unknown', '未知'):
                        mi.title = path.stem
                    if not mi.authors:
                        mi.authors = ['佚名']
                    book_id = self.db.create_book_entry(mi, add_duplicates=True, apply_import_tags=False)
                    if not self.db.add_format(book_id, fmt, str(path), run_hooks=False):
                        raise LibraryError('无法将文件写入书库。')
                    self.db.dump_metadata([book_id])
                    result['added'].append(book_id)
            except Exception as err:
                if book_id is not None:
                    with self._lock:
                        if book_id in self.db.all_book_ids():
                            self.db.remove_books([book_id], permanent=False)
                result['errors'].append({'path': str(raw_path), 'error': str(err)})
        return result

    def update_metadata(self, book_id, values):
        with self._lock:
            self._check_book(book_id)
            mi = self.db.get_metadata(book_id)
            if 'title' in values:
                title = str(values['title']).strip()
                if not title:
                    raise LibraryError('书名不能为空。')
                mi.title, mi.title_sort = title, None
            if 'authors' in values:
                authors = values['authors']
                authors = string_to_authors(authors) if isinstance(authors, str) else authors
                mi.authors = [str(a).strip() for a in authors if str(a).strip()] or ['佚名']
                mi.author_sort = None
            for name in ('publisher', 'series', 'comments'):
                if name in values:
                    setattr(mi, name, str(values[name] or '').strip())
            if 'series_index' in values:
                index = float(values['series_index'])
                if not 0 <= index <= 1000000:
                    raise LibraryError('丛书序号应介于 0 和 1000000 之间。')
                mi.series_index = index
            if 'tags' in values:
                tags = values['tags']
                tags = tags.replace('，', ',').split(',') if isinstance(tags, str) else tags
                mi.tags = list(dict.fromkeys(str(t).strip() for t in tags if str(t).strip()))
            if 'languages' in values:
                languages = values['languages']
                languages = languages.replace('，', ',').split(',') if isinstance(languages, str) else languages
                normalized = []
                for language in languages:
                    if not str(language).strip():
                        continue
                    code = canonicalize_lang(str(language).strip())
                    if not code:
                        raise LibraryError(tr('无法识别语言代码：{language}（例如 zh、en、ja）。', language=language))
                    normalized.append(code)
                mi.languages = list(dict.fromkeys(normalized))
            if 'rating' in values:
                rating = int(values['rating'])
                if rating < 0 or rating > 10:
                    raise LibraryError('评分必须介于 0 和 10 之间。')
                mi.rating = rating
            if 'identifiers' in values:
                mi.set_identifiers(values['identifiers'])
            if 'isbn' in values:
                identifiers = mi.get_identifiers()
                identifiers.pop('isbn', None)
                isbn = str(values['isbn'] or '').strip()
                if isbn:
                    identifiers['isbn'] = isbn
                mi.set_identifiers(identifiers)
            if 'pubdate' in values:
                from calibre.utils.date import UNDEFINED_DATE, parse_date
                text = str(values['pubdate'] or '').strip()
                mi.pubdate = parse_date(text, assume_utc=True) if text else UNDEFINED_DATE
            if values.get('cover_path'):
                from PIL import Image
                cover = Path(values['cover_path']).read_bytes()
                with Image.open(io.BytesIO(cover)) as image:
                    image.verify()
                mi.cover_data = ('jpg', cover)
            self.db.set_metadata(book_id, mi, force_changes=True, allow_case_change=True)
            self.db.dump_metadata([book_id])
            return self.get_book(book_id)

    def remove_books(self, book_ids):
        with self._lock:
            ids = list(dict.fromkeys(int(book_id) for book_id in book_ids))
            for book_id in ids:
                self._check_book(book_id)
            self.db.remove_books(ids, permanent=False)
            return ids

    def add_format(self, book_id, path, replace=True):
        path, fmt = self._validate_file(path)
        with self._lock:
            self._check_book(book_id)
            if not self._install_format(book_id, fmt, path, replace):
                raise LibraryError(tr('书库中已经有 {fmt} 格式。', fmt=fmt))
            self.db.dump_metadata([book_id])
            return self.get_book(book_id)

    def export_format(self, book_id, fmt, destination, replace=False):
        """Export a copy, applying current metadata when the format supports it."""
        from calibre.ebooks.metadata.meta import set_metadata
        from calibre.customize.ui import apply_null_metadata, force_identifiers

        fmt = str(fmt).upper()
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not replace:
            raise LibraryError('目标文件已存在，请确认覆盖后重试。')
        with self._lock:
            self._check_book(book_id)
            source = Path(self.format_path(book_id, fmt)).resolve()
            if destination == source or destination.is_relative_to(self.path):
                raise LibraryError('请将导出文件保存到书库目录之外。')
            mi = self.db.get_metadata(book_id, get_cover=True, cover_as_data=True)
            with tempfile.TemporaryDirectory(prefix='.retro-export-', dir=str(destination.parent)) as temp:
                staged = Path(temp) / ('export.' + fmt.lower())
                self.db.copy_format_to(book_id, fmt, str(staged))
                embedded = can_set_metadata(fmt)
                if embedded:
                    errors = []
                    with staged.open('r+b') as stream, apply_null_metadata, force_identifiers:
                        set_metadata(stream, mi, stream_type=fmt.lower(), report_error=lambda *args: errors.append(str(args[-1])))
                    if errors:
                        raise LibraryError(tr('写入导出文件元数据失败。') + '\n' + '\n'.join(errors))
                if destination.exists() and not replace:
                    raise LibraryError('目标文件已存在，请确认覆盖后重试。')
                os.replace(staged, destination)
        return {'path': str(destination), 'format': fmt, 'metadata_embedded': embedded}

    def _install_format(self, book_id, fmt, source, replace):
        """Stage replacements on the library volume before the atomic rename."""
        current = self.db.format_abspath(book_id, fmt)
        if not current:
            return self.db.add_format(book_id, fmt, str(source), replace=replace, run_hooks=False)
        if not replace:
            return False
        current = Path(current)
        with tempfile.TemporaryDirectory(prefix='.retro-format-', dir=str(current.parent)) as stage:
            new = Path(stage) / current.name
            old = Path(stage) / ('original.' + fmt.lower())
            shutil.copyfile(source, new)
            shutil.copyfile(current, old)
            os.replace(new, current)
            try:
                # calibre detects the same file and only refreshes DB metadata.
                return self.db.add_format(book_id, fmt, str(current), replace=True, run_hooks=False)
            except Exception:
                os.replace(old, current)
                raise

    def convert_book(self, book_id, source_fmt, target_fmt, log_callback=None,
                     replace=False, cancel_event=None, timeout=1200):
        source_fmt, target_fmt = str(source_fmt).upper(), str(target_fmt).upper()
        if source_fmt not in self.input_formats():
            raise LibraryError(tr('{fmt} 暂不支持作为转换来源。', fmt=source_fmt))
        if target_fmt not in self.output_formats():
            raise LibraryError(tr('不支持转换为 {fmt}。', fmt=target_fmt))
        if source_fmt == target_fmt:
            raise LibraryError('来源格式与目标格式不能相同。')
        if cancel_event is not None and cancel_event.is_set():
            raise LibraryError('转换已取消，原文件保持不变。')
        executable = self.runtime_dir / ('ebook-convert.exe' if os.name == 'nt' else 'ebook-convert')
        if not executable.is_file():
            raise LibraryError(tr('找不到转换引擎：{path}', path=str(executable)))
        with tempfile.TemporaryDirectory(prefix='retroreader-convert-') as temp:
            temp = Path(temp)
            source, output = temp / f'source.{source_fmt.lower()}', temp / f'converted.{target_fmt.lower()}'
            metadata = temp / 'metadata.opf'
            with self._lock:
                self._check_book(book_id)
                if target_fmt in self.db.formats(book_id) and not replace:
                    raise LibraryError(tr('书库中已经有 {fmt} 格式。请确认覆盖后再试。', fmt=target_fmt))
                self.db.copy_format_to(book_id, source_fmt, str(source))
                mi = self.db.get_metadata(book_id)
                metadata.write_bytes(metadata_to_opf(mi))
                cover = self.db.cover(book_id)
            command = [str(executable), str(source), str(output), '--from-opf', str(metadata)]
            if cover:
                cover_path = temp / 'cover.jpg'
                cover_path.write_bytes(cover)
                command += ['--cover', str(cover_path)]
            log_path = temp / 'conversion.log'
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            started, position = time.monotonic(), 0
            with log_path.open('wb') as log_stream:
                process = subprocess.Popen(command, stdout=log_stream, stderr=subprocess.STDOUT,
                                           env=env, creationflags=flags, stdin=subprocess.DEVNULL)
                try:
                    while process.poll() is None:
                        if cancel_event is not None and cancel_event.is_set():
                            raise LibraryError('转换已取消，原文件保持不变。')
                        if time.monotonic() - started > timeout:
                            raise LibraryError('转换超时，原文件保持不变。')
                        if log_callback:
                            with log_path.open('rb') as reader:
                                reader.seek(position)
                                chunk = reader.read()
                                position = reader.tell()
                            if chunk:
                                log_callback(chunk.decode('utf-8', 'replace'))
                        time.sleep(0.1)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            log = log_path.read_text(encoding='utf-8', errors='replace')
            if log_callback:
                with log_path.open('rb') as reader:
                    reader.seek(position)
                    chunk = reader.read()
                if chunk:
                    log_callback(chunk.decode('utf-8', 'replace'))
            if process.returncode != 0 or not output.is_file() or not output.stat().st_size:
                raise LibraryError(tr('格式转换失败，原文件保持不变。') + '\n\n' + log[-12000:])
            self._validate_file(output)
            with self._lock:
                self._check_book(book_id)
                if not self._install_format(book_id, target_fmt, output, replace):
                    raise LibraryError(tr('转换完成，但 {fmt} 格式已存在；结果未覆盖。', fmt=target_fmt))
                self.db.dump_metadata([book_id])
                return {'id': book_id, 'format': target_fmt, 'path': self.format_path(book_id, target_fmt), 'log': log}

    def close(self):
        with self._lock:
            if not self._closed:
                self._db.close()
                self._closed = True
