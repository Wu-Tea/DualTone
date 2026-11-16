param([string]$SlintSdkDirectory)
$ErrorActionPreference = 'Stop'
$vendor = Join-Path $PSScriptRoot 'vendor'
New-Item -ItemType Directory -Force -Path $vendor | Out-Null
function Download-Checked([string]$Url, [string]$Path, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path)) { Invoke-WebRequest -Uri $Url -OutFile $Path }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256) { throw "Checksum mismatch: $Path" }
}
$slintVersion = '1.18.1'
$slintTarget = Join-Path $vendor 'slint'
if (-not (Test-Path -LiteralPath (Join-Path $slintTarget 'lib\slint_cpp.dll'))) {
    if ($SlintSdkDirectory) {
        $sdk = (Resolve-Path -LiteralPath $SlintSdkDirectory).Path
        New-Item -ItemType Directory -Force -Path $slintTarget | Out-Null
        foreach ($name in @('bin', 'include', 'lib', 'licenses')) {
            Copy-Item -LiteralPath (Join-Path $sdk $name) -Destination (Join-Path $slintTarget $name) -Recurse
        }
    } else {
        $installer = Join-Path $vendor 'slint-sdk.exe'
        Download-Checked "https://github.com/slint-ui/slint/releases/download/v$slintVersion/Slint-cpp-$slintVersion-win64-MSVC-AMD64.exe" $installer 'eea71789a54982bc1c164d9e1d2c7f00fead1415e9ac396ccb48676f2f66a7a9'
        $sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
        $bandizip = Join-Path $env:ProgramFiles 'Bandizip\bz.exe'
        if ($sevenZip) { & $sevenZip.Source x -y "-o$slintTarget" $installer | Out-Null }
        elseif (Test-Path -LiteralPath $bandizip) { & $bandizip x -y "-o:$slintTarget" $installer | Out-Null }
        else { throw 'Extract the official Slint C++ SDK first, then pass -SlintSdkDirectory. No system installation is needed.' }
        if ($LASTEXITCODE -ne 0) { throw 'SDK extraction failed' }
    }
}
Download-Checked 'https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp' (Join-Path $vendor 'json.hpp') 'aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63'
foreach ($entry in @(
    @('https://raw.githubusercontent.com/nlohmann/json/v3.12.0/LICENSE.MIT','json-LICENSE.MIT'),
    @('https://raw.githubusercontent.com/slint-ui/slint/v1.18.1/LICENSES/LicenseRef-Slint-Royalty-free-2.0.md','Slint-Royalty-free.md')
)) {
    $destination = Join-Path $vendor $entry[1]
    if (-not (Test-Path -LiteralPath $destination)) { Invoke-WebRequest -Uri $entry[0] -OutFile $destination }
}
Write-Output 'Native dependencies ready. No PATH or device settings changed.'
