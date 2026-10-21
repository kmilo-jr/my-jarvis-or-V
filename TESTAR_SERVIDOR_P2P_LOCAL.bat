@echo off
cd /d "%~dp0\p2p_server"
title V P2P - Servidor Local de Teste
python -m pip install -r requirements.txt
python server.py
pause
