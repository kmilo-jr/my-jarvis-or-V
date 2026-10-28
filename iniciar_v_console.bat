@echo off
setlocal
cd /d "%~dp0"
title V 1.9.8 - Console
set "VPY="
if exist ".venv\Scripts\python.exe" set "VPY=%CD%\.venv\Scripts\python.exe"
if not defined VPY (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Ambiente .venv nao encontrado nesta pasta e python nao esta no PATH.
    echo Execute configurar_prototype.bat primeiro.
    pause
    exit /b 1
  )
  echo Aviso: .venv nao encontrado, usando o python do PATH.
  set "VPY=python"
)
echo Interpretador: %VPY%
"%VPY%" main.py
pause
endlocal
