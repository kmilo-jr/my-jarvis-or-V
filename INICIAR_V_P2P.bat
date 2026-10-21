@echo off
cd /d "%~dp0"
title V Remote P2P
cls
echo ==============================================
echo   V REMOTE P2P - INICIO FACIL
echo ==============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
  echo Python nao encontrado no PATH.
  pause
  exit /b 1
)
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
  echo Primeira execucao: instalando dependencias principais do V...
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :erro
)
python -c "import websockets" >nul 2>&1
if errorlevel 1 (
  echo Instalando suporte de conexao remota...
  python -m pip install "websockets>=15,<17"
  if errorlevel 1 goto :erro
)
python -c "import aiortc" >nul 2>&1
if errorlevel 1 (
  echo Instalando WebRTC P2P...
  python -m pip install "aiortc>=1.15,<2"
  if errorlevel 1 (
    echo AVISO: aiortc nao instalou. O V ainda pode funcionar pelo RELAY.
  )
)
echo.
echo Iniciando V...
python main_dual_ui.py
exit /b %errorlevel%
:erro
echo.
echo Houve um erro instalando as dependencias.
echo Copie a mensagem acima e envie para o ChatGPT.
pause
exit /b 1
