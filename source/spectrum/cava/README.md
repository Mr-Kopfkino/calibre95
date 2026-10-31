# calibre95 CAVA core integration

This module uses the actual, unchanged CAVA `cavacore.c` and `cavacore.h`, pinned to
commit `d272bb61d28a2e91217e927a1f099670290f59e0`. See
[`../../cava-reference/SOURCE.json`](../../cava-reference/SOURCE.json) for upstream
Git blob identifiers and SHA-256 hashes, and the source directory for the MIT
notice. The additional wrapper and adapter are original GPL-3.0-or-later project
code, consistent with calibre95.

CAVA supplies logarithmic bands, equalization, sensitivity adaptation and
falloff/integral smoothing. The upstream core normally uses FFTW. This build
implements only the tiny FFTW API subset it calls, using the **already bundled
FFmpeg 6.1.2 `avutil-58.dll` real-to-complex transform**. The API declaration is
the upstream `libavutil/tx.h` in `../ffmpeg-6.1.2` (LGPL-2.1-or-later). No FFTW
code, FFTW DLL, terminal renderer, SDL, sound capture program, microphone input
or browser is added. The existing audio decoding/backend feeds normalized mono
PCM; all bar values come from this PCM, never random or time-only animation.

The adapter performs an unnormalized forward double-precision real DFT, matching
the FFTW sign/scale convention expected by CAVA. It permits unaligned arrays and
uses one native FFT context per CAVA transform. Only one analysis worker should
own and operate a given CAVA handle. Bindings must keep the avutil module loaded
for the lifetime of all handles. The wrapper does not load DLLs from an arbitrary
search path: its first call binds the already-loaded `avutil-58.dll` by name.
The Python backend loads that bundled dependency by absolute path first.

## Parameters and ABI

The UI uses 18 mono bands, 22,050 samples/sec, 50–10,000 Hz, 20 updates/sec,
automatic sensitivity, and smoothing 0.58. FFT sizes are 4,096 for bass and
2,048 for higher frequencies. A typical update feeds 1,102–1,103 new samples.

- `void* c95_cava_create(int bars, int rate)` — accepts 1–64 bands and 22050/24000 Hz; NULL on failure.
- `int c95_cava_process(void*, const float*, int count, float* output)` — normalized float PCM, output one value in [0,1] per band; 0 on success. More than the internal buffer uses the newest samples; maximum accepted caller count is 16,384.
- `int c95_cava_reset(void*)` — clears old FFT history and smoothing after seek/track changes; 0 on success.
- `int c95_cava_cutoffs(void*, float* output)` — writes `bars+1` cutoff frequencies, for diagnostics.
- `void c95_cava_destroy(void*)` — releases FFT contexts, all CAVA arrays, the upstream plan and wrapper.

## Rebuild and verify

From the release directory in PowerShell:

```powershell
./source/spectrum/cava/build.ps1 -BuildTestAdapter
```

Requires Visual Studio x64 C tools and the FFmpeg public headers included in the
source tree. The script discovers Visual Studio with vswhere, compiles `/O2 /MT`,
and produces `app/native/cava95.dll`. Static CRT linking avoids adding a new
Visual C++ runtime installation requirement. Intermediate objects and the
optional **test-only** `fft_adapter_check.dll` go under the workspace `build`.

The development-only integration test harness is not included in this clean source companion. The optional native FFT test adapter above can be rebuilt independently.

Tests compare FFT results against a direct DFT, check real tone-to-band mapping,
silence, reset, invalid inputs and repeated native object cleanup. Timing records
are for **analysis only**; they do not include decoding, painting or the rest of
the application. Full integration and visible/hidden worker behavior are tested
by the spectrum backend/UI checks separately.
