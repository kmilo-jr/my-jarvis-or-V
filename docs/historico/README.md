# docs/historico/

Notas de versões antigas, análises de desempenho e artefatos que **não** descrevem o
comportamento atual do V. Mantidos por rastreabilidade.

- `LEIA_ME_*` — notas de lançamento de versões antigas (1.5 → 1.9.7).
- `REVISAO_*`, `MELHORIAS_*`, `DESEMPENHO_*`, `ESTABILIDADE_*`, `TRES_MELHORIAS_*`,
  `VIDEO_*`, `INVESTIGACAO_*` — análises datadas de 2026-10-03 a 10-05.
- `PLANO_V_JARVIS.md`, `EVOLUCAO_ASSISTENTE_PESSOAL.md` — planejamento de produto.
- `PANORAMA_V.html` — panorama visual antigo.

## historico/migracoes/

Os scripts `migrar_config_*` e `migrar_spotify_*` das versões 0.8 até 1.5 são
**históricos e obsoletos**: o V atual cria `config/default.json` a partir de
`config/default.example.json` na primeira execução, e essas migrações esperavam a
antiga estrutura de pastas (`V_PROTOTYPE_1_5_SPOTIFY_BRIDGE` ao lado do projeto).
Eles foram movidos para cá sem ajuste de caminho de propósito — são referência, não
ferramenta de uso diário. Não os execute sobre um config atual.

O acesso remoto de fora de casa (P2P + Cloudflare Quick Tunnel) foi removido do código
na versão 1.9.8; os changelogs em `../changelog/` ainda o descrevem porque são registro
histórico.
