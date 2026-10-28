# Fluidez das animações — 02/10/2026

## Alterações

- **Orbital e resumo diário:** grade, fundo e halo ficam em um único cache de imagem, reconstruído quando tamanho ou escala de tela mudam. Os nove anéis mantêm os mesmos 161 pontos; a base trigonométrica é reaproveitada. Apenas as regiões dos anéis e do indicador inferior pedem atualização a cada quadro.
- **Núcleo clássico:** posições dos 58 pontos e suas conexões são calculadas uma vez por tamanho de janela, em vez de repetir a busca e ordenação dos vizinhos a cada quadro.
- **Interface com rosto:** polígonos fixos são reaproveitados e as 96 marcações do anel são desenhadas em dois grupos. Reações à fala, cores e detalhes continuam presentes.
- **Ritmo:** Orbital e núcleo clássico usam tempo decorrido e timer preciso com alvo de aproximadamente 30 quadros/s. O ritmo do movimento original foi conservado; pausas longas não provocam uma corrida para compensar quadros perdidos. A interface com rosto conserva o alvo de aproximadamente 60 quadros/s.
- **Visibilidade:** a animação principal para quando fica coberta pelo resumo. O fundo do resumo também respeita minimização e modo jogo. Ao fechar o resumo, a animação principal retorna conforme o modo atual. Timers de voz e execução de comandos são independentes.

Não foram alterados os modelos de IA, credenciais, voz escolhida, comandos ou configurações das contas. A correção concentra-se no desenho e no controle dos timers visuais. Reabra o V para carregar o código atualizado.

## Medição de desenho

Comparação alternada entre o código preservado e a versão otimizada, no mesmo processo Qt, após cinco aquecimentos e com 60 amostras de cada versão. São tempos de renderização completa em memória, não FPS medidos no monitor nem latência total do V.

| Visual / resolução lógica | Antes, mediana | Depois, mediana | Redução aproximada |
| --- | ---: | ---: | ---: |
| Orbital / 1180 × 720 | 35,87 ms | 19,75 ms | 45% |
| Rosto / 690 × 620 | 7,11 ms | 5,62 ms | 21% |
| Núcleo clássico / 500 × 500 | 9,67 ms | 4,15 ms | 57% |

Foram comparados pixels em READY, LISTENING, PROCESSING, SPEAKING e ERROR, na mesma fase de animação. As 15 comparações resultaram em diferença zero nos quadros avaliados. Isso confirma esses estados de referência, não todas as combinações de monitor, driver ou escala do Windows.

Os caches aumentam o uso de memória para reduzir o trabalho repetido. O fundo guarda apenas o tamanho/escala atual, e as geometrias são limitadas aos elementos existentes. Não há promessa de FPS constante durante jogos, carregamentos ou outras tarefas pesadas.

Relatório: `logs/animation_20261002/comparison.json`. Imagens antes/depois e cópias dos cinco arquivos originais alterados estão na mesma pasta. O novo relógio de animação está em `ui/animation_clock.py`.

## Verificações reproduzíveis

Resultado final: **66 testes passaram** em animações, modo jogo, resumo diário, câmera e controles de fala. O teste de ocultação identificou e ajudou a corrigir um timer de fundo que podia permanecer ativo ao esconder a janela.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_animation_rendering tests.test_game_mode tests.test_daily_briefing tests.test_vision tests.test_speech_controls
.\.venv\Scripts\python.exe -m tests.benchmark_animation_rendering
```

O comparador visual usa as cópias `.before` preservadas localmente. Os testes de integração verificam troca de interface, modo jogo, cobertura pelo resumo e manutenção dos timers de voz, além das regressões de câmera e fala.

No uso real, conferir o V com Spotify e câmera ligados, abrir e fechar o resumo, alternar F6, minimizar/restaurar e ativar/desativar o modo jogo. A medição sintética não substitui essa combinação no seu ambiente.
