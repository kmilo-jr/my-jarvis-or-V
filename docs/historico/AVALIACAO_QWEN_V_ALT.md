# Avaliação local da V Alt com Qwen

Avaliação iniciada em 24/09/2026 e integrada em 25/09/2026 após aprovação auditiva do usuário. O padrão agora é `qwen_local`, usando a nova amostra V Alt. XTTS está desativado no perfil padrão.

## Implementação

- Modelo: Qwen3-TTS 0.6B Base, GGUF Q8_0, com português (`language_id=2071`).
- Runtime: Qwen-TTS Studio v0.2.9, biblioteca nativa distribuída pelo projeto, sem instalar o aplicativo.
- ABI conferida no commit `16bb5afcd06311031c72a8488f8d59660dc2fb46` do submódulo qwen3-tts.cpp.
- GPU detectada: GTX 1650, 4 GB; backend CUDA0.
- Referência: `assets/voice/v_alt_reference_short.wav`, processada localmente para gerar `vendor/qwen-eval/v_alt_embedding.json`. A amostra não foi enviada a um serviço.
- Arquivos de avaliação e runtime em `vendor/qwen-eval`; nenhuma dependência do ambiente Python existente foi substituída.

## Resultado

Frase: “Estou pronto para ouvir seu pedido e ajudar no que precisar.”

| Medida | Resultado |
| --- | --- |
| Carregamento dos modelos | 2,382 s |
| Primeira geração completa | 4,236 s para 3,920 s de áudio |
| Segunda geração, modelos em memória | 3,575 s para 3,920 s de áudio |
| XTTS FP32 repetido, mesma frase em teste anterior | 5,814 s para 4,171 s de áudio |

Os dois arquivos Qwen contêm valores finitos e sinal não silencioso. O tempo de geração completa não é a latência acústica nem o tempo de primeira fala em streaming. Os testes não foram simultâneos; são indícios locais, não um benchmark controlado entre modelos. A aprovação do timbre depende de ouvir os arquivos. Não assumir que velocidade comprova semelhança da voz.

Relatório: `logs/qwen_alt_benchmark.json`. Áudios: `logs/qwen_alt_1.wav` e `logs/qwen_alt_2.wav`. Reexecução: `.venv/Scripts/python.exe vendor/qwen-eval/benchmark.py`.

## Fontes

- Modelo original e suporte a idiomas/clonagem: https://github.com/QwenLM/Qwen3-TTS
- Runtime: https://github.com/Danmoreng/qwen3-tts.cpp
- Pacote Windows: https://github.com/Danmoreng/qwen-tts-studio/releases/tag/v0.2.9
- Pesos GGUF: https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF

## Integração validada em 25/09/2026

O processo nativo fica residente e prepara a próxima frase durante a reprodução da atual. A identidade da amostra fica em cache local, invalidado por caminho, tamanho e data de modificação; arquivos inválidos são reconstruídos. Cancelar uma geração encerra o processo nativo, que é recriado na próxima fala. Falhas são exibidas sem trocar silenciosamente por outro timbre.

Teste real pelo VoiceEngine e reprodução Windows: duas frases reproduzidas consecutivamente, sem erro; cancelamento em 0,101 s e retomada com sucesso; XTTS não carregado. Relatório: `logs/qwen_integrated_check.json`. Nesse teste inicial a preparação levou 36,108 s e a primeira reprodução começou após 7,018 s. Não é garantia de latência constante.

Após reaproveitar a identidade salva: preparação 2,634 s, gerações completas da frase de referência em 4,594 s e 4,720 s. Relatório: `logs/qwen_cached_check.json`. A preparação inicial com arquivos fora do cache do sistema pode ser mais lenta. Ainda existe espera perceptível e respostas maiores podem precisar aguardar a próxima frase; não foi comprovada ausência de pausas em uso prolongado ou reconhecimento simultâneo.

Validação automatizada: 95 testes passaram. Seletor distingue Qwen dos motores XTTS antigos e mantém a escolha ao salvar. Controles de ritmo/entonação ficam desabilitados para Qwen, que usa a voz natural aprovada. Reinicie o V para carregar a configuração atual.


## Ajuste de continuidade — 25/09/2026

A saída agora fica aberta durante toda a resposta (SoundDevice), eliminando a abertura/fechamento MCI entre frases. A síntese continua sobreposta à reprodução. A preparação inicial também executa uma geração curta e silenciosa para inicializar os recursos usados na primeira fala, uma vez por identidade de amostra no processo.

Validação real: duas respostas com primeira saída prevista pelo dispositivo em 5,200 s e 2,959 s; nenhuma falha de alimentação do dispositivo. Ainda houve falta de áudio gerado no buffer por 0,440 s e 2,940 s, respectivamente. Essas pausas vêm da geração mais lenta que a reprodução e não foram eliminadas. Relatório: `logs/qwen_continuous_warm_check.json`. Cancelamento e retomada aprovados: `logs/qwen_continuous_cancel_check.json`. 96 testes automatizados passaram, além do self-test.

