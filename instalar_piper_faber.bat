@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo       V - INSTALAR PIPER FABER OFFLINE
echo =============================================
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" instalar_piper_faber.py
) else (
  echo Ambiente .venv nao encontrado.
  echo Rode configurar_prototype.bat primeiro.
)
echo.
pause
