# V Orbital e leitura do Gmail

O Orbital usa a grade azul e o núcleo luminoso do resumo como interface principal.
A resposta aparece no cartão central; as três respostas anteriores ficam em
miniaturas. **Histórico da conversa** abre o registro completo da sessão.
**Controles** reúne voz, conversa, sistema e Gmail; **Ferramentas** abre a barra
de atalhos. F6 continua alternando as interfaces.

## Conectar Gmail

1. Reabra o V Orbital e abra **Controles → Gmail**.
2. Informe o endereço e uma **senha de app do Google**, não a senha comum.
3. Clique em **Salvar conexão**, depois **Listar e ouvir meus e-mails**.

A senha de app exige verificação em duas etapas e pode não estar disponível em
algumas contas gerenciadas ou com Proteção Avançada. Instruções oficiais:
https://support.google.com/accounts/answer/185833?hl=pt-BR

O V usa IMAP com TLS e armazena a configuração protegida pelo Windows DPAPI em
`%LOCALAPPDATA%/VAssistant/gmail.json`. A conexão só é verificada ao listar.

## Comandos

- “V, bom dia”: inclui até três e-mails não lidos mais recentes da caixa de entrada,
  apenas com remetente e assunto, sem buscar ou ler o corpo da mensagem.
  Os e-mails permanecem não lidos e podem aparecer novamente no próximo resumo.
  Sem configuração ou se a consulta falhar, o resumo informa isso e continua.
  “Me explique melhor” nesses cartões repete os dados disponíveis sem enviá-los à IA.
- “V, leia meus e-mails”: lista remetente e assunto dos cinco mais recentes.
- “V, liste meus e-mails não lidos”: lista até cinco mensagens não lidas.
- “V, leia o e-mail 2”: lê a mensagem número 2 da última lista.
- Esc interrompe a fala.

A leitura usa acesso somente de leitura e BODY.PEEK, sem marcar como lido,
enviar ou excluir mensagens. Anexos e imagens de rastreamento não são abertos.
Mensagens longas têm leitura parcial, indicada pelo V. O texto do e-mail não é
encaminhado ao planejador de IA; a voz usa o provedor de TTS já configurado no V.
**Desconectar Gmail** remove a configuração local; a senha de app também pode
ser revogada na conta Google.

## Notícias

O resumo usa a imagem do feed ou a imagem declarada pela própria matéria.
Para links intermediários do Google News, busca uma matéria com título
correspondente. Se nenhuma imagem puder ser obtida, mantém o texto e a fonte.

As prévias são demonstrações; não representam uma conta Gmail conectada.
