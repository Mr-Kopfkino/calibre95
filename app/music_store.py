"""Portable local music catalog; importing never changes the user's originals."""
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app/vendor'))
import mutagen
from lyrics import decode_lyrics, parse_lrc, synchronized_lyrics, MAX_LYRIC_BYTES
from i18n import register, tr

register({
    '无法读取此音频文件。': ('Cannot read this audio file', 'この音声ファイルを読み取れません。'),
    '音乐库数据无效。': ('Invalid music catalog', '音楽ライブラリのデータが無効です。'),
    '音乐库文件路径无效。': ('Invalid managed music path', '音楽ライブラリのファイルパスが無効です。'),
    '音乐文件路径超出音乐库。': ('Music path escapes the library', '音楽ファイルのパスがライブラリの外を指しています。'),
    '曲目标识无效。': ('Invalid track identity', '曲の識別子が無効です。'),
    '歌单数据无效。': ('Invalid playlist', 'プレイリストのデータが無効です。'),
    '未知的播放模式。': ('Unknown play mode', '不明な再生モードです。'),
    '未知的占位图类型。': ('Unknown placeholder kind', '不明な代替画像の種類です。'),
    '找不到此歌单。': ('Playlist not found', 'このプレイリストが見つかりません。'),
    '歌单名称不能为空。': ('Playlist name cannot be empty', 'プレイリスト名を入力してください。'),
    '歌单排序必须包含且仅包含该歌单的全部曲目。': ('Reorder must contain exactly the playlist tracks', '並べ替える曲は、このプレイリストの全曲と一致する必要があります。'),
    '不支持此音频文件。': ('Unsupported audio file', 'この音声ファイルには対応していません。'),
    '导入过程中原始音频文件发生变化。': ('Audio source changed while importing', '追加中に元の音声ファイルが変更されました。'),
    '找不到此曲目。': ('Track not found', 'この曲が見つかりません。'),
    '占位图片超过 20 MiB 大小上限。': ('Placeholder image exceeds the 20 MiB limit', '代替画像が上限の20 MiBを超えています。'),
    '占位图片的像素尺寸过大。': ('Placeholder image dimensions too large', '代替画像のピクセル数が大きすぎます。'),
})

SUPPORTED_EXTENSIONS = frozenset({'.mp3', '.flac', '.wav', '.wave', '.m4a', '.mp4',
    '.aac', '.ogg', '.opus', '.aif', '.aiff', '.wma', '.ape', '.wv', '.m4b'})
MAX_ART_BYTES = 20 * 1024 * 1024
DEFAULT_PLACEHOLDER = r'''   .--------------------------.
   |       CALIBRE95          |
   |    .----.    .----.      |
   |    | () |====| () |      |
   |    '----'    '----'      |
   |      MUSIC & BOOKS       |
   '--------------------------' '''
DEFAULT_SETTINGS = {'volume': 45, 'play_mode': 'order', 'show_lyrics': True, 'show_spectrum': True,
    'placeholder_text': DEFAULT_PLACEHOLDER, 'placeholder_kind': 'text',
    'placeholder_image': None, 'active_playlist': None, 'last_track': None}


def _first(tags, keys):
    for key in keys:
        value = tags.get(key)
        if value is None:
            continue
        if hasattr(value, 'text'):
            value = value.text
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ''
        value = str(value).strip().replace('\x00', '')
        if value:
            return value[:4096]
    return ''


def _asf_picture(value):
    """WM/Picture: type byte, little-endian size, two UTF16 strings, payload."""
    data = bytes(getattr(value, 'value', value))
    if len(data) < 9:
        return None
    length = int.from_bytes(data[1:5], 'little')
    if length <= 0 or length > MAX_ART_BYTES:
        return None
    offset = 5
    for _ in range(2):
        while offset + 1 < len(data) and data[offset:offset+2] != b'\0\0':
            offset += 2
        offset += 2
    return data[offset:offset+length] if offset + length <= len(data) else None


