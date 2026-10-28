@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" migrar_config_1_0_4.py
) else (
  python migrar_config_1_0_4.py
)
pause
