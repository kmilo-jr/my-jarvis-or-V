# Avatar e criação de arquivos

## Uso

Reinicie pelo `iniciar_v_dual_interface.bat`. Diga “V, modo jogo” para recolher.
Clique no avatar para conversar. O menu do botão direito abre a interface completa.
O botão Falar ativa a escuta existente; diga “V” antes do pedido. Parar microfone
desativa essa escuta. Fechar a caixinha não desliga a voz contínua.

Exemplos de pedidos:

- `Crie um PDF sobre um plano de estudos de inglês para iniciantes`
- `Crie um documento sobre a organização de um trabalho da faculdade`
- `Gere uma planilha de orçamento mensal com campos para eu preencher`
- `Crie um PDF: Este é o texto exato que deve aparecer no arquivo.`

Os arquivos ficam em `exports`, com data e identificador único. A resposta informa
o caminho; a conversa compacta oferece **Abrir arquivo criado**.
PDF e DOCX aceitam texto literal depois de dois-pontos, mesmo sem IA conectada.
Para elaborar conteúdo de um assunto, é necessária uma conexão de IA funcionando.

Esta primeira versão produz documentos de texto e planilhas de uma aba, com
cabeçalho, filtros e valores. Não inclui macros, fórmulas geradas ou gráficos.
Dados ausentes devem virar campos vazios ou exemplos identificados, nunca dados
pessoais inventados. Revise conteúdo elaborado pela IA antes de utilizar.
Uma resposta inválida da IA é reportada como falha e não vira arquivo de sucesso.

## Correção do crash

O teste com execução real em segundo plano reproduziu uma violação de acesso em
`Qt6Gui.dll`, no mesmo deslocamento registrado pelo Windows na falha relatada.
A entrega de `CommandWorker.finished` chamava a implementação da interface
orbital na thread do worker. Essa implementação alterava widgets de texto
simultaneamente ao desenho da interface.

A resposta agora passa por um slot Qt registrado, com conexão enfileirada na
janela principal; somente depois chama a implementação específica da interface.
O teste de regressão verifica respostas nas três interfaces e confirma que as
alterações do texto ocorrem na thread da aplicação.

Também foram corrigidos o carregamento de bibliotecas de visão em todo pedido,
a resposta da interface Amber na caixinha e o tratamento de falha no envio.
As entradas principais registram stacks em `logs/app_crash.log` para diagnóstico.

## Verificação

- `python -m unittest tests.test_avatar_chat tests.test_game_mode`
- `python -m unittest tests.test_documents`
- Com `QT_QPA_PLATFORM=windows`: `python -m tests.avatar_native_stress`

O teste nativo não abre contas nem usa modelos de voz. Ele exercita janelas,
cliques, digitação, expressões, animações, recolhimento e restauração.
Os testes de documentos geram e reabrem PDF, DOCX e XLSX, verificam acentos,
valores numéricos, conteúdo literal em células, nomes únicos e limpeza em falhas.
