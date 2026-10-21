@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title V 1.7 - Dual Interface
cls
echo ==========================================================
echo   V 1.7 - DUAL INTERFACE + MIC RECOVERY
echo   F6 alterna: ORBITAL ^<^> NEURAL AMBER
echo ==========================================================
echo.
set "VPY="
if exist ".venv\Scripts\python.exe" set "VPY=%CD%\.venv\Scripts\python.exe"
if not defined VPY (
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=Join-Path $env:USERPROFILE 'Downloads'; if(Test-Path $root){ Get-ChildItem -LiteralPath $root -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue ^| Where-Object { $_.FullName -like '*V_PROTOTYPE*\.venv\Scripts\python.exe' } ^| Select-Object -First 1 -ExpandProperty FullName }"`) do set "VPY=%%P"
)
if not defined VPY (
  py -3.12 -c "import PySide6" >nul 2>nul
  if not errorlevel 1 set "VPY=py -3.12"
)
if not defined VPY (
  echo Nao encontrei o ambiente Python do V com PySide6.
  echo Execute configurar_prototype.bat uma vez e tente novamente.
  pause
  exit /b 1
)
if /I "%VPY%"=="py -3.12" (
  py -3.12 main_dual_ui.py
) else (
  "%VPY%" main_dual_ui.py
)
if errorlevel 1 pause
endlocal
