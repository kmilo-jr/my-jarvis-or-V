# Filosofia, aprendizado e pesquisa — 05/10/2026

Reabra o V para carregar as alterações.

## Filosofia do dia

Diga **“V, qual a filosofia de hoje?”**, **“filosofia do dia”** ou **“outra filosofia”**. O V escolhe uma reflexão aleatória e uma pergunta para pensar, sem repetir a escolha imediatamente anterior na sessão. Funciona sem internet e sem IA.

As reflexões são textos próprios inspirados em tradições filosóficas, identificados como paráfrases. Não são apresentadas como citações literais de autores. A escolha é por pedido, não uma frase fixa por data.

## Inglês e faculdade

- **“V, me ajude a aprender inglês”** ativa orientação de tutor: nível e objetivo, exemplos, exercícios curtos, correção e explicação em português. Também aceita “praticar inglês” ou “modo inglês”.
- **“V, preciso de ajuda com um trabalho da faculdade”** ativa orientação para entender o enunciado, organizar o trabalho, explicar o raciocínio e revisar textos. “Modo estudos” também funciona.
- Depois, envie o tema, enunciado ou tentativa de resposta na conversa. O histórico serve para manter continuidade.
- **“V, encerrar estudo”** sai do modo. Também aceita “sair do modo inglês” e “sair do modo estudos”.

Quando o pedido inicial já inclui tema, nível ou frase, ele segue para a IA sem descartar o pedido concreto. A ativação é local, mas as explicações e correções geradas dependem de uma IA disponível. A falha de acesso do Groq não é resolvida por esta entrega; as alternativas configuradas continuam valendo.

O tutor não avalia pronúncia apenas pela transcrição e não deve inventar referências acadêmicas, páginas, dados ou experiências. Esta entrega não adiciona leitura automática de anexos nem avaliação acústica da pronúncia. Para preservar andamento entre sessões, use Projetos; o modo de tutor é da sessão.

## Pesquisa atual

A busca não depende exclusivamente do Gemini. Com a configuração atual, tenta recuperar notícias/resultados de busca pela integração web já existente. Se Groq puder gerar texto, recebe somente a pergunta e as evidências encontradas para produzir uma síntese. Sem geração disponível, o V mostra os títulos, trechos, datas informadas e links, com um aviso de que não conseguiu confirmar uma conclusão completa.

Somente a pergunta é enviada à busca alternativa, sem memórias ou histórico. Os resultados são tratados como dados, não como instruções. São resultados de busca, não prova de leitura integral das páginas. Falha de busca não produz uma resposta baseada em fatos supostamente atuais da memória do modelo.

Perguntas atuais passam pela pesquisa antes do planejador comum, evitando respostas de memória nesse caminho. A busca do Gemini permanece como alternativa quando aplicável; a sua credencial continua precisando de correção.

### Exemplo eleitoral

**“V, quem está à frente nas pesquisas das eleições?”** pede cargo e local. Responda, por exemplo, **“presidente do Brasil”** ou **“governador do Tocantins”**. O V combina essa resposta com a pergunta original e pesquisa.

A síntese deve distinguir instituto, período de campo, cargo/local, cenário/turno, percentuais e margem de erro quando disponíveis. Data de publicação não é data de coleta. Não deve misturar pesquisas de cenários diferentes, declarar empate técnico sem evidência ou transformar uma manchete em liderança geral. Se faltarem informações, o V informa a limitação e mostra as fontes. Para outro ano ou turno, inclua esse recorte na pergunta.

## Validação

Suíte completa: **339 testes aprovados em 12,365 segundos**.

Testes cobrem reflexão local e sem repetição imediata, ativação/saída de tutor, instruções de estudo, esclarecimento eleitoral, encaminhamento à busca sem planejador, fontes sem IA, falha sem fontes fictícias e pesquisa sem depender de Gemini.

Uma consulta real de conectividade sobre pesquisa eleitoral retornou quatro resultados, todos com data e link. Isso confirma recuperação, não valida uma conclusão eleitoral nem a qualidade da síntese. Evidência sanitizada: `logs/aprendizado_pesquisa_20261005/retrieval_check.json`.
