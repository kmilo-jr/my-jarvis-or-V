@echo off
chcp 65001 >nul
title V Spotify Bridge // Instalar Spicetify
where spicetify >nul 2>&1
if %errorlevel%==0 (
  echo Spicetify ja esta instalado.
  spicetify --version
  pause
  exit /b 0
)
echo Instalando Spicetify pelo Winget (fonte oficial listada na documentacao)...
where winget >nul 2>&1
if not %errorlevel%==0 (
  echo Winget nao encontrado.
  echo Instale manualmente seguindo https://spicetify.app/docs/getting-started
  pause
  exit /b 1
)
winget install --id Spicetify.Spicetify -e --accept-package-agreements --accept-source-agreements
if not %errorlevel%==0 (
  echo Falha ao instalar Spicetify.
  pause
  exit /b 1
)
echo.
echo Feche este CMD e abra outro se o comando spicetify ainda nao for reconhecido.
pause
