"""Safe explanations derived from error codes, never raw service responses."""
import re


def _reasons(raw):
    codes = set(re.findall(r'\b(?:401|403|429|500|502|503|504)\b', raw))
    reasons = []
    if '401' in codes:
        reasons.append('Uma credencial foi recusada. Confira a chave do serviço na configuração.')
    if '403' in codes:
        reasons.append('Um serviço negou acesso. Confira as permissões da conta e do modelo.')
    if '429' in codes:
        reasons.append('Um serviço atingiu o limite de uso. Aguarde antes de tentar novamente.')
    if codes & {'500', '502', '503', '504'}:
        reasons.append('Um serviço está indisponível. Tente novamente mais tarde.')
    if 'timeout' in raw.lower() or 'timed out' in raw.lower():
        reasons.append('Um serviço demorou além do limite. Confira a conexão e tente novamente.')
    if not reasons:
        reasons.append('Não consegui concluir o pedido. Abra Conexões para testar os serviços e conferir a configuração.')
    return ' '.join(reasons)


def explain(error):
    raw = str(error or '')
    parts = re.split(r'\b(Groq|Gemini|Ollama|Gmail|Spotify)\b', raw, flags=re.I)
    labels = {name.lower(): name for name in ('Groq', 'Gemini', 'Ollama', 'Gmail', 'Spotify')}
    segments = {}
    for index in range(1, len(parts), 2):
        name = labels[parts[index].lower()]
        segments[name] = segments.get(name, '') + ' ' + parts[index + 1]
    message = '\n'.join(name + ': ' + _reasons(segment) for name, segment in segments.items()) if segments else _reasons(raw)
    return {'message': message, 'services': list(segments),
            'actions': ['Testar conexões', 'Abrir configuração'],
            'speech_text': message}
