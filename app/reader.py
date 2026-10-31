"""Local, pixel-font book reading without executing ebook markup or styles."""
import hashlib
import json
import os
import re
import tempfile
import subprocess
import base64
from urllib.parse import urlsplit, unquote, unquote_to_bytes
from pathlib import Path

from calibre.ebooks.oeb.polish.container import get_container
from qt.core import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
                     QListWidget, QTextBrowser, QPushButton, QShortcut,
                     QKeySequence, QSplitter, QTimer, Qt, QVBoxLayout, QWidget,
                     QUrl, QTextDocument, QTextCursor, QTextCharFormat, QTextImageFormat,
                     QEvent, QVariant, QTextBlockFormat, pyqtSignal)
from i18n import tr, register
from theme import pixel_font
from preferences import get_image_mode, set_image_mode

register({
    '文本段 {number}': ('Text section {number}', 'テキスト {number}'),
    '书籍中没有可阅读的章节。': ('This book has no readable chapters.', 'この本には読める章がありません。'),
    '阅读支持 EPUB、AZW3 和 TXT；请先将此书转换为 EPUB。':
        ('Reading supports EPUB, AZW3 and TXT. Convert this book to EPUB first.', 'EPUB・AZW3・TXTを読めます。この本を先にEPUBへ変換してください。'),
    '阅读': ('Read', '読む'), '像素阅读室': ('Pixel reading room', 'ピクセル読書室'),
    '字号': ('Text size', '文字サイズ'), '正文语言': ('Text language', '本文の言語'),
    '自动（书籍语言）': ('Auto (book language)', '自動（本の言語）'),
    '查找当前章节…': ('Find in this chapter…', 'この章で検索…'),
    '查找': ('Find', '検索'), '章节目录': ('Chapters', '章の一覧'),
    '上一章': ('Previous chapter', '前の章'), '下一章': ('Next chapter', '次の章'),
    '关闭': ('Close', '閉じる'),
    '纯文本阅读 · 保留正文顺序 · 统一像素字体 · 自动记住位置':
        ('Plain-text reading · Original chapter order · Pixel type · Position saved automatically',
         'テキスト読書・原文の章順・ピクセルフォント・読書位置を自動保存'),
    '无法读取此章节：': ('Cannot read this chapter: ', 'この章を読めません：'),
    '第 {current} / {total} 章 · {progress}% ':
        ('Chapter {current} / {total} · {progress}% ', '{current} / {total} 章・{progress}% '),
    '没有找到：': ('Not found: ', '見つかりません：'),
    '正文与字符画 · 图片保持完整比例 · 自动记住位置':
        ('Text and ASCII images · Full image proportions · Reading position saved',
         '本文とASCII画像・画像の比率を保持・読書位置を保存'),
    '图片无法显示：': ('Cannot display image: ', '画像を表示できません：'),
    '正在准备阅读文件，请稍候。': ('Preparing the reading file. Please wait.', '読書用ファイルを準備しています。'),
    '阅读文件转换失败：': ('Reading conversion failed: ', '読書用の変換に失敗しました：'),
    '图片资源过大，无法安全显示。': ('This image is too large to display safely.', '画像が大きすぎるため表示できません。'),
    '图片不可用': ('Image unavailable', '画像を利用できません'),
    '不支持直接阅读这种文件。': ('This file type cannot be opened for reading.', 'この形式は直接読めません。'),
    '适合窗口': ('Fit window', 'ウィンドウに合わせる'),
    '适合页宽': ('Fit page width', 'ページ幅に合わせる'),
    '图片缩放': ('Image fit', '画像の拡大縮小'),
    '封面': ('Cover', '表紙'),
    '正文 {number}': ('Section {number}', '本文 {number}'),
    '插图': ('Illustrations', '挿絵'),
    '双击图片可放大查看细节': ('Double-click an image to inspect details', '画像をダブルクリックして詳細を拡大'),
})


class PreparedReadingFile:
    def __init__(self, path, temporary=None):
        self.path = Path(path).resolve()
        self.temporary = temporary

    def close(self):
        if self.temporary is not None:
            self.temporary.cleanup()
            self.temporary = None


