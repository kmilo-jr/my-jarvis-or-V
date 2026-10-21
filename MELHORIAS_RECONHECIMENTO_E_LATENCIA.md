# Reconhecimento e tempo de resposta

Alterações de 23/09/2026:

- O áudio capturado em 44,1/48 kHz passa por filtro antes da conversão para 16 kHz. Isso reduz a entrada de ruído agudo na faixa de voz durante a reamostragem, sem dependências novas.
- Frases a partir de 1 segundo toleram 650 ms de silêncio, para preservar pausas naturais. Comandos curtos continuam com 380 ms. A tolerância maior acrescenta até 190 ms às frases longas em comparação com a configuração anterior; é uma escolha de precisão, não uma redução desse tempo.
- O Whisper mantém o modelo small em português e beam 3. Uma transcrição com logprob abaixo de -0,8 pode receber uma segunda tentativa com beam 5. Só substitui o resultado quando o indicador melhora; essa pontuação não garante acerto. Áudio vazio ou classificado como ausência de fala não dispara essa tentativa. Falha da segunda tentativa preserva a primeira.
- O stream da IA entrega linhas SSE sem esperar acumular 512 bytes, permitindo encaminhar a primeira frase completa mais cedo.
- Respostas longas sem pontuação também são divididas para síntese de voz, respeitando palavras e o limite configurado de caracteres.
- A duração máxima de captura usa a duração dos blocos de áudio, evitando truncamento prematuro por atrasos do processamento.

As métricas da transcrição incluem `recognition_retry`, `recognition_logprob` e `transcription_ms`. A configuração permite desativar a segunda tentativa com `voice.recognition_retry_enabled: false` se o custo extra de CPU for indesejado.

Validação automatizada: filtro com tons sintéticos em 44,1/48 kHz, pausas, transcrição com modelo simulado, falhas/fallback, divisão de áudio e entrega antecipada de SSE via servidor HTTP local. Sem medição de acerto com a voz do usuário ou de latência com serviços externos. A segunda tentativa pode aumentar a demora em áudio difícil.

Para validar no uso: reabra o V, ative a voz contínua e fique em silêncio durante a calibração. Teste um comando curto, uma frase longa com pausa e uma pergunta de conversa. Compare o texto reconhecido e o registro `logs/latency_last.json`. O botão Testar microfone permite conferir a transcrição antes de enviar comandos.


## Atualização de 01/10/2026

- Reconhecimento em `device: auto`, `compute_type: auto`: usa a GPU quando
  disponível, com int8_float16, ou CPU int8. A GTX 1650 deste PC foi validada.
- As bibliotecas CUDA já presentes em `.venv/Lib/site-packages/torch/lib` são
  registradas apenas no processo do V. Não houve instalação ou alteração do PATH
  global do Windows. Falhas de carregamento na GPU retornam à CPU; erros CUDA,
  cuDNN/cuBLAS e falta de memória durante a inferência também repetem o áudio na CPU.
- Uma transcrição muito incerta, repetitiva com baixa confiança, ou com evidência
  de ausência de fala não é enviada como comando. Um segmento rejeitado invalida
  a frase inteira: removê-lo isoladamente poderia eliminar um “não”.
- A segunda tentativa só substitui a primeira quando melhora a pontuação e passa
  nas verificações. `recognition_min_logprob: -1.35` é uma heurística ajustável,
  não uma probabilidade de acerto; pode pedir repetição de fala legítima.
- Perdas no driver ou na fila de áudio passam a solicitar repetição, em vez de
  transcrever silenciosamente uma frase com lacunas. A interface mantém esse aviso
  por até três segundos ou até a próxima fala.
- Cancelar a escuta durante a transcrição descarta a resposta atrasada. Um trecho
  de voz do próprio V que inicia e termina durante a captura é detectado pelo
  contador de reprodução, salvo quando a interrupção por voz foi ativada.
- Teste de microfone e escuta contínua não executam inferências simultâneas.
- Metadados incluem dispositivo de inferência, fallback, motivos da rejeição e
  percentual de amostras próximas de saturação (`clipping_percent`).

### Medição local

O arquivo de voz sintetizada já existente `logs/qwen_news_final.wav`, de 9,36 s,
foi transcrito com o código final, mesmas opções de português e beam 3:

| Execução | CPU int8 | GPU int8_float16 |
| --- | ---: | ---: |
| Primeira após carregar modelo | 3583,3 ms | 1612,7 ms |
| Segunda, aquecida | 3032,4 ms | 1117,2 ms |

Os quatro textos foram iguais. O tempo acima exclui o carregamento do modelo e
não mede o microfone, a IA ou a síntese. É um único áudio sintetizado, não uma
avaliação de precisão com a voz do usuário. Relatório:
`logs/recognition_backend_benchmark.json`.

### Teste com sua voz

Reinicie o V para aplicar. O microfone preferido continua sendo Realtek; confira
na interface se é o microfone que você realmente está usando. Para uma avaliação
sem executar ações, desligue a escuta contínua do V e abra
`testar_voice_input_2.bat`. Ele usa agora o Python da `.venv`, prioriza o microfone
configurado e testa dez frases, incluindo “bom dia” e uma ordem com negação.
O teste salva os textos esperados/reconhecidos e métricas, sem salvar áudio.

Opções: `--list-devices`, `--device NUMERO` e `--backend cpu|cuda|auto`.
A taxa de erro por palavras (WER) conta inserções, remoções e trocas; menor é
melhor e 0% significa palavras iguais no teste. A similaridade antiga continua
no relatório apenas para comparação. Use o mesmo microfone e ambiente para
comparar execuções. O relatório fica em `logs/voice_input_2_benchmark.json`.

Verificação: 73 testes passaram nos módulos recognition_backend,
recognition_quality, voice_input_v2, conversation, speech_controls e daily_briefing.
GPU e listagem de microfones foram exercitadas no ambiente real; a precisão com
sua fala e o comportamento com música no ambiente ainda precisam desse teste.
