@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" testar_piper_faber.py
) else (
  echo Ambiente .venv nao encontrado. Rode configurar_prototype.bat primeiro.
)
echo.
pause
