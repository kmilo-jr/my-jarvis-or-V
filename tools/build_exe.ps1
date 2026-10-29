# Gera o executavel do V com PyInstaller (pasta dist\V).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\tools\build_exe.ps1
#   ... -SkipInstall   # reaproveita o pyinstaller ja instalado
#
# Requer o venv do projeto criado por setup.bat.
param(
    [switch]$SkipInstall,
    [switch]$NoClean
)

$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz
$venvPy = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv nao encontrado. Rode setup.bat primeiro." }

Write-Host "== versao" -ForegroundColor Cyan
& $venvPy -c "import versao; print(versao.versao_completa())"

if (-not $SkipInstall) {
    Write-Host "== instalando pyinstaller" -ForegroundColor Cyan
    & $venvPy -m pip install -r requirements-build.txt --quiet
    if ($LASTEXITCODE -ne 0) { throw "falha ao instalar requirements-build.txt" }
}

Write-Host "== limpando saidas antigas" -ForegroundColor Cyan
if (-not $NoClean) {
    foreach ($pasta in @("build", "dist")) {
        $alvo = Join-Path $raiz $pasta
        if (Test-Path $alvo) { Remove-Item -LiteralPath $alvo -Recurse -Force }
    }
}

Write-Host "== gerando executavel (pode levar alguns minutos)" -ForegroundColor Cyan
& $venvPy -m PyInstaller V.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

# Recursos que o app le da raiz (app_paths.ROOT = pasta do exe). No modo pasta
# do PyInstaller eles iriam para _internal, entao copiamos para o lado do exe.
Write-Host "== copiando dados para a pasta do executavel" -ForegroundColor Cyan
$destino = Join-Path $raiz "dist\V"
New-Item -ItemType Directory -Force -Path (Join-Path $destino "config") | Out-Null
Copy-Item -LiteralPath (Join-Path $raiz "assets") -Destination $destino -Recurse -Force
Copy-Item -LiteralPath (Join-Path $raiz "config\default.example.json") -Destination (Join-Path $destino "config") -Force
foreach ($arquivo in @("README.md", "VERSAO.txt")) {
    $origem = Join-Path $raiz $arquivo
    if (Test-Path $origem) { Copy-Item -LiteralPath $origem -Destination $destino -Force }
}

$exe = Join-Path $raiz "dist\V\V.exe"
if (-not (Test-Path $exe)) { throw "V.exe nao foi gerado" }

$tamanho = [math]::Round(((Get-ChildItem (Join-Path $raiz "dist\V") -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "== pronto" -ForegroundColor Green
Write-Host "   executavel: $exe"
Write-Host "   pasta     : $(Join-Path $raiz 'dist\V')"
Write-Host "   tamanho   : $tamanho MB"
Write-Host ""
Write-Host "   Teste rapido:  .\dist\V\V.exe"
Write-Host "   Limites do pacote minimo: sem torch/TTS/modelos locais (ver V.spec)."
