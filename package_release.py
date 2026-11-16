"""Package a clean staged Windows build, never the user's live portable folder."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', args.version):
        parser.error('Use a semantic version, for example 0.1.0')
    stage = ROOT / 'staging' / 'DualTone'
    for name in ('DualTone.exe', 'DualToneCLI.exe', '_internal'):
        if not (stage / name).exists():
            parser.error('Run build.ps1 -StageOnly first')
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    filename = f'DualTone-{args.version}-windows-x64-portable'
    archive = artifacts / (filename + '.zip')
    if archive.exists():
        parser.error(f'Artifact already exists: {archive.name}; use a new version or move it first')
    with tempfile.TemporaryDirectory(prefix='dualtone-package-') as temporary:
        bundle = Path(temporary) / 'DualTone'
        bundle.mkdir()
        # Only PyInstaller products are copied. Never carry data/settings or logs.
        for name in ('DualTone.exe', 'DualToneCLI.exe'):
            shutil.copy2(stage / name, bundle / name)
        shutil.copytree(stage / '_internal', bundle / '_internal')
        subprocess.run([sys.executable, str(ROOT / 'collect_licenses.py'), '--output', str(bundle)], check=True)
        for source, destination in (('README.md', '使用说明.md'),
                                    ('hardware-and-research.md', '硬件与研究.md'),
                                    ('acoustics-and-game-audio.md', '脚步与听感研究.md'),
                                    ('RELEASE_NOTES.md', 'RELEASE_NOTES.md')):
            shutil.copy2(ROOT / source, bundle / destination)
        (bundle / 'VERSION').write_text(args.version + '\n', encoding='utf-8')
        shutil.make_archive(str(artifacts / filename), 'zip', temporary, 'DualTone')
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None, 'Archive integrity failure'
        assert not any(name.startswith('DualTone/data/') for name in package.namelist()), 'User data in archive'
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (artifacts / (filename + '.sha256')).write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(archive)
    print('SHA256:', digest)

if __name__ == '__main__':
    main()
