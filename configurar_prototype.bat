@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo       V PROTOTYPE - CONFIGURACAO WINDOWS
echo =============================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher nao encontrado.
  echo Instale Python 3.12 64-bit e marque "Add Python to PATH".
  pause
  exit /b 1
)
py -3.12 -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 nao encontrado.
  echo O Prototype foi desenhado para Python 3.12 64-bit.
  pause
  exit /b 1
)
if not exist .venv (
  echo Criando ambiente virtual...
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Houve um erro ao instalar dependencias.
  pause
  exit /b 1
)
python self_test.py
echo.
echo Configuracao concluida.
pause
