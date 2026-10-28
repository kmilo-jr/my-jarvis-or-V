# Assistente pessoal do V — entrega de 29/09/2026

Direção definida pelo usuário: melhorar assistente pessoal, controle do PC, automação, proatividade e personalidade. Agenda, alarmes e lembretes têm como destino principal o próprio PC, com o V aberto. Decisões rotineiras de implementação podem seguir sem nova confirmação.

## Comandos disponíveis

| Área | Exemplos |
| --- | --- |
| Listas | `crie a lista compras`; `adicione café à lista compras`; `mostre a lista compras`; `conclua café na lista compras`; `remova pão da lista compras`; `minhas listas` |
| Lembretes | `me lembre de revisar o projeto em 10 minutos`; `me lembre de pagar a conta amanhã às 15h` |
| Alarmes | `crie um alarme em 5 minutos`; `crie um alarme amanhã às 8h` |
| Compromissos | `agende reunião amanhã às 15h`; `agende um compromisso dentista 02/10/2026 às 9h30` |
| Agenda | `agenda de hoje`; `agenda de amanhã`; `minha agenda`; `o que tenho hoje?`; `meus alarmes`; `meus lembretes` |
| Cancelamento | `cancele o lembrete CODIGO`; `cancele o alarme CODIGO`; `cancele o compromisso CODIGO`. A agenda mostra o código; também aceita um título completo quando único. |
| PC | `mostre os monitores`; `mova a janela para o monitor 2`; `alterne a janela`; `feche a janela`; os comandos de abrir programas, minimizar, maximizar, mídia e volume continuam disponíveis. |
| Sequências | `abra o navegador e ajuste o volume para 25 e depois mostre os monitores` |

Use `V, ...` quando necessário na voz contínua. Os mesmos pedidos funcionam por texto. Se faltar o horário de um lembrete, o V pede essa informação; a próxima resposta pode ser `amanhã às 15h`. Após `agenda de hoje`, aceita `e amanhã?`.

Correção de interpretação: também aceita `avise quando for 14:30`, `me avise quando der 14:30`, `hoje daqui 30 minutos`, `daqui meia hora` e horas por extenso como `às duas e meia da tarde`. Um pedido apenas para avisar o horário recebe o assunto “Aviso de horário”. A resposta curta `30 minutos` completa o lembrete anterior. Quando um horário inválido é corrigido, o horário novo substitui o fragmento anterior, preservando o assunto. Dias da semana e recorrência continuam fora desta etapa.

Listas e avisos são salvos localmente em `data/lists.json` e `data/initiative.json`. As consultas e confirmações locais vêm do executor e não dependem da disponibilidade de IA. O iPhone só é escolhido quando o pedido menciona explicitamente iPhone, celular ou V Mobile.

## Como os avisos funcionam

- Alarmes mostram aviso e solicitam um sinal sonoro único do Windows. Eles podem avisar durante outra atividade e no horário de silêncio. Pausar a iniciativa, desabilitar avisos ou desmarcar Alarmes suspende a entrega. Não são despertadores com toque contínuo.
- Lembretes seguem o silêncio, a pausa, o intervalo mínimo e a espera pelo fim de comandos/fala.
- Compromissos tentam avisar 10 minutos antes, respeitando os mesmos limites dos lembretes. Continuam na agenda após o aviso antecipado. Isso não marca o compromisso como realizado.
- O V verifica os avisos a cada 5 segundos. Com o PC suspenso ou o V fechado, não há execução; avisos pendentes são avaliados quando o V volta. Não há integração com o agendador do Windows nem despertar do PC.
- Horários usam o fuso local do Windows. Aceita hoje, amanhã, depois de amanhã, data numérica e intervalos em segundos/minutos/horas. Um horário sem data que já passou fica para o dia seguinte, informado na confirmação. Não interpreta dias da semana nem cria recorrências nesta entrega: pede uma data explícita.
- A tela **Iniciativa** permite ajustar categorias, silêncio e pausa; a aba **Lembretes e histórico** inclui atalhos para consultar agenda e listas. A voz dos avisos continua desligada por padrão e depende de “Respostas em voz alta”.

## Proatividade do computador

Leituras a cada 15 segundos: CPU a partir de 95% e RAM a partir de 90%, sustentadas por dois minutos; disco do Windows com até 5% livre por 30 segundos; bateria em até 15%, fora da tomada, por 15 segundos. Não usa GPU ou sensores de temperatura nesta entrega.

Picos rápidos não geram avisos de CPU/RAM. Cada condição tem intervalo de 30 minutos entre novos registros; pendências não são duplicadas e são canceladas quando a condição se recupera. Alertas respeitam os limites da iniciativa. Não fecha programas nem altera configurações por conta própria.

## Execução e personalidade

Sequências têm até oito ferramentas. Pedidos determinísticos maiores ou com uma etapa não reconhecida recebem uma explicação antes de executar. O executor verifica as permissões de todas as ferramentas e interrompe a sequência quando uma etapa falha, identificando as etapas não executadas. As ações anteriores não são desfeitas automaticamente.

O controle de monitores usa o principal como número 1 e informa os números na consulta. “Janela ativa” significa a que estiver em primeiro plano no momento da execução, podendo ser o próprio V ao digitar nele. O teste automatizado simula a movimentação; valide por voz com a janela desejada em foco no uso real.

As instruções de personalidade mantêm português brasileiro, identidade própria do V, humor ocasional e ausência de piadas em alarmes/erros. Reforçam confirmações baseadas no resultado real, perguntas curtas para dados ausentes e relato de execução parcial. A voz ElevenLabs e o efeito configurado permanecem os mesmos. A qualidade da conversa livre ainda depende do provedor de IA.

## Validação e próximos incrementos

Resultado final: **152 testes automatizados passaram**, além do `self_test.py`. O self-test passou a aceitar a prosódia dinâmica desligada, preservando a preferência atual do usuário e verificando o ritmo correspondente.

Testes automatizados verificam persistência, datas inválidas, agenda, cancelamento, alarmes em silêncio, aviso antecipado, continuidade do horário, roteamento local/mobile, limites de sequências, parada após falha, alertas sustentados e geometria simulada de monitores. A tela de categorias foi renderizada e inspecionada.

Os testes antigos de recuperação Gemini→Ollama agora desabilitam Groq explicitamente para não acessar uma conta real durante a simulação. Validação física do som de alarme, fala/reconhecimento simultâneos e movimentação entre monitores continua sendo um teste de uso; não foi executada automaticamente nesta entrega.

Próximos incrementos possíveis: recorrência de agenda, edição por conversa, horários por extenso/dias da semana, rotinas nomeadas além do modo trabalho, monitoramento de GPU/temperatura e ajustes de personalidade com avaliação de conversas reais.
