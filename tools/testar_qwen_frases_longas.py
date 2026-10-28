
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
"""Generate long-form listening samples locally without changing V's main voice."""
from pathlib import Path
import html
import json
import threading
import time

import numpy as np
import soundfile as sf

from voice.engine import VoiceEngine
from voice.qwen_backend import QwenBackend
from voice.qwen_worker import validate_prompt
from voice.news_speech import news_text
from voice.robot_effect import process_audio
from voice.qwen_audio import shorten_phrase_silence

ROOT = _ROOT
CASES = [
    ('conversa', 'Conversa longa',
     'Bom dia. Antes de começar, quero organizar suas prioridades com calma e explicar o que vou fazer. '
     'Primeiro, vou separar os compromissos importantes, conferir as tarefas que ficaram pendentes e apresentar um resumo claro, sem repetir informações desnecessárias. '
     'Se alguma conexão falhar, vou dizer exatamente o que aconteceu, preservar o restante do seu pedido e continuar com as funções disponíveis. '
     'Não vou apagar seus arquivos nem enviar mensagens sem uma solicitação sua. '
     'Enquanto você trabalha, posso ajudar com pesquisas, música e lembretes, mas quero que minha voz continue natural do começo ao fim, com pausas confortáveis e sem cortar as últimas palavras. '
     'Quando quiser mudar de assunto, basta me chamar e dizer qual será o próximo passo.'),
    ('noticia', 'Notícia fictícia: números e nomes brasileiros',
     'Esta é uma notícia fictícia, criada apenas para testar a voz. '
     'Em 02/10/2026, uma equipe de pesquisadores de São Paulo apresentou a 3ª etapa de um projeto sobre transporte urbano. '
     'No cenário simulado, o tempo médio de espera diminuiu 12,5%, enquanto 1.250 participantes responderam ao questionário. '
     'A pesquisadora Mariana Gonçalves explicou que os resultados de Belo Horizonte, Brasília e Florianópolis ainda precisam de revisão. '
     'Segundo ela, uma porcentagem isolada não permite concluir que todas as cidades tiveram a mesma melhora. '
     'Os próximos testes vão comparar diferentes horários, verificar a qualidade das medições e publicar uma explicação acessível para quem utiliza o transporte todos os dias.'),
]


def main():
    config = json.loads((ROOT/'config/default.json').read_text(encoding='utf-8'))['voice']
    output = ROOT/'logs'/('qwen_longos_' + time.strftime('%Y%m%d_%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    reference = ROOT/config['tts_qwen_reference']
    prompt = ROOT/config['tts_qwen_prompt']
    validate_prompt(prompt, reference)
    backend = QwenBackend(config)
    splitter = VoiceEngine(config)
    report = {'active_voice_unchanged': config.get('tts_profile'),
              'method': 'local Qwen, conservative opening clause and silence trimming; joined WAVs without simulated network/playback gaps',
              'reference': reference.name, 'cases': []}
    print('Output:', output, flush=True)
    started = time.perf_counter()
    try:
        print('Loading and warming Qwen locally...', flush=True)
        backend.prepare(reference)
        report['prepare_seconds'] = round(time.perf_counter()-started, 3)
        print('Warmup seconds:', report['prepare_seconds'], flush=True)
        for key, title, original in CASES:
            text = news_text(original) if key == 'noticia' else original
            chunks = splitter._split_qwen_response(text)
            entry = {'id': key, 'title': title, 'original_text': original, 'spoken_text': text,
                     'chunks': [], 'files': {}}
            parts, effected = [], []
            for i, chunk in enumerate(chunks):
                start = time.perf_counter()
                path = backend.synthesize(chunk, reference, threading.Event())
                generation = time.perf_counter()-start
                try:
                    audio, rate = sf.read(path, dtype='float32')
                finally:
                    Path(path).unlink(missing_ok=True)
                if rate != 24000 or not audio.size or not np.isfinite(audio).all():
                    raise RuntimeError('Invalid generated audio')
                original_frames = len(audio)
                audio = shorten_phrase_silence(audio, rate)
                parts.append(audio)
                effected.append(process_audio(audio, rate, config.get('tts_robot_intensity', .35)))
                duration = len(audio)/rate
                entry['chunks'].append({'text': chunk, 'generation_seconds': round(generation,3),
                                        'audio_seconds': round(duration,3),
                                        'trimmed_silence_ms': round((original_frames-len(audio))*1000/rate, 1),
                                        'cache_hit': bool(backend.last_metrics.get('cache_hit'))})
                print(f'{key}: chunk {i+1}/{len(chunks)}, generation {generation:.2f}s, audio {duration:.2f}s', flush=True)
            for variant, arrays in [('natural', parts), ('efeito_atual', effected)]:
                audio = np.concatenate(arrays)
                target = output/f'{key}_{variant}.wav'
                sf.write(target, audio, 24000, subtype='PCM_16')
                entry['files'][variant] = target.name
            entry['audio_seconds'] = round(sum(len(a) for a in parts)/24000,3)
            entry['generation_seconds'] = round(sum(c['generation_seconds'] for c in entry['chunks']),3)
            entry['first_chunk_seconds'] = entry['chunks'][0]['generation_seconds']
            entry['generation_to_audio_ratio'] = round(entry['generation_seconds']/entry['audio_seconds'],3)
            report['cases'].append(entry)
            (output/'resultado.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        backend.close()
    sections = []
    for entry in report['cases']:
        players = ''.join(f'<h3>{label}</h3><audio controls preload="metadata" src="{entry["files"][key]}"></audio>'
                          for key,label in [('natural','A · Qwen sem efeito'),('efeito_atual','B · Mesmo áudio com o efeito atual')])
        sections.append(f'<section><h2>{html.escape(entry["title"])}</h2><p>{html.escape(entry["spoken_text"])}</p>'
                        f'{players}<p>Duração: {entry["audio_seconds"]:.1f} s · geração: {entry["generation_seconds"]:.1f} s · '
                        f'primeiro trecho após aquecimento: {entry["first_chunk_seconds"]:.1f} s</p>'
                        f'<p>Razão geração/áudio: {entry["generation_to_audio_ratio"]:.2f}. '
                        'Acima de 1 significa que a geração total demorou mais que a fala; o uso ao vivo pode ter pausas.</p></section>')
    page = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>V · Teste longo Qwen</title><style>body{margin:40px auto;max-width:900px;padding:0 22px;background:#081323;color:#d8ecfa;font:17px/1.6 Segoe UI,Arial}h1,h2{color:#76dfec}section{background:#102237;padding:25px;border-radius:16px;margin:24px 0}audio{width:100%}p{color:#b9cbdc}small{color:#ffce87}</style>
    <h1>V / Qwen em frases longas</h1><p>Compare pronúncia, sotaque, pausas e estabilidade até o final. A versão B usa exatamente a mesma geração da versão A, com o efeito robótico aplicado depois.</p>
    <small>Teste local. A voz principal não foi trocada. Os WAVs juntam trechos já gerados; a reprodução ao vivo pode ter esperas adicionais. Notícias e números são fictícios.</small>'''
    (output/'OUVIR.html').write_text(page+''.join(sections)+'</html>', encoding='utf-8')
    print('DONE:', output/'OUVIR.html', flush=True)


if __name__ == '__main__':
    main()
