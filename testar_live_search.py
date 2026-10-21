from __future__ import annotations
import json
from pathlib import Path
from brain.service import BrainService

BASE = Path(__file__).resolve().parent
cfg = json.loads((BASE / "config" / "default.json").read_text(encoding="utf-8"))
brain_cfg = cfg.get("brain", cfg)
brain = BrainService(brain_cfg, personality={"name": "V"})

print("=== V LIVE SEARCH 1.3 ===")
print("Busca ativa:", "SIM" if brain.live_search_enabled else "NAO")
print("Gemini configurado:", "SIM" if bool(brain.gemini_key) else "NAO")
print("Modelo de busca:", brain.live_search_model)
if not brain.gemini_key:
    print("\nRode configurar_gemini.bat antes do teste.")
    raise SystemExit(1)

query = "Quais são as principais notícias de tecnologia de hoje no Brasil?"
print("\nConsulta:", query)
print("\nPesquisando...\n")
answer = brain.live_search(query, [], {})
print(answer or brain.last_error or "Sem resposta.")
print("\nConsultas Google:", (brain.last_live_search or {}).get("queries", []))
print("Fontes:", len((brain.last_live_search or {}).get("items", [])))
