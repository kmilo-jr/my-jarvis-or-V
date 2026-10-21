# V Prototype

Assistente de desktop para Windows com comandos locais, interface animada e
recursos opcionais de voz, IA e Spotify.

## Começar

1. Instale Python e crie um ambiente virtual: `py -m venv .venv`.
2. Ative o ambiente e instale as dependências: `pip install -r requirements.txt`.
3. Inicie com `python main.py`. Na primeira execução, o V cria uma configuração
   local a partir de `config/default.example.json`.
4. Ollama e o modelo configurado são necessários para conversa local. Os recursos
   externos ficam desativados até você configurá-los na sua máquina.

O exemplo publicado não inclui chaves, tokens, configurações pessoais de IA,
histórico, notificações, logs, gravações de voz ou modelos baixados. O Git ignora
esses dados locais. Configure qualquer serviço diretamente no seu computador e
nunca envie os arquivos privados de `config/`.

## Dependências opcionais

- Ollama para respostas locais de IA.
- Edge TTS para fala neural em português; requer conexão com a internet.
- Spotify Desktop e credenciais próprias para os controles do Spotify.
- Modelos Whisper e visão são baixados/instalados separadamente.

---

# Histórico de versões

As notas abaixo descrevem versões anteriores e podem mencionar integrações que
agora são opcionais.

## V Prototype 1.6 — Neural Interface + Processing FX

## Rotina de bom dia com cartões sincronizados

Diga **“V, bom dia”** ou clique em **Resumo do dia** para apresentar clima no
Rio de Janeiro, agenda local, pendências, notificações e notícias. Cada assunto
acompanha a fala e continua acessível nos cartões menores. Reabra o V para
carregar a atualização. Veja [RESUMO_DO_DIA.md](RESUMO_DO_DIA.md).

Esta versão preserva o cérebro Gemini, personalidade, voz personalizada e Spotify Bridge da 1.5 e adiciona a primeira etapa da nova interface neural.

## Novidades
- Som ambiente discreto enquanto o V realmente está **PROCESSANDO**.
- O efeito só começa após ~260 ms; comandos muito rápidos continuam silenciosos.
- O efeito para imediatamente quando o V começa a falar, termina a ação ou encontra erro.
- A voz contínua é bloqueada enquanto o efeito toca, evitando que o Whisper escute o próprio V.
- Novo estado visual **FALANDO** e núcleo com arcos/pulsação diferentes para ONLINE, OUVINDO, PROCESSANDO, FALANDO e ERRO.
- Checkbox `SOM AO PROCESSAR` na interface. A preferência fica salva.
- O arquivo do efeito fica em `assets/sounds/v_processing.wav`.

## Migração
1. Deixe `V_PROTOTYPE_1_5_SPOTIFY_BRIDGE` ao lado desta pasta.
2. Rode `migrar_config_1_5.bat`.
3. Inicie normalmente com `iniciar_v_prototype.bat`.

Para ouvir apenas o novo efeito, rode `testar_som_processamento.bat`.

O volume inicial é propositalmente baixo. Pode ser ajustado em `config/default.json` -> `ui.processing_sound_volume`.

---

# V Prototype 1.5 — Spotify Bridge

Esta versão integra o caminho de Spotify validado no Windows: **Spotify Web API para busca + Spicetify Bridge para playback no Spotify Desktop oficial**.

## Migração rápida
1. Deixe `V_PROTOTYPE_1_4_1_STREAM_ROUTING_HOTFIX` ao lado desta pasta.
2. Rode `migrar_config_1_4_1.bat`.
3. Rode `configurar_spotify_bridge.bat` uma vez.
4. Feche completamente o Spotify e abra de novo.
5. Inicie o V com `iniciar_v_prototype.bat`. O servidor local do bridge inicia oculto dentro do próprio V; não é preciso deixar um CMD separado aberto.

## Spotify
- `toque Creep do Radiohead` -> Web API encontra a URI -> `Spicetify.Player.playUri()`
- `próxima música` -> `Spicetify.Player.next()`
- `música anterior` -> `Spicetify.Player.back()`
- `pause/continue` -> controle direto do Spotify Desktop.

