"""Offline LRC/plain lyric parsing. Times are milliseconds, never wall-clock time."""
from bisect import bisect_right
import codecs
import re
from i18n import register, tr

register({
    '歌词文件超过 2 MiB 大小上限。': ('Lyrics exceed the 2 MiB limit', '歌詞ファイルが上限の2 MiBを超えています。'),
})

MAX_LYRIC_BYTES = 2 * 1024 * 1024
MAX_LYRIC_CHARS = 250_000
_STAMP = re.compile(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]')
_META = re.compile(r'^\s*\[([a-zA-Z]+):(.*?)\]\s*$')
_WORD_STAMP = re.compile(r'<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>')


def decode_lyrics(data):
    if len(data) > MAX_LYRIC_BYTES:
        raise ValueError(tr('歌词文件超过 2 MiB 大小上限。'))
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        pass
    # calibre ships chardet; it also distinguishes Japanese legacy lyric files.
    try:
        import chardet
        detected = chardet.detect(data)
        encoding = detected.get('encoding')
        # Short GB/SJIS text is often mislabeled as a Western single-byte codepage.
        # Accept a confident multibyte detection, then resolve common CJK cases.
        if (encoding and detected.get('confidence', 0) >= .5
                and any(name in encoding.lower() for name in ('utf', 'gb', 'big5', 'shift', 'euc', 'iso-2022'))):
            return data.decode(encoding)
    except (ImportError, LookupError, UnicodeError):
        pass
    try:
        japanese = data.decode('cp932')
        kana = sum('\u3040' <= char <= '\u30ff' for char in japanese)
        halfwidth = sum('\uff61' <= char <= '\uff9f' for char in japanese)
        if kana >= 2 and kana > halfwidth*2:
            return japanese
    except UnicodeDecodeError:
        pass
    for encoding in ('gb18030', 'cp932', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode('utf-8', errors='replace')


def parse_lrc(text):
    """Parse repeated timestamps, global offsets and plain unsynchronized lyrics.

    A positive LRC offset moves its lines earlier relative to audio. Simultaneous
    translated lines are merged, preserving both texts for one scroll position.
    """
    if isinstance(text, bytes):
        text = decode_lyrics(text)
    text = str(text or '').replace('\x00', '').lstrip('\ufeff')[:MAX_LYRIC_CHARS]
    metadata, timed, plain = {}, [], []
    offset = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        stamps = list(_STAMP.finditer(line))
        if stamps:
            content = _WORD_STAMP.sub('', _STAMP.sub('', line)).strip()
            for stamp in stamps:
                minutes, seconds, fraction = stamp.groups()
                if int(seconds) >= 60:
                    continue
                ms = (int(minutes)*60 + int(seconds))*1000 + int((fraction or '').ljust(3, '0') or '0')
                timed.append((ms, content))
        else:
            meta = _META.match(line)
            if meta and meta[1].lower() in {'ar', 'al', 'ti', 'by', 'offset', 'length', 're', 've'}:
                key, value = meta[1].lower(), meta[2].strip()
                metadata[key] = value
                if key == 'offset':
                    try:
                        offset = max(-86_400_000, min(86_400_000, int(value)))
                    except ValueError:
                        pass
            else:
                plain.append(_WORD_STAMP.sub('', line))
    lines = []
    for when, content in sorted(timed, key=lambda item: item[0]):
        when = max(0, when - offset)
        if lines and lines[-1]['time'] == when:
            if content and content not in lines[-1]['text'].split('\n'):
                lines[-1]['text'] = '\n'.join(filter(None, (lines[-1]['text'], content)))
        else:
            lines.append({'time': when, 'text': content})
    if lines:
        rendered = '\n'.join(line['text'] for line in lines)
    else:
        rendered = '\n'.join(plain)
        lines = [{'time': None, 'text': line} for line in plain]
    return {'timed': bool(timed), 'lines': lines, 'text': rendered, 'metadata': metadata}


def synchronized_lyrics(pairs):
    """Convert ID3 SYLT millisecond pairs into the same display document."""
    grouped = {}
    for text, position in pairs:
        try:
            position = max(0, int(position))
        except (ValueError, TypeError):
            continue
        if len(grouped) >= 20_000:
            break
        grouped.setdefault(position, []).append(str(text).strip())
    lines = [{'time': position, 'text': '\n'.join(filter(None, words))}
             for position, words in sorted(grouped.items())]
    return {'timed': bool(lines), 'lines': lines,
            'text': '\n'.join(line['text'] for line in lines), 'metadata': {}}


def line_index(document, position_ms):
    if not document or not document.get('timed'):
        return -1
    times = [line['time'] for line in document['lines']]
    return bisect_right(times, max(0, int(position_ms))) - 1
