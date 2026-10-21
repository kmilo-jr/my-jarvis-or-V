# V — referência de evolução

Referência: conversa fornecida pelo usuário em 28/09/2026. Esta lista registra a visão desejada; não significa que todas as integrações estejam implementadas.

Atualização de 29/09/2026: o núcleo flutuante já está implementado. As melhorias de assistente pessoal, comandos do PC, sequências, proatividade e personalidade estão descritas em `EVOLUCAO_ASSISTENTE_PESSOAL.md`, com comandos, limites e validação. Agenda e avisos usam o PC por padrão, conforme escolha do usuário.

## Visão completa

- Assistente pessoal: conversa natural, listas, agenda, alarmes e lembretes.
- Controle do computador: programas, áudio, janelas, monitores e comandos.
- Multimídia: Spotify, YouTube, playlists e dispositivos de áudio.
- Pesquisa: notícias, clima, mercado, preços e resumos.
- Monitoramento: CPU, GPU, RAM, temperaturas, discos, rede e processos.
- Visão: interpretar câmera, objetos, textos e capturas de tela.
- Automação: coordenar várias ferramentas com um pedido.
- Casa inteligente: integrar dispositivos compatíveis.
- Controle remoto: celular, acesso externo e Wake-on-LAN.
- Comunicação: notificações e integrações de mensagens com autorização.
- IA: contexto de conversa, planejamento e escolha de ferramentas.
- Memória: preferências, equipamentos, projetos e rotinas.
- Segurança: autenticação, criptografia, permissões, confirmações e registros.
- Proatividade: alertas úteis, compromissos e condições do computador.
- Personalidade: voz e comportamento consistentes, humor e estilo próprio.

## Base encontrada

Há módulos de voz, memória, pesquisa, mídia, rotinas, iniciativa, controle remoto e Wake-on-LAN. A presença dos módulos não comprova funcionamento de cada integração no ambiente atual. O launcher dual alterna entre duas janelas, compartilhando os serviços; não mantém duas interfaces visíveis simultaneamente.

## Primeira entrega: Modo Jogo manual

- Nas interfaces: **Modo Jogo [F9]** e **Recolher V** na barra superior.
- Comandos de texto/voz: `V, modo jogo`, `V, vou jogar`, `V, sair do modo jogo`, `V, modo normal`, `V, recolher V` e `V, abrir interface`. Voz depende de o microfone já estar ativo.
- Ao ativar, move a interface atual para outro monitor disponível. Com um monitor, recolhe para a bandeja; se a bandeja não estiver disponível, minimiza na barra de tarefas.
- A bandeja permite abrir, alternar Modo Jogo, recolher e encerrar. Fechar a janela continua encerrando a sessão.
- Modo Jogo limita o timer da animação a no máximo 10 FPS e atualiza o painel de sistema a cada 2 segundos. Oculta ou minimizada, a janela para o timer da animação.
- A voz, os comandos, as rotinas e os alertas conservam seus controles existentes. Não fecha programas nem inicia playlists automaticamente.
- Sair do Modo Jogo restaura a geometria anterior. F6 conserva o estado de Modo Jogo ao trocar o visual.
- O modo vale para a sessão atual; não altera credenciais nem configurações persistentes.

## Próximas etapas

1. Validar no PC real com dois monitores, jogo e voz simultâneos; medir CPU/GPU antes e depois.
2. Redesenhar a primeira interface como painel funcional, com estados normal e compacto; conservar a segunda como presença visual.
3. Adicionar opção de núcleo flutuante (32–48 px), reações ao estado e Modo Fantasma; preferências de ícone, bandeja ou invisível.
4. Detecção opcional de jogo/tela cheia, seleção de monitor e retorno automático ao terminar.
5. Rotina configurável “vou jogar”: programas, música, monitoramento e segunda tela, coordenados pela IA. Definir explicitamente quais processos podem ser fechados.
6. Auditar as demais áreas da visão, priorizando integrações incompletas e memória/contexto entre ações.

Ainda não há garantia de redução do consumo total: reconhecimento de voz, TTS e outros serviços continuam consumindo recursos conforme sua configuração.
