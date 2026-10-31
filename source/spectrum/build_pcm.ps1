$ErrorActionPreference = 'Stop'
$sourceRoot = $PSScriptRoot
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $sourceRoot '../..'))
$buildRoot = Join-Path $releaseRoot '../build/spectrum-probe'
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (!(Test-Path -LiteralPath $vswhere)) { throw 'Visual Studio C++ build tools are required.' }
$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
& $env:ComSpec /d /c "`"$vcvars`" >nul && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
& cl.exe /nologo /O2 /MT /LD /EHsc /std:c++17 /utf-8 /I (Join-Path $sourceRoot 'ffmpeg-6.1.2') `
    (Join-Path $sourceRoot 'pcm_reader.cpp') "/Fo$buildRoot/pcm_reader.obj" /link `
    "/OUT:$releaseRoot/app/native/pcm95.dll" "/IMPLIB:$buildRoot/pcm95.lib"
if ($LASTEXITCODE) { throw 'PCM adapter compilation failed.' }
