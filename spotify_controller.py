import ctypes
import os
import re
import time
import unicodedata
from ctypes import wintypes
from pathlib import Path
from urllib.parse import quote_plus


def _norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'\s+', ' ', text).strip().lower()
    return text


def split_track_artist(query):
    q = str(query or '').strip()
    if not q:
        return '', ''
    m = re.match(r'^(.+?)\s+(?:do|da)\s+(.+)$', q, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return q, ''


def build_precise_query(query):
    track, artist = split_track_artist(query)
    if artist:
        return f'track:{track} artist:{artist}', track, artist
    return track, track, ''


def _uia_available():
    try:
        import pywinauto  # noqa: F401
        return True
    except Exception:
        return False


def _element_text(el):
    values = []
    try:
        v = el.window_text()
        if v:
            values.append(str(v))
    except Exception:
        pass
    try:
        info = el.element_info
        for attr in ('name', 'rich_text', 'automation_id'):
            v = getattr(info, attr, None)
            if v:
                values.append(str(v))
    except Exception:
        pass
    return ' | '.join(dict.fromkeys(values))


def _control_type(el):
    try:
        return str(el.element_info.control_type or '').lower()
    except Exception:
        return ''


def _safe_descendants(root):
    try:
        return root.descendants()
    except Exception:
        return []


def _safe_parent(el):
    try:
        return el.parent()
    except Exception:
        return None


def _rect(el):
    try:
        r = el.rectangle()
        return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        return None


def _visible_rect(rect):
    if not rect:
        return False
    l, t, r, b = rect
    return r > l and b > t and r > 0 and b > 0


def _nearby_has_artist(el, artist):
    wanted = _norm(artist)
    if not wanted:
        return True
    cur = el
    for _ in range(4):
        if cur is None:
            break
        if wanted in _norm(_element_text(cur)):
            return True
        for d in _safe_descendants(cur)[:100]:
            if wanted in _norm(_element_text(d)):
                return True
        cur = _safe_parent(cur)
    return False


def _find_exact_title(root, track, artist=''):
    """Encontra o ELEMENTO EXATO do título da faixa.

    Esta é a estratégia que já funcionou no V 2.4. Não calcula um ponto
    genérico da linha: usa o retângulo do próprio título exposto pela UIA.
    """
    wanted_track = _norm(track)
    wanted_artist = _norm(artist)
    if not wanted_track:
        return None

    candidates = []
    for el in _safe_descendants(root):
        txt = _norm(_element_text(el))
        if not txt:
            continue
        exact = txt == wanted_track
        prefix = txt.startswith(wanted_track + ' |') or txt.startswith(wanted_track + ',')
        if not (exact or prefix):
            continue
        if wanted_artist and not _nearby_has_artist(el, wanted_artist):
            continue
        rect = _rect(el)
        if not _visible_rect(rect):
            continue
        l, t, r, b = rect
        w, h = r - l, b - t
        # Evita containers gigantes; título/label normalmente é compacto.
        if h > 140 or w > 1200:
            continue
        ctype = _control_type(el)
        score = 0
        if exact:
            score += 100
        else:
            score += 75
        if ctype in ('text', 'hyperlink', 'custom', 'listitem', 'dataitem'):
            score += 20
        if 14 <= h <= 80:
            score += 20
        if wanted_artist and wanted_artist in txt:
            score += 10
        candidates.append((score, w * h, el))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]


def _foreground_hwnd():
    if os.name != 'nt':
        return None
    try:
        return int(ctypes.windll.user32.GetForegroundWindow()) or None
    except Exception:
        return None


def _root_hwnd_at_point(x, y):
    if os.name != 'nt':
        return None
    try:
        pt = wintypes.POINT(int(x), int(y))
        child = ctypes.windll.user32.WindowFromPoint(pt)
        if not child:
            return None
        GA_ROOT = 2
        root = ctypes.windll.user32.GetAncestor(child, GA_ROOT)
        return int(root or child)
    except Exception:
        return None


