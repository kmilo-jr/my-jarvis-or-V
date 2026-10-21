from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
candidates = [
    PARENT / "V_PROTOTYPE_1_1_1_GEMINI_FAST_RESPONSE",
    PARENT / "V_PROTOTYPE_1_1_GEMINI_HYBRID_BRAIN",
]
old = next((p for p in candidates if p.exists()), None)
if old is None:
    print("Pasta V 1.1.1/1.1 nao encontrada ao lado desta pasta.")
    raise SystemExit(1)

# Credenciais, tokens e memoria: copiamos sem exibir conteudo.
for rel in [
    "config/gemini_key.dat",
    "config/spotify_token.json",
    "data/memory.json",
    "data/conversation_history.json",
]:
    src, dst = old / rel, HERE / rel
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("Copiado:", rel)

# Modelo Piper ja baixado pode ser reaproveitado como fallback offline.
for name in ["pt_BR-faber-medium.onnx", "pt_BR-faber-medium.onnx.json"]:
    src = old / "models" / "piper" / name
    dst = HERE / "models" / "piper" / name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("Copiado:", f"models/piper/{name}")

old_cfg = old / "config" / "default.json"
new_cfg = HERE / "config" / "default.json"
if old_cfg.exists() and new_cfg.exists():
    a = json.loads(old_cfg.read_text(encoding="utf-8"))
    b = json.loads(new_cfg.read_text(encoding="utf-8"))

    # Mantem integracoes e configuracoes pessoais, mas NAO sobrescreve o novo
    # Personality Layer nem os novos parametros de prosodia/TTS 1.2.
    if isinstance(a.get("spotify_api"), dict):
        b["spotify_api"] = a["spotify_api"]
    if isinstance(a.get("memory"), dict):
        b.setdefault("memory", {}).update(a["memory"])
    if isinstance(a.get("ui"), dict):
        b.setdefault("ui", {}).update(a["ui"])

    # Reconhecimento/microfone do usuario permanece; parametros tts_* novos ficam.
    old_voice = a.get("voice", {}) if isinstance(a.get("voice"), dict) else {}
    recognition_keys = [
        "model", "device", "compute_type", "language", "record_seconds", "beam_size",
        "silence_peak", "silence_rms", "target_peak", "max_gain", "initial_prompt",
        "continuous_voice_default", "wake_words", "cpu_threads", "calibration_seconds",
        "energy_frame_ms", "stream_block_ms", "pre_roll_seconds", "max_phrase_seconds",
        "min_phrase_seconds", "listen_wait_seconds", "speech_start_blocks",
        "speech_start_floor_rms", "speech_end_floor_rms", "speech_start_noise_mult",
        "speech_end_noise_mult", "speech_start_max_rms", "speech_end_max_rms",
        "target_rms", "term_replacements",
    ]
    for key in recognition_keys:
        if key in old_voice:
            b.setdefault("voice", {})[key] = old_voice[key]

    # Se o usuario escolheu outra voz pt-BR no laboratorio, preservamos apenas o
    # nome da voz. Rate/pitch novos continuam sendo os naturais do 1.2.
    if old_voice.get("tts_edge_voice"):
        b["voice"]["tts_edge_voice"] = old_voice["tts_edge_voice"]

    new_cfg.write_text(json.dumps(b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("Migracao concluida. Gemini/memoria preservados; Personality + Natural Voice 1.2 mantidos.")
