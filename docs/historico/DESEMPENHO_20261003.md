# Ajustes de desempenho — 03/10/2026

O efeito da voz reutiliza os coeficientes de seus filtros, com cache limitado a quatro frequências de amostragem. O estado de processamento continua independente por trecho. Nenhum áudio pessoal é acrescentado ao cache por esta alteração.

As threads do detector ONNX da câmera agora descansam entre análises, em vez de aguardar ativamente. O modelo, os dois threads de inferência, a resolução e os critérios de reconhecimento continuam iguais. O temporizador do painel fica parado sem câmera e sem trabalho pendente; resultados em andamento ainda são recolhidos e descartados corretamente quando a câmera é desligada.

## Medições

Script e dados: `logs/performance_20261003/benchmark.py` e `resultado.json`. Cópias anteriores dos dois processadores foram preservadas nessa pasta para a comparação.

| Teste | Antes | Depois |
|---|---:|---:|
| Efeito em áudio de 1 s, mediana | 38,43 ms | 23,23 ms |
| Efeito em áudio de 5 s, mediana | 138,50 ms | 121,93 ms |
| Efeito em áudio de 10 s, mediana | 340,16 ms | 322,67 ms |
| CPU do processo em 10 análises espaçadas por 700 ms | 0,844 s | 0,391 s |
| Inferência da câmera, mediana | 20,59 ms | 21,83 ms |

As amostras do áudio processado foram exatamente iguais antes e depois nos três tamanhos. O tensor completo de saída do detector também foi exatamente igual no teste sintético. O teste da câmera não capturou imagens reais. Os números medem componentes isolados, não o consumo total do V ou do PC, nem demonstram economia de GPU ou RAM. Cargas diferentes podem produzir outros tempos.

O Qwen permanece com o mesmo modelo e referência; não foi descarregado entre respostas, pois isso aumentaria novamente o tempo para começar a falar. Não houve redução da taxa de animação. Reinicie o V para carregar as alterações.