def _spotify_foreground_matches(hwnd):
    fg = _foreground_hwnd()
    if not fg or not hwnd:
        return False
    if int(fg) == int(hwnd):
        return True
    try:
        GA_ROOT = 2
        fg_root = ctypes.windll.user32.GetAncestor(int(fg), GA_ROOT)
        hwnd_root = ctypes.windll.user32.GetAncestor(int(hwnd), GA_ROOT)
        return int(fg_root or fg) == int(hwnd_root or hwnd)
    except Exception:
        return False


def _force_foreground(hwnd):
    if os.name != 'nt' or not hwnd:
        return False
    user32 = ctypes.windll.user32
    try:
        SW_RESTORE = 9
        user32.ShowWindow(int(hwnd), SW_RESTORE)
        # ALT neutro ajuda o Windows a liberar SetForegroundWindow.
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(int(hwnd))
        for _ in range(10):
            time.sleep(0.08)
            if _spotify_foreground_matches(hwnd):
                return True
    except Exception:
        pass
    return _spotify_foreground_matches(hwnd)


def _win32_double_click(x, y):
    """Duplo clique real via user32.mouse_event.

    PyAutoGUI conseguia mover o cursor no PC do usuário, mas aparentemente o
    Spotify não recebia o evento de clique. Este caminho usa a API Win32
    diretamente e envia DOWN/UP duas vezes.
    """
    if os.name != 'nt':
        return False
    user32 = ctypes.windll.user32
    try:
        if not user32.SetCursorPos(int(x), int(y)):
            return False
        time.sleep(0.10)
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        for _ in range(2):
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.045)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.105)
        return True
    except Exception:
        return False


def _pywinauto_double_click(x, y):
    try:
        from pywinauto import mouse
        mouse.double_click(button='left', coords=(int(x), int(y)), double_click_interval=0.12)
        return True
    except Exception:
        return False


def _pyautogui_manual_double_click(x, y):
    try:
        import pyautogui
        pyautogui.moveTo(int(x), int(y), duration=0.08)
        for _ in range(2):
            pyautogui.mouseDown(button='left')
            time.sleep(0.05)
            pyautogui.mouseUp(button='left')
            time.sleep(0.11)
        return True
    except Exception:
        return False


def _title_click_point(title_el):
    rect = _rect(title_el)
    if not _visible_rect(rect):
        return None
    l, t, r, b = rect
    w = max(1, r - l)
    h = max(1, b - t)
    # Clica dentro do próprio texto da faixa, próximo ao começo, e não numa
    # coluna calculada da linha. Margem evita borda/ícones.
    x = l + max(8, min(28, int(w * 0.18)))
    y = t + int(h / 2)
    x = min(max(l + 3, x), r - 3)
    y = min(max(t + 3, y), b - 3)
    return x, y


def _now_playing_matches(root, track, artist=''):
    """Tenta confirmar a faixa na barra inferior do Spotify.

    A busca também contém o título; por isso só consideramos elementos na
    faixa inferior da janela (onde fica o player atual).
    """
    wanted_track = _norm(track)
    wanted_artist = _norm(artist)
    root_rect = _rect(root)
    if not root_rect:
        return False
    _rl, rt, _rr, rb = root_rect
    height = max(1, rb - rt)
    cutoff = rb - max(150, int(height * 0.22))

    title_hits = []
    artist_hits = []
    for el in _safe_descendants(root):
        rect = _rect(el)
        if not rect or rect[1] < cutoff:
            continue
        txt = _norm(_element_text(el))
        if not txt:
            continue
        if txt == wanted_track or txt.startswith(wanted_track + ' |') or txt.startswith(wanted_track + ','):
            title_hits.append(el)
        if wanted_artist and (txt == wanted_artist or wanted_artist in txt):
            artist_hits.append(el)
    if not title_hits:
        return False
    if not wanted_artist:
        return True
    # Artista pode não ser exposto no player em alguns builds. Se o título
    # está na barra inferior, já é evidência forte; artista é bônus.
    return bool(artist_hits) or bool(title_hits)


