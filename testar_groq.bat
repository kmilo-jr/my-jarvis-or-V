@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" testar_groq.py
pause
endlocal
