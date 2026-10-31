"""Small offline UI catalog. Persisted language codes: zh_CN, en, ja."""
import json
from pathlib import Path

LANGUAGES = [('zh_CN', '中文'), ('en', 'English'), ('ja', '日本語')]
_language = 'zh_CN'
_settings_path = None
_catalog = {}

def register(values):
    """Add {Chinese source: (English, Japanese)} translations."""
    _catalog.update(values)

def get_language():
    return _language

def load_language(data_dir):
    global _settings_path, _language
    _settings_path = Path(data_dir) / 'settings.json'
    try:
        settings = json.loads(_settings_path.read_text(encoding='utf-8'))
        value = settings.get('language', 'zh_CN') if isinstance(settings, dict) else 'zh_CN'
        if value in dict(LANGUAGES):
            _language = value
    except (OSError, ValueError, TypeError):
        pass
    return _language

def set_language(value):
    global _language
    if value not in dict(LANGUAGES):
        raise ValueError('Unsupported language code')
    if _settings_path is not None:
        try:
            settings = json.loads(_settings_path.read_text(encoding='utf-8'))
            if not isinstance(settings, dict):
                settings = {}
        except (OSError, ValueError):
            settings = {}
        settings['language'] = value
        temporary = _settings_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(_settings_path)
    _language = value

def tr(key, **values):
    text = key
    if _language != 'zh_CN' and key in _catalog:
        text = _catalog[key][0 if _language == 'en' else 1]
    return text.format(**values) if values else text

