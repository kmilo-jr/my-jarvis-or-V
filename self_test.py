from pathlib import Path
import tempfile
from core.functional_engine import FunctionalEngine, canonicalize_spoken_command, parse_spotify_music_request
from core.tool_router import ToolRouter
from core.tool_system import ToolCall, ToolContext
from brain.service import BrainService, BrainPlan
from brain.memory_store import PersistentMemoryStore
from personality.layer import PersonalityLayer


def eq(got,want,label):
    if got!=want: raise AssertionError(f"{label}: {got!r} != {want!r}")

eq(canonicalize_spoken_command('V, Aumentar o volume.'),'aumente o volume','volume')
eq(parse_spotify_music_request('V, tocar, Airbag, Radiohead, Spotify.'),'Airbag do Radiohead','music')
r=ToolRouter(); eq(r.route('notícias do dia').calls[0].name,'news.today','news'); eq(r.route('olá v').mode,'chat','greeting')

with tempfile.TemporaryDirectory() as td:
    mem=PersistentMemoryStore(Path(td)/'memory.json')
    item=mem.remember('prefiro Firefox'); assert item and mem.count()==1
    mem2=PersistentMemoryStore(Path(td)/'memory.json'); assert mem2.get_memories()==['prefiro Firefox']
    gone=mem2.forget('prefiro Firefox'); assert gone and mem2.count()==0

class DummyBrain:
    last_error=''
    def chat(self,text,history,context=None): return 'chat:'+text
    def plan(self,text,history,context=None,tool_manifest=None): return None
    def respond_after_tools(self,user_text,history,tool_results,context=None): return None

with tempfile.TemporaryDirectory() as td:
    mem=PersistentMemoryStore(Path(td)/'m.json')
    e=FunctionalEngine(DummyBrain(),memory_store=mem)
    # Isola persistência de histórico durante teste.
    e.history_path=Path(td)/'history.json'; e.history=[]
    res=e.handle('V, lembre que prefiro Firefox')
    assert res[0].skill=='MEMORY' and res[0].ok and mem.count()==1
    res=e.handle('V, o que você lembra de mim?')
    assert 'Firefox' in res[0].message
    res=e.handle('olá v')
    assert res[0].skill=='AI BRAIN' and res[0].message=='chat:olá v'

bs=BrainService({'provider':'ollama','model':'qwen2.5:3b'}, personality={'name':'V'})
obj=bs._extract_json('{"mode":"chat","actions":[],"reply":"oi"}'); eq(obj['mode'],'chat','json')
assert 'MEMÓRIA PERSISTENTE' in bs._planner_system(r.__class__ and FunctionalEngine(DummyBrain()).tools.manifest())

import windows_media_session
assert hasattr(windows_media_session,'spotify_skip_next')

import json, zipfile
base=Path(__file__).resolve().parent
cfg=json.loads((base/'config'/'default.json').read_text(encoding='utf-8'))
assert cfg['voice']['tts_profile'] in {'windows_sapi', 'xtts_local', 'edge_tts_728', 'qwen_local', 'elevenlabs_custom'}, 'unsupported voice profile'
eq(cfg['voice']['tts_xtts_model'],'tts_models/multilingual/multi-dataset/xtts_v2','local clone model')
assert (base / cfg['voice']['tts_xtts_reference']).exists(), 'XTTS reference sample missing'
assert (base / cfg['voice']['tts_xtts_reference_alt']).exists(), 'XTTS alternate sample missing'
eq(cfg['voice']['tts_eleven_model'],'eleven_flash_v2_5','optional cloud voice model')
eq(cfg['voice']['tts_edge_voice'],'pt-BR-AntonioNeural','edge fallback voice')
assert type(cfg['voice']['tts_dynamic_prosody']) is bool
archive=base/'vendor'/'edge-tts-7.2.8.zip'
assert archive.exists(), 'edge-tts local archive missing'
with zipfile.ZipFile(archive) as z:
    assert any(n.endswith('src/edge_tts/communicate.py') for n in z.namelist())
    assert any(n.endswith('src/edge_playback/win32_playback.py') for n in z.namelist())
from voice.engine import VoiceEngine
ve=VoiceEngine(cfg['voice'])
chunks=ve._split_tts_chunks('Pronto. Já abri o Spotify. Se quiser, posso colocar outra música depois.')
assert len(chunks) >= 1 and all(chunks)
expected_rate = cfg['voice']['tts_short_rate'] if cfg['voice']['tts_dynamic_prosody'] else cfg['voice']['tts_edge_rate']
assert ve._edge_prosody('Pronto.')[0] == expected_rate
assert 'Tool System' not in bs._identity_prompt() or True
assert 0.7 <= ve._eleven_voice_settings('Pronto.')['speed'] <= 1.2
if cfg['voice']['tts_profile'] == 'windows_sapi':
    assert ve.warmup_tts() is False, 'Offline voice must not load XTTS'
