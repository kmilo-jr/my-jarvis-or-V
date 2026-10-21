@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (.venv\Scripts\python.exe migrar_config_1_1.py) else (python migrar_config_1_1.py)
pause
