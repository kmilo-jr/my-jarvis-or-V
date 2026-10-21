# Proteção de recursos — 03/10/2026

A configuração atual prioriza estabilidade na GTX 1650 de 4 GB:

- Whisper small mantido, agora em CPU/int8 com dois threads. Libera a GPU para a síntese; a transcrição pode demorar mais.
- Qwen mantém modelo, referência e parâmetros da voz aprovada. Threads de CPU reduzidos de oito para dois; bibliotecas auxiliares recebem o mesmo limite.
- O processo Qwen é encerrado após 120 segundos sem geração, liberando RAM/VRAM. É recriado automaticamente na próxima fala. Esse retorno pode adicionar alguns segundos ao início. Geração ativa é protegida por lock; o temporizador não a interrompe.
- Pedidos do V ao Ollama local usam `num_gpu=0`, dois threads e `keep_alive=0`. O fallback pode ficar mais lento; ao terminar, seu modelo não é mantido carregado pelo pedido do V. Isso não altera o uso do Ollama por outros programas.

É necessário reiniciar o V para aplicar as opções aos modelos já carregados. Não foram encerrados processos de outros aplicativos nem alterados clocks ou drivers.

## Medições e limites

Leitura inicial do computador: 1940 MiB de VRAM e 37% de utilização. Esses números incluem outros aplicativos.

Teste controlado do Qwen: 567 MiB antes, 2126 MiB carregado, 565 MiB após liberar o processo ocioso. Para testar sem esperar dois minutos, foi usado timeout de três segundos somente na instância de teste. A configuração do V continua em 120 segundos. Evidência: `logs/gpu_20261003/idle_release_measurement.json`.

O limite de threads não é um teto percentual de CPU ou GPU. Ainda pode haver picos durante a fala, e uma leitura de 100% não identifica sozinha a origem de um travamento. Não há garantia de eliminar travamentos de driver, jogos ou outros processos. O teste de voz com dois threads e recarga após ociosidade está em `logs/gpu_20261003/cpu_limited_test.json`.

As configurações anteriores de reconhecimento/Ollama foram registradas em `logs/gpu_20261003/previous_resource_settings.json`. Para voltar ao comportamento anterior do Qwen: `tts_qwen_cpu_threads: 8` e `tts_qwen_idle_seconds: 0` desativam a economia nova. Isso volta a permitir ocupação prolongada de recursos.
