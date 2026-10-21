# Voz e interação com tarefas

Reabra o V e acesse **Voz e tarefas** na barra superior (ou no menu de excesso da barra, em janelas estreitas).

## Redução da espera e das pausas

- O primeiro trecho usa um alvo de 100 caracteres; os seguintes podem agrupar frases até 240, preservando palavras e conteúdo. Textos longos são preparados enquanto os trechos anteriores tocam, usando a fila de síntese existente.
- Avisos de andamento por voz começam desativados nesta versão: o progresso visual continua, mas o aviso não ocupa a fila antes da resposta útil. Você pode reativá-los na aba Voz.
- O caminho ElevenLabs conserva em memória até 16 áudios de textos curtos, limitados a 512 KB cada. Repetições idênticas evitam uma nova síntese. A chave inclui voz, modelo, formato e parâmetros vocais; alterar o ritmo invalida o reaproveitamento correspondente. Arquivos temporários de reprodução continuam independentes e são removidos normalmente. Nada é pré-sintetizado por conta própria.
- SAPI, a voz de reserva do Windows, só é inicializada quando necessária.
- Marcas de títulos, numeração e endereços de links Markdown não são lidos literalmente; o texto do link é preservado.

Não foi medido ganho de latência com a rede real. Uma primeira resposta nova ainda depende da IA e do serviço de síntese. O reaproveitamento de áudio beneficia repetições, não a primeira fala. O ritmo de reprodução não reduz o tempo que a IA leva para responder.

## Interação

- O painel mostra o pedido atual, a etapa informada pelo executor, o tempo decorrido e a fila. Não inventa percentual nem previsão de término.
- É possível remover um pedido pendente ou limpar a fila; ações já iniciadas continuam. Interromper fala cancela áudio, não ações do computador.
- Ações simples preservam a mensagem real do executor, em vez de substituí-la por “Claro” ou “Feito”.
- Repetir última resposta reproduz a resposta armazenada sem executar novamente o comando. Aguarda a tarefa atual terminar e respeita Respostas em voz alta.
- Comandos locais: “V, status da tarefa”, “V, como está meu pedido”, “V, repita a última resposta” e “V, limpar fila”.

Na aba Voz, escolha um ritmo entre 90% e 115%, ative ou desative o ritmo expressivo e os avisos de andamento. Salvar e ouvir reproduz uma amostra explícita com a voz atual; pode usar o serviço de voz configurado. As preferências são salvas em `config/default.json` sem substituir a identidade da voz ou outras configurações.

Validação: 61 testes passaram, incluindo cancelamento, nova segmentação, cache com provedor simulado, mudança de parâmetros, preservação dos resultados e remoção de pedidos da fila. O painel foi renderizado nas duas interfaces. Reprodução audível e latência de ponta a ponta ainda precisam ser avaliadas no uso.