register({
    '旧时书房': ('calibre95', 'calibre95'),
    '旧时书房 · Retro Reader': ('calibre95', 'calibre95'),
    '确定': ('OK', 'OK'), '取消': ('Cancel', 'キャンセル'),
    '编辑元数据 — ': ('Edit metadata — ', 'メタデータ編集 — '),
    '书籍资料卡 / BOOK PROPERTIES': ('BOOK PROPERTIES', '書籍情報 / BOOK PROPERTIES'),
    '书名': ('Title', '書名'), '作者': ('Author', '著者'), '格式': ('Format', '形式'),
    '标签': ('Tags', 'タグ'), '评分': ('Rating', '評価'),
    '作者（用 & 分隔）': ('Authors (separate with &)', '著者（& で区切る）'),
    '出版社': ('Publisher', '出版社'), '丛书': ('Series', 'シリーズ'),
    '标签（用逗号分隔）': ('Tags (comma separated)', 'タグ（カンマ区切り）'),
    '语言代码': ('Language codes', '言語コード'), '丛书序号': ('Series number', '巻番号'),
    '评分（0–5）': ('Rating (0–5)', '評価（0–5）'), '内容简介': ('Description', 'あらすじ'),
    '更换封面…': ('Change cover…', '表紙を変更…'), '保存资料': ('Save metadata', '情報を保存'),
    '选择封面': ('Choose a cover', '表紙を選択'),
    '图片 (*.png *.jpg *.jpeg *.webp)': ('Images (*.png *.jpg *.jpeg *.webp)', '画像 (*.png *.jpg *.jpeg *.webp)'),
    '封面：': ('Cover: ', '表紙：'), '请填写书名': ('Title required', '書名が必要です'),
    '书名不能为空。': ('The title cannot be empty.', '書名を入力してください。'),
    '未知作者': ('Unknown author', '著者不明'),
    '导入书籍': ('Import books', '書籍を追加'), '阅读书籍': ('Read book', '読む'),
    '编辑元数据': ('Metadata', 'メタデータ'), '编辑书籍': ('Edit book', '書籍を編集'),
    '格式转换': ('Convert', '形式変換'), '导出文件': ('Export', '書き出し'),
    '删除书籍': ('Remove', '削除'), '文件(F)': ('File (&F)', 'ファイル(&F)'),
    '退出': ('Exit', '終了'), '书籍(B)': ('Book (&B)', '書籍(&B)'),
    '视图(V)': ('View (&V)', '表示(&V)'), '封面书架': ('Cover shelf', '表紙の本棚'),
    '详细列表': ('Details list', '詳細一覧'), '刷新': ('Refresh', '更新'),
    '帮助(H)': ('Help (&H)', 'ヘルプ(&H)'), '使用说明': ('User guide', '使い方'),
    '关于旧时书房': ('About calibre95', 'calibre95 について'),
    '位置(D)': ('Location', '場所'),
    '我的电脑  /  旧时书房  /  本地书库': ('My Computer  /  calibre95  /  Library', 'マイ コンピューター  /  calibre95  /  書庫'),
    '书库目录': ('LIBRARY', '書庫'), '全部藏书': ('All books', 'すべての本'),
    '最近添加': ('Recently added', '最近追加した本'), '我的收藏': ('Favorites', 'お気に入り'),
    '其他格式': ('Other formats', 'その他の形式'),
    '▦ 书架': ('▦ Shelf', '▦ 本棚'), '≡ 列表': ('≡ List', '≡ 一覧'),
    '搜索书名、作者、标签…': ('Search title, author, tags…', '書名・著者・タグを検索…'),
    '最新添加': ('Newest first', '新しい順'), '书名 A → Z': ('Title A → Z', '書名 A → Z'),
    '作者 A → Z': ('Author A → Z', '著者 A → Z'),
    '书架还是空的\n\n点击“导入书籍”，或把文件拖到这里。': ('No books here yet.\n\nImport books or drop files here.', '本がありません。\n\n書籍を追加するか、ここにファイルをドロップしてください。'),
    '提示：拖入文件即可收藏 · Ctrl + O 导入 · Ctrl + E 编辑资料': ('Drop files to import · Ctrl + O Import · Ctrl + E Metadata', 'ドラッグで追加 · Ctrl + O 追加 · Ctrl + E メタデータ'),
    '书籍资料 / DETAILS': ('BOOK DETAILS', '書籍情報 / DETAILS'), '选择一本书': ('Select a book', '本を選んでください'),
    '☆ 加入收藏': ('☆ Add to favorites', '☆ お気に入りに追加'),
    '★ 已收藏 · 移出收藏': ('★ Remove favorite', '★ お気に入りから削除'),
    '编辑这本书的资料': ('Edit book metadata', '書籍情報を編集'),
    '本地书库  |  离线就绪': ('Local library  |  Offline ready', 'ローカル書庫  |  オフライン'),
    '{count:03d} 本书籍\nLOCAL DISK / CATALOG': ('{count:03d} books\nLOCAL DISK / CATALOG', '{count:03d} 冊\nLOCAL DISK / CATALOG'),
    '共 {total} 本书籍  |  当前显示 {shown} 本': ('{total} books  |  {shown} shown', '全 {total} 冊  |  {shown} 冊を表示'),
    '作者  ': ('Author  ', '著者  '), '格式  ': ('Format  ', '形式  '),
    '\n标签  ': ('\nTags  ', '\nタグ  '), '\n评分  ': ('\nRating  ', '\n評価  '),
    '未分类': ('Uncategorized', '未分類'),
    '暂无简介。可以在“编辑元数据”中添加。': ('No description. Add one in Metadata.', 'あらすじはありません。メタデータから追加できます。'),
    '，请稍候…': (', please wait…', '、お待ちください…'),
    '操作未完成': ('Operation failed', '操作に失敗しました'), '完成': (' completed', 'が完了しました'),
    '导入电子书': ('Import ebooks', '電子書籍を追加'),
    '电子书 (*.epub *.pdf *.azw3 *.mobi *.azw *.txt *.docx *.rtf *.fb2 *.cbz *.cbr *.html *.htmlz *.lit *.lrf *.djvu);;所有文件 (*)': ('Ebooks (*.epub *.pdf *.azw3 *.mobi *.azw *.txt *.docx *.rtf *.fb2 *.cbz *.cbr *.html *.htmlz *.lit *.lrf *.djvu);;All files (*)', '電子書籍 (*.epub *.pdf *.azw3 *.mobi *.azw *.txt *.docx *.rtf *.fb2 *.cbz *.cbr *.html *.htmlz *.lit *.lrf *.djvu);;すべてのファイル (*)'),
    '已导入 {added} 本，跳过 {duplicates} 个重复文件。': ('Imported {added}; skipped {duplicates} duplicate files.', '{added} 冊を追加、重複する {duplicates} ファイルをスキップしました。'),
    '\n\n未能导入：\n': ('\n\nCould not import:\n', '\n\n追加できなかったファイル：\n'),
    '导入结果': ('Import result', '追加結果'), '保存元数据': ('Save metadata', 'メタデータを保存'),
    '更新收藏': ('Update favorites', 'お気に入りを更新'),
    '内容编辑支持 EPUB、AZW3。请先使用“格式转换”生成 EPUB。': ('Editing supports EPUB and AZW3. Convert this book to EPUB first.', '編集は EPUB・AZW3 に対応しています。先に EPUB に変換してください。'),
    '选择要编辑的格式': ('Choose a format to edit', '編集する形式を選択'),
    '无法编辑': ('Unable to edit', '編集できません'), '源格式': ('Input format', '入力形式'),
    '目标格式': ('Output format', '出力形式'),
    '转换结果保存在同一本书中。\n源格式将保留，转换期间请勿关闭软件。': ('The result is added to this book.\nThe source format is kept. Keep the app open during conversion.', '変換結果は同じ本に追加されます。\n元の形式は保持されます。変換中は終了しないでください。'),
    '开始转换': ('Start conversion', '変換を開始'), '不支持转换': ('Cannot convert', '変換できません'),
    '该书没有可用的输入格式。': ('This book has no supported input format.', '対応する入力形式がありません。'),
    '请选择不同格式': ('Choose a different format', '別の形式を選択'),
    '源格式与目标格式不能相同。': ('Input and output formats must differ.', '入力形式と出力形式は別の形式を選んでください。'),
    '替换已有格式': ('Replace existing format', '既存の形式を置き換える'),
    '此书已有 {format} 格式。确认用新转换结果替换？': ('This book already has {format}. Replace it with the new conversion?', 'この本には既に {format} があります。変換結果で置き換えますか？'),
    '转换为 ': ('Convert to ', '変換先：'), '转换完成': ('Conversion complete', '変換が完了しました'),
    '已生成 {format}，可以通过“导出文件”保存副本。': ('Created {format}. Use Export to save a copy.', '{format} を作成しました。書き出しでコピーを保存できます。'),
    '选择格式': ('Choose a format', '形式を選択'), '导出书籍': ('Export book', '書籍を書き出し'),
    '将从书库移除选中的 {count} 本书及其全部格式。\n导入前的原始文件不受影响。\n\n确认删除？': ('Remove {count} selected book(s) and all their formats from this library?\nYour original import files are kept.\n\nConfirm removal?', '選択した {count} 冊とその全形式を書庫から削除します。\n追加前の元ファイルは保持されます。\n\n削除しますか？'),
    '任务正在进行': ('Task in progress', '処理中です'),
    '请等待当前任务完成后再退出。': ('Wait for the current task to finish before exiting.', '処理が完了してから終了してください。'),
    '书库已打开': ('Library already open', '書庫は既に開いています'),
    '这个书库已在另一个窗口中打开。': ('This library is open in another window.', 'この書庫は別のウィンドウで開いています。'),
    '启动失败': ('Startup failed', '起動に失敗しました'),
    '请检查 Data/logs/startup-error.log。\n': ('Check Data/logs/startup-error.log.\n', 'Data/logs/startup-error.log を確認してください。\n'),
    '语言': ('Language', '言語'),
    '无法切换语言': ('Unable to switch language', '言語を変更できません'),
    '选择要阅读的格式': ('Choose a format to read', '読む形式を選択'),
    '无法阅读': ('Unable to open book', '書籍を開けません'),
    '此格式暂不支持直接阅读，请转换为 EPUB 后再打开。': ('Convert this book to EPUB to read it here.', 'この書籍を EPUB に変換してから開いてください。'),
    '未找到匹配的书籍\n\n尝试清除搜索内容或更换分类。': ('No matching books.\n\nClear the search or select another category.', '一致する本がありません。\n\n検索を消すか、別の分類を選んでください。'),
    '使用说明正文': ('Import: choose files or drop them here; multiple selection is supported.\nRead: double-click a book to open the retro reader.\nManage: search, filter, favorite, sort and export.\nMetadata: edit title, authors, cover, tags and description.\nEdit: edit EPUB / AZW3 source and styles. Other convertible formats are prepared as EPUB automatically; originals are kept.\nConvert: use the calibre engine; source files are kept.\nRemove: removes library copies, keeping your original import files.\n\nThe library is stored in Data/Library. Close the app before backing up the entire Data folder.\n\nChoose 中文 / English / 日本語 at the top to switch the interface. UI and reading use the bundled GNU Unifont pixel font.', '追加：ファイルを選択またはドロップします。複数選択できます。\n読む：本をダブルクリックしてレトロリーダーを開きます。\n管理：検索、形式の絞り込み、お気に入り、並べ替え、書き出し。\nメタデータ：書名、著者、表紙、タグ、あらすじを編集。\n編集：EPUB / AZW3 のソースやスタイルを編集。変換可能な他形式は自動で EPUB を作成し、元の形式を保持します。\n変換：calibre を使用し、元の形式を保持。\n削除：書庫内のコピーだけを削除します。\n\n書庫は Data/Library に保存されます。終了してから Data フォルダー全体をバックアップしてください。\n\n上部の 中文 / English / 日本語 から表示言語を変更できます。UI と読書には同梱の GNU Unifont ピクセルフォントを使用します。'),
    '关于正文': ('calibre95 1.0.1\nA quiet home for your books.\n\nPowered by calibre 7.26.0 / GPL v3\nUI: original Qt-drawn Windows 95/98 style\nPixel font: GNU Unifont / OFL 1.1\n\nImport, read, manage, edit books, edit metadata, convert and remove.', 'calibre95 1.0.1\n本のための静かな場所。\n\ncalibre 7.26.0 / GPL v3 を使用\nUI：Qtで描画した独自のWindows 95/98風デザイン\nピクセルフォント：GNU Unifont / OFL 1.1\n\n書籍の追加、読書、管理、編集、メタデータ編集、形式変換、削除。'),
})

