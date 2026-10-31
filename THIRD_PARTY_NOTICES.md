# calibre95 — third-party notices

calibre95 is an independently modified application built on calibre 7.26.0. It is not an official calibre, Microsoft, or Qt product. The Windows 95/98-like interface is drawn by the application's Qt code. No Windows system artwork is included, and the unlicensed RetroWindowsGUI reference PNGs are omitted from this public package.

The application is distributed under GNU GPL version 3; see `LICENSE`. This does not replace the original licenses or copyright notices of the components below. The full original notices extracted from the exact upstream dependency archives are in `licenses/dependencies/`; each component's `INDEX.json` maps every saved notice back to its path in the source archive. SPDX license texts supplied by Qt 6.7.2 are also retained in `licenses/QT-*.txt`; inclusion of a commercial-license reference in that upstream collection does **not** grant or assert a Qt commercial license.

| Component | Version / identity | License and source location |
| --- | --- | --- |
| calibre | 7.26.0, Copyright Kovid Goyal and contributors | GPL v3; `licenses/LICENSE`, `licenses/COPYRIGHT`; full upstream tree plus local changes in the source companion |
| CPython | 3.11.5 (DLL version checked) | PSF license and incorporated third-party notices; `licenses/dependencies/python/` |
| Qt | 6.7.2 (Qt6Core DLL version checked) | Qt's applicable LGPL v3 / GPL licenses and third-party licenses; `licenses/QT-*.txt`, component notices, and exact module source URLs in `DEPENDENCY_SOURCES.json` |
| PyQt6 / PyQt6-WebEngine | 6.7.1 / 6.7.0 | GPL v3 and Riverbank notices; `licenses/dependencies/pyqt/` and `pyqt-webengine/` |
| PyQt6-sip | 13.8.0 | Upstream SIP runtime license; `licenses/dependencies/pyqt-sip/` |
| FFmpeg | 6.1.2, DLL ABI avcodec 60 / avutil 58 | **GPL v2 or later for this actual build**; `licenses/dependencies/ffmpeg/` and `FFMPEG-BUILD.txt` |
| Mutagen | 1.47.0 | GPL v2 or later; `licenses/MUTAGEN-GPL-2.0-or-later.txt`; unchanged source in `app/vendor/mutagen` |
| CAVA core | commit d272bb61d28a2e91217e927a1f099670290f59e0 | MIT; `licenses/CAVA-MIT.txt`; original core and provenance in `source/cava-reference/` |
| GNU Unifont / Unifont JP | 16.0.04 (embedded font name tables checked) | Distributed under SIL OFL 1.1; `licenses/UNIFONT.txt`, `licenses/OFL-1.1.txt`; upstream also offers GPL v2+ with font embedding exception |
| ASCII converter reference | User-provided Rainbow-Dreamer/ascii-converter snapshot | LGPL 2.1; `licenses/ASCII-CONVERTER-LGPL-2.1.txt`; reference source/provenance in source companion |
| Webamp / lrc_kit references | Pinned commits in `source/music-references/manifest.json` | MIT; matching licenses retained. Design references, not browser/player runtime dependencies |
| Image, text, compression, cryptography and Python support libraries | Versions pinned by calibre 7.26.0 `bypy/sources.json` | Original component licenses preserved individually; see dependency manifest and `licenses/dependencies/` |
| Microsoft Visual C++ / Universal CRT components | As included in the upstream Windows runtime | Microsoft redistributable components, not relicensed as GPL. Microsoft terms and redistribution information: <https://visualstudio.microsoft.com/license-terms/> and <https://aka.ms/vs/17/redist.txt> |

FFmpeg's actual `avcodec_license()` returns `GPL version 2 or later`; its configuration includes `--enable-gpl`. It must not be described as an LGPL-only binary. The small CAVA FFT adapter uses the existing FFmpeg transform API; no FFTW code or binary is shipped.

The dependency manifest includes GPL/LGPL libraries such as Poppler, PoDoFo, CHMLib and font/text-processing libraries, as well as permissively licensed libraries. UnRAR is governed by its original license and restrictions; it is not represented as an unrestricted GPL component. The runtime contains some calibre support components that are not exposed by calibre95's UI; their original notices remain applicable even when those features are hidden.

`licenses/QtWebEngine-6.7-official-notices/qtwebengine-licensing.html` is a local copy of Qt's official archived 6.7 licensing index, accompanied by all 79 linked third-party license pages. `PROVENANCE.json` records every original URL and file hash. These are supplementary official documentation for the matching Qt series, not a claim that an exact generated credits page was extracted from this particular binary. The exact complete Qt WebEngine 6.7.2 source archive and its digest remain identified in `DEPENDENCY_SOURCES.json`.

Source availability and publishing instructions are in `SOURCE_CODE.md`. Copyright remains with the respective authors. No warranty is provided except where required by applicable law.
