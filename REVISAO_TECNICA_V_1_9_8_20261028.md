# Revisão técnica — V Prototype 1.9.8 (V Remote 1.7 P2P Steam Style)

**Data:** 28/10/2026 · **Método:** análise estática de código (leitura + grep), sem executar o app
**Limitação:** o shell desta sessão está quebrado (`pwsh` retorna `0xC0000142`, falha de init de DLL).
Nada foi executado: nem `main.py`, nem testes, nem benchmarks. Todas as medições citadas são as que o
próprio projeto registrou em `logs/`.

---

## 0. Status da aplicação (28/10/2026 — fim do dia)

Este documento registra a análise original. Abaixo, o que **já foi aplicado** ao código
depois dela, e o que continua em aberto.

**Aplicado**

| Tema | O que mudou |
|---|---|
| Remoto fora de casa | `p2p_host.py`, `p2p_server/`, `remote_tunnel.py`, `configurar_p2p.py` e os `.bat`/docs de P2P e acesso externo foram **removidos**. `remote_server.py` e `main_dual_ui.py` ficaram somente LAN (PIN local, sem chave externa/public_url). |
| Segurança de segredos | `secure_store.py` (DPAPI) centraliza proteção; `spotify_api.py`, `brain/gemini_auth.py`, `voice/eleven_auth.py`, `spotify_bridge.py` e `integrations/gmail_reader.py` usam DPAPI e **não** gravam mais em texto puro. Os 4 segredos que já estavam em claro no `config/` foram migrados e a releitura foi verificada. |
| Bridge Spotify | CORS restrito (sem `*`), token por header `X-Bridge-Token` (query só no handshake), lease anti-roubo com `409 command_in_progress`, aviso de extensão desatualizada, `--rotate` para rotacionar token, ACL restrita no JS instalado. |
| Falhas silenciosas | `vlog.py` (log rotativo em `logs/v_assistant.log`); `except Exception: pass` caiu de 13 para 1 nos 4 arquivos de voz/engine/briefing (o restante é o callback de captura, de propósito). `last_tts_error` é limpo no sucesso, Piper registra a causa, fila TTS cheia loga, briefing tem timeout de 9 s e as threads de notificação têm `join(2)`. |
| Código morto | Removidas ~185 linhas de `core/functional_engine.py` (`_handle_with_ai` e cadeia), `spotify_controller.py` (510), `ui/amber_neural.py`, `ui/instagram_orb.py`, `ui/reference_face_data.py` e a constante `STYLE` do `desktop_shell`. |
| Versão | `versao.py` é a fonte única (1.9.8 / `V198-LAN-20261028`), usada por `main.py`, `ui/main_window.py`, `main_dual_ui.py`, `ui/amber_window.py` e pelos `.bat` de inicialização. `VERSAO.txt` atualizado. |
| Config e ambiente | `config/default.example.json` agora é gerado do real (254 chaves, 2 valores anonimizados) por `tools/gerar_config_exemplo.py`; `requirements.lock.txt` regenerado por `pip freeze` (132 pacotes); `.bat` de inicialização usam `.venv`. |
| Organização | Raiz de ~230 para 55 arquivos: docs em `docs/{guias,historico,changelog,preview}`, scripts em `tools/`, migradores antigos em `docs/historico/migracoes/`. `README.md` reescrito. |
| Bridge Spotify (pós-uso real) | A extensão reescrita falhava dentro do Spotify: `status()` lançava exceção em um getter real e, como resultado e heartbeat eram montados no mesmo `try`, o `POST /result` nunca acontecia (comando ficava "em andamento" e voltava 504). Agora cada campo de estado é lido defensivamente e falha de status não bloqueia o resultado. Validado ao vivo no Spotify 1.3.6: extensão online em 1 s e `volume`, `status` e `shuffle` retornando 200 com dados reais. |
| Testes e CI | Teste do detector corrigido (deriva os blocos da config; 388 testes, 0 falhas). `edge-tts` 7.2.8 → **7.3.1**, o que resolveu o 403 da síntese online (validado gerando áudio pelo `VoiceEngine`). Workflow `.github/workflows/tests.yml` roda compileall + unittest offscreen no Windows; os commits foram enviados para `origin/main`. |
| Spotify: teste e2e | `tools/verificar_spotify_e2e.py` automatiza o diagnóstico manual (bridge → extensão → comando real → bloqueio do protocolo antigo) e `tests/test_spotify_bridge_flow.py` cobre por unidade o protocolo por header, o lease 409 e o ciclo poll/result. Suíte: 392 testes. |
| Performance do backdrop | `ui/briefing_scene.py` sem refazer trigonometria, com canetas e cores em cache e `QPainterPath.addPolygon`. Medido por `tools/benchmark_render.py`: **17,4 → 16,1 ms** tela cheia e **11,6 → 10,4 ms** na repintura parcial, com pixels idênticos (diff 0,000000). Chave morta `ui.animation_fps` removida do config. |
| Robustez da voz e da UI | Falha de COM/`pythoncom` não mata mais a thread de saída (SAPI é desativado com log e Edge/Piper/XTTS seguem). A câmera é encerrada na troca de interface (F6), não só no fechamento. |
| Caminhos e executável | `app_paths.py` virou a fonte única da raiz (funciona no código e no `.exe`, via `sys.frozen`), com 43 referências `Path(__file__)` migradas em 33 módulos. `setup.ps1`/`setup.bat` preparam uma máquina limpa. `V.spec` + `tools/build_exe.ps1` geram `dist\V\V.exe` (PyInstaller, ~560 MB) — validado rodando: bridge na 8766 com DPAPI e extensão do Spotify vista, servidor remoto na 8765, `config/`/`logs/` criados ao lado do exe. Sem torch/TTS/modelos locais no pacote mínimo. |
| Git | O repositório já existia (remote `kmilo-jr/my-jarvis-or-V`) mas o estado da pasta não estava commitado. Criados dois commits na `main`: `8533a9f` (baseline) e `bfee612` (esta refatoração); árvore limpa com 387 arquivos versionados e nenhum segredo em `config/` (só o `default.example.json`). |

