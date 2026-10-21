# Efeito robótico inspirado no Ultron

Implementado em 29/09/2026 com base na descrição fornecida pelo usuário. Não é uma reprodução verificada dos vídeos.

A voz configurada atualmente é ElevenLabs personalizada. O efeito é local, aplicado depois da síntese, mantendo o Voice ID e o cache de áudio original. Também funciona na rota Qwen; os demais motores não recebem este efeito.

Mistura inicial de 35%: camada com pitch -1,4 semitom por duas linhas de atraso, vocoder de 12 bandas com portadoras harmônicas, reforço de graves/médios, saturação suave e reflexões de 19/37/61 ms. Mantém a duração da fala. O restante da mistura preserva a articulação original. Não adiciona ruído contínuo durante silêncio.

- Ativar: `ativar_efeito_ultron.bat`.
- Desligar e voltar à voz original: `desligar_efeito_ultron.bat`.
- Ajustar: `.venv\Scripts\python.exe configurar_efeito_voz.py --intensidade 0.65` (0 a 1).
- Reinicie o V depois de alterar. A configuração não muda a voz nem suas credenciais.

As opções ficam na seção `voice` de `config/default.json`: `tts_robot_enabled` e `tts_robot_intensity`. Falhas de processamento mantêm a voz original e registram `robot_effect_error` nas métricas.

## Amostras e validação

Em `logs/efeito_ultron/`: voz original, mistura moderada (35%), forte (65%) e `verificacao.json`. A frase foi gerada com a configuração atual do ElevenLabs. O processamento local medido ficou em aproximadamente 226 ms para 3,576 s de áudio a 44,1 kHz, sem saturação de pico. Essa medida não inclui geração, importação inicial de bibliotecas nem reprodução.

Testes cobrem silêncio, bypass, duração, picos, formatos, criação/remoção de arquivos temporários, cancelamento antes do efeito e falha de DSP. Qualidade do timbre e intensidade dependem da avaliação auditiva; não houve aprovação auditiva nesta implementação. Reflexões são limitadas à duração de cada frase para não adicionar pausas artificiais entre elas.
