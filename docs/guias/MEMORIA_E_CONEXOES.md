# Memória e central de conexões — 03/10/2026

Reinicie o V e use **Memórias** e **Conexões** na barra de controles, disponível nas interfaces que compartilham a janela principal.

## Memórias

O painel permite buscar, criar, categorizar, corrigir e esquecer registros individualmente. Categorias: preferências, equipamentos, projetos, rotinas e geral. A gravação continua explícita: o V não passa a registrar silenciosamente tudo que ouve. Rotinas lembradas são contexto, não novas automações.

Exemplos:

- `lembre equipamentos: minha GPU é GTX 1650`
- `lembre preferências: prefiro respostas curtas`
- `mostre suas memórias`
- `corrija memória 1 para minha GPU é RTX 4060`
- `esqueça memória 1`

Os números são os mostrados no painel e na consulta por conversa. Corrigir preserva o número e a data de criação; a data de atualização é registrada. Registros antigos continuam legíveis. A gravação usa substituição de arquivo temporário; falhas de escrita não alteram a lista em memória. IDs removidos não são reaproveitados.

A recuperação usa palavras relevantes à pergunta, seguida de recência, com até 24 registros e 6000 caracteres. Isso melhora o acesso a fatos antigos relacionados ao pedido, sem mandar toda a base à IA. Não é uma busca semântica e não garante que o modelo nunca repita uma pergunta. Fatos incompatíveis devem ser corrigidos; a orientação ao modelo é esclarecer a divergência, não escolher silenciosamente.

Ao corrigir ou esquecer, o histórico recente usado como contexto e os resultados recentes de ferramentas são reiniciados para impedir que um fato antigo retorne por esses caminhos. O texto visual já exibido no chat não é apagado. Na tela, alterações aguardam o término de uma ação em andamento.

## Conexões

A central mostra configuração, estado, horário do último teste, resultado/erro e próxima ação. Testa um serviço ou todos, em segundo plano. Não há monitoramento periódico. O último teste é mantido nesta sessão, não entre reinicializações. Configurar Gmail está disponível dentro da central; as demais linhas orientam para os configuradores existentes.

Alcance real dos testes:

| Serviço | O que confirma | O que não confirma |
|---|---|---|
| Gmail | Login IMAP, caixa somente leitura e NOOP | Conteúdo, envio ou recebimento de nova mensagem |
| Spotify | Sinal recente da extensão ou API autenticada e consulta de dispositivos | Reprodução audível |
| Mensagens | Acesso somente leitura ao banco de notificações do Windows | Login WhatsApp/Instagram ou entrega de uma nova notificação |
| Gemini/Groq | Autenticação da API e acesso ao modelo/catálogo | Cota de geração e qualidade de resposta |
| Ollama | Servidor e modelo instalado | Inferência; o teste não carrega o modelo na GPU |
| Remoto | Resposta HTTP do servidor local iniciado pelo Dual | Pareamento, P2P ou acesso pela internet |

Falhas HTTP mostram códigos e instruções, sem expor corpos de resposta, URLs autenticadas ou credenciais. Resultados reais sanitizados desta entrega: `logs/contexto_conexoes_20261003/testes_reais.json`. Gmail, API Spotify, leitor Windows, catálogo Groq e servidor Ollama responderam; Spotify tinha zero dispositivos. Gemini retornou HTTP 401. Remoto não foi testado em uma sessão Dual ativa.

Validação automatizada cobre migração, correção, exclusão ambígua, relevância, falha de gravação, limpeza do contexto antigo, erros HTTP sem segredos, ausência de modelos, Gmail sem leitura de mensagens, heartbeat Spotify vencido, remoto indisponível e operação dos painéis. Capturas dos painéis usam memória fictícia em arquivo temporário.
