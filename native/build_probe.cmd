@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cl /nologo /O2 /EHsc /std:c++17 /MT audio_probe.cpp /Fe:audio_probe.exe /link ole32.lib
