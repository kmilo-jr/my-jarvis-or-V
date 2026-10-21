# Rotina de bom dia

Reabra o V pelo iniciador que já utiliza. Diga **“V, bom dia”**, digite
**“resumo do dia”** ou clique em **Resumo do dia** na barra superior.

A rotina apresenta um assunto de cada vez: abertura, clima no Rio de Janeiro,
agenda local de hoje, itens pendentes das listas, notificações recebidas nas
últimas 24 horas, até três e-mails não lidos mais recentes do Gmail e até cinco
manchetes. Os assuntos já apresentados continuam acessíveis nos cartões menores.
As consultas não alteram listas, compromissos ou notificações.

Cada cartão acompanha a conclusão da sua própria fala. Sem voz, os cartões
avançam com tempo para leitura. Se o áudio falhar, a apresentação continua
pela tela. Uma fonte indisponível aparece como indisponível, sem transformar
uma falha em uma afirmação de que a agenda está livre.

## Controles

A apresentação ocupa a área da janela com grade azul, núcleo luminoso animado,
cartão principal ao centro e miniaturas dos assuntos anteriores abaixo, seguindo
a composição do vídeo de referência. Ao avançar, o cartão anterior se reduz até
sua miniatura enquanto o novo aparece. As miniaturas mostram os próprios dados
do assunto e permitem revisitá-lo. O indicador superior acompanha o estado real
da fala; o rodapé mantém os controles e a indicação do próximo assunto.

A barra de ferramentas habitual fica oculta durante o resumo e volta ao fechá-lo.
As notícias consultam os feeds diretos do g1 e da Agência Brasil a cada execução,
com o leitor Google News como alternativa em caso de falha das duas fontes.
As fotos são carregadas antes da apresentação e aparecem no cartão e na miniatura.
Quando uma foto não puder ser obtida, o cartão permanece textual.

O arquivo local `data/briefing_news_seen.json` guarda identificadores das manchetes
selecionadas. O V prioriza notícias ainda não apresentadas, inclusive após reiniciar.
Quando todas as notícias disponíveis já tiverem sido usadas, volta às menos recentes;
isso alterna o conteúdo, sem afirmar que uma matéria antiga acabou de ser publicada.

- **Próximo / Voltar:** muda o assunto e interrompe a fala anterior.
- **Pausar / Continuar:** guarda o assunto atual; continuar o lê novamente.
- **Me explique melhor:** pausa a sequência e pede uma explicação à IA configurada,
  usando o título, o texto e a fonte do cartão como contexto. A resposta aparece
  e é lida no próprio painel. Se a IA não responder, mostra os dados disponíveis.
  Para Gmail, apenas repete os dados disponíveis sem enviá-los à IA.
- **Retomar resumo:** volta ao cartão original do mesmo assunto e retoma a sequência.
- **Ver cartão original:** sai da explicação mantendo a sequência pausada.
- **Cartão menor:** revisita o assunto e pausa a sequência automática.
- **Abrir fonte:** abre o endereço da notícia, do clima ou do Gmail.
- **Fechar / Esc:** encerra a apresentação e sua fala.
- Por voz: **“V, próximo”**, **“V, voltar”**, **“V, pausar resumo”**,
  **“V, continuar resumo”**, **“V, abre esse”**, **“V, repita esse”**.
- Também: **“V, me explique melhor”**, **“V, mais detalhes”**,
  **“V, retomar resumo”**, **“V, pode continuar”** e **“V, para”**.

Avançar ou voltar enquanto estiver pausado mantém a sequência pausada e lê
apenas o cartão escolhido. Trocar de assunto, pausar ou fechar invalida uma
explicação ainda em preparação. A explicação usa os dados já consultados;
ela não busca o texto integral da notícia nem executa comandos.

Para comandos durante a fala, é necessário ativar a voz contínua e o controle
existente **Interromper por voz (use fones)**. Os botões funcionam a qualquer
momento. Um novo pedido encerra a apresentação atual.

## Fontes e limites

- Gmail: configure em **Controles → Gmail** no Orbital com endereço e senha de app
  do Google. A rotina lê apenas remetente e assunto de cada mensagem,
  sem marcar como lida. Sem conexão, informa a indisponibilidade e continua.
  Os cartões do Gmail não são enviados à IA ao pedir mais detalhes.
- Clima: [Open-Meteo](https://open-meteo.com/en/docs), coordenadas do centro do
  Rio de Janeiro, fuso America/Sao_Paulo. Não requer chave.
- Agenda e pendências: apenas os registros locais do V; não implica conexão
  com Google Calendar ou e-mail.
- Mensagens: notificações já recebidas pelo V. Se o espelhamento estiver
  indisponível, isso é informado. Até quatro notificações são mostradas.
- Notícias: o leitor de notícias existente. Cada manchete mantém a fonte e o
  link; não há resumos inventados por IA.

Disponível nas interfaces principal, Orbital e Amber. As imagens
`resumo_do_dia_preview.png`, `resumo_do_dia_compacto.png` e
`resumo_do_dia_detalhes.png` usam dados ilustrativos, identificados na tela.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_daily_briefing tests.test_gmail_reader tests.test_task_interaction tests.test_routines tests.test_speech_controls tests.test_news_speech tests.test_personal_assistant tests.test_initiative_voice
.\.venv\Scripts\python.exe -m tests.preview_daily_briefing
```

## Música ao iniciar

O comando de resumo inicia a playlist definida em `config/briefing_music.json`
em modo aleatório antes de consultar as fontes. A playlist configurada é:
https://open.spotify.com/playlist/37i9dQZF1Epxpa7WkAt2RE
Sem playlist configurada, usa a seleção atual do Spotify.
O Spotify Bridge precisa estar configurado. A rotina reduz apenas o volume do
Spotify a no máximo 15%, sem elevar um volume menor. O modo aleatório e o volume
permanecem assim após o resumo; a música continua tocando.
Sem conexão ou seleção musical, o resumo continua e informa o problema.
A escolha usa sua playlist configurada, sem inferir humor. São apresentadas cinco notícias
quando há cinco matérias distintas disponíveis nas fontes.