# Chinese full-text help uses readable copy rather than the catalog key.
_zh_long = {
    # Keep existing translation keys compatible while presenting the new brand.
    '旧时书房': 'calibre95',
    '旧时书房 · Retro Reader': 'calibre95',
    '关于旧时书房': '关于 calibre95',
    '我的电脑  /  旧时书房  /  本地书库': '我的电脑  /  calibre95  /  本地书库',
    '使用说明正文': '导入：点击导入或拖入文件；支持多选。\n阅读：双击书籍，打开复古阅读器。\n管理：搜索、格式筛选、收藏、排序和导出。\n元数据：修改书名、作者、封面、标签等。\n编辑：编辑 EPUB / AZW3 的章节源码与样式；其他可转换格式会自动生成 EPUB，保留源格式。\n转换：调用 calibre 引擎，源格式保留。\n删除：仅删除库内副本，保留导入源文件。\n\n书库保存在软件目录 Data/Library。\n关闭软件后备份整个 Data 文件夹。\n\n上方可切换中文 / English / 日本語。界面与阅读正文统一使用 GNU Unifont 像素字体。',
    '关于正文': 'calibre95 1.0.1\n一个安静的本地电子书书库。\n\n基于 calibre 7.26.0 / GPL v3\n界面：Qt 绘制的原创 Windows 95/98 风格控件\n像素字体：GNU Unifont / OFL 1.1\n\n支持导入、阅读、删除、管理、编辑书籍、\n编辑元数据与格式转换。',
}
_base_tr = tr
def tr(key, **values):
    if _language == 'zh_CN' and key in _zh_long:
        text = _zh_long[key]
        return text.format(**values) if values else text
    return _base_tr(key, **values)

