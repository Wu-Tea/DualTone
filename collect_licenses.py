"""Collect upstream distribution notices alongside the portable binary."""
import sys,shutil,argparse,importlib.metadata as meta
from pathlib import Path
root=Path(__file__).parent
sys.path.insert(0,str(root/'lib'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=root/'release'/'DualTone')
output=parser.parse_args().output.resolve()
out=output/'licenses';out.mkdir(parents=True,exist_ok=True)
packages=['numpy','scipy','cffi','pycparser','SoundCard','PySide6-Essentials','shiboken6','PyInstaller']
lines=['DualTone third-party notices','',
       'Qt/PySide6 are dynamically linked and distributed under LGPLv3 / applicable Qt licenses.',
       'The _internal directory contains replaceable shared libraries. No restrictions on debugging modifications are imposed.',
       'Upstream Qt sources: https://download.qt.io/official_releases/qt/',
       'Upstream PySide sources: https://download.qt.io/official_releases/QtForPython/',
       'Python source and license: https://www.python.org/downloads/source/',
       'Application source is included in the source directory.','']
for name in packages:
    d=meta.distribution(name);lines.append(f'{d.metadata["Name"]} {d.version}')
    for f in d.files or []:
        if any(s in str(f).lower() for s in ('license','copying','notice')) and str(f).lower().endswith(('.txt','.md','.rst','license','copying')):
            src=Path(d.locate_file(f))
            if src.is_file():
                dest=out/name/str(f).replace('..','_');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,out/'Python-LICENSE.txt')
for f in (root/'upstream-licenses').iterdir():shutil.copy2(f,out/f.name)
(out/'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(lines),encoding='utf-8')
source=output/'source';source.mkdir(exist_ok=True)
for name in ('app.py','ui_model.py','cli.py','control.py','config.py','audio_engine.py','band_filter.py','test_multiband.py','audio_scheduling.py','resampling.py','equalizer.py','native_wasapi.py','settings.py','build.ps1','portable.spec','collect_licenses.py','test_application.py','test_native_output.py','test_cli_integration.py','test_audio_event.py','measure_latency.py','test_latency_pipeline.py','routing.py','system_effects.py','test_routing_presets.py'):
    shutil.copy2(root/name,source/name)
shutil.copytree(root/'ui',source/'ui',dirs_exist_ok=True)
for name in ('spatial.py','test_spatial.py'):shutil.copy2(root/name,source/name)
for name in ('README.md','package_release.py','RELEASE_NOTES.md'):shutil.copy2(root/name,source/name)
shutil.copytree(root/'upstream-licenses',source/'upstream-licenses',dirs_exist_ok=True)
(source/'requirements.txt').write_text('\n'.join(f'{meta.distribution(n).metadata["Name"]}=={meta.version(n)}' for n in packages),encoding='utf-8')
print('Collected third-party notices and application source.')
