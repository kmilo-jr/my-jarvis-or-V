@echo off
chcp 65001 >nul
cd /d "%~dp0"
title V 1.9.8 // Preparar ambiente
echo ==========================================================
echo   V PROTOTYPE 1.9.8 - PREPARAR AMBIENTE
echo ==========================================================
echo.
if not exist "setup.ps1" (
  echo setup.ps1 nao encontrado nesta pasta.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set CODIGO=%errorlevel%
echo.
if not "%CODIGO%"=="0" (
  echo Falhou com codigo %CODIGO%. Leia as mensagens acima.
) else (
  echo Ambiente pronto.
)
pause
exit /b %CODIGO%