Use `diagnosticar_spotify_bridge.bat` se a extensão não aparecer.

---

# V Prototype 1.4.1 — Stream + Routing Hotfix

Baseado no V 1.3 Custom Voice. Esta versão não troca a personalidade, a memória nem o Voice ID.

## O que mudou
- Conversa Gemini via `streamGenerateContent` (SSE): a primeira frase pode ir ao TTS antes do fim da resposta.
- Fast Path local: ações triviais de app/volume/janela/mídia não chamam Gemini só para naturalizar o “pronto”.
- Sessão HTTP persistente para Gemini e ElevenLabs, reduzindo custo de conexão/TLS entre chamadas.
- Fim de frase da voz contínua reduzido de 0,68 s para 0,50 s.
- Contexto enviado ao Gemini foi enxugado sem remover a memória persistente.
- Medição visível de latência na interface e log `logs/latency_last.json`.

## Migração
Deixe `V_PROTOTYPE_1_3_CUSTOM_VOICE` ao lado desta pasta e execute `migrar_config_1_3.bat`.

## Meta do diagnóstico
Após uma conversa, a interface mostra valores como `1ª fala`, `Gemini`, `Whisper` e `Core`. Use `logs/latency_last.json` se algo ainda parecer lento.

## Importante
O streaming só altera o caminho de conversa. Planner/Tool System continuam estruturados e protegidos pelo Tool Firewall.


## Hotfix 1.4.1

Corrige três problemas observados no uso real:

- `OlÃ¡` e outros acentos corrompidos no streaming SSE: agora a decodificação é UTF-8 explícita.
- frases cortadas: o TTS recebe a primeira frase completa cedo e o restante somente após o fim confirmado da resposta; streams suspeitos são refeitos por uma rota segura.
- `olá V, toque ...` não é mais tratado como simples saudação: a saudação inicial é removida e o pedido real segue para o Tool Router.

Para trazer a configuração da 1.4, execute `migrar_config_1_4.bat`.

## Experimento visual inspirado no video do Instagram
A versao inclui um launcher separado: `iniciar_interface_instagram_teste.bat`.
Ele troca somente a camada visual; o V funcional continua disponivel em
`iniciar_v_prototype.bat`.

## V 1.7 Dual Interface + Mic Recovery
Abra `iniciar_v_dual_interface.bat`. Pressione **F6** (ou use o botão na tela) para alternar entre o modo Orbital ciano e o modo Neural Amber. O Core, Gemini, memória, voz e Spotify continuam compartilhados; somente a janela visual é trocada.

O microfone recebeu correções de captura/reconexão, persistência do dispositivo escolhido e VAD mais tolerante ao início/fim da frase.

## 1.8.3 — News Visual + Mercado
- Notícias: HUD compacto na lateral esquerda, imagens por matéria e leitura sem repetir manchete.
- Bolsa: diga "V, como está a bolsa?", "V, como está o Ibovespa?" ou "V, qual a cotação da PETR4?".
- Cotações são informativas e podem ter atraso da fonte.

## V Remote 1.4 — Mobile Face + V Mobile

- A segunda interface usa a face angular do V Remote/mobile, com halo, partículas discretas e reação a fala/processamento em ~60 FPS.
- Alarmes e lembretes podem ser preparados por comando natural e executados no iPhone pelo atalho **V Mobile**.
- O V Remote também possui campos diretos para criar alarme e lembrete.
- O leitor de notificações do Windows é somente leitura e filtra **WhatsApp** e **Instagram**. Para iPhone, o Phone Link precisa conseguir espelhar as notificações; isso requer Bluetooth no PC.
- Consulte `CONFIGURAR_V_MOBILE_IPHONE.txt` antes do primeiro teste no iPhone.


## Atualização 1.6
- textura neural na face da segunda interface
- V Remote preparado para uso fora de casa
- suporte opcional a Cloudflare Quick Tunnel
