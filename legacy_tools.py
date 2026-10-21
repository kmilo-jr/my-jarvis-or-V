import os
import re
import subprocess
import webbrowser
import datetime
import shutil
import unicodedata
import ctypes
from ctypes import wintypes
import time
from pathlib import Path
from urllib.parse import quote_plus

import psutil
import pyautogui

from web_research import news_brief, research_brief, last_sources

try:
    import pygetwindow as gw
except Exception:
    gw = None



# Teclas multimidia nativas do Windows. Elas controlam a sessao de midia ativa
# (Spotify, YouTube no navegador, VLC etc.) sem depender da IA.
_MEDIA_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}

def _press_media_key(action):
    vk = _MEDIA_KEYS.get(action)
    if not vk or os.name != "nt":
        return False
    try:
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.04)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False

def media_control(action):
    messages = {
        "play_pause": "Pronto.",
        "next": "Avançando para a próxima faixa.",
        "previous": "Voltando para a faixa anterior.",
        "stop": "Parando a reprodução.",
        "mute": "Alternando o mudo do sistema.",
    }
    # Se o Spotify Desktop estiver aberto, o Spicetify Bridge é o transporte
    # preferido. Foi validado no PC do usuário para play/pause/next/previous.
    if action in ("play_pause", "next", "previous"):
        try:
            if _spotify_process_ids():
                from spotify_bridge import control as spotify_bridge_control
                ok, msg = spotify_bridge_control(action)
                if ok:
                    return msg
        except Exception:
            pass
    # Fallback genérico para YouTube/VLC/outros players.
    if _press_media_key(action):
        return messages.get(action, "Comando de mídia enviado.")
    return "Não consegui enviar o comando de mídia ao Windows."

def _spotify_process_ids():
    """Retorna os PIDs do Spotify Desktop em execução."""
    ids = set()
    try:
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = (proc.info.get("name") or "").lower()
                exe = (proc.info.get("exe") or "").lower()
                if name in ("spotify.exe", "spotify") or exe.endswith("\\spotify.exe"):
                    ids.add(int(proc.info["pid"]))
            except Exception:
                pass
    except Exception:
        pass
    return ids


def _spotify_hwnd():
    """Localiza a janela principal do Spotify pelo PID, não pelo título.

    O título do Spotify muda para o nome da música/artista e, por isso,
    procurar simplesmente por uma janela contendo 'Spotify' é pouco confiável.
    """
    if os.name != "nt":
        return None
    pids = _spotify_process_ids()
    if not pids:
        return None

    user32 = ctypes.windll.user32
    candidates = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if int(pid.value) not in pids:
                return True
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = int(rect.right - rect.left)
                h = int(rect.bottom - rect.top)
                if w > 500 and h > 350:
                    candidates.append((w * h, int(hwnd), (rect.left, rect.top, rect.right, rect.bottom)))
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        return None

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _spotify_rect():
    hwnd = _spotify_hwnd()
    if not hwnd or os.name != "nt":
        return None
    try:
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except Exception:
        pass
    return None


def _foreground_pid():
    if os.name != "nt":
        return None
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return None


def _spotify_is_foreground():
    pid = _foreground_pid()
    return pid is not None and pid in _spotify_process_ids()


def _activate_spotify_window():
    """Traz o Spotify para frente e confirma que ele realmente recebeu foco.

    Nunca retorna True apenas porque a chamada de ativação não lançou erro.
    Isso evita que atalhos/digitação vazem para Explorer, navegador ou outro app.
    """
    if os.name != "nt":
        return False
    hwnd = _spotify_hwnd()
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.15)

        # Tenta trazer a janela para frente. O Windows às vezes bloqueia
        # SetForegroundWindow, então também fazemos um ALT neutro antes.
        try:
            pyautogui.press("alt")
        except Exception:
            pass
        user32.SetForegroundWindow(hwnd)

        for _ in range(12):
            time.sleep(0.12)
            if _spotify_is_foreground():
                return True
        return False
    except Exception:
        return False


