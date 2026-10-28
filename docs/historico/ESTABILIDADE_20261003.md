# Estabilidade do V — 03/10/2026

Esta rodada cobre regressões automatizadas e endurecimento de falhas conhecidas. Não representa certificação de ausência de travamentos no computador inteiro.

## Alterações

- Qwen prepara dois trechos antes de abrir a reprodução. A fila continua limitada a oito blocos. Respostas de um trecho continuam funcionando. Há mais espera inicial em respostas maiores; isso dá folga à geração, mas não garante eliminar todas as pausas se a geração continuar mais lenta que a fala. O ajuste é `voice.tts_qwen_prebuffer_phrases=2`.
- Mantida a margem maior do dispositivo de áudio, sem mudar os samples, modelo ou referência de voz. A fila simulada de cinquenta blocos preservou ordem e conteúdo das amostras e encerrou o dispositivo.
- Pedidos ao motor fechado saem com erro em vez de aguardar uma trava ocupada. Configurações inválidas do tempo ocioso retornam ao padrão seguro. Geração ativa continua protegida do descarregamento por inatividade.
- Memória ilegível fica protegida contra gravação. Uma nova lembrança não pode substituir silenciosamente um arquivo corrompido por uma base vazia. O arquivo original permanece para recuperação.
- Diagnóstico F8 mostra falhas de alimentação do dispositivo e tempo acumulado sem áudio na última fala.
- Atualizado um teste antigo do streaming da IA para a assinatura atual da recuperação de memória.

## Validação

Comando: `.venv\Scripts\python.exe -m unittest discover -s tests`.

A primeira execução encontrou uma incompatibilidade no dublê de memória do teste de streaming. Corrigido o dublê, a suíte completa passou. Foram acrescentados testes para cinquenta blocos de reprodução, memória corrompida, encerramento com trava ocupada, tempo ocioso inválido e reserva configurável do Qwen.

Os testes de reprodução usam um dispositivo simulado; não confirmam a qualidade audível nem a estabilidade dos drivers. Os limites de CPU e a liberação real de VRAM foram medidos na rodada anterior, documentada em `GPU_E_CPU_ECONOMIA.md`. Não foi feito um novo teste prolongado com jogo, câmera e voz simultâneos nesta rodada.

Reinicie o V para aplicar. Se o ruído semelhante a risada continuar, uma gravação curta e os indicadores de F8 ajudarão a separar defeito no áudio gerado, efeito robótico e falha do dispositivo. A causa desse som específico ainda não foi confirmada.
