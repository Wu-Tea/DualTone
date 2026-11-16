param([string]$Version = '0.2.0')
$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid version' }
$root = $PSScriptRoot
$artifacts = Join-Path (Split-Path $root -Parent) 'artifacts'
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
$name = "DualTone-$Version-windows-x64-native"
$zip = Join-Path $artifacts "$name.zip"
if (Test-Path -LiteralPath $zip) { throw "Artifact already exists: $zip" }
$packageRoot = Join-Path $root ('qa\package-' + [guid]::NewGuid().ToString('N'))
$bundle = Join-Path $packageRoot 'DualTone'
New-Item -ItemType Directory -Force -Path $bundle | Out-Null
$binaryNames = @('DualTone.exe','DualToneCLI.exe','slint_cpp.dll','msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll','msvcp140_1.dll','msvcp140_2.dll')
foreach ($file in $binaryNames) { Copy-Item -LiteralPath (Join-Path $root "dist\$file") -Destination $bundle }
Copy-Item -LiteralPath (Join-Path $root 'README.md') -Destination (Join-Path $bundle '使用说明.md')
Copy-Item -LiteralPath (Join-Path $root 'RELEASE_NOTES.md') -Destination $bundle
Set-Content -LiteralPath (Join-Path $bundle 'VERSION') -Value $Version -Encoding UTF8
$licenses = Join-Path $bundle 'licenses'
New-Item -ItemType Directory -Force -Path $licenses | Out-Null
Copy-Item -Path (Join-Path $root 'vendor\slint\licenses\*') -Destination $licenses
Copy-Item -LiteralPath (Join-Path $root 'vendor\Slint-Royalty-free.md'),(Join-Path $root 'vendor\json-LICENSE.MIT') -Destination $licenses
Copy-Item -LiteralPath (Join-Path $root 'THIRD-PARTY.md') -Destination $licenses
$source = Join-Path $bundle 'source'
New-Item -ItemType Directory -Force -Path $source | Out-Null
foreach ($pattern in @('*.cpp','*.hpp','*.cmd','*.ps1','*.rc','*.manifest','*.md','verify_*.py','generate_tables.py','.clang-format')) {
    Get-ChildItem -LiteralPath $root -Filter $pattern -File | Copy-Item -Destination $source
}
Copy-Item -LiteralPath (Join-Path $root 'ui') -Destination $source -Recurse
Compress-Archive -LiteralPath $bundle -DestinationPath $zip -CompressionLevel Optimal
$bytes = (Get-Item -LiteralPath $zip).Length
if ($bytes -gt 20MB) { throw "Native ZIP exceeds 20 MiB: $bytes bytes" }
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $artifacts "$name.sha256") -Value "$hash  $name.zip" -Encoding ASCII
Write-Output "ZIP: $zip"
Write-Output "ZIP MiB: $([math]::Round($bytes / 1MB, 2))"
$unpacked = (Get-ChildItem -LiteralPath $bundle -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Output "Unpacked MiB: $([math]::Round($unpacked / 1MB, 2))"
Write-Output "SHA256: $hash"
