from __future__ import annotations
from app_paths import ROOT
import json
import sys
from pathlib import Path
from PySide6.QtCore import QObject,QTimer,Signal,Slot
from PySide6.QtWidgets import QApplication
from main import build_app
from versao import TITULO
from vlog import get_logger

log = get_logger(__name__)

BASE=ROOT


class RemoteBridge(QObject):
    commandRequested = Signal(str)
    actionRequested = Signal(str)


class UiModeManager(QObject):
    MODES=('orbital','amber')
    def __init__(self, app, engine, registry, voice):
        super().__init__(); self.app=app; self.engine=engine; self.registry=registry; self.voice=voice; self.window=None; self._switch_pending=False
        self.mode=self._load_mode()
        self.remote_status={'state':'READY','mode':self.mode,'voice_enabled':False,'busy':False}
        self.remote_bridge=RemoteBridge(self)
        self.remote_bridge.commandRequested.connect(self._remote_command)
        self.remote_bridge.actionRequested.connect(self._remote_action)
        self.remote_server=None
        self.wake_config=None
        self._create_window(self.mode, startup_greeting=True)
        self._remote_timer=QTimer(self); self._remote_timer.timeout.connect(self._refresh_remote_status); self._remote_timer.start(500)
        self.notification_reader=None
        self._notification_timer=QTimer(self); self._notification_timer.timeout.connect(self._poll_iphone_notifications); self._notification_timer.start(2200)
        self._setup_notification_reader()
        self._start_remote_server()

    def _setup_notification_reader(self):
        try:
            cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))
            mcfg=cfg.get('mobile',{}) or {}
            ncfg=mcfg.get('notifications',{}) or {}
            if not bool(ncfg.get('enabled',True)):
                return
            from windows_notification_reader import WindowsPhoneNotificationReader
            self.notification_reader=WindowsPhoneNotificationReader(ncfg.get('allowed_apps') or ['whatsapp','instagram'])
            import mobile_bridge
            if self.notification_reader.available:
                mobile_bridge.set_notification_backend(True,'wpndatabase','Leitor do Windows ativo. Recebe avisos do WhatsApp/Instagram no PC; Phone Link é opcional.')
            else:
                mobile_bridge.set_notification_backend(False,'wpndatabase','Banco de notificações do Windows não encontrado. Ative as notificações dos aplicativos no Windows.')
        except Exception as exc:
            try:
                import mobile_bridge
                mobile_bridge.set_notification_backend(False,'wpndatabase','Leitor de notificações indisponível.',f'{type(exc).__name__}: {exc}')
            except Exception:
                pass

    def _poll_iphone_notifications(self):
        reader=self.notification_reader
        if reader is None:
            return
        try:
            items=reader.poll_new()
            import mobile_bridge
            if reader.last_error:
                mobile_bridge.set_notification_backend(False,'wpndatabase','Não consegui ler as notificações do Windows agora.',reader.last_error)
                return
            if not reader.available:
                mobile_bridge.set_notification_backend(False,'wpndatabase','Banco de notificações do Windows indisponível.')
                return
            mobile_bridge.set_notification_backend(True,'wpndatabase','Leitor do Windows ativo. Apenas WhatsApp/Instagram são encaminhados ao V.')
            for item in items:
                saved=mobile_bridge.record_notification(item.get('app','iPhone'),item.get('title',''),item.get('body',''),source=item.get('source','windows-desktop'))
                # Delivery is centralized in Iniciativa: deduplication, silence and voice limits.
        except Exception as exc:
            print(f'V Mobile notification poll: {type(exc).__name__}: {exc}')

    def _start_remote_server(self):
        try:
            from remote_server import VRemoteServer
            try:
                cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))
                remote_cfg=cfg.get('remote',{}) or {}
                enabled=bool(remote_cfg.get('enabled',True))
                port=int(remote_cfg.get('port',8765))
                from wake_on_lan import WakeConfig
                self.wake_config=WakeConfig.from_dict(remote_cfg.get('wake_on_lan'))
            except Exception:
                enabled=True; port=8765
            if not enabled:
                return
            self.remote_server=VRemoteServer(
                command_callback=lambda text:self.remote_bridge.commandRequested.emit(text),
                action_callback=lambda name:self.remote_bridge.actionRequested.emit(name),
                status_provider=lambda:dict(self.remote_status),
                wake_callback=self._wake_pc if (self.wake_config and self.wake_config.configured) else None,
                port=port,
            ).start()
            print('')
            print('=== V REMOTE v1.6 ===')
            print(f'Local: {self.remote_server.url}')
            print(f'PIN de pareamento: {self.remote_server.pin}')
            print('Mesma rede Wi-Fi/LAN. Nenhuma porta externa necessária.')
            print('=====================')
            print('')
            if self.window is not None:
                QTimer.singleShot(900, lambda: self._show_remote_info())
        except Exception as exc:
            print(f'V Remote startup: {type(exc).__name__}: {exc}')

    def _show_remote_info(self):
        if self.remote_server is None or self.window is None:
            return
        try:
            msg=f'V Remote ativo: {self.remote_server.url}  •  PIN: {self.remote_server.pin}'
            self.window.append_v(msg)
        except Exception:
            pass

    def _refresh_remote_status(self):
        w=self.window
        if w is None:
            return
        try:
            state=str(getattr(getattr(w,'neural',None),'state','READY') or 'READY').upper()
        except Exception:
            state='READY'
        try:
            voice_enabled=bool(getattr(w,'voice_enabled',False))
        except Exception:
            voice_enabled=False
        try:
            busy=bool(getattr(w,'command_thread',None) is not None and w.command_thread.isRunning())
        except Exception:
            busy=False
        try:
            import psutil
            cpu_percent=round(float(psutil.cpu_percent(interval=None)),1)
            ram_percent=round(float(psutil.virtual_memory().percent),1)
            disk_percent=round(float(psutil.disk_usage(str(BASE.anchor or 'C:/')).percent),1)
        except Exception:
            cpu_percent=ram_percent=disk_percent=None
        self.remote_status={
            'state':state,
            'mode':self.mode,
            'voice_enabled':voice_enabled,
            'busy':busy,
            'wol_configured':bool(self.wake_config and self.wake_config.configured),
            'cpu_percent':cpu_percent,
            'ram_percent':ram_percent,
            'disk_percent':disk_percent,
            'mobile_pending':0,
            'mobile_notifications':0,
        }
        try:
            import mobile_bridge
            self.remote_status['mobile_pending']=len(mobile_bridge.pending_actions(20))
            self.remote_status['mobile_notifications']=len(mobile_bridge.recent_notifications(20))
        except Exception:
            pass


    def _wake_pc(self):
        if not self.wake_config or not self.wake_config.configured:
            raise RuntimeError('Wake-on-LAN not configured')
        from wake_on_lan import send_magic_packet
        send_magic_packet(self.wake_config.mac, self.wake_config.broadcast, self.wake_config.port)
        print('V Remote: Magic Packet Wake-on-LAN enviado.')

    @Slot(str)
    def _remote_command(self, text):
        w=self.window
        if w is None:
            return
        try:
            w.enqueue_command(str(text), source='remote')
        except Exception as exc:
            print(f'V Remote command: {type(exc).__name__}: {exc}')

    @Slot(str)
    def _remote_action(self, name):
        w=self.window
        if w is None:
            return
        if name=='switch_ui':
            self.switch_mode()
            return
        if name=='toggle_voice':
            try:
                if bool(getattr(w,'voice_enabled',False)):
                    w.stop_continuous_voice()
                else:
                    w.start_continuous_voice()
            except Exception as exc:
                print(f'V Remote voice: {type(exc).__name__}: {exc}')
            return
        try:
            from pc_remote import execute
            execute(name)
        except Exception as exc:
            print(f'V Remote PC action: {type(exc).__name__}: {exc}')

    def _load_mode(self):
        try:
            cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))
            mode=str(cfg.get('ui',{}).get('last_visual_mode','orbital')).lower()
            return mode if mode in self.MODES else 'orbital'
        except Exception:
            return 'orbital'

    def _load_visual_theme(self):
        try:
            cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))
            theme=str(cfg.get('ui',{}).get('visual_theme','red')).lower()
            return theme if theme in {'blue','red'} else 'red'
        except Exception:
            return 'red'

    def _save_mode(self):
        try:
            p=BASE/'config'/'default.json'; cfg=json.loads(p.read_text(encoding='utf-8'))
            cfg.setdefault('ui',{})['last_visual_mode']=self.mode
            p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            pass

    def _create_window(self, mode, startup_greeting=False, restore_voice=False, tts_enabled=True):
        if mode=='amber':
            from ui.amber_window import AmberExperimentWindow
            w=AmberExperimentWindow(self.engine,self.registry,self.voice,startup_greeting=startup_greeting)
        else:
            from ui.instagram_window import InstagramExperimentWindow
            w=InstagramExperimentWindow(
                self.engine, self.registry, self.voice,
                startup_greeting=startup_greeting,
                theme=self._load_visual_theme(),
            )
        w.remote_diagnostics_provider=lambda: {"server": self.remote_server is not None, "url": self.remote_server.url if self.remote_server else ''}
        w.mode_switch_callback=self.switch_mode
        w.tts_toggle.setChecked(bool(tts_enabled))
        self.window=w; w.show()
        if self.remote_server is not None:
            QTimer.singleShot(500, self._show_remote_info)
        if restore_voice:
            QTimer.singleShot(750,w.start_continuous_voice)

    def switch_mode(self):
        if self._switch_pending or self.window is None: return
        old=self.window
        if old.command_thread is not None and old.command_thread.isRunning():
            old.append_v('Termino esta ação e depois podemos trocar a interface. Tente F6 novamente em instantes.')
            return
        self._switch_pending=True
        restore_voice=bool(old.voice_enabled)
        tts_enabled=bool(old.tts_toggle.isChecked())
        game_enabled=old.game_mode.enabled
        game_geometry=old.game_mode._geometry
        game_maximized=old.game_mode._maximized
        was_hidden=not old.isVisible()
        was_minimized=old.isMinimized()
        current_geometry=old.saveGeometry()

        def finish_switch():
            nonlocal old
            if hasattr(old, '_briefing_panel'):
                old._briefing_panel.cancel()
            try:
                old.processing_sound.shutdown()
            except Exception: pass
            try:
                if hasattr(old,'timer'): old.timer.stop()
            except Exception: pass
            # A camera precisa ser liberada na troca (F6), nao so no fechamento:
            # sem isso ela continua capturando com a janela antiga destruida.
            try:
                camera = getattr(old, '_camera_panel', None)
                if camera is not None:
                    camera.shutdown()
            except Exception as exc:
                log.warning("falha ao encerrar a camera na troca de interface: %s", type(exc).__name__)
            old._mode_switching=True
            old.game_mode.shutdown()
            old.hide(); old.deleteLater()
            self.mode='amber' if self.mode=='orbital' else 'orbital'
            self._save_mode()
            self._create_window(self.mode, startup_greeting=False, restore_voice=restore_voice, tts_enabled=tts_enabled)
            w=self.window
            w.restoreGeometry(current_geometry)
            w.game_mode.enabled=game_enabled
            w.game_mode.action.setChecked(game_enabled)
            w.game_mode._geometry=game_geometry
            w.game_mode._maximized=game_maximized
            if was_hidden or was_minimized:
                w.game_mode.minimize()
            w.game_mode.refresh_rendering()
            self._switch_pending=False

        if old.voice_thread is not None and old.voice_thread.isRunning():
            old.stop_continuous_voice()
            try:
                old.voice_thread.finished.connect(lambda: QTimer.singleShot(60,finish_switch))
            except Exception:
                QTimer.singleShot(650,finish_switch)
        else:
            QTimer.singleShot(20,finish_switch)


def main():
    from core.crash_diagnostics import enable
    enable()
    print(f'=== {TITULO} ===')
    app=QApplication(sys.argv); app.setApplicationName('V Dual Interface')
    try:
        from spotify_bridge import start_bridge_background
        start_bridge_background()
    except Exception as exc:
        print(f'Spotify Bridge startup: {type(exc).__name__}: {exc}')
    engine,registry,voice=build_app()
    manager=UiModeManager(app,engine,registry,voice)
    app._v_mode_manager=manager
    if manager.remote_server is not None:
        app.aboutToQuit.connect(manager.remote_server.stop)
    return app.exec()

if __name__=='__main__':
    raise SystemExit(main())