def install_qt_translator(app):
    """Translate Qt's own file dialogs without shipping an OS-specific catalog."""
    from qt.core import QTranslator, QLocale
    mapping = {
        'Look in:': ('查找范围：', '場所：'), 'File name:': ('文件名：', 'ファイル名：'),
        'File &name:': ('文件名(&N)：', 'ファイル名(&N)：'), 'Files of type:': ('文件类型：', 'ファイルの種類：'),
        'Files of &type:': ('文件类型(&T)：', 'ファイルの種類(&T)：'),
        '&Open': ('打开(&O)', '開く(&O)'), 'Open': ('打开', '開く'),
        '&Save': ('保存(&S)', '保存(&S)'), 'Save': ('保存', '保存'),
        '&Cancel': ('取消(&C)', 'キャンセル(&C)'), 'Cancel': ('取消', 'キャンセル'),
        'OK': ('确定', 'OK'), '&OK': ('确定(&O)', 'OK(&O)'),
        '&Yes': ('是(&Y)', 'はい(&Y)'), '&No': ('否(&N)', 'いいえ(&N)'),
        'Name': ('名称', '名前'), 'Size': ('大小', 'サイズ'), 'Type': ('类型', '種類'),
        'Date Modified': ('修改时间', '更新日時'), 'Folder': ('文件夹', 'フォルダー'),
        'New Folder': ('新建文件夹', '新しいフォルダー'), 'Choose': ('选择', '選択'),
        'Back': ('后退', '戻る'), 'Forward': ('前进', '進む'),
        'Parent Directory': ('上级目录', '親フォルダー'), 'List View': ('列表', '一覧'),
        'Detail View': ('详细信息', '詳細'), 'Computer': ('计算机', 'コンピューター'),
        'Show ': ('显示 ', '表示 '), 'All Files (*)': ('所有文件 (*)', 'すべてのファイル (*)'),
        '%1 already exists.\nDo you want to replace it?': ('%1 已存在。\n是否替换？', '%1 は既に存在します。\n置き換えますか？'),
        'Confirm Save As': ('确认另存为', '名前を付けて保存の確認'),
        '%1\nFile not found.\nPlease verify the correct file name was given.': ('%1\n找不到文件。\n请检查文件名。', '%1\nファイルが見つかりません。\nファイル名を確認してください。'),
    }
    class CatalogTranslator(QTranslator):
        def isEmpty(self):
            return False
        def translate(self, context, sourceText, disambiguation=None, n=-1):
            if get_language() == 'en':
                return sourceText
            value = mapping.get(sourceText)
            return value[0 if get_language() == 'zh_CN' else 1] if value else sourceText
    old = getattr(app, '_retro_translator', None)
    if old is not None:
        app.removeTranslator(old)
    translator = CatalogTranslator(app)
    app.installTranslator(translator)
    app._retro_translator = translator
    QLocale.setDefault(QLocale({'zh_CN': 'zh_CN', 'en': 'en_US', 'ja': 'ja_JP'}[get_language()]))