def prepare_readable_path(path):
    """Convert in a worker thread; never write into an imported/source book."""
    path = Path(path).resolve(strict=True)
    if path.suffix.lower() in {'.epub', '.azw3', '.txt'}:
        return PreparedReadingFile(path)
    from calibre.customize.ui import available_input_formats
    if path.suffix.lower().lstrip('.') not in available_input_formats():
        raise ValueError(tr('不支持直接阅读这种文件。'))
    temp = tempfile.TemporaryDirectory(prefix='calibre95-read-')
    output = Path(temp.name) / 'book.epub'
    converter = Path(__file__).resolve().parents[1] / 'runtime/ebook-convert.exe'
    try:
        with (Path(temp.name) / 'conversion.log').open('wb') as log:
            process = subprocess.run([str(converter), str(path), str(output)],
                stdout=log, stderr=subprocess.STDOUT, timeout=600,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode or not output.is_file():
            details = (Path(temp.name) / 'conversion.log').read_text(encoding='utf-8', errors='replace')
            raise ValueError(tr('阅读文件转换失败：') + details[-1800:])
        return PreparedReadingFile(output, temp)
    except BaseException:
        temp.cleanup()
        raise


def _html_root(markup):
    from lxml import html
    markup = re.sub(r'<\?xml\s[^>]*\?>', '', markup, count=1, flags=re.IGNORECASE)
    return html.document_fromstring(markup or '<html><body></body></html>')


def readable_text(markup):
    """Extract Unicode text; never pass book CSS, URLs or HTML to a renderer."""
    from lxml import html
    if not markup.strip():
        return '', ''
    # Already-decoded XHTML commonly retains an XML encoding declaration.
    # lxml rejects that combination; remove the declaration, not any book text.
    markup = re.sub(r'<\?xml\s[^>]*\?>', '', markup, count=1, flags=re.IGNORECASE)
    markup = re.sub(r'(?i)</(?:p|div|h[1-6]|li|section|article|blockquote|tr)>', '\n\n\\g<0>', markup)
    markup = re.sub(r'(?i)<br\s*/?>', '\n', markup)
    markup = re.sub(r'(?i)</(?:td|th)>', '    \\g<0>', markup)
    root = html.document_fromstring(markup)
    headings = root.xpath('//h1|//h2') or root.xpath('//title')
    title = next((' '.join(node.text_content().split()) for node in headings
                  if node.text_content().strip()), '')
    for node in root.xpath('//script|//style|//head'):
        node.drop_tree()
    text = root.text_content().replace('\r', '')
    text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text).strip()
    return title, text