def _parse_spotify_track_query(query):
    """Separa frases como 'No Surprises do Radiohead' em faixa/artista.

    O objetivo não é adivinhar metadados complexos, apenas reconhecer a forma
    natural mais comum em português. Isso permite usar os filtros nativos do
    Spotify (track:/artist:) e reduz a chance de um álbum virar o resultado
    principal.
    """
    q = str(query or "").strip()
    if not q:
        return "", ""

    # 'X do Y' / 'X da Y' / 'X de Y'. Exigimos conteúdo dos dois lados e
    # usamos a última ocorrência para não quebrar títulos que contenham 'de'.
    m = re.match(r"^(.+?)\s+(?:do|da)\s+(.+)$", q, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return q, ""


def _spotify_search_text(query):
    track, artist = _parse_spotify_track_query(query)
    if artist:
        # A sintaxe de pesquisa do Spotify restringe o resultado ao tipo/faixa
        # e ao artista, evitando que o primeiro resultado seja um álbum.
        return f'track:{track} artist:{artist}'
    return track


def _spotify_click_first_song():
    """Tenta tocar a primeira linha da seção Músicas dos resultados.

    O layout do Spotify Desktop normalmente coloca 'Melhor resultado' à
    esquerda e 'Músicas' à direita. O V evita deliberadamente a coluna da
    esquerda (onde álbuns/artistas podem aparecer) e tenta a primeira linha da
    lista de músicas. Se a janela perder foco, o clique é cancelado.
    """
    if not _spotify_is_foreground():
        return False
    rect = _spotify_rect()
    if rect is None:
        return False
    try:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # Região direita/central onde a seção 'Músicas' aparece no layout
        # desktop. Mantemos distância da coluna 'Melhor resultado'.
        candidates = [
            (0.70, 0.39),
            (0.72, 0.43),
            (0.68, 0.46),
        ]

        for xr, yr in candidates:
            if not _spotify_is_foreground():
                return False
            x = left + int(width * xr)
            y = top + int(height * yr)
            pyautogui.moveTo(x, y, duration=0.12)
            pyautogui.doubleClick(interval=0.10)
            time.sleep(0.9)
            # Um único clique bem posicionado é preferível a continuar
            # clicando em vários resultados. Não há API local confiável para
            # confirmar o URI da faixa sem OAuth, então encerramos aqui.
            return True
        return False
    except Exception:
        return False


def _type_unicode_windows(text):
    """Digita texto sem criar uma segunda instância do Tkinter.

    A versão 1.1 criava um Tk() auxiliar dentro da thread de automação para
    manipular o clipboard. Em algumas instalações do Windows/Tcl isso pode
    encerrar o processo inteiro (Tcl_AsyncDelete / thread errada).
    Para comandos ASCII, como a maioria das buscas musicais, pyautogui.write
    é suficiente. Para Unicode, tentamos o clipboard nativo do Windows via
    win32clipboard, sem tocar no Tkinter da interface.
    """
    value = str(text)

    # Caminho simples e estável para ASCII.
    try:
        value.encode("ascii")
        pyautogui.write(value, interval=0.025)
        return True
    except UnicodeEncodeError:
        pass
    except Exception:
        pass

    if os.name == "nt":
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                old = None
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        old = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                except Exception:
                    old = None
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(value, win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()

            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)

            # Restaura somente texto simples quando havia texto anterior.
            if old is not None:
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(old, win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                except Exception:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass
            return True
        except Exception:
            pass

    # Último fallback: remove acentos apenas para conseguir concluir a busca.
    try:
        safe = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        pyautogui.write(safe, interval=0.025)
        return True
    except Exception:
        return False


def play_music_on_spotify(query=None):
    """Spotify 1.5: busca pela Web API + playback pelo Spicetify Bridge.

    A Web API só resolve título/artista -> URI. O controle real acontece
    dentro do Spotify Desktop oficial via Spicetify.Player.
    """
    if not query:
        if _launch_spotify():
            time.sleep(0.5)
        try:
            from spotify_bridge import control as spotify_bridge_control
            ok, msg = spotify_bridge_control("play_pause")
            if ok:
                return msg
        except Exception:
            pass
        return media_control("play_pause")

    q = str(query).strip()
    if not q:
        return "Não recebi o nome da música para pesquisar no Spotify."
    try:
        from spotify_bridge import play_query
        ok, msg = play_query(q)
        return msg
    except Exception as exc:
        return f"Spotify Bridge falhou antes de controlar a faixa: {exc}"


SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "you tube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "discord web": "https://discord.com/app",
    "spotify web": "https://open.spotify.com",
    "whatsapp web": "https://web.whatsapp.com",
    "github": "https://github.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    "twitch": "https://www.twitch.tv",
    "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com",
}



def _normalize_name(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace(".lnk", "").replace(".url", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _shortcut_roots():
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop",
    ]
    return [r for r in roots if r.exists()]


def _launch_installed_shortcut(name):
    """Procura apps pelos atalhos reais do Menu Iniciar/Desktop do usuário."""
    wanted = _normalize_name(name)
    if not wanted:
        return False
    candidates = []
    for root in _shortcut_roots():
        try:
            for ext in ("*.lnk", "*.url"):
                for item in root.rglob(ext):
                    norm = _normalize_name(item.stem)
                    # Segurança: só aceite correspondências fortes. A versão 4.2
                    # usava sobreposição de palavras e podia transformar frases como
                    # "abra a live do jogo..." em um atalho sem relação (ex.: EA App).
                    if wanted == norm:
                        score = 100
                    elif len(wanted) >= 4 and (wanted in norm or norm in wanted):
                        # Contenção só vale quando o nome menor ainda é significativo.
                        shorter = min(len(wanted), len(norm))
                        score = 80 if shorter >= 4 else 0
                    else:
                        score = 0
                    if score >= 80:
                        candidates.append((score, len(norm), item))
        except Exception:
            continue
    if not candidates:
        return False
    candidates.sort(key=lambda x: (-x[0], x[1]))
    try:
        os.startfile(str(candidates[0][2]))
        return True
    except Exception:
        return False

def _shell_open(target):
    """Abre URL, protocolo ou caminho usando o Shell do Windows."""
    try:
        os.startfile(str(target))
        return True
    except Exception:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
            return True
        except Exception:
            return False


def _first_existing(paths):
    for p in paths:
        if p and Path(p).exists():
            return str(p)
    return None


def _launch_exe(exe, args=None):
    args = args or []
    try:
        subprocess.Popen([str(exe), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _launch_discord():
    local = Path(os.environ.get("LOCALAPPDATA", ""))

    # 1) Instalador padrão do Discord (mais confiável para atualizar e iniciar).
    update = local / "Discord" / "Update.exe"
    if update.exists() and _launch_exe(update, ["--processStart", "Discord.exe"]):
        return True

    # 2) Executável dentro de app-*.
    root = local / "Discord"
    if root.exists():
        candidates = sorted(root.glob("app-*/Discord.exe"), reverse=True)
        for exe in candidates:
            if _launch_exe(exe):
                return True

    # 3) Protocolo registrado no Windows.
    if _shell_open("discord://-/channels/@me"):
        return True

    return False


def _launch_spotify():
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "Spotify.exe",
    ]
    for exe in candidates:
        if exe.exists() and _launch_exe(exe):
            return True
    return _shell_open("spotify:")


def _launch_browser(name):
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")

    paths = {
        "chrome": [
            Path(program_files) / "Google/Chrome/Application/chrome.exe",
            Path(program_files_x86) / "Google/Chrome/Application/chrome.exe",
            Path(local) / "Google/Chrome/Application/chrome.exe",
        ],
        "edge": [
            Path(program_files_x86) / "Microsoft/Edge/Application/msedge.exe",
            Path(program_files) / "Microsoft/Edge/Application/msedge.exe",
        ],
        "firefox": [
            Path(program_files) / "Mozilla Firefox/firefox.exe",
            Path(program_files_x86) / "Mozilla Firefox/firefox.exe",
        ],
    }
    for exe in paths.get(name, []):
        if exe.exists() and _launch_exe(exe):
            return True

    # Também tenta pelo PATH / App Execution Alias.
    aliases = {"chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe"}
    found = shutil.which(aliases.get(name, ""))
    return bool(found and _launch_exe(found))


def open_target(name):
    n = name.lower().strip().strip(" .,!?")
    n = re.sub(r"^(?:o|a|meu|minha)\s+", "", n).strip()

    aliases = {
        "yt": "youtube",
        "you tube": "youtube",
        "discord app": "discord",
        "google chrome": "chrome",
        "mozilla firefox": "firefox",
        "explorer": "explorador",
        "explorador de arquivos": "explorador",
        "arquivos": "explorador",
        "configuracoes": "configurações",
        "zap": "whatsapp",
        "whats": "whatsapp",
        "code": "visual studio code",
        "v s code": "visual studio code",
        "teams": "microsoft teams",
        "epic": "epic games launcher",
        "epic games": "epic games launcher",
        "battle net": "battle.net",
        "py charm": "pycharm",
    }
    n = aliases.get(n, n)

    # Sites: usa o navegador padrão do Windows, preservando login/cookies do usuário.
    if n in SITES:
        if _shell_open(SITES[n]):
            return f"Abrindo {n}."
        if webbrowser.open(SITES[n]):
            return f"Abrindo {n}."
        return f"Não consegui abrir {n} no navegador padrão."

    if n == "discord":
        if _launch_discord():
            return "Abrindo o Discord."
        if _shell_open("https://discord.com/app"):
            return "Não encontrei o aplicativo do Discord. Abri o Discord no navegador."
        return "Não consegui abrir o Discord."

    if n == "spotify":
        if _launch_spotify():
            return "Abrindo o Spotify."
        if _shell_open("https://open.spotify.com"):
            return "Não encontrei o Spotify instalado. Abri o Spotify Web."
        return "Não consegui abrir o Spotify."

    if n == "whatsapp":
        if _shell_open("whatsapp:"):
            return "Abrindo o WhatsApp."
        if _shell_open("https://web.whatsapp.com"):
            return "Abri o WhatsApp Web."
        return "Não consegui abrir o WhatsApp."

    if n in ("chrome", "edge", "firefox"):
        if _launch_browser(n):
            return f"Abrindo o {n}."
        if _shell_open("https://www.google.com"):
            return f"Não encontrei o {n}. Abri o navegador padrão."
        return f"Não consegui abrir o {n}."

    if n in ("bloco de notas", "notepad"):
        return "Abrindo o bloco de notas." if _launch_exe("notepad.exe") else "Não consegui abrir o bloco de notas."

    if n in ("calculadora", "calculator"):
        return "Abrindo a calculadora." if _shell_open("calculator:") or _launch_exe("calc.exe") else "Não consegui abrir a calculadora."

    if n == "explorador":
        return "Abrindo o explorador de arquivos." if _launch_exe("explorer.exe") else "Não consegui abrir o explorador de arquivos."

    if n == "configurações":
        return "Abrindo as configurações." if _shell_open("ms-settings:") else "Não consegui abrir as configurações."

    if n in ("gerenciador de tarefas", "task manager"):
        return "Abrindo o Gerenciador de Tarefas." if _launch_exe("taskmgr.exe") else "Não consegui abrir o Gerenciador de Tarefas."

    if n in ("steam",):
        if _shell_open("steam://open/main"):
            return "Abrindo a Steam."
        return "Não consegui abrir a Steam."

    if n in ("visual studio code", "vs code", "vscode"):
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Microsoft VS Code/Code.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft VS Code/Code.exe",
        ]
        exe = _first_existing(candidates) or shutil.which("code")
        if exe and _launch_exe(exe):
            return "Abrindo o Visual Studio Code."
        if _launch_installed_shortcut("Visual Studio Code"):
            return "Abrindo o Visual Studio Code."
        return "Não encontrei o Visual Studio Code instalado."

    # Integração genérica: encontra qualquer aplicativo que tenha atalho no
    # Menu Iniciar ou Desktop, sem permitir execução arbitrária de comandos.
    if _launch_installed_shortcut(n):
        return f"Abrindo {n}."

    return f"Não encontrei {n} instalado nem um atalho correspondente no Menu Iniciar."


def search(query):
    _shell_open("https://www.google.com/search?q=" + quote_plus(query))
    return f"Pesquisando por {query}."


def youtube_search(query):
    if _shell_open("https://www.youtube.com/results?search_query=" + quote_plus(query)):
        return f"Pesquisando {query} no YouTube."
    return "Não consegui abrir a pesquisa do YouTube."


def youtube_channel(query):
    """Abre a busca do YouTube já filtrada para canais.

    Isso evita mandar pedidos como 'vá no canal da CazéTV' para a IA: o
    próprio V executa a navegação no navegador padrão do Windows.
    """
    q = (query or "").strip().strip(" .,!?")
    q = re.sub(r"^(?:do|da|de|o|a)\s+", "", q, flags=re.I).strip()
    if not q:
        return "Diga o nome do canal que você quer abrir no YouTube."
    # sp=EgIQAg%3D%3D corresponde ao filtro 'Tipo: Canal' do YouTube.
    url = "https://www.youtube.com/results?search_query=" + quote_plus(q) + "&sp=EgIQAg%253D%253D"
    if _shell_open(url):
        return f"Abrindo os canais de {q} no YouTube."
    return f"Não consegui abrir o canal de {q} no YouTube."


def youtube_play(query):
    """Localiza o primeiro resultado real do YouTube e abre o vídeo diretamente."""
    q = (query or "").strip()
    if not q:
        return "Diga o nome da música ou vídeo que você quer tocar no YouTube."
    try:
        import yt_dlp
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": True,
            # O V só precisa do primeiro resultado. Estes limites evitam que
            # uma conexão ruim deixe a interface presa em PROCESSING.
            "playlistend": 1,
            "socket_timeout": 5,
            "retries": 0,
            "extractor_retries": 0,
            "fragment_retries": 0,
            "cachedir": False,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"ytsearch1:{q}", download=False)
        entries = (info or {}).get("entries") or []
        if not entries:
            raise RuntimeError("nenhum resultado")
        first = entries[0]
        video_id = first.get("id")
        url = first.get("webpage_url") or first.get("url")
        if video_id and (not url or not str(url).startswith("http")):
            url = f"https://www.youtube.com/watch?v={video_id}"
        if url and _shell_open(url):
            title = first.get("title") or q
            return f"Abrindo {title} no YouTube."
        raise RuntimeError("não foi possível abrir o vídeo")
    except Exception:
        # Fallback útil: ao menos abre a busca, mas sem fingir que iniciou o vídeo.
        _shell_open("https://www.youtube.com/results?search_query=" + quote_plus(q))
        return (
            f"Não consegui abrir automaticamente o primeiro vídeo de {q}. "
            "Abri a busca no YouTube. Execute configurar.bat para garantir que o yt-dlp esteja instalado."
        )


def _activate_youtube_window():
    """Tenta trazer uma janela do YouTube para frente antes de enviar atalhos."""
    if gw is None:
        return False
    try:
        wins = [w for w in gw.getAllWindows() if w.title and "youtube" in w.title.lower()]
        if not wins:
            return False
        win = wins[0]
        if getattr(win, "isMinimized", False):
            win.restore()
        win.activate()
        time.sleep(0.2)
        return True
    except Exception:
        return False


def youtube_control(action):
    """Controla a aba/janela ativa do YouTube com atalhos nativos do player."""
    # Play/pause também funciona por tecla multimídia mesmo sem localizar a janela.
    if action == "play_pause" and not _activate_youtube_window():
        return media_control("play_pause")

    if not _activate_youtube_window():
        return "Não encontrei uma janela ativa do YouTube. Abra um vídeo primeiro."

    try:
        if action == "play_pause":
            pyautogui.press("k")
            return "Alternando reprodução do YouTube."
        if action == "forward":
            pyautogui.press("l")
            return "Avançando 10 segundos no YouTube."
        if action == "back":
            pyautogui.press("j")
            return "Voltando 10 segundos no YouTube."
        if action == "fullscreen":
            pyautogui.press("f")
            return "Alternando tela cheia no YouTube."
        if action == "mute":
            pyautogui.press("m")
            return "Alternando mudo no YouTube."
        if action == "next":
            pyautogui.hotkey("shift", "n")
            return "Indo para o próximo vídeo do YouTube."
        if action == "previous":
            pyautogui.hotkey("shift", "p")
            return "Voltando ao vídeo anterior do YouTube."
    except Exception:
        pass
    return "Não consegui controlar o YouTube agora."


def system_info():
    cpu = psutil.cpu_percent(interval=0.4)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor)
    bat = psutil.sensors_battery()
    battery = f"{bat.percent:.0f}%" if bat else "N/D"
    return (
        f"CPU {cpu:.0f}%. "
        f"RAM {ram.percent:.0f}%. "
        f"Disco {disk.percent:.0f}% usado. "
        f"Bateria {battery}."
    )


