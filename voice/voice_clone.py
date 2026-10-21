"""Authorized voice-sample registration for the configured ElevenLabs account."""
from pathlib import Path
import json

from .eleven_auth import load_key


class VoiceCloneSetupError(RuntimeError):
    pass


def register_voice_from_sample(sample_path, config=None, *, name="V Prime", description="V original voice", session=None):
    """Register a user-authorized sample and persist the returned voice id.

    This function never sends a file when the key, sample, or extension is
    missing. It uses the account already configured by the user and keeps the
    previous voice id until the provider confirms success.
    """
    config = dict(config or {})
    sample = Path(sample_path)
    if not sample.is_file():
        raise VoiceCloneSetupError(f"Amostra não encontrada: {sample}")
    if sample.suffix.lower() not in {".mp3", ".wav", ".m4a", ".flac", ".ogg"}:
        raise VoiceCloneSetupError("Formato de áudio não suportado para cadastro.")
    key = load_key(config)
    if not key:
        raise VoiceCloneSetupError("Chave ElevenLabs ausente. Configure-a localmente antes de enviar a amostra.")
    try:
        import requests
    except Exception as exc:
        raise VoiceCloneSetupError("A biblioteca de rede não está disponível.") from exc
    session = session or requests.Session()
    try:
        with sample.open("rb") as audio:
            response = session.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers={"xi-api-key": key, "Accept": "application/json"},
                data={"name": str(name).strip()[:80], "description": str(description).strip()[:500],
                      "labels": json.dumps({"source": "user_authorized_sample", "assistant": "V"})},
                files={"files": (sample.name, audio, "audio/mpeg")},
                timeout=(5, 60),
            )
    except Exception as exc:
        raise VoiceCloneSetupError(f"Não consegui conectar ao ElevenLabs: {type(exc).__name__}.") from exc
    if response.status_code >= 400:
        detail = ""
        try:
            obj = response.json()
            detail = str(obj.get("detail", obj.get("message", "")))[:240]
        except Exception:
            detail = str(getattr(response, "text", ""))[:240]
        if "paid_plan_required" in detail or "instant_voice_cloning" in detail.lower():
            raise VoiceCloneSetupError(
                "A conta ElevenLabs não permite clonagem instantânea neste plano. "
                "Faça upgrade no provedor ou use o V Prime com a voz atual."
            )
        raise VoiceCloneSetupError(f"O cadastro foi recusado (HTTP {response.status_code}). {detail}".strip())
    try:
        voice_id = str(response.json().get("voice_id", "")).strip()
    except Exception as exc:
        raise VoiceCloneSetupError("Resposta do ElevenLabs não trouxe um voice_id.") from exc
    if not voice_id:
        raise VoiceCloneSetupError("Resposta do ElevenLabs não trouxe um voice_id.")
    config_path = Path(config.get("config_path", Path(__file__).resolve().parents[1] / "config/default.json"))
    document = json.loads(config_path.read_text(encoding="utf-8"))
    voice_cfg = document.setdefault("voice", {})
    previous = voice_cfg.get("tts_eleven_voice_id", "")
    voice_cfg["tts_eleven_voice_id"] = voice_id
    voice_cfg["tts_voice_preset"] = "v_prime"
    voice_cfg["tts_profile"] = "elevenlabs_custom"
    temp = config_path.with_suffix(".tmp")
    try:
        temp.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(config_path)
    except Exception:
        # Preserve the provider result but do not pretend the local switch was saved.
        raise VoiceCloneSetupError(f"Voz cadastrada ({voice_id}), mas não consegui salvar a configuração local.")
    return {"voice_id": voice_id, "previous_voice_id": previous, "name": name, "sample": str(sample)}
