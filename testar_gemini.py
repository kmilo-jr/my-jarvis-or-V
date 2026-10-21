from __future__ import annotations

import json
import time
from pathlib import Path
from brain.service import BrainService

BASE = Path(__file__).resolve().parent
cfg = json.loads((BASE / "config" / "default.json").read_text(encoding="utf-8"))
brain = BrainService(cfg.get("brain", {}), personality=cfg.get("personality", {}))
print("=== V 1.1.1 — TESTE GEMINI FAST RESPONSE ===")
print("Chave configurada:", "SIM" if bool(brain.gemini_key) else "NAO")
if not brain.gemini_key:
    print("Rode configurar_gemini.bat primeiro.")
    raise SystemExit(2)

print("Chat model:", brain.gemini_chat_model)
print("Planner model:", brain.gemini_plan_model)
print("Thinking:", brain.config.get("gemini_thinking_budget", 0) if brain.gemini_model.startswith("gemini-2.5-") else brain.gemini_thinking_level)
print("Testando geração real...")
t0 = time.perf_counter()
answer = brain._gemini_chat("Responda apenas com: Gemini online.", [], {})
dt = time.perf_counter() - t0
if answer:
    print("Resposta:", answer)
    print("Provider real:", brain.last_provider)
    print(f"Latencia: {dt:.2f}s")
    print("TESTE: OK")
else:
    print(f"Latencia ate falha: {dt:.2f}s")
    print("TESTE: FALHOU")
    print("Diagnostico:", brain.last_error)
    raise SystemExit(1)