**Validação executada**

- `compileall` do código próprio: OK.
- Suíte completa: **392 testes, 0 falhas** (28/10 tinha 1 falha de teste — ver "Testes e CI" acima).
- Validação de segurança: roundtrip DPAPI, migração de token legado, falha explícita sem DPAPI, allowlist de CORS e ACL — todos OK.
- `tools/diagnostico_startup.py` rodando de `tools/`: OK.
- Migração dos 4 segredos em texto puro: OK, releitura verificada.
- `tools/verificar_spotify_e2e.py`: OK ao vivo (player real, protocolo antigo bloqueado, exit 0).
- `tools/benchmark_render.py`: orbital 16,1 ms tela cheia / 10,4 ms região, pixels idênticos.
- `setup.ps1 -DryRun` e `setup.ps1 -SkipTests`: OK (exit 0, venv detectado, config preservada).
- `dist\V\V.exe` (PyInstaller): inicia, cria `config/`/`logs/` ao lado do exe, sobe bridge (8766, DPAPI, extensão online) e servidor remoto (8765), sem traceback.

**Continua em aberto (por prioridade)**

1. `core/connections.py` só valida `access_mode == 'local'` — coerente agora, mas o teste de conexão continua raso.
2. O `.exe` tem ~560 MB; dá para reduzir excluindo `transformers`/`hf_xet` (não usados pelo faster-whisper no fluxo atual) e revisando os módulos Qt. Não há instalador (só a pasta `dist\V`).
3. Voz local (XTTS/Qwen), modelos Whisper baixados e `vendor/` não vão no pacote mínimo — distribuir com esses recursos exige um segundo pacote/instalador de modelos.
4. A pintura do backdrop ainda é feita no thread da GUI; para folga extra daria para reduzir pontos dos anéis com perda visual imperceptível (hoje a geometria é preservada ao pixel).

---

## 1. Retrato do projeto

Aplicativo desktop Windows em Python/PySide6: assistente de voz em português ("V") com face animada,
comandos de sistema, briefing diário, notícias/mercado, Spotify, câmera/visão, lembretes, e controle
remoto pelo celular (P2P estilo Steam ou relay). Total estimado em ~15 mil linhas de código próprio
dentro de 5 pacotes + ~25 módulos Python soltos na raiz.

