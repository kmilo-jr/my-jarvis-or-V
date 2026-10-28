# tools/

Scripts avulsos que **não** fazem parte do app em execução: testes manuais, diagnósticos
e utilitários. Antes, ficavam espalhados na raiz do projeto.

Todos rodam a partir desta pasta. Os `.py` já ajustam `sys.path` e a raiz do projeto
automaticamente (bootstrap no topo do arquivo), então `config/`, `data/` e os módulos do
app são encontrados mesmo com o arquivo aqui.

## Diagnóstico

| Script | Para que serve |
|---|---|
| `diagnostico_startup.py` | Checa Python, config JSON, dependências, Action Core e construção da janela |
| `diagnosticar_spotify_bridge.bat/.py` | Sobe o bridge, mostra `/health`, espera a extensão do Spicetify |

## Testes manuais

| Script | Para que serve |
|---|---|
| `testar_gemini.bat/.py`, `testar_groq.bat/.py` | Verifica provedor de IA configurado |
| `testar_voz_v.bat/.py`, `testar_voz_edge.bat/.py`, `testar_voz_natural.bat/.py` | Testes de fala por motor |
| `testar_voice_input_2.bat/.py` | Voice input 2.0 (VAD/endpoint) |
| `testar_som_processamento.bat/.py` | Efeito sonoro de PROCESSING |
| `testar_piper_faber.bat/.py` | Piper/Faber offline |
| `testar_live_search.bat/.py` | Busca ao vivo |
| `testar_v_mobile.bat/.py` | Notificações do celular (Phone Link) |
| `testar_qwen_inicio.py`, `testar_qwen_frases_longas.py` | Motor Qwen3-TTS local |
| `TESTAR_ROSTO_2D.bat` | Abre o laboratório da face 2D (`main_face_2d_test.py`) |
| `laboratorio_voz_v.bat` | Atalho para configurar o perfil Edge-TTS |

## Utilitários

| Script | Para que serve |
|---|---|
| `usar_edge_como_voz.bat/.py` | Define Edge-TTS como voz principal |
| `usar_piper_como_voz.bat/.py` | Define Piper (offline) como voz principal |
| `gerar_config_exemplo.py` | Gera `config/default.example.json` a partir do config real, anonimizando segredos (`--check` valida sem gravar) |

Os testes automatizados de verdade ficam em `../tests/` e rodam com
`python -m unittest discover -s tests -p "test_*.py"`.
