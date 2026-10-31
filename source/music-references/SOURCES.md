# calibre95 音乐模块：开源参考来源

检索与获取日期：2026-10-30。

本目录保存从 GitHub 获取并审阅的有限源码快照，用于追溯音乐模块的设计参考。它不是完整项目，也不加入运行时导入路径。calibre95 的播放器采用现有 Qt Multimedia 解码和本地文件；Windows 95/98 界面、像素歌词滚动、歌单管理与 ASCII 封面视图由项目原生实现。

逐文件的上游提交、文件路径及 Git blob 标识见 [manifest.json](manifest.json)。每个项目的原始许可已与快照保存在一起；发行包 licenses 目录另存许可副本。

## Webamp：复古播放器交互参考

- 仓库：[captbaritone/webamp](https://github.com/captbaritone/webamp)
- 固定提交：[f5c578bfa5c61d898df190d47e9830d639577724](https://github.com/captbaritone/webamp/tree/f5c578bfa5c61d898df190d47e9830d639577724)
- 提交日期：2026-10-27T21:00:50Z。
- 许可：MIT；Copyright (c) [2015] [Jordan Eldredge]。
- 本地许可：[webamp/LICENSE.txt](webamp/LICENSE.txt)。

Webamp 是基于浏览器的 Winamp 2 重现。这里保存 README、许可、MainWindow/Marquee.tsx、ActionButtons.tsx、Shuffle.tsx、reducers/playlist.ts，参考点包括：

1. 独立的上一首、播放、暂停、停止、下一首控制，以及明确的随机模式状态。
2. 长标题在固定像素显示区域内循环；短标题保持静止。源码的步进为每 220 毫秒移动一个 5 像素字符，并在文本循环之间插入分隔空白。
3. 用稳定曲目 ID 表示当前曲目和选中曲目，将播放状态与显示顺序分开。

calibre95 使用自己的 Qt 控件和中英日像素字体；不依赖 Webamp 的 React、浏览器音频实现、位图字体或皮肤素材。标题跑马灯与同步歌词是不同视图，歌词跟随真实播放位置，避免仅靠动画计时推进歌词。

## lrc_kit：歌词结构参考

- 仓库：[reteps/lrc_kit](https://github.com/reteps/lrc_kit)
- 固定提交：[1e1c49d2a6a4288e78947affd2ee1ed8510e22e6](https://github.com/reteps/lrc_kit/tree/1e1c49d2a6a4288e78947affd2ee1ed8510e22e6)
- 提交日期：2024-09-06T04:24:49Z。
- 许可：MIT；Copyright (c) 2021 Peter Stenger。
- 本地许可：[lrc_kit/LICENSE](lrc_kit/LICENSE)。

保存 README、许可、parser.py 与 lyrics.py。参考其“时间戳/歌词文本/元信息”分离方式，而不引入网络歌词搜索器。原项目的正则解析对同一行多个时间戳有限制，calibre95 使用本项目的独立解析器，处理多时间戳、毫秒小数、时间偏移以及没有时间标签的文本。

这里没有复制商业音乐、歌词数据库或网上封面。实际歌词和封面来自用户导入的音频文件及其本地附属文件。

LRC 偏移方向另外核对了 [OSD Lyrics 的实际播放时间计算](https://github.com/osdlyrics/osdlyrics/blob/a006e3eee0c3a90060b586da51930c6362f2fab5/src/ol_lrc.c#L492)：其显示时间为时间戳减去 offset，因此正值提前、负值延后。本项目采用同一语义。核对提交为 a006e3eee0c3a90060b586da51930c6362f2fab5（2026-10-27T16:55:26Z），未复制该项目代码。

## Mutagen：实际使用的音频元数据依赖

- 仓库：[Mutagen](https://github.com/quodlibet/mutagen)
- 固定版本：[release-1.47.0](https://github.com/quodlibet/mutagen/tree/release-1.47.0)
- 用途：本地音乐标签、内嵌歌词和封面读取。
- 许可：GPL-2.0-or-later。
- 已放入发行包的 app/vendor/mutagen；完整下载来源和归档 SHA-256 见 [MUTAGEN-SOURCE.json](../../app/vendor/MUTAGEN-SOURCE.json)，许可见 [MUTAGEN-GPL-2.0-or-later.txt](../../licenses/MUTAGEN-GPL-2.0-or-later.txt)。

Mutagen 的运行时代码与上面仅供参考的两个项目分开保存。

## 已检查但未纳入的候选

- [jsmolka/egg-player](https://github.com/jsmolka/egg-player)：检查到的仓库根目录未发现 LICENSE 文件，因此未复制其代码或素材。
- [zhiyiYo/Groove](https://github.com/zhiyiYo/Groove)：README 对 GPLv3 之外另有非商业用途表述，因此未采用其代码或素材。

这些候选仅记录筛选过程，不是 calibre95 的运行时依赖。