**O que mais impressiona:** a arquitetura de fallback. Cérebro com 4 provedores (Gemini → Groq →
Ollama → web), voz com 6 motores (Edge-TTS, Piper, XTTS-v2, ElevenLabs, Qwen3 local, SAPI5), e
controle remoto com WebRTC direto + relay automático. Cada camada tem plano B.

**O que mais preocupa:** não é a falta de plano B — é que o plano B costuma falhar **em silêncio**.
São 259 blocos `except Exception:` no código próprio, boa parte sem log, e a configuração de uma
instalação nova não reproduz a que você usa.

---

## 2. Arquitetura de execução

```
main_dual_ui.py  (lançador real: P2P/remote + dupla interface, F6 alterna)
  └─ UiModeManager
       ├─ InstagramExperimentWindow -> DesktopShell (nav + QStackedWidget)   [modo orbital]
       └─ AmberExperimentWindow                                             [modo amber]
main.py  (lançador simples, janela clássica — continua funcionando)

UI (QThread de voz)                    Núcleo funcional
  ContinuousVoiceWorker                  core/functional_engine.py :: handle()
    voice/engine.py :: capture_phrase       → normalização / wake word
      endpoint.py (VAD adaptativo)          → firewall semântico de intenção
    engine.py :: transcribe                 → core/tool_router.py :: route()
      faster-whisper + Silero VAD           → core/tool_system.py :: ToolRegistry
        → heard → enqueue_command           → core/legacy_tools.py (implementações)
          → _pump_commands                  → brain/service.py (Gemini/Groq/Ollama/web)
            → VoiceEngine.speak  ←──────────┘    personality/layer.py (persona)

Remoto: p2p_host.py (PC conecta para fora) ⇄ p2p_server/ (sinalização + relay) ⇄ iPhone
        fallback legado: remote_server.py + remote_tunnel.py (cloudflared, desligado por padrão)
```

**Fluxo de voz (resumo):** `main.py:29` cria o `VoiceEngine` e `:32` faz `warmup_tts()` em thread →
`ui/main_window.py:86` sobe o worker de captura → `voice/engine.py:372` detecta o fim da fala →
`:550` transcreve → `ui/main_window.py:1360` valida wake word/janela de follow-up → `:766` enfileira
→ `core/functional_engine.py:963` decide e executa → `voice/engine.py:734` fala, com `_tts_loop`
único em `:1877`.

**Fluxo remoto:** `p2p_host.py:39` gera `room_id` + `device_token` (persistidos no config) e PIN de
6 dígitos por sessão (`:91`) → link `https://host/#room=…&token=…` (`:108`) → pareamento pelo PIN com
`hmac.compare_digest` (`:261`) → DataChannel WebRTC (`:312`) ou relay JSON pelo mesmo WebSocket.

---

## 3. Inventário e tamanho dos módulos

| Área | Arquivos | Maiores arquivos |
|---|---|---|
| `ui/` | ~50 | `main_window.py` 1491, `internal_panel.py` 898, `amber_window.py` 269, `desktop_shell.py` 268 |
| `voice/` | ~20 | `engine.py` **2052**, `qwen_backend.py`, `recognition_backend.py` |
| `core/` | ~28 | `functional_engine.py` 1185, `tool_system.py` 430, `personal_assistant.py` 272 |
| `brain/` | 6 | `service.py` 1043, `memory_store.py` |
| raiz | ~25 .py | `legacy_tools.py` 1237, `spotify_api.py` 858, `spotify_controller.py` 510 (morto), `p2p_host.py` 407, `remote_server.py` 429 |
| `p2p_server/` | 1 | `server.py` 174 (aiohttp + HTML/JS remoto embutido) |
| `tests/` | 57 | 9 são `preview_*`/`benchmark_*`/stress, não testes |

Config real: 326 linhas · config de exemplo: 67 linhas.

---

## 4. O que está bem feito (não mexer)

1. **Cadeia de fallback do cérebro** com ordem explícita e testada — `brain/service.py:172-245`,
   cobertura em `tests/test_brain_recovery.py` e `tests/test_groq.py`.
2. **ToolRegistry com validação e trace** — `core/tool_system.py:74-100`, limite de 8 ações e
   interrupção após falha em `functional_engine.py:844-879`, trace em `logs/tool_trace_last.json`.
