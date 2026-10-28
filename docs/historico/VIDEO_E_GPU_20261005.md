# Vídeo engasgando durante o uso do V — 05/10/2026

A hipótese é disputa de GPU entre a voz Qwen e a reprodução do vídeo, ainda sem medição durante um engasgo. A leitura pontual encontrou 15% de GPU e 441 MiB de 4096 MiB utilizados no computador inteiro, fora do incidente. Não comprova nem descarta o problema.

O processo separado que gera a voz passa a solicitar prioridade de GPU abaixo da normal pelo agendador do Windows. O código lê de volta a prioridade e só registra sucesso quando confirma a classe solicitada. Um processo de teste neste PC confirmou `applied: true`, classe 1, retorno zero. Isso não é uma medição de melhora no vídeo nem um limite de porcentagem/VRAM.

Também foi reduzida a prioridade de CPU apenas desse processo. A interface e a reprodução de áudio continuam com suas prioridades anteriores. Modelo, referência, resolução do áudio e parâmetros de geração permanecem iguais. Sob disputa, a geração pode levar mais tempo.

As opções `tts_qwen_gpu_background_priority` e `tts_qwen_background_priority`, na seção `voice`, ficam ativadas por padrão quando ausentes. Definir uma delas como `false` desativa o respectivo ajuste na próxima inicialização do processo. Nenhuma configuração global de driver ou prioridade de outros aplicativos foi alterada.

Reabra o V para aplicar. O resultado da solicitação será registrado em `logs/qwen_worker.log` e nas métricas `gpu_priority` do próximo diagnóstico real de voz. Se o Windows recusar a prioridade, a voz continua funcionando e o diagnóstico registra a recusa.

Validação: 12 testes do backend Qwen e três testes do controle de prioridade passaram; a API do Windows foi exercitada em um processo de teste, sem carregar o modelo. Ainda falta comparar reprodução de vídeo e voz juntas, observando quadros perdidos, geração e lacunas de áudio.

Referência: [Microsoft — D3DKMTSetProcessSchedulingPriorityClass](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/d3dkmthk/nf-d3dkmthk-d3dkmtsetprocessschedulingpriorityclass).
