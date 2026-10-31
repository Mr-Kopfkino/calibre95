# calibre95 v1.0.1

Windows 10 / 11 x64 便携发布版，采用 Windows 95/98 风格界面和中英日像素字体。

- 空书库、空音乐库，无示例自动导入，无个人数据或设置。
- 电子书导入、管理、元数据编辑、内容编辑、格式转换与阅读。
- ASCII 封面和插图；真实章节目录；兼容旧阅读进度。
- 本地音乐、歌单、歌词、ASCII 封面与 CAVA 像素频谱。
- 修复提示框裁切、MOBI 编辑入口和书库取消选择。
- 整个目录可移动，首次启动自动创建本地 Data。

使用者下载 windows-x64.zip，完整解压后运行 calibre95.exe；建议短路径，如 D:\calibre95。
开发者可下载源码包与依赖源码。许可见 LICENSE、THIRD_PARTY_NOTICES.md 和 SOURCE_CODE.md。
各下载文件可通过 SHA256SUMS.txt 核对。当前验证覆盖同一 Windows 主机上的隔离启动、重启、移动目录及真实格式转换。

## 对应源码与许可

同页的 `calibre95-1.0.1-source.zip` 包含应用和 calibre 修改源码；`calibre95-1.0.1-dependency-sources-*.zip` 包含 102 项已校验的依赖源码归档。保留所有附件与许可。

以下 Qt 组件的完整源码使用官方历史档案地址提供，未放入本地依赖源码 ZIP；对应版本和哈希如下。源码包根目录附有 fetch_dependency_sources.py 下载校验脚本，源码访问免费、不需要账号。

- [qt-webengine](https://download.qt.io/archive/qt/6.7/6.7.2/submodules/qtwebengine-everywhere-src-6.7.2.tar.xz) — `sha256:c7755875594d8be382b07bf3634d44fd77012805794d8b588891709a6405ffd1`

完整组件清单和原始许可见源码包的 DEPENDENCY_SOURCES.json、THIRD_PARTY_NOTICES.md、SOURCE_CODE.md 与 licenses/。