class ReaderDocument:
    def __init__(self, path, language='zh'):
        self.path = Path(path).resolve()
        self.prepared = None
        self.temp = None
        self.container = None
        self.title = self.path.stem
        self.language = language
        self.chapters = []
        self.cache = {}
        self.block_cache = {}
        self.image_cache = {}
        self.chapter_parts = []
        self.legacy_chapters = []
        self.prepared = prepare_readable_path(self.path)
        reading_path = self.prepared.path
        suffix = reading_path.suffix.lower()
        if suffix == '.txt':
            raw = reading_path.read_bytes()
            if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
                text = raw.decode('utf-16')
            else:
                try:
                    text = raw.decode('utf-8-sig')
                except UnicodeDecodeError:
                    from calibre.ebooks.chardet import xml_to_unicode
                    text = xml_to_unicode(raw, strip_encoding_pats=True)[0]
            # Keep each paragraph intact where practical while bounding UI size.
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            pages = []
            while len(text) > 18000:
                boundary = text.rfind('\n', 10000, 18000)
                if boundary < 0:
                    boundary = 18000
                else:
                    boundary += 1
                pages.append(text[:boundary])
                text = text[boundary:]
            pages.append(text)
            for index, page in enumerate(pages):
                title = tr('文本段 {number}', number=index + 1)
                self.chapters.append((str(index), title))
                self.cache[index] = page
        elif suffix in {'.epub', '.azw3'}:
            self.temp = tempfile.TemporaryDirectory(prefix='retro-reader-')
            try:
                self.container = get_container(str(reading_path), tdir=self.temp.name)
                metadata = self.container.mi
                self.title = metadata.title or self.title
                languages = metadata.languages or []
                if languages:
                    code = languages[0].lower()
                    self.language = 'ja' if code.startswith(('ja', 'jp')) else (
                        'zh' if code.startswith(('zh', 'chi')) else 'en')
                for name, linear in self.container.spine_names:
                    self.chapters.append((name, Path(name).stem))
                self._add_missing_cover()
                self._build_chapters()
                if not self.chapters:
                    raise ValueError(tr('书籍中没有可阅读的章节。'))
            except BaseException:
                self.close()
                raise
        else:
            raise ValueError(tr('阅读支持 EPUB、AZW3 和 TXT；请先将此书转换为 EPUB。'))

    def _add_missing_cover(self):
        """Kindle packages may store their cover only in OPF metadata."""
        from calibre.ebooks.oeb.polish.cover import get_raster_cover_name, get_cover_page_name
        cover_name = get_raster_cover_name(self.container)
        if not cover_name or cover_name not in self.container.name_path_map:
            return
        if get_cover_page_name(self.container) in {name for name, _ in self.chapters}:
            return
        for chapter, _ in self.chapters:
            root = _html_root(self.container.raw_data(chapter))
            for node in root.iter():
                if not isinstance(node.tag, str):
                    continue
                for attr in ('src', 'href', 'xlink:href', '{http://www.w3.org/1999/xlink}href', 'data'):
                    value = node.get(attr)
                    if value and self.container.href_to_name(value, chapter) == cover_name:
                        return
        block = self._image(self.container.name_to_href(cover_name, self.container.opf_name), self.container.opf_name, tr('封面'))
        if block is not None:
            self.chapters.insert(0, ('__calibre95_cover__', tr('封面')))
            self.cache[0] = ''
            self.block_cache[0] = [block]

    @staticmethod
    def _clean_title(value):
        return ' '.join((value or '').split())

    def _build_chapters(self):
        """Use book navigation, not conversion filenames, as chapter boundaries.

        A chapter may span several spine files, or start at an anchor inside
        one. Keep every spine fragment, including material outside the TOC.
        """
        from calibre.ebooks.oeb.polish.toc import get_toc, get_landmarks
        from calibre.ebooks.oeb.polish.cover import get_cover_page_name
        self.legacy_chapters = [name for name, _ in self.chapters]
        entries = {}
        try:
            for item in get_toc(self.container, verify_destinations=False).iterdescendants():
                title = self._clean_title(item.title)
                if title and item.dest in self.container.name_path_map:
                    entries.setdefault(item.dest, []).append((unquote(item.frag or ''), title))
        except Exception:
            # Broken navigation must not prevent reading intact spine content.
            pass
        special = {}
        try:
            for item in get_landmarks(self.container):
                if item['type'] in {'cover', 'title-page', 'toc'} and not item['frag']:
                    special[item['dest']] = (tr('封面') if item['type'] == 'cover' else
                                             self._clean_title(item['title']))
        except Exception:
            pass
        cover = get_cover_page_name(self.container)
        if cover:
            special[cover] = tr('封面')
        chapters, parts = [], []
        active_toc = False
        for number, name in enumerate(self.legacy_chapters):
            if name == '__calibre95_cover__':
                chapters.append((name, tr('封面')))
                parts.append([(name, '', '')])
                continue
            root = _html_root(self.container.raw_data(name))
            body = next(iter(root.xpath('//body')), root)
            nodes = list(body.iter())
            anchors = {}
            for position, node in enumerate(nodes):
                for key in (node.get('id'), node.get('name')):
                    if key:
                        anchors.setdefault(key, position)
            boundaries = {}
            for fragment, title in entries.get(name, ()):
                position = anchors.get(fragment) if fragment else 0
                if position is not None:
                    boundaries.setdefault(position, (fragment, title))
            # The fallback uses visible headings; the repeated HTML <title>
            # in converted Kindle files is the book name, not a chapter name.
            heading = next((self._clean_title(n.text_content()) for n in body.xpath('.//h1|.//h2|.//h3')
                            if self._clean_title(n.text_content()) not in {'', self.title}), '')
            title_tag = next(iter(root.xpath('//title')), None)
            html_title = self._clean_title(title_tag.text_content()) if title_tag is not None else ''
            if html_title.casefold() in {self.title.casefold(), Path(name).stem.casefold(), 'untitled'}:
                html_title = ''
            fallback = special.get(name) or heading or html_title
            if not fallback:
                text = self._clean_title(body.text_content())
                if not text and body.xpath('.//img|.//*[local-name()="image"]'):
                    fallback = tr('插图')
                else:
                    fallback = tr('正文 {number}', number=number + 1)
            starts = sorted({0, *boundaries})
            for offset, position in enumerate(starts):
                fragment, title = boundaries.get(position, ('', ''))
                end = boundaries[starts[offset + 1]][0] if offset + 1 < len(starts) else ''
                part = (name, fragment, end)
                if end:
                    prefix = self._part_markup(part)
                    prefix_root = _html_root(prefix)
                    if (not readable_text(prefix)[1] and
                            not prefix_root.xpath('//body//img|//body//*[local-name()="image"]|//body//svg|//body//object') and
                            'url(' not in prefix):
                        continue
                # A prefix before the first anchor belongs to the previous
                # chapter, if present; never discard it or duplicate it.
                fresh = bool(title) or not parts or name in special or (
                    position == 0 and not active_toc) or (
                    position == 0 and heading and heading != chapters[-1][1])
                if fresh:
                    chapters.append((name, title or fallback))
                    parts.append([part])
                else:
                    parts[-1].append(part)
                if title:
                    active_toc = True
        self.chapters = chapters
        self.chapter_parts = parts

    def _part_markup(self, part):
        name, start, end = part
        markup = self.container.raw_data(name)
        if not start and not end:
            return markup
        # Prune by document order while retaining ancestors and <head>, so
        # inherited image styling still works. Text/tails each belong to one
        # range. In particular the tail of the end anchor is not kept here.
        from lxml import etree
        root = _html_root(markup)
        body = next(iter(root.xpath('//body')), root)
        nodes = list(body.iter())
        starts = {node: position for position, node in enumerate(nodes)}
        anchors = {}
        for node, position in starts.items():
            for value in (node.get('id'), node.get('name')):
                if value:
                    anchors.setdefault(value, position)
        low, high = anchors.get(start, 0), anchors.get(end, len(nodes))
        def trim(node):
            position = starts[node]
            keep_self = low <= position < high
            if not keep_self:
                node.text = None
                node.set('data-calibre95-range-ancestor', '1')
            keep = keep_self
            for child in list(node):
                child_end = starts[child] + sum(1 for _ in child.iter())
                tail = child.tail if low <= child_end - 0.5 < high else None
                if trim(child):
                    child.tail = tail
                    keep = True
                else:
                    previous = child.getprevious()
                    node.remove(child)
                    if tail:
                        if previous is None:
                            node.text = (node.text or '') + tail
                        else:
                            previous.tail = (previous.tail or '') + tail
                        keep = True
            return keep
        trim(body)
        return etree.tostring(root, encoding='unicode', method='html')

    def restore_position(self, saved):
        """Map older spine-index bookmarks to the new logical chapter list."""
        index = min(max(0, int(saved.get('chapter', 0))), len(self.chapters) - 1)
        ratio = min(1.0, max(0.0, float(saved.get('scroll', 0))))
        if not self.chapter_parts:
            return index, ratio
        source = saved.get('source')
        if saved.get('chapter_schema') == 2 and source:
            fragment = saved.get('fragment', '')
            for current, parts in enumerate(self.chapter_parts):
                if parts[0][:2] == (source, fragment):
                    return current, ratio
        elif self.legacy_chapters:
            old = min(max(0, int(saved.get('chapter', 0))), len(self.legacy_chapters) - 1)
            source = self.legacy_chapters[old]
            for current, parts in enumerate(self.chapter_parts):
                for part_index, part in enumerate(parts):
                    if part[0] == source:
                        return current, (part_index + ratio) / len(parts)
        return index, ratio

    def text(self, index):
        if index not in self.cache:
            self.cache[index] = '\n\n'.join(readable_text(self._part_markup(part))[1]
                                            for part in self.chapter_parts[index])
        return self.cache[index]

    def _image(self, source, chapter, alt=''):
        """Read only package-local resources or bounded inline image data."""
        limit = 32 * 1024 * 1024
        if source.startswith('data:image/'):
            if len(source) > limit * 2:
                raise ValueError(tr('图片资源过大，无法安全显示。'))
            header, encoded = source.split(',', 1)
            data = base64.b64decode(encoded, validate=True) if ';base64' in header else unquote_to_bytes(encoded)
            name = 'inline-' + hashlib.sha256(data).hexdigest()
        else:
            parsed = urlsplit(source)
            if parsed.scheme or parsed.netloc:
                return None
            name = self.container.href_to_name(source, chapter)
            if not name or name not in self.container.name_path_map:
                return None
            image_path = Path(self.container.name_path_map[name]).resolve()
            if not image_path.is_relative_to(Path(self.container.root).resolve()):
                return None
            if image_path.stat().st_size > limit:
                raise ValueError(tr('图片资源过大，无法安全显示。'))
            data = self.image_cache.get(name)
            if data is None:
                data = image_path.read_bytes()
        if len(data) > limit:
            raise ValueError(tr('图片资源过大，无法安全显示。'))
        self.image_cache[name] = data
        return {'kind': 'image', 'name': name, 'data': data, 'alt': alt}

    def _background_images(self, root, chapter):
        """Extract static CSS artwork without applying CSS or fetching URLs."""
        from css_parser import CSSParser
        from css_selectors import Select, SelectorError
        import logging
        parser = CSSParser(fetcher=lambda url: (None, None), loglevel=logging.CRITICAL)
        select = Select(root, ignore_inappropriate_pseudo_classes=True)
        result, visited = {}, set()
        url_pattern = re.compile(r'url\(\s*(?:"([^"]*)"|\x27([^\x27]*)\x27|([^)]*))\s*\)', re.I)

        def resources(style, base):
            sources = None
            for declaration in style:
                if declaration.name.lower() in ('background', 'background-image'):
                    sources = []
                    for match in url_pattern.finditer(declaration.value):
                        source = next((part for part in match.groups() if part is not None), '').strip()
                        if source:
                            sources.append((source, base))
            return sources

        def apply_rules(rules, base, depth):
            for rule in rules:
                if rule.type == rule.STYLE_RULE:
                    found = resources(rule.style, base)
                    if found is not None:
                        try:
                            for element in select(rule.selectorText):
                                result[element] = found
                        except SelectorError:
                            pass
                elif rule.type == rule.IMPORT_RULE:
                    read_sheet(rule.href, base, depth + 1)
                elif hasattr(rule, 'cssRules'):
                    apply_rules(rule.cssRules, base, depth)

        def read_sheet(href, base, depth=0):
            if depth > 8:
                return
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                return
            name = self.container.href_to_name(href, base)
            if not name or name in visited or name not in self.container.name_path_map:
                return
            visited.add(name)
            path = Path(self.container.name_path_map[name]).resolve()
            if not path.is_relative_to(Path(self.container.root).resolve()) or path.stat().st_size > 2 * 1024 * 1024:
                return
            sheet = parser.parseString(self.container.raw_data(name), validate=False)
            apply_rules(sheet.cssRules, name, depth)

        for node in root.iter():
            if not isinstance(node.tag, str):
                continue
            tag = node.tag.rsplit('}', 1)[-1].lower()
            if tag == 'style' and node.text:
                apply_rules(parser.parseString(node.text, validate=False).cssRules, chapter, 0)
            elif tag == 'link' and 'stylesheet' in node.get('rel', '').lower().split() and node.get('href'):
                read_sheet(node.get('href'), chapter)
        for node in root.iter():
            if isinstance(node.tag, str) and node.get('style'):
                found = resources(parser.parseStyle(node.get('style'), validate=False), chapter)
                if found is not None:
                    result[node] = found
        return result

    def blocks(self, index):
        """Safe reading order: plain text blocks and original image byte resources."""
        if index in self.block_cache:
            return self.block_cache[index]
        if self.container is None:
            blocks = [{'kind': 'text', 'text': self.text(index)}]
            self.block_cache[index] = blocks
            return blocks
        blocks = []
        for part in self.chapter_parts[index]:
            blocks.extend(self._markup_blocks(part[0], self._part_markup(part)))
        self.block_cache[index] = blocks
        return blocks

    def _markup_blocks(self, name, markup):
        root = _html_root(markup)
        blocks, pending = [], []
        try:
            background_images = self._background_images(root, name)
        except Exception:
            background_images = {}

        def flush():
            text = ''.join(pending).replace('\r', '')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text).strip()
            if text:
                blocks.append({'kind': 'text', 'text': text})
            pending.clear()

        def local_tag(element):
            return str(element.tag).rsplit('}', 1)[-1].rsplit(':', 1)[-1].lower()

        def walk(node):
            if not isinstance(node.tag, str):
                return
            tag = local_tag(node)
            if tag in {'head', 'script', 'style', 'noscript', 'iframe', 'audio', 'video'}:
                return
            # Ancestors retained only to preserve a fragment's structure do
            # not repeat their decorative background in every TOC fragment.
            backgrounds = () if node.get('data-calibre95-range-ancestor') == '1' else background_images.get(node, ())
            for source, base in backgrounds:
                try:
                    block = self._image(source, base)
                    if block is not None:
                        flush()
                        blocks.append(block)
                except (OSError, ValueError):
                    pass
            if tag in {'img', 'image', 'object'}:
                source = node.get('src') or node.get('href') or node.get('xlink:href') or node.get('{http://www.w3.org/1999/xlink}href') or node.get('data')
                flush()
                if source:
                    try:
                        block = self._image(source.strip(), name, node.get('alt', ''))
                        if block is not None:
                            blocks.append(block)
                        else:
                            blocks.append({'kind': 'text', 'text': '[' + tr('图片不可用') + '] ' + node.get('alt', '')})
                    except (OSError, ValueError) as error:
                        blocks.append({'kind': 'text', 'text': tr('图片无法显示：') + str(error)})
                return
            if tag == 'svg' and not any(local_tag(x) == 'image' for x in node.iter()):
                # Inline vector artwork is rasterized by the same ASCII engine.
                # Remove links/scripts before passing SVG bytes to QtSvg.
                from lxml import etree
                flush()
                for bad in list(node.iter()):
                    if local_tag(bad) in {'script', 'foreignobject'}:
                        if bad.getparent() is not None:
                            bad.getparent().remove(bad)
                    for attr in list(bad.attrib):
                        if attr.lower().startswith('on') or 'href' in attr.lower():
                            if not bad.attrib[attr].startswith('#'):
                                del bad.attrib[attr]
                data = etree.tostring(node, encoding='utf-8')
                blocks.append({'kind': 'image', 'name': 'inline-svg-' + hashlib.sha256(data).hexdigest(), 'data': data, 'alt': ''})
                return
            if tag == 'br':
                pending.append('\n')
            if node.text:
                pending.append(node.text)
            for child in node:
                walk(child)
                if child.tail:
                    pending.append(child.tail)
            if tag in {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'section', 'article', 'blockquote', 'tr'}:
                pending.append('\n\n')
            elif tag in {'td', 'th'}:
                pending.append('    ')

        walk(root)
        flush()
        return blocks

    def images(self, index):
        return [block for block in self.blocks(index) if block['kind'] == 'image']

    def close(self):
        self.container = None
        self.block_cache.clear()
        self.image_cache.clear()
        if self.temp is not None:
            self.temp.cleanup()
            self.temp = None
        if self.prepared is not None:
            self.prepared.close()
            self.prepared = None


