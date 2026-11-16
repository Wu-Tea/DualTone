param([string]$PythonExecutable = 'python', [switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = (Get-Command $PythonExecutable -ErrorAction Stop).Source
$originalBuildPath = $env:Path
Push-Location $projectRoot
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot 'build-cache'
    # Process-local isolation: never collect unrelated DLLs from developer tools.
    # System ICU must resolve from Windows, not a Poppler/libheif PATH entry.
    $pythonRoot = Split-Path -Parent $pythonExe
    $env:Path = "$pythonRoot;$pythonRoot\DLLs;$env:SystemRoot\System32;$env:SystemRoot"
    # Build in staging: PyInstaller replaces its output directory. Never point
    # it at the user's live portable folder, which also contains data/settings.
    & $pythonExe -m PyInstaller --noconfirm --distpath staging --workpath build-isolated portable.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    if ($StageOnly) { return }
    New-Item -ItemType Directory -Path 'release\DualTone' -Force | Out-Null
    Copy-Item -Path 'staging\DualTone\*' -Destination 'release\DualTone' -Recurse -Force
    Copy-Item -LiteralPath 'README.md' -Destination 'release\DualTone\使用说明.md'
    Copy-Item -LiteralPath 'hardware-and-research.md' -Destination 'release\DualTone\硬件与研究.md'
    Copy-Item -LiteralPath 'acoustics-and-game-audio.md' -Destination 'release\DualTone\脚步与听感研究.md'
    & $pythonExe collect_licenses.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
} finally { $env:Path = $originalBuildPath; Pop-Location }