def screenshot():
    try:
        from PIL import ImageGrab
        path = Path.cwd() / ("jarvis_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
        ImageGrab.grab().save(path)
        return f"Captura salva em {path}"
    except Exception:
        return "Não consegui capturar a tela."


def set_volume(value):
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        speakers = AudioUtilities.GetSpeakers()
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = cast(interface, POINTER(IAudioEndpointVolume))
        p = max(0, min(100, int(value)))
        endpoint.SetMasterVolumeLevelScalar(p / 100, None)
        return f"Volume ajustado para {p}%."
    except Exception:
        return "Não consegui controlar o volume."


def mouse_action(command):
    c = command.lower()
    match = re.search(r"mova o mouse para\s+(\d+)\s+(\d+)", c)
    if match:
        x, y = int(match.group(1)), int(match.group(2))
        pyautogui.moveTo(x, y, duration=0.25)
        return f"Mouse movido para {x}, {y}."
    if c in ("clique", "clique esquerdo"):
        pyautogui.click()
        return "Clique realizado."
    if c in ("duplo clique", "double click"):
        pyautogui.doubleClick()
        return "Duplo clique realizado."
    return None


def keyboard_action(command):
    c = command.lower().strip()
    if c.startswith("escreva "):
        text = command[8:]
        pyautogui.write(text, interval=0.01)
        return "Texto digitado."

    keymap = {
        "pressione enter": "enter", "pressione espaço": "space", "pressione espaco": "space",
        "pressione escape": "esc", "pressione tab": "tab", "pressione backspace": "backspace",
        "pressione ctrl c": "ctrl+c", "pressione ctrl v": "ctrl+v", "pressione ctrl a": "ctrl+a",
        "pressione alt tab": "alt+tab",
    }
    if c in keymap:
        key = keymap[c]
        pyautogui.hotkey(*key.split("+")) if "+" in key else pyautogui.press(key)
        return "Tecla executada."
    return None


def file_action(command):
    home = Path.home()
    folders = {
        "downloads": home / "Downloads", "download": home / "Downloads",
        "documentos": home / "Documents", "desktop": home / "Desktop",
        "área de trabalho": home / "Desktop", "area de trabalho": home / "Desktop",
    }
    c = command.lower().strip()
    if c.startswith("abra minha pasta "):
        name = c[16:].strip()
        path = folders.get(name)
        if path and path.exists():
            os.startfile(path)
            return f"Abrindo {name}."
    if c in ("abra downloads", "abrir downloads"):
        path = home / "Downloads"
        if path.exists():
            os.startfile(path)
            return "Abrindo Downloads."
    if c in ("liste meus downloads", "listar downloads"):
        path = home / "Downloads"
        if not path.exists():
            return "A pasta Downloads não existe."
        items = list(path.iterdir())[:12]
        if not items:
            return "Downloads está vazio."
        return "Encontrei: " + ", ".join(x.name for x in items)
    return None



# ===== PC CONTROL 4.2 =====
# Ações locais explícitas. Comandos destrutivos de shell continuam bloqueados.
_PROTECTED_PROCESSES = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe", "winlogon.exe",
}

