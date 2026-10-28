# Perfis de voz

Em **Voz e tarefas → Voz**, o V oferece três perfis:

- **Jarvis · elegante e controlado**: ritmo próximo do normal, voz mais estável, pitch discretamente grave e variações leves. É o padrão.
- **Ultron · grave e sintético**: fala mais lenta, pitch mais baixo, maior estabilidade e pouca variação. O efeito depende da voz instalada ou do provedor configurado.
- **V · natural**: mantém o comportamento anterior, mais conversacional.
- **V Prime · original**: perfil autoral do V, com grave moderado, dicção clara e presença discreta. É o novo padrão.

Os nomes indicam uma direção estética; não são cópias exatas das vozes dos personagens, e o resultado depende da voz ElevenLabs, Edge-TTS, Piper ou SAPI configurada no computador. O V mantém o identificador de voz que já estava configurado. Se a síntese principal falhar, o fallback pode soar diferente porque usa outro mecanismo.

O ritmo pode ser ajustado entre 90% e 115%. Escolher um perfil altera pitch, estabilidade, estilo e valores de ritmo relacionados; o ajuste manual de ritmo continua valendo. “Ritmo expressivo” permite adaptar a fala a perguntas e textos longos. Salvar aplica as próximas falas e atualiza `config/default.json`.

O V Prime é uma assinatura de parâmetros sobre a voz configurada. Para criar um timbre novo de verdade, ainda será necessário usar uma ferramenta de criação/clonagem de voz do provedor e então informar o novo identificador em `tts_eleven_voice_id`.

Use **Salvar e ouvir** para testar uma amostra. A amostra usa o serviço de voz configurado e pode consumir cota da ElevenLabs. Não há alteração de voz sem uma ação explícita nessa tela.

Validação: os presets foram testados como configurações, com o identificador de voz preservado, parâmetros distintos para Jarvis e Ultron e compilação das interfaces. A qualidade sonora final precisa ser avaliada ouvindo no seu computador.
