@echo off
setlocal
if not defined DUALTONE_VCVARS (
  for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find VC\Auxiliary\Build\vcvars64.bat`) do set "DUALTONE_VCVARS=%%i"
)
if not defined DUALTONE_VCVARS exit /b 2
call "%DUALTONE_VCVARS%" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0"
if not exist build mkdir build
if not exist dist mkdir dist
set "SLINT_HEADER=build\ui-%RANDOM%-%RANDOM%.h"
vendor\slint\bin\slint-compiler.exe --style fluent --embed-resources embed-files ui\main.slint -o "%SLINT_HEADER%"
if errorlevel 1 exit /b 1
if not exist "%SLINT_HEADER%" exit /b 1
move /y "%SLINT_HEADER%" build\ui.h >nul
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /MD /DNOMINMAX /DUNICODE /D_UNICODE /Ivendor\slint\include\slint /Ibuild /c settings.cpp dsp.cpp reverb.cpp sync.cpp audio.cpp host.cpp /Fobuild\
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /MD /DNOMINMAX /DUNICODE /D_UNICODE cli.cpp build\settings.obj build\dsp.obj build\reverb.obj build\sync.obj build\audio.obj build\host.obj /Fobuild\ /Fe:dist\DualToneCLI.exe /link ole32.lib uuid.lib avrt.lib advapi32.lib bcrypt.lib user32.lib
if errorlevel 1 exit /b 1
rc /nologo /fo build\app.res resources.rc
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /MD /bigobj /DNOMINMAX /DUNICODE /D_UNICODE /Ivendor\slint\include\slint /Ibuild gui.cpp build\app.res build\settings.obj build\dsp.obj build\reverb.obj build\sync.obj build\audio.obj build\host.obj vendor\slint\lib\slint_cpp.dll.lib /Fobuild\ /Fe:dist\DualTone.exe /link /MANIFEST:NO /SUBSYSTEM:WINDOWS ole32.lib uuid.lib avrt.lib advapi32.lib bcrypt.lib shell32.lib comdlg32.lib gdiplus.lib user32.lib gdi32.lib comctl32.lib dwmapi.lib
if errorlevel 1 exit /b 1
copy /y vendor\slint\lib\slint_cpp.dll dist\ >nul
for %%f in (msvcp140.dll vcruntime140.dll vcruntime140_1.dll msvcp140_1.dll msvcp140_2.dll) do if exist "%VCToolsRedistDir%x64\Microsoft.VC143.CRT\%%f" copy /y "%VCToolsRedistDir%x64\Microsoft.VC143.CRT\%%f" dist\ >nul
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /MD /DNOMINMAX /DUNICODE /D_UNICODE test_driver.cpp build\settings.obj build\dsp.obj build\reverb.obj build\sync.obj build\audio.obj build\host.obj /Fobuild\ /Fe:build\test_driver.exe /link ole32.lib uuid.lib avrt.lib advapi32.lib bcrypt.lib user32.lib
if errorlevel 1 exit /b 1
echo Native build complete.
