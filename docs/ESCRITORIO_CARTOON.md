# Escritório cartoon interativo

O desenho ativo agora é feito em `ui/cartoon_office_art.py`, incluindo o robô.
As imagens geradas anteriormente permanecem guardadas, mas o escritório não
as carrega. `PixelOffice` mantém o nome por compatibilidade com a navegação.

- Fundo e oito quadros do personagem são desenhados uma vez e guardados em memória.
- Mesa, estante, sofá, TV, cama, calendário e rádio possuem regiões de interação.
- Mouse destaca o objeto; setas e Enter oferecem uma alternativa pelo teclado.
- Mesa, estante, calendário e rádio preenchem o campo de pedido, sem enviar.
  Um rascunho existente é preservado. Enviar continua usando a fila normal do V.
- Sofá, TV e cama iniciam atividades visuais. Cliques não interrompem pedidos
  em processamento, nem iniciam IA, áudio ou reprodução musical.
- Monitor, livro na estante, TV e almofada reagem quando o personagem chega.
- A atualização inclui apenas personagem e móvel ativo; o temporizador para
  quando a aba fica oculta. Não há renderização 3D contínua.

Verificação: 31 testes distintos de escritório, navegação e modo jogo passaram.
Prévia gerada pelo aplicativo: `logs/office_preview/office.png`.

Medição isolada, Qt nativo, janela 1000 × 660, quatro segundos por situação:
`logs/office_preview/benchmark_cartoon.json`. Memória na caminhada: 57,14 MiB,
contra 61,03 MiB na medição anterior. CPU observada entre 0 e 0,78% de um núcleo
nesta amostra curta; valores zero refletem também a resolução da medição.
Oculto: zero atualizações de animação e zero eventos de desenho. Isso não mede
o consumo completo do V ou da GPU e não garante percentuais em outras máquinas.
