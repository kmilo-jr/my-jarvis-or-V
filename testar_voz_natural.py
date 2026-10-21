from __future__ import annotations

import json
from pathlib import Path

from voice.engine import VoiceEngine

BASE = Path(__file__).resolve().parent
cfg = json.loads((BASE / "config" / "default.json").read_text(encoding="utf-8"))
voice_cfg = cfg.get("voice", {})
engine = VoiceEngine(voice_cfg)

print("=== V 1.2 NATURAL VOICE TEST ===")
print("Voz:", voice_cfg.get("tts_edge_voice"))
print("Perfil:", voice_cfg.get("tts_profile"))
print("Rate base:", voice_cfg.get("tts_edge_rate"), "Pitch:", voice_cfg.get("tts_edge_pitch"))

samples = [
    "Pronto. Spotify aberto.",
    "Boa tarde. Já estou por aqui. O que temos para hoje?",
    "Curioso. Quanto mais a tecnologia avança, mais importante fica decidir o que vale a pena automatizar.",
]
for i, text in enumerate(samples, 1):
    print(f"[{i}/3]", text)
    if not engine._speak_edge_tts(text):
        print("FALHOU: Edge-TTS não conseguiu reproduzir a amostra.")
        raise SystemExit(1)
print("OK: três estilos de fala reproduzidos.")
