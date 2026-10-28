# XTTS local — motor opcional antigo

O padrão atual é **V Alt com Qwen local**, aprovado pelo usuário. Consulte `AVALIACAO_QWEN_V_ALT.md` para configuração, validação e limitações de latência. O texto abaixo documenta o motor XTTS opcional; ele não está ativo no perfil padrão.

O V usa o XTTS-v2 local para reproduzir a identidade da amostra sem depender da clonagem da ElevenLabs. O modelo foi configurado em `config/default.json` com o perfil `xtts_local`, idioma `pt` e a referência `assets/voice/v_prime_reference_short.wav`.

Na primeira execução o modelo pede o aceite dos termos não comerciais da Coqui e baixa aproximadamente 1,87 GB. Depois disso o modelo fica no cache do usuário e é carregado em segundo plano durante a inicialização do V.

O ambiente atual usa PyTorch com CUDA e a GTX 1650 quando disponível. Se o driver, a memória da placa ou o pacote local falhar, o V tenta Edge-TTS e Piper automaticamente para não ficar sem resposta.

O áudio recebe uma polida leve: o V reduz o ruído grave abaixo de 65 Hz, corta o silêncio das bordas e nivela o pico em 92%. Isso pode ser desligado com `voice.tts_xtts_polish_enabled: false`.

Há duas amostras disponíveis no seletor da interface: `v_prime` usa a referência original e `v_alt` usa `assets/voice/v_alt_reference_short.wav`. A escolha fica em `voice.tts_xtts_voice` e não altera as demais preferências de ritmo e entonação.

Para a amostra alternativa, o perfil usa velocidade `1.08`, configurada em `tts_xtts_speed_alt`. Os seletores principal e do painel Voz e tarefas são sincronizados; trocar a amostra cancela as falas anteriores e descarta o áudio preparado com a seleção antiga.

O padrão usa streaming com uma reserva de três blocos (`tts_xtts_streaming_enabled: true`, `tts_xtts_stream_prebuffer_chunks: 3`). O dispositivo de áudio fica aberto durante a resposta, enquanto a geração continua. Frases curtas também tocam quando terminam com menos de três blocos. A divisão de texto é feita localmente, preservando finais de frase e limitando trechos longos a 220 caracteres. O divisor opcional do Coqui foi desativado porque depende de Spacy e falhava em textos maiores neste ambiente. Se o streaming falhar antes de começar a tocar, o modo WAV completo continua disponível. Áudio já iniciado não é repetido por outra voz.

O modelo e a identidade de cada amostra ficam em memória. Com CUDA, `tts_xtts_cpu_threads` limita o trabalho auxiliar a quatro threads; os pesos normalizados do gerador de áudio são preparados uma única vez. O modo WAV reaproveita frases idênticas em um cache limitado a 8 MB, separado por amostra, arquivo e configurações. Esse cache não acelera frases inéditas nem o carregamento do modelo.

O corte de silêncio nas bordas usa um limiar conservador e pelo menos 100 ms de margem para preservar sons fracos. Pausas naturais dentro das frases são mantidas. Respostas não são mais truncadas em 1.800 caracteres, e o limite de reprodução acompanha a duração do arquivo, inclusive acima de dois minutos.

O aquecimento prepara o modelo e a identidade da voz em segundo plano. A fala aguarda essa preparação para preservar a amostra selecionada; a interface mostra carregamento ou preparação e Esc cancela a espera. A voz de reserva continua disponível se a síntese falhar. Reinicie o V depois de atualizar o código. O streaming registra `first_audio_ms`, `buffer_gap_ms` e `device_underflows`; o modo por arquivo registra `synthesis_ms`. Nenhum desses tempos inclui reconhecimento do microfone nem geração do texto.

Validação de 24/09/2026: 87 testes automatizados e self-test aprovados. Pelo fluxo público `speak`, a V Alt começou uma resposta de 204 caracteres em 8,08 s e uma frase de 43 caracteres em 2,91 s, ambas com zero lacunas e zero underflows registrados. O modo completo anterior começou o texto de 204 caracteres em 15,74 s. São execuções locais, sem garantia para qualquer texto ou carga da máquina; textos mais longos ainda precisam de avaliação. O carregamento inicial do modelo levou 44,23 s e continua sendo uma limitação. Relatório: `logs/xtts_reserved_stream_fixed.json`.

Para trocar a amostra, converta o arquivo para WAV e altere `voice.tts_xtts_reference`. Uma fala limpa, de uma só pessoa, entre 6 e 12 segundos costuma produzir uma identidade mais estável que uma montagem com várias frases ou vozes.

O perfil anterior da ElevenLabs permanece no arquivo para uso opcional quando houver uma conta que permita clonagem instantânea.
