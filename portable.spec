# Shared dependency bundle for the GUI and the console entry point.
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['app.py', 'cli.py'], pathex=['lib'],
    binaries=[], datas=collect_data_files('soundcard')+[('ui','ui')], hiddenimports=['_cffi_backend'],
    # SciPy's optional array backends are unrelated to the NumPy audio path.
    excludes=['matplotlib','tkinter','PyQt5','PyQt6','torch','torchvision','torchaudio',
              'tensorflow','jax','jaxlib','cupy','pandas','sklearn','IPython','numba',
              'sympy','transformers','cv2','PIL'],
    hookspath=[], runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
runtime_hooks = [item for item in a.scripts if item[0] not in ('app','cli')]
gui_script = next(item for item in a.scripts if item[0]=='app')
cli_script = next(item for item in a.scripts if item[0]=='cli')
gui = EXE(pyz, runtime_hooks+[gui_script], [], exclude_binaries=True,
          name='DualTone', debug=False, strip=False, upx=False, console=False)
cli = EXE(pyz, runtime_hooks+[cli_script], [], exclude_binaries=True,
          name='DualToneCLI', debug=False, strip=False, upx=False, console=True)
bundle = COLLECT(gui,cli,a.binaries,a.datas,strip=False,upx=False,name='DualTone')
