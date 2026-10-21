@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title V - Instagram UI Experiment
cls
echo ==========================================================
echo   V 1.6 - INSTAGRAM UI EXPERIMENT - ENV HOTFIX
echo ==========================================================
echo.

set "VPY="

rem 1) Prefer the virtual environment in this folder.
if exist ".venv\Scripts\python.exe" (
    set "VPY=%CD%\.venv\Scripts\python.exe"
)

rem 2) If this experimental copy has no .venv, reuse the environment
rem    from another V 1.6 folder already configured in Downloads.
if not defined VPY (
    for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=Join-Path $env:USERPROFILE 'Downloads'; if(Test-Path $root){ Get-ChildItem -LiteralPath $root -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue ^| Where-Object { $_.FullName -like '*V_PROTOTYPE_1_6*\.venv\Scripts\python.exe' } ^| Select-Object -First 1 -ExpandProperty FullName }"`) do set "VPY=%%P"
)

rem 3) Last fallback: system Python 3.12, but only if PySide6 is installed there.
if not defined VPY (
    py -3.12 -c "import PySide6" >nul 2>nul
    if not errorlevel 1 set "VPY=py -3.12"
)

if not defined VPY (
    echo Nao encontrei um ambiente Python do V com PySide6.
    echo.
    echo Isso nao e um erro da interface. A copia experimental nao inclui a pasta .venv.
    echo Execute uma vez:
    echo.
    echo     configurar_prototype.bat
    echo.
    echo Depois rode este arquivo novamente.
    echo.
    pause
    exit /b 1
)

echo Ambiente do V encontrado:
echo %VPY%
echo.

if /I "%VPY%"=="py -3.12" (
    py -3.12 main_instagram_ui.py
) else (
    "%VPY%" main_instagram_ui.py
)

if errorlevel 1 (
    echo.
    echo O experimento visual encerrou com erro.
    pause
)
endlocal
