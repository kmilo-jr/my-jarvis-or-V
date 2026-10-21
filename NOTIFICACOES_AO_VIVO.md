# Avisos de Gmail, mensagens e agenda — 04/10/2026

Reinicie o V e abra **Iniciativa**. As opções **Novos e-mails do Gmail** e **Novas notificações de WhatsApp/Instagram** controlam as duas novas categorias. Lembretes e compromissos mantêm o funcionamento existente. Para leitura em voz alta, ative **Também falar os avisos** e **Respostas em voz alta**. O padrão de voz continua desativado.

## Funcionamento

- Gmail: consulta IMAP a cada 30 segundos após a consulta anterior terminar. Apenas caixa de entrada, sem alterar leitura. O monitor acompanha novos UIDs, mesmo que a mensagem já tenha sido lida em outro dispositivo. Consulta somente cabeçalhos de remetente/assunto do e-mail mais recente do lote. Vários e-mails geram um aviso agrupado.
- Mensagens: verifica a cada aproximadamente 5 segundos as notificações já capturadas pelo V. A captura Windows existente continua no inicializador Dual, restrita a WhatsApp/Instagram. Não equivale a entrar nas contas nem acessar mensagens que o Windows não notificou. O aviso novo contém aplicativo e título, não o corpo.
- Agenda: mantém lembretes e alertas de compromissos existentes; não cria calendário externo.

São consultas periódicas, não push instantâneo. A entrega pode esperar o V ficar livre, o horário de silêncio terminar e o intervalo mínimo de avisos, por padrão 120 segundos. Alarmes mantêm suas exceções existentes. Funciona enquanto o V está aberto; não foi instalado serviço do Windows.

## Controles e persistência

Pausar por uma hora ou desativar os avisos suspende novas consultas. Resultados de consultas que terminem depois da pausa/desativação não são gravados. Falhas recuam progressivamente até cinco minutos, sem repetir alertas de erro na conversa; o estado aparece em **Iniciativa → Lembretes e histórico → Atualizar**, com orientação para **Conexões**.

Na primeira consulta, os itens existentes viram a referência e não são anunciados. Os cursores ficam em `data/initiative.json`, junto da criação do aviso numa única gravação, evitando duplicação normal após reiniciar. Troca da conta Gmail ou da identidade da caixa inicia uma nova referência. A entrega usa o histórico e a fila de Iniciativa; o antigo aviso direto da interface Dual foi removido para evitar duplicação e desrespeito ao silêncio.

Há no máximo um aviso visual pendente por categoria nova. Chegadas durante silêncio são agrupadas e mostram a atualização mais recente. O buffer existente de mensagens mantém até 100 notificações; não é um histórico integral dos aplicativos. Nenhuma credencial nem corpo de e-mail é salvo no cursor.

## Validação

Testes cobrem cursores após reinício, pausa durante consulta, agrupamento de rajadas, silêncio, falhas com recuo, fechamento, prevenção de consultas simultâneas da mesma origem, seleção de novos UIDs e leitura apenas de cabeçalhos. A consulta real de referência Gmail funcionou, sem anunciar mensagens antigas ou alterar o estado persistente: `logs/notificacoes_20261004/gmail_baseline_check.json`.

Ainda é necessária a verificação de ponta a ponta recebendo um e-mail e uma notificação nova com o V aberto. Nenhuma mensagem foi enviada como parte dos testes.
