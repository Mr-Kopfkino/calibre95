# Source code accompanying the Windows release

Publish the source companion and dependency-source assets beside the portable Windows ZIP in the **same GitHub Release**. A binary ZIP alone is not this project's complete source delivery.

The source companion contains the human-readable calibre95 Python application, C# launcher, native CAVA/PCM modules and build scripts, unmodified vendored Mutagen source, the original CAVA core, retained reference-source license notices, and the full calibre 7.26.0 source tree with the local changes identified in its build documentation. The font files carry their original OFL license and copyright notice.

`DEPENDENCY_SOURCES.json` records the Windows dependency source archives pinned by calibre 7.26.0's `bypy/sources.json`. For each entry it records the original declared digest, actual local SHA-256 where mirrored, source URLs, and local-mirror status. Dependency archives remain intact so that their hashes and upstream copyright notices can be checked. Their internal tests/examples are upstream source fixtures; they are not imported into the application and the portable application's book and music libraries are empty.

The companion dependency-source ZIPs contain the verified local archives from that manifest. Pure-Python `*-none-any.whl` files contain readable Python source and original notices. Native Python extension archives are their source distributions. Some build-helper source packages are retained because they are listed by the upstream build recipe. Windows NASM, gnuwin32 and ninja build-tool binary packages are not included.

Any manifest entry marked `upstream-only` is **not** contained in the local companion archives: use its exact upstream source URL and declared digest. Qt's historical archive provides the complete 6.7.2 modules, including Qt WebEngine's Chromium sources. These URLs are explicit source directions, not a claim that a missing archive has been mirrored. If an upstream source URL becomes unavailable, the distributor must provide equivalent corresponding-source access; preserve a local copy before deleting/replacing release source assets. GNU GPL v3 section 6(d) permits a third-party source server with equivalent copying facilities and clear directions next to the object-code download; it does not remove the distributor's source-availability responsibility.

Source collector scripts are included with this manifest. They do not execute downloaded source. Archived files are accepted only after matching the exact upstream digest, with an additional SHA-256 recorded for entries whose original manifest used SHA-1. Retired upstream locations may be replaced by an explicitly recorded mirror only when the declared digest still matches. `jaconv-0.40.tar.gz` is an upstream manifest naming typo: PyPI's actual `jaconv-0.4.0.tar.gz` has the identical pinned SHA-256.

Runtime source/build references:

- calibre 7.26.0: <https://download.calibre-ebook.com/7.26.0/> and <https://github.com/kovidgoyal/calibre/tree/v7.26.0>
- Windows build recipe and exact dependency versions: `upstream/calibre-7.26.0/bypy/` in the source companion; original repository path <https://github.com/kovidgoyal/calibre/blob/v7.26.0/bypy/sources.json>
- Qt 6.7.2 full module archives: <https://download.qt.io/archive/qt/6.7/6.7.2/submodules/>
- CAVA core: <https://github.com/karlstav/cava/tree/d272bb61d28a2e91217e927a1f099670290f59e0>
- Mutagen 1.47.0: <https://github.com/quodlibet/mutagen/tree/release-1.47.0>
- GNU Unifont 16.0.04: <https://unifoundry.com/pub/unifont/unifont-16.0.04/>

The application loads its DLLs dynamically and does not prevent replacing/rebuilding its GPL/LGPL components. Building the native Windows modules requires the Microsoft C/C++ toolchain and SDK; ordinary users do not need them. The existing calibre runtime is an upstream prebuilt distribution, so the source information does not claim a byte-for-byte reproducible build of that historical binary.

See `THIRD_PARTY_NOTICES.md` and the original license files for each component's terms. This file identifies source delivery; it does not change any component's license.
