# calibre95 1.0.1

Windows 95/98 风格的本地电子书管理、阅读与音乐播放器。
A local ebook library, reader and music player with a Windows 95/98-inspired interface.

## 下载与运行

下载 GitHub Releases 中的 **calibre95-1.0.1-windows-x64.zip**，完整解压后双击 **calibre95.exe**。
仅支持 **Windows 10 / 11，x64**。无需安装 Python、Node、Qt 或 calibre。
这是复古外观的软件，不能在真正的 Windows 95/98 上运行。

推荐解压到 `D:\calibre95` 或其他可写的短路径。不要只复制 EXE，不要在 ZIP 内直接运行，也不要放入需要管理员权限才能写入的 Program Files。
calibre 7.26.0 要求新建书库的完整 `Data/Library` 路径少于 75 个字符。

发布版不附带任何书籍、音乐、播放记录、个人设置或用户数据库，首次启动不会自动导入示例。
程序首次运行后在自身目录内创建 `Data`。移动整个文件夹即可携带书库、音乐库和设置；备份整个 Data 文件夹。
更新时先退出程序并备份 Data，再将旧版 Data 复制到新版本目录中。

## 功能

- 导入、删除、搜索、收藏、编辑书籍元数据和格式转换，使用 calibre 7.26.0 引擎。
- EPUB/AZW3 内容编辑；其他可转换格式会自动生成 EPUB，保留原格式。
- 章节目录、中英日像素字体、阅读进度、彩色/黑白 ASCII 封面与插图。
- 本地音乐、歌单、顺序/随机播放、LRC/内嵌歌词及 ASCII 音频封面。
- CAVA 黑底绿色像素频谱，暂停或隐藏时停止分析。
- 中文、English、日本語界面；窗口与图标由 Qt 绘制。

软件只管理你自行导入的文件。音乐导入是复制到 `Data/Music/Audio`；电子书复制到 `Data/Library`。
保存编辑修改 EPUB/AZW3，不会同步修改原 MOBI。点击书库空白处或按 Esc 可取消选中。

## 开源与来源

本项目自有代码以 **GNU GPL v3** 发布；组件保留各自许可。请阅读 **LICENSE**、**THIRD_PARTY_NOTICES.md**、**SOURCE_CODE.md** 和 `licenses/`。
calibre95 是独立衍生项目，不代表 calibre、Qt、Microsoft 或其他上游项目的官方产品。
Windows 95/98 是外观描述。未分发来源不明的 RetroWindowsGUI PNG 素材。

源码包为 **calibre95-1.0.1-source.zip**；同版本依赖源码归档及清单随 GitHub Release 一起提供。
修改版应用、CAVA/PCM 适配、启动器及 calibre 开发覆盖层均含源码与构建说明。自编译步骤见源码包的 BUILD.md。

## 运行范围与已知边界

测试覆盖 Windows x64 捆绑运行时、空库首次启动与重启、移动目录、三语字体、编辑、转换、阅读和音乐联动。
不宣称已经在所有电脑实测。扫描型 PDF、复杂排版、受 DRM 保护或损坏文件的支持取决于上游引擎；不提供 DRM 移除。
程序未签名；Windows 可能根据下载来源显示未知发布者提示。发布页附 SHA256SUMS.txt，可用 PowerShell `Get-FileHash 文件名 -Algorithm SHA256` 核对。


