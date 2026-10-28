@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" migrar_config_0_8_3.py
) else (
  python migrar_config_0_8_3.py
)
pause