Streaming nativo de 1 e 2 segundos foi avaliado e rejeitado para o padrão: a produção ficava atrás da duração dos blocos, aumentando o risco de cortes (`logs/qwen_stream_bench.json`). Também não se alterou a quantidade de threads: testes com 2, 4 e 8 produziram durações de fala diferentes e não demonstraram ganho consistente proporcional à duração (`logs/qwen_threads_check.json`). A voz, a referência e o ritmo aprovados foram preservados. Os testes não são uma comparação controlada de latência com o código anterior.


## Pronúncia aprovada e cache — 25/09/2026

O usuário confirmou que a segunda gravação (`logs/qwen_accent_icl.wav`) melhorou o sotaque mantendo a voz. O padrão passou a usar o prompt ICL completo em `assets/voice/v_alt_qwen_prompt.json`, configurado em `voice.tts_qwen_prompt`. Ele inclui os primeiros 7,24 segundos da mesma V Alt, os códigos acústicos e a transcrição correspondente. O idioma continua português (2071), com o mesmo modelo 0.6B Q8_0. Não há envio da amostra a serviços externos.

A origem é conferida pelo SHA-256 do arquivo de referência original. Se a amostra mudar, a geração falha com mensagem explícita em vez de reutilizar outra identidade. O arquivo do prompt guarda o intervalo extraído e o commit do runtime. A codificação da referência está pronta no arquivo; não é repetida a cada fala.

Adicionado cache LRU de áudio em memória, limitado a 8 MiB e separado por texto, referência e prompt. Repetições idênticas no mesmo processo não repetem a inferência; encerrar/interromper o processo limpa o cache. Isso não acelera a geração de textos inéditos.

Testes: a frase "Estou pronto para ajudar com o próximo pedido." começou em 3,898 s; a repetição começou em 0,164 s. Sem lacunas de buffer nessa frase. Cancelamento seguido de retomada funcionou, com a mesma referência ICL; a fala nova após reiniciar o processo começou em 5,334 s. Relatório `logs/qwen_icl_playback_check.json`. No teste direto, repetir uma resposta de duas frases levou 11 ms para recuperar o WAV, contra 6,286 s para gerá-lo (`logs/qwen_icl_integrated_cache.json`); recuperação de arquivo não é latência acústica.

Comparações auxiliares: Q4_K_M levou 7,25–7,79 s, Q8_0 levou 5,89–6,04 s para o texto de comparação, com diferentes durações de áudio. Q4 não foi ativado. Reduzir temperatura também não demonstrou ganho, e o padrão de amostragem aprovado foi mantido. A transcrição automática preservou o texto nas três variantes; a avaliação de sotaque foi feita pelo usuário. Relatórios `logs/qwen_quant_check.json`, `logs/qwen_accent_check.json` e `logs/qwen_accent_transcripts.json`.

98 testes automatizados e self-test passaram. Ainda há atraso perceptível na geração inédita, especialmente depois de cancelamentos que exigem recarregar o processo. Não se afirma resolução total do desempenho.


## Leitura de notícias — diagnóstico e correções

O usuário esclareceu que o sotaque aparece na maioria das notícias, mesmo após aprovar uma amostra curta de ICL. Portanto, a aprovação anterior não comprova resolução de sotaque em manchetes. O idioma 2071 foi novamente conferido no config oficial: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base/raw/main/config.json. A ABI também repassa esse campo corretamente. Não foi identificada uma troca de idioma na configuração.

A narração recebia porcentagens, ordinais, siglas e nomes de domínio do RSS. `voice/news_speech.py` passa esses formatos para leitura em português, preservando os valores; o texto exibido permanece original. A apresentação começa direto pela manchete e deixa posição/fonte na tela, evitando gerar locuções separadas só para anunciar contador e fonte. O resumo de notícias fora do slideshow também normaliza os títulos. Isso reduz ambiguidades de leitura, mas não demonstra eliminação do sotaque geral do modelo.

Corrigidos dois problemas de controle: a apresentação aguarda falas pendentes na fila; uma exceção ao gerar a próxima frase deixa terminar o áudio já preparado antes de encerrar a reprodução. Erros mantêm a mensagem de diagnóstico e não acionam outra voz.

Teste com manchete do histórico (não uma nova checagem jornalística): versão com contador/fonte levou 10,357 s para gerar; versão final só da manchete levou 6,824 s (`logs/qwen_news_headline.json`, áudio `logs/qwen_news_headline.wav`). São textos diferentes; o ganho vem também da redução da locução. Ainda existe atraso alto para texto inédito. Uma temperatura menor foi testada, mas não ativada: gerou fala mais longa sem melhora comprovada. O modelo, a amostra e os parâmetros aprovados foram mantidos.

102 testes e self-test passaram. A avaliação auditiva do sotaque na manchete final continua necessária; testes de texto/controle não comprovam qualidade de voz.