def read_metadata(path):
    """Read tags/art/lyrics with vendored, unmodified Mutagen (GPL2 or later)."""
    path = Path(path)
    audio = mutagen.File(str(path), easy=False)
    if audio is None or getattr(audio, 'info', None) is None:
        raise ValueError(tr('无法读取此音频文件。'))
    tags = audio.tags if audio.tags is not None else {}
    duration = max(0.0, float(getattr(audio.info, 'length', 0) or 0))
    result = {'title': _first(tags, ('TIT2', '\xa9nam', 'title', 'Title')) or path.stem,
              'artist': _first(tags, ('TPE1', '\xa9ART', 'artist', 'Author', 'ARTIST')),
              'album': _first(tags, ('TALB', '\xa9alb', 'album', 'WM/AlbumTitle', 'ALBUM')),
              'duration': duration, 'duration_ms': round(duration*1000), 'cover': None,
              'lyrics': parse_lrc('')}
    pictures = []
    if hasattr(tags, 'getall'):
        frames = tags.getall('APIC')
        frames.sort(key=lambda item: getattr(item, 'type', 0) != 3)
        pictures.extend(getattr(frame, 'data', b'') for frame in frames)
        for frame in tags.getall('SYLT'):
            if getattr(frame, 'format', 0) == 2:
                result['lyrics'] = synchronized_lyrics(frame.text)
                break
        if not result['lyrics']['lines']:
            frames = tags.getall('USLT')
            if frames:
                result['lyrics'] = parse_lrc(frames[0].text)
    if hasattr(audio, 'pictures'):
        pictures.extend(item.data for item in sorted(audio.pictures, key=lambda item: item.type != 3))
    pictures.extend(bytes(item) for item in tags.get('covr', []) if isinstance(item, bytes))
    for item in tags.get('WM/Picture', []):
        try:
            cover = _asf_picture(item)
            if cover: pictures.append(cover)
        except (TypeError, ValueError):
            pass
    for item in tags.get('metadata_block_picture', []):
        try:
            from mutagen.flac import Picture
            if len(item) <= MAX_ART_BYTES*2:
                pictures.append(Picture(base64.b64decode(item)).data)
        except (ValueError, TypeError, mutagen.MutagenError):
            pass
    if not pictures:
        for key in ('Cover Art (Front)', 'Cover Art (Back)'):
            try:
                item = tags.get(key)
                if item is not None:
                    data = bytes(item)
                    pictures.append(data.split(b'\0', 1)[-1])
            except (ValueError, TypeError):
                pass
    result['cover'] = next((data for data in pictures if data and len(data) <= MAX_ART_BYTES), None)
    if not result['lyrics']['lines']:
        lyric_text = _first(tags, ('\xa9lyr', 'lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS', 'WM/Lyrics'))
        # Lyrics can be much longer than a title; avoid _first's title bound.
        for key in ('\xa9lyr', 'lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS', 'WM/Lyrics'):
            value = tags.get(key)
            if value:
                lyric_text = str(value[0] if isinstance(value, (list, tuple)) else value)
                break
        result['lyrics'] = parse_lrc(lyric_text)
    return result


