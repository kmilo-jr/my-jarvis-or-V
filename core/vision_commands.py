"""Camera intent matching without loading imaging libraries."""
import re
import unicodedata

def vision_command(text):
    """Narrow allowlist: unrelated commands and negations keep their normal route."""
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9 ]', '', text).strip()
    text = re.sub(r'\s+', ' ', text)
    groups = {
        'open': {'abrir camera', 'abra a camera', 'abrir a camera', 'ligar camera', 'ligar a camera',
                 'ligue a camera', 'ativar camera', 'ative a camera'},
        'close': {'fechar camera', 'feche a camera', 'desligar camera', 'desligar a camera',
                  'desligue a camera', 'desativar camera', 'desative a camera'},
        'detect': {'o que voce esta vendo', 'o que voce ve', 'voce esta me vendo',
                   'voce consegue me ver', 'reconhecer objetos', 'reconheca os objetos',
                   'identificar objetos', 'identifique os objetos', 'o que tem na camera'},
        'describe': {'descreva a imagem', 'descreva o que esta vendo', 'analise a imagem',
                     'leia o texto na camera', 'leia o texto da camera'},
    }
    return next((action for action, phrases in groups.items() if text in phrases), None)

