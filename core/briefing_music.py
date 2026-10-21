"""Start the configured Spotify playlist in shuffle mode for the briefing."""
import json
from pathlib import Path
import re

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'briefing_music.json'


def configured_playlist():
    if not CONFIG_PATH.exists():
        return ''
    return str(json.loads(CONFIG_PATH.read_text(encoding='utf-8')).get('playlist_uri', ''))


def start_music(command=None, playlist_uri=None, volume_limit=.15):
    from .daily_briefing import card
    if command is None:
        from spotify_bridge import command
    def unavailable(message):
        return card('música', 'Música indisponível', message,
                    source='Spotify · música do bom dia', ok=False)
    try:
        playlist_uri = configured_playlist() if playlist_uri is None else playlist_uri
        if playlist_uri and not re.fullmatch(r'spotify:playlist:[A-Za-z0-9]{22}', playlist_uri):
            return unavailable('A playlist do bom dia está configurada com um endereço inválido.')
        ok, result = command('status', timeout=3, launch_if_needed=True)
        if not ok:
            return unavailable('Não consegui conectar ao Spotify. O resumo vai continuar sem música.')
        state = result.get('status') or {}
        if not playlist_uri and not str(state.get('uri') or '').startswith('spotify:track:'):
            return unavailable('Escolha uma playlist e toque uma música no Spotify antes do bom dia. Vou usar essa seleção como base.')
        # Only lower Spotify's own volume, preserving a quieter user setting.
        volume = float(state.get('volume', 0.15))
        actions = [('volume', {'level': max(0, min(volume, float(volume_limit), 1.0))})]
        if playlist_uri:
            actions.append(('play_uri', {'uri': playlist_uri}))
        actions.extend([('shuffle', {'enabled': True}), ('next', {}), ('play', {})])
        for action, args in actions:
            ok, result = command(action, args, timeout=3)
            if not ok:
                return unavailable('Não consegui concluir o início da música. O resumo vai continuar; confira o Spotify.')
        state = result.get('status') or {}
        if not state.get('playing') or not str(state.get('uri') or '').startswith('spotify:track:'):
            return unavailable('Enviei o pedido ao Spotify, mas não consegui confirmar uma música tocando.')
        if playlist_uri and state.get('context_uri') != playlist_uri:
            return unavailable('Não consegui confirmar a playlist do bom dia no Spotify. Confira o aplicativo.')
        if not state.get('shuffle'):
            return unavailable('Não consegui confirmar o modo aleatório no Spotify. Confira o aplicativo.')
        title = state.get('title') or 'Música da sua fila'
        artist = state.get('artist') or ''
        return card('música', title, f'{title}' + (f' — {artist}' if artist else '')
                    + ('. Playlist do bom dia em modo aleatório.' if playlist_uri else '. Seleção atual do Spotify em modo aleatório.'),
                    speech='Música iniciada a partir da sua seleção no Spotify.',
                    source='Spotify · aleatório', url=playlist_uri.replace('spotify:playlist:', 'https://open.spotify.com/playlist/') if playlist_uri else '')
    except Exception:
        return unavailable('Não consegui iniciar a música agora. Vou continuar com o resumo.')