class MusicStore:
    def __init__(self, data_dir):
        self.music_dir = (Path(data_dir).resolve() / 'Music')
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.music_dir / 'music.json'
        self._lock = threading.RLock()
        self._art_cache = {}
        self._state = {'version': 1, 'tracks': [], 'playlists': [], 'settings': deepcopy(DEFAULT_SETTINGS)}
        if self.path.exists():
            try:
                state = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(state, dict) or not isinstance(state.get('tracks'), list) or not isinstance(state.get('playlists'), list):
                    raise ValueError(tr('音乐库数据无效。'))
                self._state.update(state)
                saved = state.get('settings', {})
                self._state['settings'] = {**DEFAULT_SETTINGS, **(saved if isinstance(saved, dict) else {})}
                self._validate()
            except (OSError, ValueError, TypeError, KeyError):
                # Preserve damaged state for recovery instead of silently replacing it.
                backup = self.music_dir / ('music-invalid-' + uuid.uuid4().hex[:8] + '.json')
                shutil.copy2(self.path, backup)
                self._state = {'version': 1, 'tracks': [], 'playlists': [], 'settings': deepcopy(DEFAULT_SETTINGS)}

    def _resolve(self, relative):
        if not relative or Path(relative).is_absolute():
            raise ValueError(tr('音乐库文件路径无效。'))
        path = (self.music_dir / relative).resolve()
        if not path.is_relative_to(self.music_dir):
            raise ValueError(tr('音乐文件路径超出音乐库。'))
        return path

    def _validate(self):
        ids = set()
        for track in self._state['tracks']:
            if not isinstance(track, dict) or not isinstance(track['id'], str) or track['id'] in ids:
                raise ValueError(tr('曲目标识无效。'))
            ids.add(track['id'])
            self._resolve(track['audio_path'])
            for key in ('cover_path', 'lyrics_path'):
                if track.get(key): self._resolve(track[key])
        playlist_ids = set()
        for playlist in self._state['playlists']:
            if not isinstance(playlist, dict) or playlist['id'] in playlist_ids or not isinstance(playlist['track_ids'], list):
                raise ValueError(tr('歌单数据无效。'))
            playlist_ids.add(playlist['id'])
            playlist['track_ids'] = list(dict.fromkeys(t for t in playlist['track_ids'] if t in ids))

    def _commit(self, state):
        fd, staged = tempfile.mkstemp(prefix='.music-', suffix='.json', dir=self.music_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged, self.path)
            self._state = state
        finally:
            if os.path.exists(staged): os.unlink(staged)

    def _view(self, track, details=False):
        result = deepcopy(track)
        result['path'] = str(self._resolve(track['audio_path']))
        result['missing'] = not Path(result['path']).is_file()
        result['has_cover'] = bool(track.get('cover_path'))
        result['has_lyrics'] = bool(track.get('lyrics', {}).get('text', '').strip())
        if not details:
            result.pop('lyrics', None)
            return result
        result['cover'] = None
        if track.get('cover_path'):
            try:
                path = self._resolve(track['cover_path'])
                if path.stat().st_size <= MAX_ART_BYTES:
                    key = str(path)
                    result['cover'] = self._art_cache.get(key)
                    if result['cover'] is None:
                        result['cover'] = path.read_bytes()
                        if sum(map(len, self._art_cache.values())) + len(result['cover']) > 32*1024*1024:
                            self._art_cache.clear()
                        self._art_cache[key] = result['cover']
            except OSError:
                pass
        result.setdefault('lyrics', parse_lrc(''))
        return result

    def tracks(self, playlist_id=None):
        with self._lock:
            tracks = self._state['tracks']
            if playlist_id:
                playlist = self._playlist(self._state, playlist_id)
                lookup = {track['id']: track for track in tracks}
                tracks = [lookup[identity] for identity in playlist['track_ids'] if identity in lookup]
            return [self._view(track) for track in tracks]

    def get_track(self, identity):
        with self._lock:
            track = next((t for t in self._state['tracks'] if t['id'] == identity), None)
            return self._view(track, True) if track else None

    def playlists(self):
        with self._lock:
            return deepcopy(self._state['playlists'])

    def settings(self):
        with self._lock:
            return deepcopy(self._state['settings'])

    def update_settings(self, **values):
        with self._lock:
            state = deepcopy(self._state)
            if 'volume' in values: values['volume'] = max(0, min(100, int(values['volume'])))
            if 'play_mode' in values and values['play_mode'] not in ('order', 'shuffle'): raise ValueError(tr('未知的播放模式。'))
            if 'show_lyrics' in values: values['show_lyrics'] = bool(values['show_lyrics'])
            if 'show_spectrum' in values: values['show_spectrum'] = bool(values['show_spectrum'])
            if 'placeholder_text' in values: values['placeholder_text'] = str(values['placeholder_text'])[:12000]
            if 'placeholder_kind' in values and values['placeholder_kind'] not in ('text', 'image'): raise ValueError(tr('未知的占位图类型。'))
            if values.get('placeholder_image'): self._resolve(values['placeholder_image'])
            state['settings'].update(values)
            self._commit(state)

    @staticmethod
    def _playlist(state, identity):
        playlist = next((p for p in state['playlists'] if p['id'] == identity), None)
        if playlist is None: raise KeyError(tr('找不到此歌单。'))
        return playlist

    @staticmethod
    def _name(value):
        value = str(value).strip()[:100]
        if not value: raise ValueError(tr('歌单名称不能为空。'))
        return value

    def create_playlist(self, name):
        with self._lock:
            state = deepcopy(self._state)
            identity = uuid.uuid4().hex
            state['playlists'].append({'id': identity, 'name': self._name(name), 'track_ids': []})
            self._commit(state)
            return identity

    def rename_playlist(self, identity, name):
        with self._lock:
            state = deepcopy(self._state)
            self._playlist(state, identity)['name'] = self._name(name)
            self._commit(state)

    def delete_playlist(self, identity):
        with self._lock:
            state = deepcopy(self._state)
            self._playlist(state, identity)
            state['playlists'] = [p for p in state['playlists'] if p['id'] != identity]
            if state['settings'].get('active_playlist') == identity: state['settings']['active_playlist'] = None
            self._commit(state)

    def add_to_playlist(self, identity, track_ids):
        with self._lock:
            state = deepcopy(self._state)
            playlist = self._playlist(state, identity)
            valid = {track['id'] for track in state['tracks']}
            playlist['track_ids'] = list(dict.fromkeys(playlist['track_ids'] + [t for t in track_ids if t in valid]))
            self._commit(state)

    def remove_from_playlist(self, identity, track_ids):
        with self._lock:
            state = deepcopy(self._state)
            playlist = self._playlist(state, identity)
            removing = set(track_ids)
            playlist['track_ids'] = [t for t in playlist['track_ids'] if t not in removing]
            self._commit(state)

    def reorder_playlist(self, identity, track_ids):
        with self._lock:
            state = deepcopy(self._state)
            playlist = self._playlist(state, identity)
            track_ids = list(track_ids)
            if len(track_ids) != len(set(track_ids)) or set(track_ids) != set(playlist['track_ids']):
                raise ValueError(tr('歌单排序必须包含且仅包含该歌单的全部曲目。'))
            playlist['track_ids'] = track_ids
            self._commit(state)

    def _write_asset(self, relative, data):
        target = self._resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def import_files(self, paths, playlist_id=None):
        result = {'added': [], 'duplicates': [], 'errors': []}
        with self._lock:
            if playlist_id: self._playlist(self._state, playlist_id)
        for value in paths:
            created = []
            try:
                # Audio IO and tag parsing run on the import worker without
                # locking the catalog read by playback and the GUI thread.
                source = Path(value).resolve()
                if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    raise ValueError(tr('不支持此音频文件。'))
                digest = hashlib.sha256()
                with source.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
                sha = digest.hexdigest()
                with self._lock:
                    duplicate = next((t for t in self._state['tracks'] if t['sha256'] == sha), None)
                    if duplicate:
                        if any(p['id'] == playlist_id for p in self._state['playlists']):
                            self.add_to_playlist(playlist_id, [duplicate['id']])
                        result['duplicates'].append(str(source))
                        continue
                metadata = read_metadata(source)
                identity = uuid.uuid4().hex
                relative = 'Audio/' + identity + source.suffix.lower()
                destination = self._resolve(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                created.append(destination)
                shutil.copy2(source, destination)
                # Reject a changing source rather than cataloging a different copy.
                copied = hashlib.sha256()
                with destination.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024*1024), b''): copied.update(chunk)
                if copied.hexdigest() != sha: raise OSError(tr('导入过程中原始音频文件发生变化。'))
                cover = metadata.pop('cover')
                track = dict(metadata, id=identity, sha256=sha, audio_path=relative,
                             source_name=source.name, cover_path=None, lyrics_path=None)
                if cover:
                    track['cover_path'] = 'Artwork/' + identity + '.img'
                    created.append(self._write_asset(track['cover_path'], cover))
                sidecars = {p.suffix.lower(): p for p in source.parent.iterdir()
                            if p.is_file() and p.stem.casefold() == source.stem.casefold() and p.suffix.lower() in ('.lrc', '.txt')}
                sidecar = sidecars.get('.lrc') or sidecars.get('.txt')
                if sidecar and sidecar.stat().st_size <= MAX_LYRIC_BYTES:
                    raw = sidecar.read_bytes()
                    track['lyrics'] = parse_lrc(decode_lyrics(raw))
                    track['lyrics_path'] = 'Lyrics/' + identity + sidecar.suffix.lower()
                    created.append(self._write_asset(track['lyrics_path'], raw))
                with self._lock:
                    # Another importer may have committed this content while
                    # our worker copied it. Re-check against the latest state.
                    duplicate = next((t for t in self._state['tracks'] if t['sha256'] == sha), None)
                    if duplicate:
                        if any(p['id'] == playlist_id for p in self._state['playlists']):
                            self.add_to_playlist(playlist_id, [duplicate['id']])
                        result['duplicates'].append(str(source))
                        for path in created:
                            path.unlink(missing_ok=True)
                        continue
                    state = deepcopy(self._state)
                    state['tracks'].append(track)
                    # Deleting the destination playlist during import keeps
                    # newly imported files in All music, never in a stale list.
                    playlist = next((p for p in state['playlists'] if p['id'] == playlist_id), None)
                    if playlist is not None: playlist['track_ids'].append(identity)
                    self._commit(state)
                    result['added'].append(identity)
            except (OSError, ValueError, TypeError, mutagen.MutagenError) as error:
                for path in created:
                    try: path.unlink(missing_ok=True)
                    except OSError: pass
                result['errors'].append({'path': str(value), 'error': str(error)})
        return result

    def set_track_lyrics(self, identity, source):
        source = Path(source)
        if source.stat().st_size > MAX_LYRIC_BYTES: raise ValueError(tr('歌词文件超过 2 MiB 大小上限。'))
        data = source.read_bytes()
        parsed = parse_lrc(decode_lyrics(data))
        with self._lock:
            state = deepcopy(self._state)
            track = next((t for t in state['tracks'] if t['id'] == identity), None)
            if track is None: raise KeyError(tr('找不到此曲目。'))
            relative = 'Lyrics/' + uuid.uuid4().hex + '.lrc'
            saved = self._write_asset(relative, data)
            try:
                old = track.get('lyrics_path')
                track.update(lyrics_path=relative, lyrics=parsed)
                self._commit(state)
            except BaseException:
                saved.unlink(missing_ok=True)
                raise
            if old:
                try: self._resolve(old).unlink(missing_ok=True)
                except OSError: pass

    def set_placeholder_image(self, source):
        source = Path(source)
        if source.stat().st_size > MAX_ART_BYTES: raise ValueError(tr('占位图片超过 20 MiB 大小上限。'))
        data = source.read_bytes()
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(data)) as image:
            if image.width*image.height > 64_000_000: raise ValueError(tr('占位图片的像素尺寸过大。'))
            image.verify()
        with self._lock:
            relative = 'Artwork/placeholder-' + uuid.uuid4().hex + source.suffix.lower()
            target = self._write_asset(relative, data)
            old = self._state['settings'].get('placeholder_image')
            try: self.update_settings(placeholder_image=relative, placeholder_kind='image')
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            if old:
                try: self._resolve(old).unlink(missing_ok=True)
                except OSError: pass
            return relative

    def placeholder_image(self):
        with self._lock:
            relative = self._state['settings'].get('placeholder_image')
            if not relative: return None
            try:
                path = self._resolve(relative)
                return path.read_bytes() if path.stat().st_size <= MAX_ART_BYTES else None
            except (OSError, ValueError):
                return None

    def remove_track(self, identity):
        """Remove the managed catalog entry and copies, never an import source."""
        with self._lock:
            state = deepcopy(self._state)
            track = next((t for t in state['tracks'] if t['id'] == identity), None)
            if not track: return
            state['tracks'] = [t for t in state['tracks'] if t['id'] != identity]
            for playlist in state['playlists']:
                playlist['track_ids'] = [t for t in playlist['track_ids'] if t != identity]
            if state['settings'].get('last_track') == identity: state['settings']['last_track'] = None
            self._commit(state)
            failures = []
            for key in ('audio_path', 'cover_path', 'lyrics_path'):
                if track.get(key):
                    try: self._resolve(track[key]).unlink(missing_ok=True)
                    except OSError as error: failures.append(str(error))
            self._art_cache.clear()
            if failures:
                raise OSError('\n'.join(failures))

    def close(self):
        with self._lock:
            self._art_cache.clear()
