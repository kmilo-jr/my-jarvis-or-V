# Escritório isométrico — 8 de outubro de 2026

Referência escolhida pelo usuário: segundo vídeo, escritório estilo Habbo.
Arte original em `ui/isometric_office_art.py`, construída com polígonos 2D,
faces claras/escuras, peças separadas, piso em losangos e personagem pixelado.
Não usa imagens do vídeo nem carrega os antigos cenários gerados.

As superfícies dos móveis e do personagem ficam em cache. O personagem é
intercalado entre as camadas conforme sua posição; os pontos de destino e as
rotas acompanham a nova sala. Cliques usam a transparência das peças para não
capturar áreas vazias dos retângulos. Continuam disponíveis interação por
teclado, preparação de pedidos sem envio automático e rotina visual livre.

TV: telejornal ilustrativo com faixa animada. Monitor: sistema ilustrativo com
gráficos. Não são notícias ou indicadores reais. Os painéis têm quadros locais
em cache; não usam serviços externos. O relógio de renderização continua em
16 ms, com regiões separadas de atualização e pausa integral fora da aba.

Validação: 33 testes de escritório, navegação e modo jogo passaram; após ajustar
os limites das camadas, os 21 de escritório e navegação passaram novamente.
Conferidas prévias em tamanho normal/compacto e limites do desenho dos móveis.

Benchmark isolado Qt nativo, 1000 × 660, sem serviços de voz/IA:
aproximadamente 60 atualizações/s, memória de 67 MiB, zero atualizações oculto.
CPU entre 16% e 31% **de um núcleo** nas duas amostras visíveis de quatro segundos,
incluindo preparação dos caches. Não é medição de GPU nem do aplicativo todo.
Detalhes: `logs/office_preview/benchmark_isometric.json`.
O benchmark passou a usar o event loop nativo, pois o polling de QTest.qWait
subcontava o timer de 16 ms; taxas antigas não são diretamente comparáveis.