def window_control(action):
    try:
        if action == "minimize":
            pyautogui.hotkey("win", "down")
            return "Minimizando a janela atual."
        if action == "maximize":
            pyautogui.hotkey("win", "up")
            return "Maximizando a janela atual."
        if action == "close":
            pyautogui.hotkey("alt", "f4")
            return "Fechando a janela atual."
        if action == "switch":
            pyautogui.hotkey("alt", "tab")
            return "Alternando para a próxima janela."
        if action == "show_desktop":
            pyautogui.hotkey("win", "d")
            return "Alternando a exibição da Área de Trabalho."
    except Exception:
        pass
    return "Não consegui controlar a janela atual."

def browser_control(action):
    try:
        keys = {
            "new_tab": ("ctrl", "t"),
            "close_tab": ("ctrl", "w"),
            "reopen_tab": ("ctrl", "shift", "t"),
            "next_tab": ("ctrl", "tab"),
            "previous_tab": ("ctrl", "shift", "tab"),
            "refresh": ("ctrl", "r"),
            "focus_address": ("ctrl", "l"),
            "back": ("alt", "left"),
            "forward": ("alt", "right"),
        }
        combo = keys.get(action)
        if not combo:
            return None
        pyautogui.hotkey(*combo)
        messages = {
            "new_tab": "Abrindo uma nova aba.", "close_tab": "Fechando a aba atual.",
            "reopen_tab": "Reabrindo a última aba fechada.", "next_tab": "Indo para a próxima aba.",
            "previous_tab": "Voltando para a aba anterior.", "refresh": "Atualizando a página.",
            "focus_address": "Selecionando a barra de endereço.", "back": "Voltando uma página.",
            "forward": "Avançando uma página.",
        }
        return messages[action]
    except Exception:
        return "Não consegui controlar o navegador agora."

