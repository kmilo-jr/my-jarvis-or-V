# Início da voz Qwen

A seleção do Qwen nas preferências agora prepara o motor em segundo plano, assim como a abertura do V já fazia. O perfil, a referência, os parâmetros de geração, o efeito e a velocidade de reprodução permanecem os mesmos.

O primeiro trecho pode ser dividido em uma vírgula, ponto e vírgula ou dois-pontos. A abertura precisa ter 60–160 caracteres e pelo menos 1,5 vez o tamanho da continuação, que deve ter no mínimo 25 caracteres. Frases curtas e textos sem uma divisão adequada permanecem inteiros. Os trechos seguintes mantêm o comportamento anterior. Esta proporção é uma heurística, não uma garantia de ausência de esperas.

## Medição local em 02/10/2026

`testar_qwen_inicio.py` compara a mesma frase com o motor preparado, sem cache e sem tocar no dispositivo de saída. Resultado em `logs/qwen_inicio_20261002_140107/resultado.json`:

- Antes: primeiro áudio pronto em 9,704 s.
- Ajustado: primeiro áudio pronto em 7,413 s (redução de 23,6%).
- A continuação demorou 2,760 s para gerar, enquanto a abertura tem 6,560 s de áudio. Portanto, a simulação desse caso não indica falta de áudio na junção.
- Preparação do processo: 3,999 s, medida separadamente.

Uma divisão mais agressiva foi descartada: começava em 3,8 s, mas provocaria cerca de 5,21 s de espera na junção. Os resultados variam com o texto e a carga da máquina. Esta medição não inclui a resposta da IA, reconhecimento de voz, processamento do efeito nem a latência do dispositivo de som. Não é streaming nativo do modelo.

Reinicie o V para carregar o código atualizado. Para repetir: `.venv\Scripts\python.exe testar_qwen_inicio.py`.