def _refresh_root(app, hwnd):
    try:
        return app.window(handle=int(hwnd))
    except Exception:
        return None


def _verify_after_click(app, hwnd, track, artist, timeout=1.8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        root = _refresh_root(app, hwnd)
        if root is not None and _now_playing_matches(root, track, artist):
            return True
        time.sleep(0.25)
    return False


def _dump_click_log(root, track, artist, hwnd, title_el=None, click_point=None, methods=None):
    try:
        base = Path(__file__).resolve().parent
        log_dir = base / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        p = log_dir / 'spotify_click_last.txt'
        lines = [
            f'TRACK={track}',
            f'ARTIST={artist}',
            f'SPOTIFY_HWND={hwnd}',
            f'FOREGROUND_HWND={_foreground_hwnd()}',
            f'CLICK_POINT={click_point}',
            f'WINDOW_AT_POINT={_root_hwnd_at_point(*(click_point or (0, 0)))}',
            f'METHODS={methods or []}',
            f'TITLE_TEXT={_element_text(title_el) if title_el is not None else ""}',
            f'TITLE_RECT={_rect(title_el) if title_el is not None else None}',
            '',
            '--- UIA RELEVANTE ---',
        ]
        wanted = [_norm(track), _norm(artist)]
        for i, el in enumerate(_safe_descendants(root)[:1400]):
            txt = _element_text(el)
            nt = _norm(txt)
            if not txt or not any(x and x in nt for x in wanted):
                continue
            lines.append(f'{i:04d} | {_control_type(el):12s} | {_rect(el)!s:28s} | {txt}')
        p.write_text('\n'.join(lines), encoding='utf-8')
        return str(p)
    except Exception:
        return ''


def play_exact_track(hwnd, query, activate_callback, foreground_callback, type_callback,
                     shell_open_callback):
    """Pesquisa e reproduz a faixa usando o título exato + input Win32.

    0.6.4 volta à estratégia que funcionou no V 2.4 para ENCONTRAR a faixa,
    mas troca o clique por um caminho de input de baixo nível e verifica o
    player inferior antes de declarar sucesso.
    """
    precise, track, artist = build_precise_query(query)

    if not activate_callback():
        target = 'spotify:search:' + quote_plus(precise)
        if shell_open_callback(target):
            return False, f'Abri a busca exata por {query}, mas não consegui confirmar o foco do Spotify.'
        return False, 'Não consegui ativar o Spotify.'

    # O handle recebido pode ser antigo após restore; o foreground atual é a
    # melhor referência imediatamente após activate_callback().
    current_hwnd = _foreground_hwnd() or hwnd
    if not current_hwnd or not foreground_callback():
        return False, 'O Spotify não ficou em primeiro plano; cancelei a automação.'

    try:
        import pyautogui
        pyautogui.hotkey('ctrl', 'k')
        time.sleep(0.35)
        if not foreground_callback():
            return False, 'O Spotify perdeu o foco antes da pesquisa.'
        pyautogui.hotkey('ctrl', 'a')
        if not type_callback(precise):
            return False, 'Não consegui digitar a busca no Spotify.'
        pyautogui.press('enter')
    except Exception as exc:
        return False, f'Falha ao pesquisar no Spotify: {exc}'

    time.sleep(1.7)

    if not _uia_available():
        return False, 'pywinauto não está disponível. Rode configurar_prototype.bat.'

    try:
        from pywinauto import Application
        # Depois da busca, recaptura novamente o HWND real em primeiro plano.
        current_hwnd = _foreground_hwnd() or current_hwnd
        app = Application(backend='uia').connect(handle=int(current_hwnd), timeout=5)
    except Exception as exc:
        return False, f'Não consegui conectar à interface do Spotify: {exc}'

    deadline = time.time() + 7.0
    last_root = None
    last_title = None
    while time.time() < deadline:
        if not foreground_callback():
            # Tenta recuperar foco uma vez, em vez de abandonar a faixa.
            if not _force_foreground(current_hwnd):
                return False, 'O Spotify perdeu o foco durante a busca.'
        last_root = _refresh_root(app, current_hwnd)
        if last_root is None:
            time.sleep(0.35)
            continue

        # Se já estiver tocando esta faixa, não precisa clicar novamente.
        if _now_playing_matches(last_root, track, artist):
            who = f' de {artist}' if artist else ''
            return True, f'{track}{who} já está tocando no Spotify.'

        title_el = _find_exact_title(last_root, track, artist)
        if title_el is None:
            time.sleep(0.45)
            continue
        last_title = title_el
        point = _title_click_point(title_el)
        if point is None:
            time.sleep(0.35)
            continue
        x, y = point

        if not _force_foreground(current_hwnd):
            return False, 'Encontrei a faixa, mas não consegui manter o Spotify em primeiro plano.'

        # Confirma que o ponto está realmente sobre a janela Spotify/root.
        over_hwnd = _root_hwnd_at_point(x, y)
        methods = []

        # 1) Win32 user32: caminho principal.
        methods.append('win32_mouse_event')
        if _win32_double_click(x, y):
            if _verify_after_click(app, current_hwnd, track, artist, timeout=1.7):
                who = f' de {artist}' if artist else ''
                return True, f'Tocando {track}{who} no Spotify.'

        # 2) pywinauto mouse: usa outro mecanismo de injeção de input.
        _force_foreground(current_hwnd)
        methods.append('pywinauto_mouse')
        if _pywinauto_double_click(x, y):
            if _verify_after_click(app, current_hwnd, track, artist, timeout=1.5):
                who = f' de {artist}' if artist else ''
                return True, f'Tocando {track}{who} no Spotify.'

        # 3) PyAutoGUI manual DOWN/UP, não doubleClick abstrato.
        _force_foreground(current_hwnd)
        methods.append('pyautogui_manual')
        if _pyautogui_manual_double_click(x, y):
            if _verify_after_click(app, current_hwnd, track, artist, timeout=1.5):
                who = f' de {artist}' if artist else ''
                return True, f'Tocando {track}{who} no Spotify.'

        # 4) Último fallback: o próprio wrapper do elemento exato, método que
        # funcionou no V 2.4. Reobtém o elemento antes de clicar.
        root2 = _refresh_root(app, current_hwnd)
        title2 = _find_exact_title(root2, track, artist) if root2 is not None else None
        if title2 is not None:
            methods.append('uia_double_click_input')
            try:
                title2.double_click_input()
                if _verify_after_click(app, current_hwnd, track, artist, timeout=1.5):
                    who = f' de {artist}' if artist else ''
                    return True, f'Tocando {track}{who} no Spotify.'
            except Exception:
                pass

        root_log = _refresh_root(app, current_hwnd) or last_root
        path = _dump_click_log(root_log, track, artist, current_hwnd, title2 or title_el, point, methods)
        return False, (
            f'Encontrei {track} e enviei quatro métodos de duplo clique, mas não consegui confirmar a troca da faixa. '
            f'Diagnóstico salvo em {path or "logs\\spotify_click_last.txt"}.'
        )

    root_log = last_root or _refresh_root(app, current_hwnd)
    path = _dump_click_log(root_log, track, artist, current_hwnd, last_title, None, ['no_exact_title']) if root_log is not None else ''
    who = f' / artista {artist}' if artist else ''
    return False, (
        f'Pesquisei {track}{who}, mas não encontrei o título exato na árvore do Spotify. '
        f'Diagnóstico salvo em {path or "logs\\spotify_click_last.txt"}.'
    )
