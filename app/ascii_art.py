"""ASCII image presentation for calibre95 (original files are never modified).

The luminance-to-character/color-sampling approach references Rainbow-Dreamer's
LGPL-2.1 ascii-converter, supplied with this project. This implementation adds
bounded decoding, aspect-correct fitting, adaptive cells and reusable glyphs.
Each cell is a printable ASCII glyph, with reverse-video glyphs in dark areas.
No original image pixels are copied into the displayed picture.
"""
from collections import OrderedDict
from functools import lru_cache
import hashlib
from io import BytesIO
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from qt.core import QImage

ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ''.join(chr(c) for c in range(32,127))
MAX_INPUT_BYTES = 40 * 1024 * 1024
MAX_SOURCE_PIXELS = 64_000_000
MAX_OUTPUT_PIXELS = 8_000_000
MAX_OUTPUT_SIDE = 8192
INVERSE = True
MAX_CELLS = 100_000
CACHE_BYTES = 32 * 1024 * 1024
_cache = OrderedDict()
_cache_bytes = 0


def normalize_mode(mode):
    return 'mono' if mode in ('mono', 'monochrome', 'bw', 'black-white') else 'color'


def clear_cache():
    global _cache_bytes
    _cache.clear()
    _cache_bytes = 0


def _decode_svg(data):
    # SVG resources supplied as bytes have no book directory context. The reader
    # resolves local image wrappers itself; this path accepts self-contained SVG.
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
    root = etree.fromstring(data, parser=parser)
    if etree.QName(root).localname.lower() != 'svg':
        raise ValueError('Unsupported image data')
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        for attr in list(node.attrib):
            value = node.attrib[attr].strip()
            if etree.QName(attr).localname == 'href' and value and not value.startswith(('#', 'data:image/')):
                del node.attrib[attr]
        if etree.QName(node.tag).localname in ('script', 'foreignObject'):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    clean = etree.tostring(root)
    # Do not let stylesheet url() read files or fetch network resources.
    clean = re.sub(rb'url\s*\(\s*[\"\x27]?(?!#)[^)]+\)', b'none', clean, flags=re.I)
    from qt.core import QByteArray, QPainter, QSvgRenderer, Qt
    renderer = QSvgRenderer(QByteArray(clean))
    if not renderer.isValid():
        raise ValueError('Invalid SVG image')
    dimensions = renderer.defaultSize()
    width, height = dimensions.width(), dimensions.height()
    if width <= 0 or height <= 0:
        box = renderer.viewBoxF()
        width, height = round(box.width()), round(box.height())
    if width <= 0 or height <= 0:
        raise ValueError('SVG has no usable dimensions')
    scale = min(1.0, 1600 / max(width, height))
    width, height = max(1, round(width * scale)), max(1, round(height * scale))
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    ptr = image.constBits()
    return Image.frombytes('RGBA', (width, height), ptr.asstring(image.sizeInBytes()),
                           'raw', 'RGBA', image.bytesPerLine()).convert('RGB')


def _decode(data):
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('Image data must be bytes')
    data = bytes(data)
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ValueError('Image is empty or exceeds the 40 MiB display limit')
    if b'<svg' in data[:4096].lower():
        return _decode_svg(data)
    try:
        with Image.open(BytesIO(data)) as opened:
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
                raise ValueError('Image dimensions exceed the display limit')
            # Applying orientation before aspect calculations avoids rotated covers.
            oriented = ImageOps.exif_transpose(opened)
            rgba = oriented.convert('RGBA')
            background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            return background.convert('RGB')
    except (Image.DecompressionBombError, OSError) as error:
        raise ValueError('Cannot decode this image') from error


