"""Session-only gaming presentation; voice and command timers remain independent."""
from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class GameModeController(QObject):
    def __init__(self, window, toolbar):
        super().__init__(window)
        self.window = window
        self.enabled = False
        self._geometry = None
        self._maximized = False
        self._closed = False
        self._frame_interval = window.neural.timer.interval()
        self._system_interval = window.timer.interval()
        self.action = QAction('Modo Jogo [F9]', self)
        self.action.setCheckable(True)
        self.action.toggled.connect(self.set_enabled)
        toolbar.addAction(self.action)
        self.shortcut = QShortcut(QKeySequence('F9'), window)
        self.shortcut.activated.connect(self.action.toggle)
        toolbar.addAction('Recolher V', self.minimize)
        self.tray = QSystemTrayIcon(window.style().standardIcon(QStyle.SP_ComputerIcon), self)
        self.tray.setToolTip('V — abrir ou controlar o Modo Jogo')
        self.menu = QMenu(window)
        self.menu.addAction('Abrir V', self.restore)
        self.menu.addAction(self.action)
        self.menu.addAction('Recolher V', self.minimize)
        self.menu.addSeparator()
        self.menu.addAction('Encerrar V', self.exit_app)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        from .floating_orb import FloatingOrb
        self.orb = FloatingOrb(self._orb_state)
        from .avatar_chat import AvatarChat
        self.quick_chat = AvatarChat(window, self.orb)
        # Finish the native mouse event before changing focus/top-level windows.
        self.orb.activated.connect(self.open_quick_chat, Qt.QueuedConnection)
        self.destroyed.connect(self.quick_chat.deleteLater)
        self.orb.menuRequested.connect(self.menu.popup)
        self.destroyed.connect(self.orb.deleteLater)
        window.installEventFilter(self)
        window.neural.installEventFilter(self)
        self._refresh = QTimer(self)
        self._refresh.setSingleShot(True)
        self._refresh.timeout.connect(self.refresh_rendering)
        QApplication.instance().screenRemoved.connect(self._screen_removed)

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore()

    def open_quick_chat(self):
        if self._closed:
            return
        self.orb.play_greeting()
        self.quick_chat.present()

    def _orb_state(self):
        return (str(getattr(self.window.neural, 'state', 'READY')).upper(),
                bool(getattr(self.window, 'voice_enabled', False)))

    def exit_app(self):
        if self.window.close():
            QApplication.instance().quit()

    def eventFilter(self, obj, event):
        if not self._closed and event.type() in (QEvent.Show, QEvent.Hide, QEvent.WindowStateChange):
            # Run after widget show handlers, which may restart their own timers.
            self._refresh.start(0)
        return False

    def refresh_rendering(self):
        if self._closed:
            return
        w = self.window
        if not w.isVisible() or w.isMinimized():
            self.orb.present(w.screen())
        else:
            self.orb.hide()
            self.quick_chat.hide()
        briefing = getattr(w, '_briefing_panel', None)
        covered = briefing is not None and briefing.isVisible()
        office = getattr(getattr(w, 'desktop_shell', None), 'office', None)
        if office is not None:
            office.set_suspended(not w.isVisible() or w.isMinimized() or covered)
        if not w.isVisible() or w.isMinimized() or not w.neural.isVisible() or covered:
            w.neural.timer.stop()
        else:
            w.neural.timer.start(max(100, self._frame_interval) if self.enabled else self._frame_interval)
        if briefing is not None:
            if not w.isVisible() or w.isMinimized() or not covered:
                briefing.backdrop.timer.stop()
            elif briefing.active:
                briefing.backdrop.timer.start(100 if self.enabled else 33)
        w.timer.setInterval(2000 if self.enabled or not w.isVisible() or w.isMinimized() else self._system_interval)

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            if enabled:
                self.minimize()
            return
        w = self.window
        self.enabled = enabled
        self.action.setChecked(enabled)
        voice = getattr(w, 'voice_engine', None)
        if voice is not None:
            voice._game_mode = enabled
            backend = getattr(voice, '_qwen', None)
            if backend is not None:
                backend.game_mode = enabled
                backend.refresh_idle_policy()
        if enabled:
            self._geometry = w.saveGeometry()
            self._maximized = w.isMaximized()
            self.minimize()
            message = 'Modo Jogo ativo: V recolhido no avatar, com a sessão mantida em segundo plano.'
        else:
            w.showNormal()
            if self._geometry is not None:
                w.restoreGeometry(self._geometry)
            if self._maximized:
                w.showMaximized()
            w.raise_()
            message = 'Modo Jogo desativado: apresentação normal restaurada.'
        if enabled:
            message += ' Análise da câmera espaçada, avisos comuns adiados e voz local liberada após 15 segundos ociosa. Alarmes continuam ativos.'
        w.append_v(message)
        self.refresh_rendering()

    def minimize(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.window.hide()
        else:
            self.window.showMinimized()
        self.refresh_rendering()

    def restore(self):
        w = self.window
        if w.isMinimized():
            w.setWindowState(w.windowState() & ~Qt.WindowMinimized)
        w.show()
        w.raise_()
        w.activateWindow()
        self.refresh_rendering()

    def _screen_removed(self, screen):
        if not self._closed:
            self.orb.keep_on_screen()
        if self.enabled and not self._closed:
            if not self.window.isVisible() or self.window.isMinimized():
                return
            target = QApplication.primaryScreen()
            if target is not None:
                self.window.showNormal()
                self.window.move(target.availableGeometry().topLeft())
                self.window.showMaximized()
                self.refresh_rendering()

    def shutdown(self):
        self._closed = True
        office = getattr(getattr(self.window, 'desktop_shell', None), 'office', None)
        if office is not None:
            office.set_suspended(True)
        self._refresh.stop()
        self.tray.hide()
        self.orb.hide()
        self.quick_chat.hide()
        self.quick_chat.setEnabled(False)
