"""Portable display preferences, shared by the shelf and reading windows."""
import json
import os
from pathlib import Path
import tempfile

from i18n import register

register({
    '图片显示': ('Images', '画像表示'),
    '彩色字符画': ('Color ASCII', 'カラーASCII'),
    '黑白字符画': ('Monochrome ASCII', '白黒ASCII'),
    '字符画显示': ('ASCII display', 'ASCII表示'),
    '无法保存显示设置': ('Cannot save display settings', '表示設定を保存できません'),
})

def settings_path():
    return Path(os.environ.get('RETROREADER_DATA_DIR', Path(__file__).resolve().parents[1]/'Data'))/'settings.json'

def get_image_mode():
    try:
        value = json.loads(settings_path().read_text(encoding='utf-8')).get('image_mode','color')
    except (OSError,ValueError,AttributeError):
        value = 'color'
    return value if value in ('color','mono') else 'color'

def set_image_mode(mode):
    if mode not in ('color','mono'):
        raise ValueError('Unknown ASCII image mode')
    path = settings_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        state = {}
    if not isinstance(state,dict): state = {}
    state['image_mode'] = mode
    fd, temporary = tempfile.mkstemp(prefix='.display-',suffix='.json',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(state,stream,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