class LocalReadingBrowser(QTextBrowser):
    """Resource loader that never accesses the filesystem or network from markup."""
    image_activated = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ascii_resources = {}
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)

    def loadResource(self, kind, url):
        return self.ascii_resources.get(url.toString(), QVariant())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            image_format = cursor.charFormat()
            if not image_format.isImageFormat():
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                image_format = cursor.charFormat()
            if image_format.isImageFormat():
                name = image_format.toImageFormat().name()
                if name in self.ascii_resources:
                    self.image_activated.emit(name)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)


class BookReader(QDialog):
    def __init__(self, path, parent=None, language='zh', book_id=None, image_mode=None, document=None, music_service=None):
        super().__init__(parent)
        self.document = document if document is not None else ReaderDocument(path, language)
        self.current_index = -1
        self.loading = False
        self.positions = {}
        self.cleaned = False
        self.image_mode = image_mode if image_mode in ('color', 'mono') else get_image_mode()
        self.rendered_images = []
        self.image_sources = {}
        self.image_errors = []
        self._render_width = 0
        self._render_height = None
        self._pending_ratio = 0
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._render_after_resize)
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_pending_scroll)
        data_dir = Path(os.environ.get('RETROREADER_DATA_DIR',
                                      Path(__file__).resolve().parents[1] / 'Data'))
        self.state_path = data_dir / 'reading.json'
        identity = str(book_id) if book_id is not None else hashlib.sha256(
            str(Path(path).resolve()).encode('utf-8')).hexdigest()
        self.state_key = 'book:' + identity
        saved = self.load_state()
        self.image_fit = saved.get('image_fit', 'window')
        if self.image_fit not in ('window', 'width'):
            self.image_fit = 'window'
        self.setWindowTitle(tr('阅读') + ' — ' + self.document.title)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(1120, 780)
        self.setMinimumSize(760, 520)
        layout = QVBoxLayout(self)
        banner = QLabel('PIXEL READER  /  ' + tr('像素阅读室'))
        banner.setStyleSheet('background:#000080;color:white;padding:10px;')
        layout.addWidget(banner)
        title = QLabel(self.document.title)
        title.setWordWrap(True)
        layout.addWidget(title)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(tr('字号')))
        self.size_combo = QComboBox()
        self.size_combo.addItem('16 px', 16)
        self.size_combo.addItem('32 px', 32)
        self.size_combo.setCurrentIndex(1 if saved.get('size') == 32 else 0)
        bar.addWidget(self.size_combo)
        bar.addWidget(QLabel(tr('正文语言')))
        self.font_language = QComboBox()
        for label, code in [(tr('自动（书籍语言）'), 'auto'), ('中文', 'zh'), ('English', 'en'), ('日本語', 'ja')]:
            self.font_language.addItem(label, code)
        index = self.font_language.findData(saved.get('language', 'auto'))
        self.font_language.setCurrentIndex(max(0, index))
        bar.addWidget(self.font_language)
        bar.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('查找当前章节…'))
        self.search.returnPressed.connect(self.find_next)
        bar.addWidget(self.search)
        find = QPushButton(tr('查找'))
        find.clicked.connect(self.find_next)
        bar.addWidget(find)
        layout.addLayout(bar)
        image_bar = QHBoxLayout()
        image_bar.addWidget(QLabel(tr('图片显示')))
        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItem(tr('彩色字符画'), 'color')
        self.image_mode_combo.addItem(tr('黑白字符画'), 'mono')
        self.image_mode_combo.setCurrentIndex(self.image_mode_combo.findData(self.image_mode))
        image_bar.addWidget(self.image_mode_combo)
        image_bar.addWidget(QLabel(tr('图片缩放')))
        self.image_fit_combo = QComboBox()
        self.image_fit_combo.addItem(tr('适合窗口'), 'window')
        self.image_fit_combo.addItem(tr('适合页宽'), 'width')
        self.image_fit_combo.setCurrentIndex(self.image_fit_combo.findData(self.image_fit))
        image_bar.addWidget(self.image_fit_combo)
        image_bar.addStretch()
        image_hint = QLabel(tr('双击图片可放大查看细节'))
        image_hint.setWordWrap(True)
        image_bar.addWidget(image_hint)
        layout.addLayout(image_bar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(QLabel(tr('章节目录')))
        self.chapters = QListWidget()
        for index, (_, chapter_title) in enumerate(self.document.chapters):
            self.chapters.addItem(f'{index + 1:02d}  {chapter_title}')
        side_layout.addWidget(self.chapters)
        splitter.addWidget(side)
        self.page = LocalReadingBrowser()
        self.page.image_activated.connect(self.show_image_details)
        self.page.setToolTip(tr('双击图片可放大查看细节'))
        self.page.setReadOnly(True)
        self.page.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page.viewport().installEventFilter(self)
        splitter.addWidget(self.page)
        splitter.setSizes([235, 840])
        layout.addWidget(splitter, 1)
        bottom = QHBoxLayout()
        self.previous_button = QPushButton(tr('上一章'))
        self.previous_button.clicked.connect(lambda: self.change_chapter(-1))
        self.next_button = QPushButton(tr('下一章'))
        self.next_button.clicked.connect(lambda: self.change_chapter(1))
        bottom.addWidget(self.previous_button)
        bottom.addWidget(self.next_button)
        self.status = QLabel()
        bottom.addWidget(self.status, 1)
        close = QPushButton(tr('关闭'))
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        note = QLabel(tr('正文与字符画 · 图片保持完整比例 · 自动记住位置'))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.music_service = music_service
        if music_service is not None:
            from music_ui import MusicBar
            self.music_bar = MusicBar(music_service, self)
            layout.addWidget(self.music_bar)
            self.music_shortcut = QShortcut(QKeySequence('Ctrl+M'), self)
            self.music_shortcut.activated.connect(self.open_music)
        self.size_combo.currentIndexChanged.connect(self.update_font)
        self.font_language.currentIndexChanged.connect(self.update_font)
        self.image_mode_combo.currentIndexChanged.connect(self.update_image_mode)
        self.image_fit_combo.currentIndexChanged.connect(self.update_image_fit)
        self.chapters.currentRowChanged.connect(self.show_chapter)
        self.page.verticalScrollBar().valueChanged.connect(self.update_status)
        self.find_shortcut = QShortcut(QKeySequence('Ctrl+F'), self)
        self.find_shortcut.activated.connect(self.search.setFocus)
        self.next_shortcut = QShortcut(QKeySequence('Alt+Right'), self)
        self.next_shortcut.activated.connect(lambda: self.change_chapter(1))
        self.prev_shortcut = QShortcut(QKeySequence('Alt+Left'), self)
        self.prev_shortcut.activated.connect(lambda: self.change_chapter(-1))
        self.update_font()
        try:
            start_index, ratio = self.document.restore_position(saved)
            self.positions[start_index] = ratio
        except (TypeError, ValueError):
            start_index = 0
        self.chapters.setCurrentRow(start_index)
        self.finished.connect(self.cleanup)

    def open_music(self):
        if self.music_service is not None:
            self.music_service.show_player(self)

    def load_state(self):
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
            value = state.get(self.state_key, {})
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def scroll_ratio(self):
        bar = self.page.verticalScrollBar()
        return bar.value() / bar.maximum() if bar.maximum() else 0

    def update_font(self, *_):
        position = self.scroll_ratio()
        size = self.size_combo.currentData()
        language = self.font_language.currentData()
        if language == 'auto':
            language = self.document.language
        font = pixel_font(size, language)
        self.page.setFont(font)
        # Explicit CSS defeats the app-wide 16px rule, preserving integer scaling.
        self.page.setStyleSheet(f'QTextBrowser {{ background:#ffffff; color:#232323; padding:16px;'
                               f'font-family:"{font.family()}";font-size:{size}px; }}')
        self.page.document().setDefaultFont(font)
        if self.current_index >= 0:
            self._render_current(position)

    def update_image_mode(self, *_):
        self.image_mode = self.image_mode_combo.currentData()
        error = None
        try:
            set_image_mode(self.image_mode)
        except OSError as problem:
            error = problem
        self._render_current(self.scroll_ratio())
        if self.music_service is not None:
            self.music_service.preferences_changed.emit()
        if error is not None:
            self.status.setText(tr('无法保存显示设置') + ': ' + str(error))

    def update_image_fit(self, *_):
        self.image_fit = self.image_fit_combo.currentData()
        self._render_current(self.scroll_ratio())

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.Resize and not self.cleaned
                and self.current_index >= 0 and watched is self.page.viewport()):
            self._resize_timer.start()
        return super().eventFilter(watched, event)

    def _image_width(self):
        # Leave room for document margins and a possible vertical scroll bar.
        # Images always fit horizontally; tall pages remain fully scrollable.
        return min(1200, max(48, self.page.viewport().width() - 2 * round(self.page.document().documentMargin()) - 20))

    def _image_height(self):
        if self.image_fit == 'window':
            return max(64, self.page.viewport().height() - 2 * round(self.page.document().documentMargin()) - 32)
        return None

    def _render_after_resize(self):
        if (not self.cleaned and self.current_index >= 0
                and (self._image_width(), self._image_height()) != (self._render_width, self._render_height)):
            ratio = self._pending_ratio if self._restore_timer.isActive() else self.scroll_ratio()
            self._render_current(ratio)

    def _restore_pending_scroll(self):
        self.restore_scroll(self._pending_ratio)

    def _render_current(self, ratio=0):
        if self.cleaned or self.current_index < 0:
            return
        from ascii_art import render_ascii
        self.loading = True
        self._render_width = self._image_width()
        self._render_height = self._image_height()
        self.rendered_images = []
        self.image_sources.clear()
        self.image_errors = []
        self.page.clear()
        self.page.ascii_resources.clear()
        document = self.page.document()
        document.setDefaultFont(self.page.font())
        cursor = QTextCursor(document)
        text_format = QTextCharFormat()
        text_format.setFont(self.page.font())
        normal_block = QTextBlockFormat()
        normal_block.setBottomMargin(12)
        image_block = QTextBlockFormat()
        image_block.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        image_block.setTopMargin(8)
        image_block.setBottomMargin(16)
        try:
            blocks = self.document.blocks(self.current_index)
        except Exception as error:
            blocks = [{'kind': 'text', 'text': tr('无法读取此章节：') + str(error)}]
        for number, block in enumerate(blocks):
            if number:
                cursor.insertBlock(normal_block)
            if block['kind'] == 'text':
                cursor.setBlockFormat(normal_block)
                cursor.insertText(block['text'], text_format)
                continue
            try:
                image = render_ascii(block['data'], self._render_width, self._render_height, mode=self.image_mode)
                name = f'ascii-image:{self.current_index}:{number}:{self.image_mode}:{self._render_width}:{self._render_height}'
                self.page.ascii_resources[name] = image
                self.image_sources[name] = block
                document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), image)
                image_format = QTextImageFormat()
                image_format.setName(name)
                image_format.setWidth(image.width())
                image_format.setHeight(image.height())
                image_format.setProperty(QTextImageFormat.Property.ImageAltText, block.get('alt', ''))
                cursor.setBlockFormat(image_block)
                cursor.insertImage(image_format)
                self.rendered_images.append({'source': block['name'], 'image': image,
                                             'width': image.width(), 'height': image.height(),
                                             'mode': self.image_mode})
            except Exception as error:
                self.image_errors.append(str(error))
                cursor.setBlockFormat(normal_block)
                cursor.insertText('[' + tr('图片无法显示：') + str(error) + ']', text_format)
        self.loading = False
        self._pending_ratio = min(1.0, max(0.0, ratio))
        self._restore_timer.start(0)
        self.update_status()

    def show_image_details(self, name):
        block = self.image_sources.get(name)
        if self.cleaned or not block:
            return
        from image_viewer import AsciiImageDialog
        dialog = AsciiImageDialog(block['data'], self,
                                  title=tr('字符画细节') + ' — ' + self.document.title)
        try:
            dialog.exec()
        finally:
            dialog.cleanup()
            dialog.deleteLater()
            mode = get_image_mode()
            if mode != self.image_mode:
                self.image_mode = mode
                self.image_mode_combo.blockSignals(True)
                self.image_mode_combo.setCurrentIndex(self.image_mode_combo.findData(mode))
                self.image_mode_combo.blockSignals(False)
                self._render_current(self.scroll_ratio())

    def restore_scroll(self, ratio):
        if self.cleaned:
            return
        bar = self.page.verticalScrollBar()
        bar.setValue(round(bar.maximum() * ratio))
        self.update_status()

    def show_chapter(self, index):
        if index < 0 or index >= len(self.document.chapters):
            return
        if self.current_index >= 0:
            self.positions[self.current_index] = self.scroll_ratio()
        self.current_index = index
        self._render_current(self.positions.get(index, 0))
        name, title = self.document.chapters[index]
        self.chapters.item(index).setText(f'{index + 1:02d}  {title}')
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.document.chapters) - 1)
        self.update_status()

    def change_chapter(self, delta):
        index = self.current_index + delta
        if 0 <= index < len(self.document.chapters):
            self.chapters.setCurrentRow(index)

    def update_status(self, *_):
        if self.loading or self.cleaned:
            return
        count = len(self.document.chapters)
        progress = 100 * (max(0, self.current_index) + self.scroll_ratio()) / count
        if self.current_index == count - 1 and not self.page.verticalScrollBar().maximum():
            progress = 100
        self.status.setText(tr('第 {current} / {total} 章 · {progress}% ',
                               current=self.current_index + 1, total=count, progress=round(progress)))

    def find_next(self):
        value = self.search.text()
        if not value:
            return
        if not self.page.find(value):
            cursor = self.page.textCursor()
            original = cursor.position()
            cursor.setPosition(0)
            self.page.setTextCursor(cursor)
            if not self.page.find(value):
                cursor.setPosition(original)
                self.page.setTextCursor(cursor)
                self.status.setText(tr('没有找到：') + value)

    def cleanup(self, *_):
        if self.cleaned:
            return
        self._resize_timer.stop()
        self._restore_timer.stop()
        self.page.viewport().removeEventFilter(self)
        self.cleaned = True
        staged = None
        try:
            try:
                state = json.loads(self.state_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                state = {}
            if not isinstance(state, dict):
                state = {}
            state[self.state_key] = {'chapter': self.current_index,
                                    'chapter_schema': 2,
                                    'source': self.document.chapter_parts[self.current_index][0][0]
                                              if self.document.chapter_parts else '',
                                    'fragment': self.document.chapter_parts[self.current_index][0][1]
                                                if self.document.chapter_parts else '',
                                    'scroll': self.scroll_ratio(),
                                    'size': self.size_combo.currentData(),
                                    'language': self.font_language.currentData(),
                                    'image_fit': self.image_fit}
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, staged = tempfile.mkstemp(prefix='.reading-', dir=str(self.state_path.parent))
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
            os.replace(staged, self.state_path)
            staged = None
        except OSError:
            # A read-only data directory must not prevent closing a book.
            pass
        finally:
            if staged:
                try:
                    os.unlink(staged)
                except OSError:
                    pass
            self.document.close()
            self.page.ascii_resources.clear()
            self.rendered_images.clear()
            self.image_sources.clear()
