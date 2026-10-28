# Três melhorias do V — 05/10/2026

Feche e reabra o V para carregar as alterações.

## O que aconteceu?

Diga **“V, o que aconteceu?”** ou use o botão de mesmo nome. A janela mostra a última falha registrada nesta sessão e oferece acesso à Central de conexões e aos configuradores de Groq, Gemini e Ollama. Na central, selecione o serviço e clique em testar.

Erros de IA agora viram explicações curtas: credencial recusada, acesso negado, limite de uso, indisponibilidade ou demora excessiva. Respostas técnicas brutas não entram nessa explicação nem na fala. Quando todas as IAs falham, o erro do Groq principal também é preservado para o diagnóstico, junto com os das alternativas. A falha não é esquecida apenas por abrir o painel.

O painel explica falhas, mas não corrige credenciais ou permissões automaticamente. Erros sem código reconhecido recebem orientação genérica. Conexão autenticada não comprova permissão de geração: no teste anterior, o Groq respondeu 403 ao tentar gerar texto. As rotas de tentativa automática continuam sendo Groq, Gemini e Ollama; pesquisa online mantém sua integração específica.

## Modo de jogo ampliado

Diga **“V, estou jogando”** ou **“V, vou jogar”**. Também é possível usar F9 ou o botão Modo Jogo.

- Mantém a redução de animações, recolhimento da interface ou uso do outro monitor.
- Espaça as análises automáticas da câmera em pelo menos 3 segundos. Uma análise em andamento termina; pedidos explícitos de análise continuam disponíveis. A captura/prévia da câmera não muda de resolução nem é desligada.
- Adia avisos comuns, inclusive sua fala, mantendo alarmes ativos. Os avisos pendentes voltam a ser elegíveis ao sair, sujeitos aos controles normais de silêncio, pausa e intervalo.
- Libera o processo Qwen após 15 segundos ocioso, sem interromper a síntese que já está em andamento. A próxima fala pode exigir recarregamento do modelo.

Diga **“V, parei de jogar”** ou **“V, modo normal”** para restaurar a apresentação e a política normal de ociosidade da voz (atualmente 120 segundos). O ajuste de jogo é temporário; não sobrescreve preferências salvas. Não impõe um teto de GPU/CPU, nem encerra outros aplicativos.

## Continuidade de projetos

O botão **Projetos** abre um editor com nome, concluído, pendente e próximo passo. Salvar também seleciona o projeto ativo. É possível retomar um projeto existente e esquecer individualmente um registro.

Comandos disponíveis:

- “V, criar projeto Meu V”
- “V, concluído: revisão da câmera”
- “V, pendente: testar a voz”
- “V, próximo passo: ouvir uma resposta longa”
- “V, continua de onde paramos”
- “V, retomar projeto Meu V”
- “V, listar projetos”
- “V, esquecer projeto Meu V”

Os três campos de andamento também aceitam texto sem os dois-pontos. Cada atualização substitui o conteúdo daquele campo. Criar um nome já existente retoma o registro sem apagar seu andamento.

O registro é explícito: o V não marca tarefas como concluídas sozinho e não executa o próximo passo automaticamente. O projeto ativo é incluído no contexto das próximas solicitações à IA, limitado a 600 caracteres por campo para conter o tamanho das requisições. Alterações limpam o contexto recente da sessão para reduzir reutilização de informações antigas.

Os projetos ficam em `data/project_progress.json`, com gravação por substituição de arquivo. Um arquivo inválido é preservado e gera erro; falha ao salvar mantém a versão anterior. Há limite de 100 projetos, nomes de 100 caracteres e campos de 3000 caracteres. O botão Esquecer remove o registro local do projeto, sem remover fatos que tenham sido salvos separadamente em Memórias.

## Validação

Suíte completa: **331 testes aprovados em 13,956 segundos**.

Testes cobrem retomada após reinício, correção, esquecimento, preservação de arquivo corrompido ou falha ao salvar, comandos sem IA, explicações sem conteúdo bruto, manutenção do erro do Groq, alarmes durante jogo, adiamento de avisos comuns e restauração dos intervalos de câmera/voz.

As telas foram abertas e conferidas com dados temporários; criar, salvar, selecionar e excluir foram exercitados sem alterar projetos reais. Imagens em `logs/tres_melhorias_20261005/`. Medições de FPS de jogos, consumo prolongado e qualidade de áudio em uso real ainda precisam de validação no PC.
