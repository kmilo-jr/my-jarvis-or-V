@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" migrar_spotify_0_7_2.py
) else (
  py -3.12 migrar_spotify_0_7_2.py 2>nul || python migrar_spotify_0_7_2.py
)
