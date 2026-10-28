@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" migrar_config_0_8_4.py
) else (
  python migrar_config_0_8_4.py
)
pause
