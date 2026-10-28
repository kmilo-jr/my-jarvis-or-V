# Iniciativa com limites

**Atualização de 29/09/2026:** agora também há comandos locais de agenda, listas, alarmes e lembretes; compromissos com aviso antecipado e alertas do PC. Alarmes têm tratamento próprio de silêncio e ocupação. Consulte `EVOLUCAO_ASSISTENTE_PESSOAL.md` para o comportamento atual; abaixo está a descrição da entrega inicial.

**Correção da entrega por voz:** notificação visual e fala possuem estados separados. Com voz habilitada, um alarme que aparece durante outra atividade mantém sua fala pendente. O histórico só mostra “Falado” depois do sucesso retornado pelo motor de áudio; em falhas há até três tentativas com intervalo de um minuto. A pendência sobrevive a reinícios. Interromper a fala cancela essa tentativa sem repetição automática. Pausa, categorias desativadas e “Resposta por voz” desligada continuam sendo respeitadas. O histórico mostra falhas de voz e seu diagnóstico. Notificações antigas, sem rastreamento da reprodução, não são repetidas automaticamente.

Acesse **Iniciativa** na barra superior das duas interfaces.

## Avisos disponíveis

- **Lembretes locais:** cadastre texto, data e horário na aba Lembretes e histórico. Ela permite cancelar e adiar um aviso em 10 minutos. Esses lembretes são independentes dos comandos existentes para o iPhone.
- **Conclusões:** pedidos que durarem pelo menos 10 segundos e terminarem enquanto a janela do V estiver sem foco geram um aviso factual. Falhas aparecem como pendências. O resultado detalhado continua na conversa; a conclusão não ganha uma segunda fala.
- **Pausas:** executar o modo trabalho com sucesso inicia as sugestões, inicialmente a cada 50 minutos. Não há acúmulo de várias pausas atrasadas. O próximo intervalo começa quando o aviso é entregue. Use Encerrar sugestões de pausa para parar; programas permanecem abertos. A sessão fica salva entre reinícios até ser encerrada.
- **Resumo ao iniciar:** mostra as quantidades de lembretes locais vencidos e previstos para mais tarde no dia, e informa se há sugestões de pausa ativas. É um retrato no momento da abertura, sem consultar calendário, e-mail ou notícias. Alternar com F6 não cria outro resumo.

## Limites iniciais

- Avisos habilitados; voz desabilitada. Habilitar voz também exige Respostas em voz alta.
- Silêncio das 22h às 8h, conforme o horário local do Windows. Início e fim iguais significam silêncio o dia todo.
- Intervalo mínimo de 120 segundos entre avisos.
- O V adia avisos durante comandos, fala/áudio pendente, calibração/transcrição, testes de microfone, a janela de continuação da conversa e a edição de uma mensagem no campo do V. Não detecta reuniões ou jogos em outros programas.
- Pausar por 1 hora suspende a entrega; Retomar remove essa pausa, preservando os outros limites. Desmarcar uma categoria mantém os avisos pendentes.

O aviso aparece na conversa e na barra de status. Fora da janela do V, também solicita uma notificação pela bandeja do Windows, quando disponível. A exibição depende das configurações de notificações do sistema. Clicar na notificação abre o V. O histórico está disponível na tela Iniciativa; use Atualizar para recarregá-lo.

O V precisa estar aberto. Com o PC suspenso ou o V fechado, não há entrega; lembretes vencidos continuam pendentes e são processados após reabrir, respeitando os limites. As configurações e os eventos ficam em `data/initiative.json`. Arquivos inválidos não são substituídos silenciosamente. O histórico conserva até 100 avisos encerrados e todos os pendentes.

Esses limites controlam os novos avisos de iniciativa. As respostas solicitadas, a saudação existente e as notificações do iPhone mantêm seus controles anteriores. O sistema não inicia rotinas, envia mensagens ou executa comandos por conta própria.

Validação: testes com relógio controlado, arquivos temporários, comandos e áudio simulados; inspeção da tela em ambas as interfaces. A entrega real pela bandeja do Windows e a reprodução de voz precisam de validação no uso.
