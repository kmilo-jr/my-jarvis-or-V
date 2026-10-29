"""Persistent cache restricted to three public, fixed briefing greetings."""
from app_paths import ROOT
import hashlib
import json
import shutil
import uuid
import wave
from pathlib import Path

ROOT = ROOT
GREETINGS = (
    'Olá, bom dia. É hora do seu resumo matinal. Vou passar para o meu colega Zê.',
    'Olá, boa tarde. É hora do seu resumo do dia. Vou passar para o meu colega Zê.',
    'Olá, boa noite. É hora do seu resumo do dia. Vou passar para o meu colega Zê.',
)


def cache_path(text, reference, config, folder=None):
    if text not in GREETINGS:
        return None
    reference = Path(reference)
    prompt = Path(config.get('tts_qwen_prompt') or reference)
    if not prompt.is_absolute():
        prompt = ROOT / prompt
    identity = ['briefing-qwen-0.6b-v1', text,
                hashlib.sha256(reference.read_bytes()).hexdigest(),
                hashlib.sha256(prompt.read_bytes()).hexdigest()]
    key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
    return Path(folder or ROOT / 'data/voice_cache/briefing') / f'{key}.wav'


def valid_audio(path):
    try:
        with wave.open(str(path), 'rb') as audio:
            frames = audio.getnframes()
            return (audio.getframerate() == 24000 and audio.getnchannels() == 1
                    and audio.getsampwidth() == 2 and 0 < frames <= 24000 * 30
                    and len(audio.readframes(frames)) == frames * 2)
    except (OSError, EOFError, wave.Error):
        return False


def store_audio(source, destination):
    if not valid_audio(source):
        raise ValueError('Saudação gerada em formato inválido.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f'.{uuid.uuid4().hex}.tmp')
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
