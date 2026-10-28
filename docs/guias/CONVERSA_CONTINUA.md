# Conversa contínua e avisos de andamento

Reabra o V e ative a voz contínua. A opção **Conversa contínua** na barra superior começa marcada e pode ser desligada para a sessão. As interfaces Orbital e Rosto futurista usam o mesmo comportamento.

1. Faça o primeiro pedido com “V”.
2. Depois da resposta e da proteção contra eco, aparece **Pode continuar · 8s**.
3. Comece a próxima frase nesse prazo, sem repetir “V”. A duração da transcrição não desconta esse prazo: vale o início da fala detectada.
4. Após cada resposta a um pedido por voz, abre-se uma nova janela. Fora dela, volta a exigir “V”.

Dizer apenas “V” abre uma janela para o pedido. “Encerrar conversa”, “fim da conversa” ou “pode descansar” fecham a janela quando ela está aberta (ou quando precedidos por “V”). Esc, desligar o microfone ou desmarcar a opção também cancelam a continuação. Encerrar a conversa não apaga o histórico.

O histórico existente continua chegando à IA. As instruções agora reforçam a interpretação de perguntas curtas e pedem esclarecimento quando referências como “esse” são ambíguas. Isso não garante que o modelo interprete toda referência corretamente. A janela não identifica o locutor: outra fala próxima pode ser aceita enquanto ela estiver aberta.

Ações reconhecidas de aplicativos, música, vídeos, notícias, pesquisa, mercado e consulta do computador podem receber um aviso curto se ainda estiverem em execução após 650 ms. No máximo um aviso por pedido. Comandos já concluídos, respostas silenciadas e avisos atrasados de comandos anteriores não geram fala extra. O resultado real da ferramenta continua sendo exibido e falado; o aviso não afirma sucesso antecipadamente.

Configuração: `voice.followup_enabled` e `voice.followup_seconds` em `config/default.json`; a duração é limitada a 1–30 segundos. A opção da barra vale para a sessão e acompanha a alternância entre interfaces.

Validação: 30 testes automatizados passaram, incluindo prazo, início da frase antes da expiração, espera pela saída de voz, cancelamento, avisos únicos e ausência de avisos após conclusão. As duas interfaces foram renderizadas em 1180×720 e os controles ficaram visíveis. Áudio, reconhecimento do usuário e continuidade de contexto com o serviço de IA real ainda precisam de validação de uso.