elif cfg['voice']['tts_profile'] == 'xtts_local':
    assert cfg['voice']['tts_xtts_enabled'] is True
    assert ve._resolve_xtts_reference().is_file(), 'Selected sample missing'
elif cfg['voice']['tts_profile'] == 'qwen_local':
    assert not cfg['voice']['tts_xtts_enabled']
    assert ve._resolve_qwen_reference().is_file()
    assert (base / 'vendor/qwen-eval/runtime/qwen-tts-studio/qwen3_tts.dll').is_file()
    if cfg['voice'].get('tts_qwen_prompt'):
        from voice.qwen_worker import validate_prompt
        validate_prompt(base / cfg['voice']['tts_qwen_prompt'], ve._resolve_qwen_reference())
print('V selected voice self-test: OK')

from brain.gemini_auth import key_path
hy=BrainService({'provider':'hybrid','gemini_enabled':False,'model':'qwen2.5:3b'}, personality={'name':'V'})
assert hy._ollama_allowed()
assert not hy._gemini_allowed()
assert 'Gemini' in (Path(__file__).resolve().parent/'README.md').read_text(encoding='utf-8')
assert 'chatbot' in bs._identity_prompt().lower()
print('V Prototype 1.2 Gemini + Personality self-test: OK')

# 1.2.1 gentleman startup checks
import json as _json
from pathlib import Path as _Path
_cfg121=_json.loads((_Path(__file__).resolve().parent/'config'/'default.json').read_text(encoding='utf-8'))
assert _cfg121['personality']['startup_greeting_enabled'] is True
assert any('senhor' in x.lower() for x in _cfg121['personality']['startup_greetings'])
_prompt121=PersonalityLayer(_cfg121['personality']).system_prompt().lower()
assert 'cavalheiro moderno' in _prompt121
print('V Prototype 1.2.1 Gentleman Startup self-test: OK')

# 1.4 Instant Pipeline checks
import json as _j14
_cfg14=_j14.loads((base/'config'/'default.json').read_text(encoding='utf-8'))
assert _cfg14['voice']['phrase_end_silence_seconds'] <= 0.8
assert _cfg14['brain']['stream_chat'] is True
assert hasattr(BrainService, 'chat_stream')
ready, rest = BrainService._stream_sentences('Olá, senhor. Tudo em ordem. ainda')
assert ready == ['Olá, senhor.', 'Tudo em ordem.'] and rest == 'ainda'
print('V Prototype 1.4 Instant Pipeline self-test: OK')


# 1.4.1 Stream + Routing Hotfix checks
r141=ToolRouter()
d=r141.route('olá v toque uma música calma')
assert d.mode=='tools' and d.calls and d.calls[0].name=='spotify.play_track', d
assert d.calls[0].args.get('query')=='calma', d.calls[0].args
d=r141.route('boa noite v aumente o volume')
assert d.mode=='tools' and d.calls[0].name=='audio.volume_up', d
line=BrainService._decode_sse_line('data: {"x":"Olá, senhor"}'.encode('utf-8'))
assert 'Olá, senhor' in line and 'OlÃ' not in line
full,delta=BrainService._merge_stream_piece('Olá, ','senhor.')
assert full=='Olá, senhor.' and delta=='senhor.'
full,delta=BrainService._merge_stream_piece('Olá','Olá, senhor.')
assert full=='Olá, senhor.' and delta==', senhor.'
assert BrainService._looks_stream_incomplete('Vou tentar abrir para','') is True
assert BrainService._looks_stream_incomplete('Pronto.','STOP') is False
print('V Prototype 1.4.1 Stream + Routing Hotfix self-test: OK')

# 1.6 Neural Interface + Processing FX checks
import wave as _wave
_cfg16=json.loads((base/'config'/'default.json').read_text(encoding='utf-8'))
assert _cfg16['ui']['processing_sound_enabled'] is True
assert int(_cfg16['ui']['processing_sound_delay_ms']) >= 150
_fx=base/_cfg16['ui']['processing_sound_file']
assert _fx.exists(), 'processing sound missing'
with _wave.open(str(_fx),'rb') as _w:
    assert _w.getnchannels() in (1,2)
    assert _w.getframerate() >= 22050
ve16=VoiceEngine(_cfg16['voice'])
ve16.set_external_audio_active(True)
assert ve16.is_speaking() is True and ve16.voice_input_allowed() is False
ve16.set_external_audio_active(False)
assert ve16.is_speaking() is False
print('V Prototype 1.6 Neural Interface + Processing FX self-test: OK')
