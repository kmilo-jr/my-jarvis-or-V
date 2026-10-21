"""Explicit Windows monitor selection; no arbitrary shell execution."""


def monitors():
    import win32api
    screens = [win32api.GetMonitorInfo(handle) for handle, _, _ in win32api.EnumDisplayMonitors()]
    return sorted(screens, key=lambda s: (not bool(s['Flags'] & 1), s['Monitor'][0], s['Monitor'][1]))


def describe_monitors():
    screens = monitors()
    lines = []
    for index, screen in enumerate(screens, 1):
        left, top, right, bottom = screen['Monitor']
        lines.append(f"Monitor {index}: {right-left} × {bottom-top}" + (' · principal' if screen['Flags'] & 1 else ''))
    return '\n'.join(lines) or 'Nenhum monitor detectado.'


def move_active_window(number):
    import win32con
    import win32gui
    screens = monitors()
    if type(number) is not int or not 1 <= number <= len(screens):
        raise ValueError(f'Escolha um monitor entre 1 e {len(screens)}.')
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or hwnd == win32gui.GetDesktopWindow():
        raise ValueError('Não encontrei uma janela ativa para mover.')
    was_maximized = win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
    if was_maximized:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    x, y, end_x, end_y = screens[number - 1]['Work']
    width = min(right - left, end_x - x)
    height = min(bottom - top, end_y - y)
    win32gui.SetWindowPos(hwnd, 0, x, y, width, height, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
    if was_maximized:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    return f'Janela ativa movida para o monitor {number}.'
