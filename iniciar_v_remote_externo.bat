@echo off
cd /d "%~dp0"
echo V Remote externo
echo.
echo Se voce ativou auto_tunnel no config/default.json e instalou o cloudflared,
echo o link remoto aparecera no console do V quando o sistema iniciar.
echo.
python main_dual_ui.py
pause
