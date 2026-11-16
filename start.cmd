@echo off
@echo off
if exist "%~dp0release\DualTone\DualTone.exe" (
  start "" "%~dp0release\DualTone\DualTone.exe"
) else (
  echo 请先构建 release\DualTone\DualTone.exe，或直接运行源码 app.py。
  pause
)
