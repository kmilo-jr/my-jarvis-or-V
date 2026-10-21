@echo off
cd /d "%~dp0"
title V - Preparar P2P
cls
echo ==============================================
echo   V REMOTE P2P - PREPARACAO AUTOMATICA
echo ==============================================
echo.
python --version
if errorlevel 1 (
  echo Python nao encontrado no PATH.
  pause
  exit /b 1
)
echo.
echo Instalando dependencias P2P...
python -m pip install --upgrade pip
python -m pip install -r requirements_p2p.txt
if errorlevel 1 (
  echo.
  echo Nao consegui instalar as dependencias P2P.
  pause
  exit /b 1
)
echo.
echo P2P preparado com sucesso.
echo Agora configure remote.p2p.signaling_url em config\default.json.
pause
