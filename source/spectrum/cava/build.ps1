param([string]$FfmpegHeaders, [switch]$BuildTestAdapter)
$ErrorActionPreference = 'Stop'
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
if (-not $FfmpegHeaders) { $FfmpegHeaders = Join-Path $releaseRoot 'source/spectrum/ffmpeg-6.1.2' }
if (-not (Test-Path -LiteralPath (Join-Path $FfmpegHeaders 'libavutil/tx.h'))) { throw 'FFmpeg 6.1.2 public headers are required.' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw 'Visual Studio x64 C tools are required to rebuild (not to run).' }
$vcvars = Join-Path $installation 'VC/Auxiliary/Build/vcvars64.bat'
& $env:ComSpec /d /c "`"$vcvars`" >nul && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$buildRoot = Join-Path (Split-Path $releaseRoot) 'build/spectrum-native/cava'
$nativeRoot = Join-Path $releaseRoot 'app/native'
New-Item -ItemType Directory -Force -Path $buildRoot,$nativeRoot | Out-Null
Push-Location -LiteralPath $buildRoot
try {
    $arguments = @('/nologo','/LD','/O2','/MT','/std:c11','/utf-8','/W3',
        ('/I' + $PSScriptRoot),('/I' + (Join-Path $releaseRoot 'source/cava-reference')),('/I' + $FfmpegHeaders),
        (Join-Path $PSScriptRoot 'fft_adapter.c'),(Join-Path $PSScriptRoot 'cava95.c'),
        (Join-Path $releaseRoot 'source/cava-reference/cavacore.c'),
        '/link',('/OUT:' + (Join-Path $nativeRoot 'cava95.dll')))
    & cl.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'CAVA native build failed.' }
    if ($BuildTestAdapter) {
        & cl.exe /nologo /LD /O2 /MT /std:c11 /utf-8 ('/I' + $PSScriptRoot) ('/I' + $FfmpegHeaders) (Join-Path $PSScriptRoot 'fft_adapter.c') (Join-Path $PSScriptRoot 'test_fft_adapter.c') /link /OUT:fft_adapter_check.dll
        if ($LASTEXITCODE -ne 0) { throw 'Test-only FFT adapter build failed.' }
    }
} finally { Pop-Location }