def _geometry(source_size, width, height, detail):
    # Bound both requested axes together, preserving the requested canvas ratio.
    # Detail viewing can request a source wider than the output-side limit.
    width = max(1, int(width))
    source_w, source_h = source_size
    if height is None:
        height = max(1, round(width * source_h / source_w))
    else:
        height = max(1, int(height))
    scale = min(1.0, MAX_OUTPUT_SIDE / max(width, height),
                math.sqrt(MAX_OUTPUT_PIXELS / (width * height)))
    width, height = max(1, round(width * scale)), max(1, round(height * scale))
    factor = min(width / source_w, height / source_h)
    fit_w = max(1, min(width, round(source_w * factor)))
    fit_h = max(1, min(height, round(source_h * factor)))
    # Fixed fine cells retain increasingly more image detail as the view grows.
    cell_w, cell_h = (3, 5) if detail != 'low' else (4, 8)
    columns = max(1, round(fit_w / cell_w))
    rows = max(1, round(fit_h / cell_h))
    if columns * rows > MAX_CELLS:
        factor = math.sqrt(MAX_CELLS / (columns * rows))
        columns, rows = max(1, int(columns * factor)), max(1, int(rows * factor))
    return width, height, ((width-fit_w)//2, (height-fit_h)//2, fit_w, fit_h), columns, rows, cell_w, cell_h


@lru_cache(maxsize=8)
def _glyphs(cell_w, cell_h):
    font = ImageFont.truetype(str(ROOT / 'assets/unifont.otf'), 16)
    masks = {}
    for char in CHARACTERS:
        mask = Image.new('L', (8, 16))
        ImageDraw.Draw(mask).text((0, 0), char, font=font, fill=255, stroke_width=0)
        # Remove the font's unused leading; character pictures need continuous
        # tonal coverage rather than the larger line gap used for book text.
        mask = mask.crop((0, 3, 8, 15))
        if (cell_w, cell_h) != (8, 16):
            # Nearest-neighbour shrinking can erase whole one-pixel stems (M/W
            # were particularly affected). Area sampling followed by a binary
            # threshold retains those strokes while keeping crisp pixel glyphs.
            mask = mask.resize((cell_w, cell_h), Image.Resampling.BOX).point(
                lambda level: 255 if level >= 70 else 0)
        else:
            mask = mask.resize((cell_w, cell_h), Image.Resampling.NEAREST)
        if (cell_w, cell_h) == (3, 5):
            # Preserve the direction of these tiny ASCII strokes explicitly:
            # shrinking the 16px font can erase or merge their end pixels.
            compact_strokes = {
                '/': ('001', '001', '010', '100', '100'),
                '\\': ('100', '100', '010', '001', '001'),
                '-': ('000', '000', '111', '000', '000'),
                '_': ('000', '000', '000', '000', '111'),
                '|': ('010', '010', '010', '010', '010'),
            }
            if char in compact_strokes:
                mask = Image.frombytes('L', (3, 5), bytes(
                    255 if bit == '1' else 0 for row in compact_strokes[char] for bit in row))
        masks[char] = mask
    # Measure actual ink coverage rather than relying on a glyph order that can
    # change with the font. This keeps the tonal ramp monotonic at every size.
    usable = [ch for ch in CHARACTERS if ch == ' ' or masks[ch].getbbox()]
    ordered = sorted(usable, key=lambda ch: sum(masks[ch].getdata()), reverse=True)
    return masks, ''.join(ordered)



@lru_cache(maxsize=8)
def _full_models(cell_w, cell_h, inverse):
    from PIL import ImageChops
    masks, ramp = _glyphs(cell_w, cell_h)
    models = []
    seen = set()
    pixels = cell_w*cell_h
    for invert in (False, True) if inverse else (False,):
        for char in CHARACTERS:
            if invert and char == ' ':
                continue
            mask = masks[char]
            if invert:
                mask = ImageChops.invert(mask)
            values = tuple(mask.getdata())
            pattern = sum(1 << i for i, value in enumerate(values) if value)
            if pattern in seen or (invert and pattern == (1 << pixels)-1):
                continue
            seen.add(pattern)
            models.append((char, invert, pattern, pattern.bit_count(), mask))
    # Preselect a tone neighborhood. Exact spatial fit resolves the character.
    tables = []
    for level in range(256):
        desired = (255-level)/255*pixels
        allowed = [item for item in models if not item[1] or desired >= pixels*.48]
        nearest = min(abs(item[3]-desired) for item in allowed)
        candidates = tuple(item + (item[3]*4 + 1.2*(item[3]-desired)**2,) for item in allowed if abs(item[3]-desired) <= nearest+2.1)
        flat = min(allowed, key=lambda item: abs(item[3]-desired))
        tables.append((desired,candidates,flat))
    return tuple(models),tuple(tables)


def _analyze(data, width, height=None, detail='auto', mode='mono'):
    from PIL import ImageChops
    source = _decode(data)
    output_w,output_h,fit,columns,rows,cell_w,cell_h = _geometry(source.size,width,height,detail)
    colors = source.resize((columns,rows),Image.Resampling.LANCZOS)
    if mode == 'color':
        channels=source.split()
        gray_source=ImageChops.darker(ImageChops.darker(channels[0],channels[1]),channels[2])
    else:
        gray_source=source.convert('L')
    micro=gray_source.resize((columns*cell_w,rows*cell_h),Image.Resampling.LANCZOS)
    micro=micro.filter(ImageFilter.UnsharpMask(radius=.55,percent=80,threshold=3))
    levels=micro.resize((columns,rows),Image.Resampling.BOX).tobytes()
    micro_values=micro.tobytes()
    quantized=micro.point(lambda value: min(4,round((255-value)*4/255))).tobytes()
    models,tables=_full_models(cell_w,cell_h,INVERSE)
    chars=[]; inversions=[]; chosen=[]; ink_counts=[]
    shape_cache={}
    stride=columns*cell_w
    offsets=tuple(y*stride+x for y in range(cell_h) for x in range(cell_w))
    for index,level in enumerate(levels):
        target,options,flat=tables[level]
        row,col=divmod(index,columns)
        base=row*cell_h*stride+col*cell_w
        values=tuple(micro_values[base+offset] for offset in offsets)
        if max(values)-min(values)<20 or len(options)==1:
            match=flat
        else:
            planes=[0,0,0,0]
            for bit,offset in enumerate(offsets):
                n=quantized[base+offset]
                flag=1<<bit
                for q in range(n):
                    planes[q] |= flag
            p0,p1,p2,p3=planes
            key=(level,p0,p1,p2,p3)
            match=shape_cache.get(key)
            if match is None:
                best=float('inf')
                for item in options:
                    bits=item[2]
                    score=item[5]-2*((bits&p0).bit_count()+(bits&p1).bit_count()+(bits&p2).bit_count()+(bits&p3).bit_count())
                    if score<best:
                        best=score; match=item
                if len(shape_cache)<16384:
                    shape_cache[key]=match
        chars.append(match[0]); inversions.append(match[1]);chosen.append(match[4]); ink_counts.append(match[3])
    probe=tuple(colors.resize((32,32),Image.Resampling.BOX).getdata())
    neutral=sum(max(rgb)-min(rgb) for rgb in probe)/len(probe)<13
    return {'source_size':source.size,'output_size':(output_w,output_h),'content_rect':fit,
            'columns':columns,'rows':rows,'cell_width':cell_w,'cell_height':cell_h,
            'text':'\n'.join(''.join(chars[y*columns:(y+1)*columns]) for y in range(rows)),
            'characters':''.join(chars),'colors':tuple(colors.getdata()),'masks':chosen,
            'inverted':inversions,'ink_counts':ink_counts,'line_art':neutral}


def analyze_ascii(data, width, height=None, detail='auto', mode='mono'):
    """Return the printable, shape-matched luminance grid and full-image geometry."""
    return _analyze(data,width,height,detail,normalize_mode(mode))


def render_ascii(data, width, height=None, mode='color', detail='auto'):
    """Draw fine ASCII glyphs with calibrated ink; preserve the complete image.

    Width/height fits and letterboxes; height=None follows source aspect. Output
    owns its pixel bytes. The bounded cache returns independent caller copies.
    """
    global _cache_bytes
    mode = normalize_mode(mode)
    key = (hashlib.sha256(data).digest(), int(width), None if height is None else int(height), mode, detail)
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached.copy()
    grid = _analyze(data, width, height, detail, mode)
    columns, rows = grid['columns'], grid['rows']
    cell_w, cell_h = grid['cell_width'], grid['cell_height']
    drawing = Image.new('RGB',(columns*cell_w,rows*cell_h),'white')
    for index,char in enumerate(grid['characters']):
        if char==' ':
            continue
        mask=grid['masks'][index]
        color=(0,0,0)
        if mode=='color':
            coverage=grid['ink_counts'][index]/(cell_w*cell_h)
            sampled=grid['colors'][index]
            color=tuple(max(0,min(255,round(255-(255-channel)/max(.01,coverage)))) for channel in sampled)
        x,y=(index%columns)*cell_w,(index//columns)*cell_h
        drawing.paste(color,(x,y,x+cell_w,y+cell_h),mask)
    x,y,fit_w,fit_h=grid['content_rect']
    if drawing.size != (fit_w,fit_h):
        drawing=drawing.resize((fit_w,fit_h),Image.Resampling.NEAREST)
    output=Image.new('RGB',grid['output_size'],'white')
    output.paste(drawing,(x,y))
    raw=output.tobytes()
    result = QImage(raw, output.width, output.height, output.width*3, QImage.Format.Format_RGB888).copy()
    cost = result.sizeInBytes()
    if cost <= CACHE_BYTES:
        while _cache and (_cache_bytes + cost > CACHE_BYTES or len(_cache) >= 64):
            _, previous = _cache.popitem(last=False)
            _cache_bytes -= previous.sizeInBytes()
        _cache[key] = result
        _cache_bytes += cost
    return result.copy()