3. **Anti-eco da voz** — `voice_input_allowed` bloqueia o microfone enquanto o V fala
   (`voice/engine.py:105`), combinado com `barge-in` e janela de follow-up.
4. **Segurança da Gmail** — senha de app criptografada com DPAPI, IMAP somente leitura e `BODY.PEEK`
   (`integrations/gmail_reader.py:13-34,79`). **Spotify OAuth** com PKCE + `state` + loopback
   (`spotify_api.py:115,148-176`).
5. **Desenho do P2P** — token no fragmento da URL (não vai em log HTTP), só hash SHA-256 no servidor,
   PIN comparado em tempo constante, PC só faz conexão de saída, WebRTC preferido com relay de
   fallback. A ideia está certa; faltam os detalhes de operação (item 5.B).
6. **Economia de recursos na UI** — `GameModeController` reduz FPS e pausa timers quando a janela está
   oculta (`ui/game_mode.py:88-97`); `AnimationClock` limita `dt` a 0,1 s.
7. **Testes de comportamento** — 48 testes reais com `unittest`, `QT_QPA_PLATFORM=offscreen`, mocks de
   rede/áudio; bom uso de `unittest.mock.patch`.
8. **`.gitignore` consciente** — cobre `config/`, tokens, `data/`, `logs/`, modelos e assets grandes.

---

## 5. Achados por severidade

### 5.A — P0: corrigir antes de expor o controle remoto

| # | Problema | Onde |
|---|---|---|
| A1 | **`ALLOWED_ACTIONS` não é fronteira de segurança.** O servidor repassa `kind:"command"` com texto livre; o host entrega esse texto ao pipeline completo do V (`main_dual_ui.py:163` → `ui/main_window.py:686`). Quem parear pode pedir qualquer coisa que o V sabe fazer — inclusive abrir arquivos, mexer em documentos, Gmail, câmera — e não só as 15 ações da lista (`p2p_host.py:27-32,379`). | `p2p_server/server.py:137-143`; `p2p_host.py:374-384` |
| A2 | **PIN sem limite de tentativas, sem expiração e sem rotação.** 6 dígitos, sem lockout nem backoff (`p2p_host.py:91,261`). O `device_token` que vai na URL é a credencial de fato e vale para sempre. | `p2p_host.py:39-59,91,261` |
| A3 | **Telemetria antes do PIN.** `host_status` é retransmitido a **todos** os clientes da sala (`server.py:145-147`), e o snapshot inclui `remote_url` — que contém room + token — além de CPU/RAM/disco e URL pública (`p2p_host.py:135-145,239`). Ressalva verificada: para entrar como `client` é preciso apresentar o token válido (`server.py:121`), então quem recebe isso já tem o link; o problema real é que o PIN deixa de proteger a leitura de estado, não que o token vaze para estranhos. | `server.py:145-147` |
| A4 | **Bridge do Spotify:** CORS `*`, token na query string e `/next` que "rouba" o comando atual — qualquer página local pode ler `/health` e, com o token, controlar o playback. | `spotify_bridge.py:90,96-99,136-146,217` |
| A5 | **Tokens em texto puro no disco:** `config/spotify_token.json` (access + refresh), `config/spotify_bridge_token.txt`, e o mesmo token embutido no JS da extensão em `%APPDATA%\spicetify\Extensions\vSpotifyBridge.js`. O `chmod 0o600` é inócuo no Windows. | `spotify_api.py:21,61-67`; `spotify_bridge.py:18,74-84`; `configurar_spotify_bridge.py:22-23` |
| A6 | **Chave Gemini pode cair em texto puro:** se o DPAPI falhar, `gemini_auth.py` grava a API key sem criptografia. | `brain/gemini_auth.py:38-41` |
| A7 | **Servidor de sinalização sem endurecimento:** `host="0.0.0.0"` sem TLS (dependente do Render), sem CORS/Origin, sem rate-limit, `except Exception: pass` global sem log, `Dockerfile` roda como root, `/health` revela nº de salas. | `p2p_server/server.py:64-65,151,167-174`; `p2p_server/Dockerfile` |

### 5.B — P1: bugs que o usuário sente

