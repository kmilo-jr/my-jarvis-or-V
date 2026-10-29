# V Prototype 1.9.8 — V Remote LAN

[![testes](https://github.com/kmilo-jr/my-jarvis-or-V/actions/workflows/tests.yml/badge.svg)](https://github.com/kmilo-jr/my-jarvis-or-V/actions/workflows/tests.yml)

Assistente de desktop para Windows: interface animada, comandos de sistema por voz ou
texto, memória persistente, briefing diário, notícias/mercado, Spotify, câmera e
controle remoto **pela mesma rede local**.

- **Versão:** 1.9.8 · build `V198-LAN-20261028` (fonte única em `versao.py`)
- **Python:** 3.12 · **UI:** PySide6 6.11
- **Controle remoto:** somente LAN/Wi-Fi — o acesso de fora de casa foi removido
  (ver [Controle remoto](#controle-remoto-somente-lan))

---

## Começar

1. **Duplo clique em `setup.bat`** (cria `.venv` com Python 3.12, instala dependências,
   cria `config/default.json` a partir do exemplo, compila e roda os testes).
   Opções: `setup.bat -Lock` (ambiente completo com torch/TTS), `-SkipTests`, `-DryRun`.
2. Inicie:
   - `iniciar_v_prototype.bat` — interface clássica (`main.py`)
   - `iniciar_v_dual_interface.bat` — interface dupla com **F6** alternando orbital/amber
     (`main_dual_ui.py`), inclui o controle remoto LAN
   - `iniciar_v_console.bat` / `iniciar_v_silencioso.bat` — variações de console

Ollama e o modelo configurado são necessários para conversa local. Recursos externos
(Gemini, Groq, ElevenLabs, Spotify) ficam desativados até você configurá-los.

Os `.bat` de `configurar_*` ajustam cada integração. Para voz local, veja `docs/guias/`.

### Gerar o executável (distribuição)

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_exe.ps1
```

Sai `dist\V\V.exe` (modo pasta, ~560 MB). O pacote mínimo **não** inclui torch/TTS,
modelos Whisper baixados, runtime do Qwen nem `vendor/` — esses recursos só existem
rodando do código-fonte com `requirements.lock.txt`. Edge-TTS, Piper, SAPI, ElevenLabs,
Spotify, cérebro, visão e briefing entram normalmente. `config/`, `data/`, `logs/` são
criados ao lado do `.exe` na primeira execução (`app_paths.ROOT`).

---

## Controle remoto (somente LAN)

O `main_dual_ui.py` sobe um servidor local (`remote_server.py`) que serve uma página de
controle para o celular **na mesma rede Wi-Fi/LAN**, protegida por PIN. O PC não abre
porta no roteador e não se conecta a nenhum servidor externo.

O acesso de fora de casa (P2P por servidor de sinalização e túnel Cloudflare) foi
**removido do projeto** nesta versão. Motivos: a lista de ações permitidas não era uma
fronteira de segurança real (o texto livre do celular entrava no pipeline completo do
assistente) e o PIN não tinha limite de tentativas. Se voltar a ser necessário, trate
como um recurso novo, com pareamento de dispositivo e autorização por ação.

---

## Voz

Perfis em `config/default.json → voice.tts_profile`:
`edge_tts_728` (padrão, online), `piper` (offline), `xtts_local` (clone local),
`elevenlabs_custom`, `qwen_local` e SAPI5 como último recurso. O reconhecimento usa
faster-whisper + VAD Silero. Falhas de motor agora aparecem em `logs/v_assistant.log`
em vez de sumirem.

---

## Estrutura

```
core/         motor funcional: intenção -> ToolRouter -> execução (tools, visão, briefing)
brain/        provedores de IA (Gemini, Groq, Ollama, web) e memória persistente
voice/        captura, reconhecimento e 6 motores de fala
ui/           janelas, face animada, painéis internos
personality/  persona do V
integrations/ Gmail (DPAPI + IMAP somente leitura), visão, spotify_bridge
tests/        suíte unittest (QT_QPA_PLATFORM=offscreen)
tools/        scripts de teste/diagnóstico avulsos (ver tools/README.md)
docs/         guias, histórico, changelogs e previews (ver docs/README.md)
config/       default.json (local, ignorado pelo git) + default.example.json
data/ logs/   estado e diagnósticos locais (ignorados pelo git)
```

Na raiz ficam só o código do app, os pontos de entrada e os configuradores:
`iniciar_*.bat`, `configurar_*.bat/.py`, `main*.py`, `versao.py`, `self_test.py`.

---

## Dados e privacidade

- `config/`, `data/`, `logs/`, `vendor/` e assets de voz são ignorados pelo git
  (ver `.gitignore`).
- Chaves e tokens são gravados **criptografados com DPAPI do Windows** quando o pywin32
  está instalado: `brain/gemini_auth.py`, `voice/eleven_auth.py`, `spotify_api.py`,
  `spotify_bridge.py`, `integrations/gmail_reader.py` — helper único em
  `secure_store.py`. Sem DPAPI, os módulos falham de forma explícita em vez de gravar
  em texto puro.
- O token do bridge do Spotify continua embutido no JS da extensão do Spicetify
  (limitação do próprio Spicetify). Se ele vazar:
  `configurar_spotify_bridge.bat --rotate`.
- Logs não registram tokens, chaves, e-mails nem corpo de resposta HTTP.

---

## Desenvolvimento

```powershell
# suíte completa (offscreen)
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# smoke test rápido (config, memória, router, personalidade)
.venv\Scripts\python.exe self_test.py

# diagnóstico de ambiente
.venv\Scripts\python.exe tools\diagnostico_startup.py

# gerar config/default.example.json a partir do config real (sem segredos)
.venv\Scripts\python.exe tools\gerar_config_exemplo.py

# Spotify ponta a ponta (bridge + extensão do Spicetify + comando real)
.venv\Scripts\python.exe tools\verificar_spotify_e2e.py

# performance de renderização (mede e compara pixels com uma referência)
.venv\Scripts\python.exe tools\benchmark_render.py --compare logs/render_bench
```

`requirements.txt` é o instalável mínimo. `requirements.lock.txt` é o ambiente completo
validado (inclui torch/TTS usados pelos motores de voz locais).

---

## Histórico

- Changelogs por versão: [`docs/changelog/`](docs/changelog/)
- Notas antigas e migradores históricos: [`docs/historico/`](docs/historico/)
- Análise técnica completa e o que foi corrigido em 28/10/2026:
  [`REVISAO_TECNICA_V_1_9_8_20261028.md`](REVISAO_TECNICA_V_1_9_8_20261028.md)
