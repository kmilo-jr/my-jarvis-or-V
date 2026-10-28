@echo off
setlocal
cd /d "%~dp0"
py -3.12 migrar_config_1_0.py
pause
