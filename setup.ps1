# Cria/repara o ambiente do V a partir de uma instalacao limpa.
#
# Uso (recomendado: duplo clique em setup.bat):
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Lock      # ambiente completo (torch/TTS)
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -DryRun    # so mostra o que faria
#
# O .venv e criado com o Python 3.12 e aponta para o Python base do sistema:
# se voce mover o projeto para outro PC, rode este script de novo.
param(
    [string]$Venv = ".venv",
    [switch]$Lock,
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$raiz = (Get-Location).Path
$venvPy = Join-Path $raiz (Join-Path $Venv "Scripts\python.exe")

function Passo($texto) { Write-Host ""; Write-Host "== $texto" -ForegroundColor Cyan }
function Rodar([string]$exe, [string[]]$argumentos) {
    $linha = "$exe $($argumentos -join ' ')"
    if ($DryRun) { Write-Host "   [dry-run] $linha"; return }
    Write-Host "   > $linha"
    & $exe @argumentos
    if ($LASTEXITCODE -ne 0) { throw "falhou (exit $LASTEXITCODE): $linha" }
}

Passo "localizando Python 3.12"
$python = $null
foreach ($candidato in @(@("py", "-3.12"), @("python", ""), @("py", "-3"))) {
    $exe, $arg = $candidato
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $argsVersao = @()
    if ($arg) { $argsVersao += $arg }
    $argsVersao += @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    try {
        $versao = (& $exe @argsVersao 2>$null | Select-Object -First 1)
    } catch { continue }
    if ($versao) {
        $python = $exe
        $prefixo = if ($arg) { "$exe $arg" } else { $exe }
        Write-Host "   encontrado: $prefixo -> Python $versao"
        if ($versao -ne "3.12") { Write-Host "   AVISO: o projeto foi validado em 3.12; voce tem $versao." -ForegroundColor Yellow }
        break
    }
}
if (-not $python) { throw "Python nao encontrado no PATH. Instale o Python 3.12 (python.org) e rode de novo." }

Passo "criando/reaproveitando o venv '$Venv'"
if (Test-Path $venvPy) {
    Write-Host "   venv ja existe: $venvPy"
} else {
    if ($python -eq "py") { Rodar "py" @("-3.12", "-m", "venv", $Venv) }
    else { Rodar $python @("-m", "venv", $Venv) }
}
if (-not $DryRun -and -not (Test-Path $venvPy)) { throw "o venv nao foi criado em $venvPy" }

Passo "instalando dependencias"
Rodar $venvPy @("-m", "pip", "install", "--upgrade", "pip", "--quiet")
if ($Lock) {
    $lock = Join-Path $raiz "requirements.lock.txt"
    if (-not (Test-Path $lock)) { throw "requirements.lock.txt nao encontrado" }
    Write-Host "   modo -Lock: instalando o ambiente completo (inclui torch/TTS). Pode demorar."
    $pinned = Join-Path $env:TEMP "v_requirements_lock_pinned.txt"
    Get-Content $lock | Where-Object { $_ -match '==' } | Set-Content -LiteralPath $pinned -Encoding UTF8
    try {
        Rodar $venvPy @("-m", "pip", "install", "-r", $pinned, "--quiet")
    } finally {
        Remove-Item -LiteralPath $pinned -Force -ErrorAction SilentlyContinue
    }
} else {
    Rodar $venvPy @("-m", "pip", "install", "-r", "requirements.txt", "--quiet")
}

Passo "preparando a configuracao local"
$cfg = Join-Path $raiz "config\default.json"
$exemplo = Join-Path $raiz "config\default.example.json"
if (Test-Path $cfg) {
    Write-Host "   config/default.json ja existe (preservado)"
} elseif (Test-Path $exemplo) {
    if (-not $DryRun) { Copy-Item -LiteralPath $exemplo -Destination $cfg }
    Write-Host "   criado config/default.json a partir do exemplo"
} else {
    Write-Host "   AVISO: config/default.example.json nao encontrado; o V criara o config na primeira execucao." -ForegroundColor Yellow
}

Passo "verificando o codigo (compileall)"
Rodar $venvPy @("-m", "compileall", "-q", "core", "brain", "voice", "ui", "personality", "integrations", "tests", "tools", "main.py", "main_dual_ui.py", "versao.py", "vlog.py", "secure_store.py")

if (-not $SkipTests) {
    Passo "rodando a suite de testes"
    $env:QT_QPA_PLATFORM = 'offscreen'
    Rodar $venvPy @("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")
}

Passo "pronto"
$versao = (& $venvPy -c "import versao; print(versao.TITULO)" 2>$null)
Write-Host "   projeto: $raiz"
Write-Host "   versao : $versao"
Write-Host "   venv   : $Venv"
Write-Host ""
Write-Host "   Iniciar: iniciar_v_prototype.bat  ou  iniciar_v_dual_interface.bat"
Write-Host "   Spotify: configurar_spotify_api.bat + configurar_spotify_bridge.bat"
Write-Host "   Diagnostico: .\$Venv\Scripts\python.exe tools\diagnostico_startup.py"
