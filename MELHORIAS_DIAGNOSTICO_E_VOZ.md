# Diagnóstico e interrupção da fala

Disponíveis nos inicializadores existentes, inclusive nas interfaces Orbital e face do V.

- **F8 / Diagnóstico:** verifica microfone, carregamento do Whisper, configuração de saída de voz, disponibilidade da IA, conexão recente da extensão do Spotify e estado do Remote no inicializador Dual. As consultas de rede rodam em segundo plano. O painel oferece atualização e reconexão do microfone.
- **Esc / Interromper fala:** para a reprodução, descarta as falas pendentes e impede que os próximos trechos da resposta atual retomem o áudio. Não cancela ações do computador já em execução.
- **Interromper por voz (use fones):** marque a opção e ative a voz contínua. Diga “V, para”, “V, pare de falar” ou “V” seguido de um novo pedido. O novo pedido segue a fila normal de ações. A opção vale para a sessão e começa desativada, salvo configuração explícita de `voice.barge_in_enabled`.

Com caixas de som, mantenha a interrupção por voz desativada: esta implementação não possui cancelamento acústico de eco. O reconhecimento espera a frase terminar e passar pelo Whisper; não é uma interrupção instantânea ao primeiro som. Esc funciona independentemente do reconhecimento.

Teste manual sugerido: solicite uma resposta longa, interrompa com Esc e confirme que a fala não recomeça. Depois, usando fones e voz contínua, repita com “V, para” e com outro pedido. Verifique no F8 as conexões reais.

Validação de desenvolvimento: 11 testes automatizados aprovados (incluindo cancelamento, descarte da fila, limpeza de áudio temporário e controle de escuta), abertura das três interfaces com dependências simuladas e inspeção visual do diagnóstico. Microfone físico, reprodução audível e serviços reais ainda precisam de validação no uso.