| # | Problema | Onde |
|---|---|---|
| B1 | **Fala descartada silenciosamente** quando a fila TTS enche (descarta a mais antiga). | `voice/engine.py:746-751` |
| B2 | **Erro fantasma na voz:** depois de um fallback bem-sucedido, `last_tts_error` antigo permanece → a UI mostra "Falha na voz selecionada" mesmo com áudio entregue. | `voice/engine.py:1919-1926,1971-1979`; `ui/main_window.py:1279-1283` |
| B3 | **Fallback que quebra a promessa:** falha ao carregar Piper é silenciosa e o perfil "offline" cai para Edge-TTS (que exige internet), sem avisar. | `voice/engine.py:1586-1589,1941-1944` |
| B4 | **Cancelar o Qwen mata o processo residente:** cada interrupção força recarga do modelo na fala seguinte (segundos). | `voice/qwen_backend.py:135-144` |
| B5 | **Reconexão do celular quebra o pareamento:** o JS esconde o painel de PIN após o primeiro `pair_ok` e não reenvia `pair_request`; o host rejeita o novo `client_id` em silêncio. O celular fica "online" sem executar nada até recarregar a página. | `p2p_server/server.py:38-39,124`; `p2p_host.py:278` |
| B6 | **Estado remoto nunca podado:** `_paired`, `_pcs` e `_channels` não são limpos na queda do signaling; `RTCPeerConnection` sem timeout de ICE acumula. | `p2p_host.py:99-101,224-228` |
| B7 | **Threads sem timeout/join:** `future.result()` sem timeout no briefing (fonte lenta trava a rotina) e threads daemon de notificações sem encerramento determinístico. | `core/daily_briefing.py:215-225`; `core/live_notifications.py:59-88` |
| B8 | **Histórico/memória somem sem diagnóstico:** leitura e escrita engolem qualquer exceção; a conversa pode desaparecer e nada aparece no log. | `core/functional_engine.py:290-307` |
| B9 | **Perfil de voz não é recomendado/validado:** `_tts_loop` depende de `pythoncom`; se falhar, a thread morre e nenhuma fala sai. | `voice/engine.py:1880-1883` |
| B10 | **Instalação nova nasce capada:** `main.py:11-13` copia `config/default.example.json` (67 linhas, ~25 chaves de voz) quando falta o `default.json`; sua config real tem 326 linhas (~160 de voz). Máquina nova perde Piper/XTTS/Eleven/Qwen e muda de comportamento sem aviso. | `main.py:11-13` |

### 5.C — P2: manutenção, performance e higiene

