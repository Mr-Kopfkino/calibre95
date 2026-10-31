# 构建 calibre95 1.0.1

本文描述独立源码包的目录结构。运行包不包含完整开发文件；重建前请下载同版本 calibre95-1.0.1-source.zip。

## 目录与工具

`app/` 为应用 Python 源码；`source/Launcher.cs` 为启动器；`source/calibre-src/` 为实际运行的 calibre 开发覆盖层。
`upstream/calibre-7.26.0/` 提供完整上游构建源码、bypy 依赖清单和构建配置（文档电子书及缓存已排除）。
`source/cava-reference/` 为固定版本 CAVA 核心；`source/spectrum/` 为 FFT 与 PCM 适配、FFmpeg 公共头文件及编译脚本。

Windows x64，需要 .NET Framework C# 编译器（系统自带）和 Visual Studio 2022 C++ 工具及 Windows SDK。
运行成品不需要这些开发工具。

## 重建应用

1. 将同版本运行版完整解压到一个新的可写短路径，例如 `D:\calibre95-build`。不要在个人书库所在目录构建。
2. 用本源码包 `app`、`assets`、`source` 的内容覆盖该目录的同名文件夹。保留成品中 `runtime` 和现有 `app/native`。
3. 在目标目录执行：

```powershell
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /win32icon:source\retro.ico /out:calibre95.exe source\Launcher.cs
& .\source\spectrum\cava\build.ps1
& .\source\spectrum\build_pcm.ps1
```

Python 文件直接加载，无需编译。启动器自动设置本地 Data、Qt 插件路径与 calibre 开发源码位置。
两个原生适配模块使用动态 FFmpeg API，编译时无需链接或分发另一个 FFmpeg/FFTW。

## 重建第三方运行库

`upstream/calibre-7.26.0/bypy/` 和 `setup/` 是上游构建入口，具体平台环境依上游 `INSTALL.rst` 与构建文档。
依赖的准确源码、版本、下载地址和 SHA-256 见 SOURCE_CODE.md 及其链接清单。
运行版保留 calibre 转换及辅助进程；原版 GUI/服务器等顶级启动入口未分发。不能随意删除 QtWebEngine，它用于部分转换路径。

calibre 的本地修改：`source/calibre-src/calibre/gui2/__init__.py` 中开发模式表单重建条件增加 `and not isfrozen`，冻结运行库使用随附预编译表单。
以 `source/calibre-src/` 的实际运行文件为准，其中预生成资源和表单对应本版 Qt 运行环境。

## 本发布版差异

移除示例书自动导入；不复制 Data、samples、tests、缓存和入门 EPUB；UI 素材只保留有明确许可的 Unifont 字体，控件/图标使用程序绘制。
启动器固定使用自身 Data，避免继承外部测试环境变量；版本为 1.0.1。
原始开发目录不受本发布打包影响。源码包内不包含运行 DLL，但有构建源码和使用成品运行库的步骤。