def change_volume(direction, steps=5):
    steps = max(1, min(20, int(steps)))
    action = "volume_up" if direction == "up" else "volume_down"
    ok = False
    for _ in range(steps):
        ok = _press_media_key(action) or ok
    if ok:
        return "Aumentei o volume." if direction == "up" else "Diminuí o volume."
    return "Não consegui alterar o volume."

def lock_pc():
    if os.name != "nt":
        return "Esse comando está disponível apenas no Windows."
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Computador bloqueado."
    except Exception:
        return "Não consegui bloquear o computador."

def close_application(name):
    wanted = _normalize_name(name)
    if not wanted:
        return "Diga qual aplicativo devo fechar."
    matches = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            norm = _normalize_name(pname.replace(".exe", ""))
            if pname in _PROTECTED_PROCESSES:
                continue
            if wanted == norm or wanted in norm or norm in wanted:
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not matches:
        # Preferir Alt+F4 para nomes genéricos quando a janela alvo já está ativa.
        return f"Não encontrei um processo seguro correspondente a {name}."
    closed = 0
    for proc in matches[:8]:
        try:
            proc.terminate()
            closed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if closed:
        return f"Fechando {name}."
    return f"Não consegui fechar {name}."

def open_windows_location(name):
    home = Path.home()
    locations = {
        "downloads": home / "Downloads",
        "documentos": home / "Documents",
        "imagens": home / "Pictures",
        "videos": home / "Videos",
        "vídeos": home / "Videos",
        "musicas": home / "Music",
        "músicas": home / "Music",
        "desktop": home / "Desktop",
        "area de trabalho": home / "Desktop",
        "área de trabalho": home / "Desktop",
    }
    path = locations.get(_normalize_name(name))
    if path and path.exists() and _shell_open(path):
        return f"Abrindo {name}."
    return None