| # | Problema | Onde |
|---|---|---|
| C1 | **Trabalho fora do histórico do Git.** O `.git/` já existia (remote `kmilo-jr/my-jarvis-or-V`), mas o estado atual da pasta não estava commitado — nenhuma alteração tinha diff, baseline ou volta atrás. Resolvido: baseline e refatoração estão em commits na `main`. | raiz |
| C2 | **≈230 arquivos na raiz do projeto.** ~35 `migrar_config_*`, ~10 `migrar_spotify_*`, 18 `CHANGELOG_*.txt`, ~35 `.md` de notas, 30+ `testar_*.py/.bat`, PNGs de preview. O código que importa está em 7 pastas. | raiz |
| C3 | **Versão em 4 lugares e todos diferentes:** `VERSAO.txt` = 1.9.8, `main.py:39` = "V 1.6 NEURAL", `ui/main_window.py:206` = "1.8.3", `config/default.json` = "PROTOTYPE 1.8 P2P REMOTE", `iniciar_v_prototype.bat` = "V 1.6". | vários |
| C4 | **Código morto confirmado:** `_handle_with_ai` (`functional_engine.py:922`) não tem chamador externo; com ele caem `_ai_action_to_command`, `_validate_ai_action`, `_write_brain_router_log`, `_fast_path_candidate`, `_looks_conversational` (~250 linhas). `spotify_controller.py` (510 linhas) não é importado por ninguém. `ui/amber_neural.py`, `ui/instagram_orb.py`, `ui/reference_face_data.py` estão fora do fluxo. | vários |
| C5 | **4 UIs completas + 5 blocos QSS duplicados:** `main_window.py`, `amber_window.py`, `amber_window_2d.py`, `instagram_window.py` repetem `append_user/append_v`, `set_state`, `_update_system` e o bloco de voz; `APP_STYLE` é aplicado e sobrescrito logo depois. | `ui/*` |
| C6 | **Performance do backdrop orbital:** 9 `QPainterPath` de 161 pontos refeitos por frame; o benchmark do projeto mede 19,8 ms (acima do orçamento de 16,7 ms para 60 fps). Rostos repintam o fundo inteiro e alocam gradientes por frame. | `ui/briefing_scene.py:119-131`; `ui/futuristic_face.py:53`; `ui/mobile_face_core.py:283-357` |
| C7 | **Timer que nunca para:** o diálogo de tarefas cria QTimer de 500 ms no construtor e é recriado a cada abertura; refreshes se acumulam. | `ui/task_interaction.py:63`; `ui/main_window.py:357-362` |
| C8 | **Ambiente não reprodutível:** `.venv` tem `torch 2.9.1+cu128`, `TTS` (Coqui), `sklearn`, `librosa`, `aiohttp` — nenhum em `requirements.txt`. E **`aiortc`/`websockets` não estão instalados no `.venv`**: na máquina atual o P2P só funciona em RELAY. Pior, `PREPARAR_V_P2P.bat` e `INICIAR_V_P2P.bat` usam o `python` global, enquanto `iniciar_v_prototype.bat` usa `.venv\Scripts\python.exe`. | `.venv/`, `requirements.txt`, `PREPARAR_V_P2P.bat:18`, `INICIAR_V_P2P.bat:37` |
| C9 | **Sem padronização de projeto:** não há `pyproject.toml`, `conftest.py`, `pytest.ini` nem CI; `tests/` mistura testes, previews e benchmarks. | raiz |
| C10 | **Redundância de "cérebro" e de remoto:** `remote_server.py` (cloudflared/LAN) e `p2p_host.py` (P2P) convivem e são iniciados juntos; `spotify_api.py`/`spotify_bridge.py`/`spotify_controller.py` se sobrepõem. | raiz |
| C11 | **Normalização de texto duplicada:** 6 variantes de "tirar acento" só neste escopo (NFKD→ASCII em `functional_engine.py:54`, NFD+`strip Mn` em `project_progress.py:14`, etc.) e ~15 no repositório — duas famílias convivem. Isso já gerou condição morta: `_validate_ai_action` checa `"áudio"`, mas o texto já perdeu o acento. | `core/*` |
| C12 | **Logs com PII:** corpo bruto de resposta HTTP em `last_error` (`brain/service.py:360,529,777`) e prompt/plano/args de ferramentas em `logs/` (`functional_engine.py:819-878`). Contraste positivo: `connections.py` e `crash_diagnostics.py` sanitizam de propósito. | `brain/`, `core/` |
| C13 | **Config como depósito:** 326 linhas com chaves que ninguém lê (`ui.animation_fps` não é usado; `ToolSpec.risk` e `confirm_callback` nunca são consultados). | `config/default.json` |

---

## 6. Plano de ação sugerido

### Onda 1 — segurança e confiabilidade (1–2 dias)
1. `server.py:145` — só retransmitir `host_status` para `client_id in host._paired`; remover
   `remote_url` (token) do snapshot de status.
2. PIN com contador de falhas por cliente + expiração (ex.: 5 min) e rotação opcional do
   `device_token`; no host, limpar `_paired/_pcs/_channels` ao cair o signaling e reenviar
   `pair_request` automaticamente na reconexão do celular.
3. Restringir `kind:"command"` a um allowlist de intenções (ou exigir confirmação no PC para ações
   de risco) — hoje é o pipeline inteiro.
4. Rotacionar os tokens Spotify/bridge, mover para DPAPI (mesmo padrão do Gmail), CORS restrito à
   origem da extensão e token em header no bridge.
5. `brain/gemini_auth.py` — falhar explicitamente se o DPAPI não estiver disponível.

### Onda 2 — parar de falhar em silêncio (2–3 dias)
6. Trocar `except Exception: pass` por `except Exception as exc: log(...)` nos caminhos de
   rede/voz/persistência (259 ocorrências; priorizar `voice/engine.py`, `core/functional_engine.py`,
   `p2p_server/server.py`).
7. `last_tts_error` zerado no sucesso do fallback; `_load_piper_voice` reportando causa; fila TTS
   com aviso em vez de descarte.
