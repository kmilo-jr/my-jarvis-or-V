# Groq como reserva do Gemini

A ordem no modo híbrido é Gemini 2.5 Flash → Groq → Ollama local. Modelo inicial: `openai/gpt-oss-120b`, disponível na lista do plano gratuito consultada em 28/09/2026. A integração não altera o plano de cobrança de sua conta. Use uma conta Free para permanecer no uso gratuito; os limites e a disponibilidade podem mudar.

1. Crie sua chave em https://console.groq.com/keys.
2. Execute `configurar_groq.bat` e insira a chave na janela local.
3. Execute `testar_groq.bat` para verificar a geração real.
4. Reabra o V para carregar a configuração.

A chave fica em `config/groq_key.dat`, protegida com DPAPI do usuário Windows. Não existe fallback de gravação em texto aberto. A variável de ambiente `GROQ_API_KEY`, quando definida, tem prioridade sobre o arquivo. Não envie sua chave no chat nem coloque no default.json.

O Groq recebe a personalidade, memórias relevantes, contexto e até dez mensagens recentes. Pode responder à conversa, gerar planos JSON e resumir resultados de ferramentas. As ações continuam passando pelo registro e pelo firewall do V; não são executadas pelo servidor Groq.

A resposta é recebida inteira antes de ser falada nesta primeira versão. Pesquisas atuais continuam na rota de pesquisa existente: uma falha da busca não gera uma resposta sem fontes pelo Groq. A memória persistente e a voz continuam nos módulos existentes.

Falhas de conexão, autenticação, limite ou resposta inválida permitem recorrer ao Ollama. Um erro 429 pausa as chamadas Groq conforme `retry-after` (até uma hora; 60 segundos se ausente), sem bloquear o processamento local. Falhas de rede/servidor pausam por 30 segundos. Não são feitas repetições imediatas.

Configuração na seção `brain` de `config/default.json`: `groq_enabled`, `groq_model`, `groq_timeout`. A chave fica separada. Sem chave, o V pula o Groq.

Fontes: https://console.groq.com/docs/models, https://console.groq.com/docs/rate-limits, https://console.groq.com/docs/structured-outputs.

Validação inicial: API simulada, troca de provedores, formato dos planos, histórico, limites e gravação/leitura DPAPI. A qualidade das respostas reais e a conexão dependem da chave do usuário.
