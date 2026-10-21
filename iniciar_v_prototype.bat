@echo off
setlocal
cd /d "%~dp0"
title V 1.6 NEURAL INTERFACE
cls
echo ==========================================================
echo   V PROTOTYPE 1.6 - NEURAL INTERFACE + PROCESS FX
 echo   BUILD: V160-NEURAL-FX-20260916
 echo   PASTA: %CD%
echo ==========================================================
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Ambiente .venv nao encontrado nesta pasta.
  echo Execute configurar_prototype.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
endlocal