8. `daily_briefing.py:221` → `result(timeout=…)`; executor com `shutdown` no `close()`.
9. `config/default.example.json` gerado a partir do `default.json` sem segredos (ou fallback que
   preserve as chaves de voz) — hoje a primeira execução muda o produto.

### Onda 3 — limpeza e reprodutibilidade (1 semana)
10. `git init` + primeiro commit + `.gitattributes`; tag `v1.9.8`.
11. Mover `migrar_*`, `testar_*`, `CHANGELOG_*`, docs e PNGs para `tools/`, `docs/`, `docs/changelog/`;
    apagar ~10 MB de duplicatas.
12. Remover código morto confirmado (`_handle_with_ai` e cadeia, `spotify_controller.py`,
    `amber_neural.py`, `instagram_orb.py`) — ~1.500 linhas.
13. Congelar dependências (`pip freeze` → `requirements.lock.txt`) e corrigir os `.bat` para sempre
    usar `.venv`; instalar `aiortc`/`websockets` no `.venv` para o P2P sair do relay.
14. Unificar normalização de texto em `core/text.py`; unificar os 3 splitters de TTS em um módulo.
15. Quebrar `voice/engine.py` (2052) e `brain/service.py` (1043) por motor/transporte; extrair
    `handle()` (220 linhas) em orquestrador + handlers.
16. Uma fonte de versão (`VERSAO.txt` ou `__version__`) consumida por UI, `main.py` e `.bat`.

---

## 7. O que eu não consegui verificar (você precisa rodar)

| Objetivo | Comando |
|---|---|
| Suíte de testes | `.venv\Scripts\python.exe -m unittest discover -s tests -v` |
| Smokes manuais | `.venv\Scripts\python.exe self_test.py` |
| Benchmark de render (baseline atual) | `.venv\Scripts\python.exe tests\benchmark_animation_rendering.py` |
| P2P local | `python p2p_server\server.py` + `TESTAR_SERVIDOR_P2P_LOCAL.bat` |
| Dependências P2P no venv | `.venv\Scripts\python.exe -m pip install -r requirements_p2p.txt` |
| Diagnóstico de startup | `.venv\Scripts\python.exe diagnostico_startup.py` |

---

## 8. Anexo — candidatos a remoção/arquivamento (por nome, confirmar importadores)

- **Mortos confirmados:** `spotify_controller.py` (510 linhas, sem importadores), `ui/amber_neural.py`,
  `ui/instagram_orb.py`, `ui/reference_face_data.py`, `ui/desktop_shell.py::STYLE` (nunca aplicado),
  `camera_panel._show_image`, `functional_engine._handle_with_ai` + cadeia (~250 linhas).
- **Migradores obsoletos:** `migrar_config_0_8_2*` … `migrar_config_1_5*` (manter só o último salto e o
  caminho de atualização automática), `migrar_spotify_0_7_*`.
- **Scripts de diagnóstico repetidos:** `testar_voz_v.py`, `testar_voz_natural.py`,
  `testar_voice_input_2.py`, `testar_qwen_inicio.py`, `testar_qwen_frases_longas.py`,
  `testar_som_processamento.py`, `testar_live_search.py`, `diagnostico_startup.py` → mover para `tools/`.
- **Docs:** 35 arquivos `.md` + 18 `CHANGELOG_*.txt` → `docs/` e `docs/changelog/`; consolidar em um
  `CHANGELOG.md`.
- **Config divergente:** `configurar_voz_v.py:10` fixa Voice ID `8UH1CSGj7v69E1F7Yo6d`, mas
  `config/default.json:168` usa `dhHn9Km3IPSuM1vkMUJv`.
- **Consistência de achados:** assets `v_face_lineart/silhouette/reference/ultron` sem referência no
  código (usados só por `reference_face_data.py`, que está morto).

---

### Resumo em 5 linhas

1. A arquitetura é boa e o produto funciona — o problema é operacional, não conceitual.
2. Prioridade nº 1: o controle remoto. `ALLOWED_ACTIONS` não limita nada e o PIN não tem força.
3. Prioridade nº 2: parar de engolir exceções — metade dos bugs de voz e de briefing desaparece com log.
4. Prioridade nº 3: `git init` + limpar a raiz + congelar dependências (o P2P nem está instalado no venv).
5. Depois disso, performance do backdrop e o `handle()` de 220 linhas são o próximo alvo natural.