def pc_control_help():
    return (
        "Controle do PC disponível: abrir e fechar aplicativos; minimizar, maximizar e fechar janelas; "
        "alternar janelas; mostrar a Área de Trabalho; controlar abas do navegador; voltar, avançar e atualizar páginas; "
        "controlar mídia e volume; abrir pastas do usuário; digitar texto, usar teclas e mouse; fazer captura de tela; "
        "ver CPU, RAM e disco; abrir Configurações, Explorador e Gerenciador de Tarefas; e bloquear o computador. "
        "CMD e PowerShell arbitrários, exclusão de arquivos e ações destrutivas continuam bloqueados."
    )


def tool(command, memory):
    c = command.lower().strip()

    # ===== CONTROLE LOCAL DO PC =====
    if c in ("o que voce pode controlar", "o que você pode controlar", "comandos do pc", "controle do pc", "suas permissoes", "suas permissões"):
        return pc_control_help()

    if c in ("minimize a janela", "minimizar janela", "minimize isso"):
        return window_control("minimize")
    if c in ("maximize a janela", "maximizar janela", "maximize isso"):
        return window_control("maximize")
    if c in ("feche a janela", "fechar janela", "feche essa janela"):
        return window_control("close")
    if c in ("troque de janela", "alternar janela", "proxima janela", "próxima janela"):
        return window_control("switch")
    if c in ("mostre a area de trabalho", "mostre a área de trabalho", "ir para o desktop", "mostrar desktop"):
        return window_control("show_desktop")

    browser_commands = {
        "nova aba": "new_tab", "abra uma nova aba": "new_tab", "abrir nova aba": "new_tab",
        "feche a aba": "close_tab", "fechar aba": "close_tab", "feche essa aba": "close_tab",
        "reabra a ultima aba": "reopen_tab", "reabra a última aba": "reopen_tab",
        "proxima aba": "next_tab", "próxima aba": "next_tab",
        "aba anterior": "previous_tab", "volte para a aba anterior": "previous_tab",
        "atualize a pagina": "refresh", "atualize a página": "refresh", "recarregue a pagina": "refresh", "recarregue a página": "refresh",
        "barra de endereco": "focus_address", "barra de endereço": "focus_address",
        "volte uma pagina": "back", "volte uma página": "back", "pagina anterior": "back", "página anterior": "back",
        "avance uma pagina": "forward", "avance uma página": "forward",
    }
    if c in browser_commands:
        return browser_control(browser_commands[c])

    if c in ("aumente o volume", "suba o volume", "volume mais alto"):
        return change_volume("up")
    if c in ("diminua o volume", "abaixe o volume", "volume mais baixo"):
        return change_volume("down")
    if c in ("mute", "mudo", "silencie o computador", "tirar som"):
        return media_control("mute")

    if c in ("bloqueie o computador", "bloquear computador", "bloqueie o pc", "bloquear pc"):
        return lock_pc()

    m = re.match(r"(?:feche|fecha|fechar|encerre|encerrar)\s+(?:o|a)?\s*(.+)$", c)
    if m and m.group(1).strip() not in ("janela", "aba", "essa janela", "essa aba"):
        return close_application(m.group(1).strip())

    m = re.match(r"(?:abra|abrir)\s+(?:minha\s+)?pasta\s+(.+)$", c)
    if m:
        result = open_windows_location(m.group(1).strip())
        if result:
            return result

    # ===== INFORMAÇÃO AO VIVO / PESQUISA WEB =====
    # Notícias gerais do dia.
    if c in (
        "noticias de hoje", "notícias de hoje", "noticias do dia", "notícias do dia",
        "leia as noticias de hoje", "leia as notícias de hoje", "me leia as noticias de hoje",
        "quais as noticias de hoje", "quais as notícias de hoje", "ultimas noticias", "últimas notícias",
        "me de as noticias de hoje", "me dê as notícias de hoje", "briefing de noticias", "briefing de notícias",
    ):
        return news_brief()

    # Notícias por assunto: "notícias de tecnologia", "notícias sobre NVIDIA" etc.
    m = re.match(r"(?:leia\s+)?(?:as\s+)?(?:ultimas\s+|últimas\s+)?not[ií]cias\s+(?:de|sobre)\s+(.+)$", c)
    if m:
        return news_brief(m.group(1).strip())

    # "o que aconteceu hoje com/sobre X" é tratado como notícias recentes.
    m = re.match(r"(?:o que aconteceu|o que houve)\s+(?:hoje\s+)?(?:com|sobre)\s+(.+)$", c)
    if m:
        return news_brief(m.group(1).strip())

    # Levantamento multi-fonte com resumo via Ollama quando disponível.
    research_prefixes = (
        "faça um levantamento sobre ", "faca um levantamento sobre ",
        "faça um levantamento de dados sobre ", "faca um levantamento de dados sobre ",
        "levantamento de dados sobre ", "levantamento sobre ",
        "pesquise e resuma ", "pesquise na web sobre ", "pesquise na web ",
        "investigue ", "faça uma pesquisa sobre ", "faca uma pesquisa sobre ",
    )
    for prefix in research_prefixes:
        if c.startswith(prefix):
            topic = command[len(prefix):].strip()
            return research_brief(topic)

    if c in ("mostre as fontes", "quais sao as fontes", "quais são as fontes", "fontes da pesquisa", "fontes"):
        return last_sources()

    # Navegação natural para canais do YouTube. Estes comandos precisam ser
    # executados localmente ANTES de consultar a IA.
    channel_patterns = (
        r"(?:va|vá|vai|ir|entre|entrar|acesse|acessar)\s+(?:no|para o|pro)\s+canal\s+(?:do|da|de)?\s*(.+?)\s+(?:no|na)\s+youtube$",
        r"(?:va|vá|vai|ir|entre|entrar|acesse|acessar)\s+(?:no|na|para o|pro)?\s*canal\s+(?:do|da|de)?\s*(.+?)\s+(?:no|na)\s+youtube$",
        r"(?:abra|abre|abrir)\s+(?:o\s+)?canal\s+(?:do|da|de)?\s*(.+?)\s+(?:no|na)\s+youtube$",
        r"(?:procure|pesquise|buscar)\s+(?:o\s+)?canal\s+(?:do|da|de)?\s*(.+?)\s+(?:no|na)\s+youtube$",
    )
    for pattern in channel_patterns:
        m = re.match(pattern, c)
        if m:
            return youtube_channel(m.group(1).strip())

    # Também entende 'vá no YouTube no canal da CazéTV'.
    m = re.match(r"(?:va|vá|acesse|entre)\s+(?:no|na)\s+youtube\s+(?:e\s+)?(?:va|vá|entre)?\s*(?:no|na)?\s*canal\s+(?:do|da|de)?\s*(.+)$", c)
    if m:
        return youtube_channel(m.group(1).strip())

    # YouTube 4.3: pedidos de live/vídeo/jogo têm prioridade ABSOLUTA sobre
    # abertura genérica de aplicativos. Nunca mande uma frase com contexto
    # explícito de YouTube para a busca de atalhos do Windows.
    live_patterns = (
        r"(?:abra|abre|abrir|procure|pesquise|ache|encontre)\s+(?:a\s+)?live\s+(?:do|da|de)?\s*(.+?)(?:\s+(?:no|na)\s+youtube(?:\s+(?:do|da|de)\s+(.+))?)?$",
        r"(?:abra|abre|abrir|procure|pesquise|ache|encontre)\s+(?:o\s+)?(?:jogo|video|vídeo)\s+(.+?)\s+(?:no|na)\s+youtube(?:\s+(?:do|da|de)\s+(.+))?$",
    )
    for pattern in live_patterns:
        m = re.match(pattern, c)
        if m:
            subject = (m.group(1) or "").strip()
            channel = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else ""
            q = " ".join(x for x in (subject, channel, "ao vivo" if "live" in c or "jogo" in c else "") if x)
            return youtube_search(q)

    # Guarda geral: qualquer pedido explícito para abrir algo NO YouTube vira
    # pesquisa do YouTube, em vez de cair no roteador de aplicativos.
    m = re.match(r"(?:abra|abre|abrir|procure|pesquise|ache|encontre)\s+(.+?)\s+(?:no|na)\s+youtube$", c)
    if m:
        return youtube_search(m.group(1).strip())

    # YouTube: tocar conteúdo específico e controlar o player diretamente.
    m = re.match(r"(?:toque|tocar|toca|reproduza|reproduzir|coloque|bote)\s+(.+?)\s+(?:no|na)\s+youtube$", c)
    if m:
        return youtube_play(m.group(1).strip())

    # Frases naturais como "toque música X no YouTube".
    m = re.match(r"(?:toque|tocar|toca|reproduza|reproduzir|coloque|bote)\s+(?:a\s+musica\s+|a\s+música\s+|musica\s+|música\s+)?(.+?)\s+(?:no|na)\s+youtube$", c)
    if m:
        return youtube_play(m.group(1).strip())

    if c in ("pause o youtube", "pausar youtube", "pause youtube", "continue o youtube", "continuar youtube", "tocar youtube"):
        return youtube_control("play_pause")
    if c in ("avance o youtube", "avançar youtube", "avance 10 segundos", "avançar 10 segundos no youtube"):
        return youtube_control("forward")
    if c in ("volte o youtube", "voltar youtube", "volte 10 segundos", "voltar 10 segundos no youtube"):
        return youtube_control("back")
    if c in ("youtube tela cheia", "tela cheia youtube", "coloque o youtube em tela cheia"):
        return youtube_control("fullscreen")
    if c in ("silencie o youtube", "mutar youtube", "mute youtube"):
        return youtube_control("mute")
    if c in ("proximo video youtube", "próximo vídeo youtube", "proximo youtube", "próximo youtube"):
        return youtube_control("next")
    if c in ("video anterior youtube", "vídeo anterior youtube", "anterior youtube"):
        return youtube_control("previous")

    # Controles de mídia reais do Windows: nunca deixe a IA fingir que executou.
    if c in ("tocar musica", "tocar música", "toque musica", "toque música",
             "continuar musica", "continuar música", "continue a musica", "continue a música",
             "play", "reproduzir", "retomar musica", "retomar música"):
        return media_control("play_pause")
    if c in ("pausar musica", "pausar música", "pause a musica", "pause a música",
             "pause", "pausar"):
        return media_control("play_pause")
    if c in ("proxima musica", "próxima música", "proxima faixa", "próxima faixa",
             "pular musica", "pular música", "avance a musica", "avance a música"):
        return media_control("next")
    if c in ("musica anterior", "música anterior", "faixa anterior",
             "voltar musica", "voltar música"):
        return media_control("previous")
    if c in ("parar musica", "parar música", "pare a musica", "pare a música"):
        return media_control("stop")

    # Busca de música no Spotify. Abrimos a busca, mas não afirmamos falsamente
    # que uma faixa específica já começou a tocar.
    m = re.match(r"(?:toque|tocar|toca|reproduza|reproduzir|coloque|coloca|bote|bota)\s+(?:a\s+musica\s+|a\s+música\s+|musica\s+|música\s+)?(.+?)\s+(?:no|na)\s+spotify$", c)
    if m:
        return play_music_on_spotify(m.group(1).strip())

    # Comandos diretos sempre têm prioridade sobre a IA.
    for prefix in ("abrir ", "abra ", "abre ", "abrindo ", "inicie ", "iniciar ", "execute ", "rodar "):
        if c.startswith(prefix):
            return open_target(c[len(prefix):].strip())

    # Formas ainda mais naturais: "quero abrir o YouTube", "pode abrir Discord".
    m = re.search(r"(?:quero|pode|consegue|por favor)?\s*(?:abrir|abra|abre|iniciar|inicie)\s+(?:o|a)?\s*(.+)$", c)
    if m:
        return open_target(m.group(1).strip())

    # Busca dedicada no YouTube.
    for prefix in ("pesquise no youtube ", "pesquisar no youtube ", "procure no youtube ", "buscar no youtube "):
        if c.startswith(prefix):
            return youtube_search(c[len(prefix):].strip())

    if c.startswith("pesquisar "):
        return search(c[10:].strip())
    if c.startswith("pesquise "):
        return search(c[9:].strip())

    if "estado do meu computador" in c or "informações do computador" in c or "informacoes do computador" in c:
        return system_info()
    if "captura de tela" in c or "print da tela" in c:
        return screenshot()

    match = re.search(r"(?:volume|coloque o volume em|aumente o volume para|diminua o volume para)\s*(\d+)", c)
    if match:
        return set_volume(match.group(1))

    if c.startswith("lembre que "):
        text = command[len("lembre que "):].strip()
        memory.remember(text)
        return "Memória registrada."
    if "o que você lembra" in c or "o que voce lembra" in c:
        items = memory.get_memories()
        if not items:
            return "Ainda não tenho memórias salvas."
        return "Eu lembro de: " + "; ".join(items[:10])

    result = mouse_action(command)
    if result:
        return result
    result = keyboard_action(command)
    if result:
        return result
    result = file_action(command)
    if result:
        return result

    if "que horas" in c:
        return "Agora são " + datetime.datetime.now().strftime("%H:%M") + "."
    if "qual a data" in c or "que dia é hoje" in c:
        return "Hoje é " + datetime.datetime.now().strftime("%d/%m/%Y") + "."

    return None
