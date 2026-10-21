# Companheiro 2.5D do escritório

## Cenário 2.5D — 7 de outubro de 2026

`room_25d.png` é o fundo estático aprovado, sem personagem embutido.
Gerado por edição com a ferramenta integrada image_gen. Prompt da edição:

> Edit this exact approved office illustration into an empty game background plate. Remove ONLY the small red robot character and its book in front of the left bookshelf, seamlessly reconstruct the floor and bookshelf behind it. Keep all furniture, camera, lighting, colors, room edges, composition and image framing exactly unchanged. No characters anywhere. No new objects or text. This will be the static background beneath a separate animated sprite. Preserve the full image dimensions and aspect ratio.

O fundo é decodificado uma vez e escalado somente ao redimensionar o widget.
Cada passo invalida a união das regiões antiga e nova do personagem; o sistema
de recorte do Qt limita o desenho a essa região. Não há renderizador 3D,
consulta de IA nem temporizador adicional. A aba oculta desliga o temporizador.
As rotas usam pontos no piso do novo cenário.

### Medição isolada

Execute `python -m tests.benchmark_office_rendering nome` na raiz com o Python
do ambiente virtual. O teste abre apenas um widget Qt de 1000 × 660, sem serviços.
Resultados em `logs/office_preview/benchmark_before.json` e `benchmark_after.json`:

| Caminhada durante 4 segundos | Antes | Depois |
| --- | ---: | ---: |
| Área total redesenhada (megapixels) | 26,40 | 1,56 |
| CPU (% de um núcleo) | 3,12 | 0,39 |
| Memória do processo (MiB) | 50,86 | 61,03 |
| Desenhos com aba oculta | 0 | 0 |

CPU é uma amostra curta e sujeita a variação; não representa uma garantia de
redução nem uma medição de GPU ou do aplicativo completo. A memória adicional
é o custo do cenário em cache. O conjunto de 28 testes de escritório, navegação
e modo jogo passou após a alteração. Prévia real: `logs/office_preview/office.png`.

`companion_25d.png` foi gerado com a ferramenta integrada image_gen.
O avatar flutuante não usa este arquivo.

Atlas transparente: quatro colunas (frente, esquerda, costas, direita), duas
linhas (parado, passo). O escritório decodifica e reduz os oito quadros uma
vez na criação do widget. As atividades continuam usando acessórios desenhados
em 2D; este atlas ainda não contém poses exclusivas de leitura ou sono.

## Prompt usado

Create a production sprite atlas with transparent background for a top-down 2.5D cozy office game. Exactly 4 columns by 2 rows, eight equal cells, NO text, NO borders. Same cute little crimson-red robot companion in EVERY cell: oversized rounded rectangular black glass visor head, warm white digital eyes, small red torso with tiny luminous V chest emblem, detached mitten-like robot hands, two small red boots. Smooth shaded 3D-rendered sprite aesthetic, readable simple shapes, crimson armor and graphite joints, not pixel art. Camera elevated 35 degrees above horizon with orthographic projection. Direction columns from left to right: facing screen bottom (front three-quarter), facing screen left (left side three-quarter), facing screen top (back three-quarter), facing screen right (right side three-quarter). First row neutral standing pose arms relaxed. Second row walking pose one foot forward, slight arm swing, SAME four directions. Consistent character proportions, identical camera scale and top-left lighting. Each complete character centered in its equal cell, occupies about 72 percent of cell height and 65 percent of width, aligned feet baseline, ample transparent margins, no cutoff. No background, no scenery, no floor, no shadow extending beyond feet, no accessories, no books. Make all eight characters precisely separated for cutting an equal grid programmatically.
