import time
from datetime import datetime
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QCheckBox, QSpinBox, QPushButton, QLineEdit, QDateTimeEdit, QListWidget, QListWidgetItem)


class InitiativeDialog(QDialog):
    def __init__(self, parent, store):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("V / Iniciativa")
        self.resize(650, 650)
        self.setStyleSheet("QDialog,QWidget {background:#0c1620;color:#dcebf4;} QLineEdit,QListWidget,QSpinBox,QDateTimeEdit {background:#142535;color:#e6f3ff;padding:6px;} QPushButton {padding:7px;background:#17374a;border:1px solid #427085;border-radius:5px;} QTabBar::tab {padding:9px;} QTabBar::tab:selected {background:#17374a;}")
        outer = QVBoxLayout(self)
        intro = QLabel("O V avisa sobre fatos locais. Não executa ações por iniciativa própria.\nOs avisos funcionam enquanto o V está aberto; atrasados ficam pendentes.")
        intro.setWordWrap(True); outer.addWidget(intro)
        tabs = QTabWidget(); outer.addWidget(tabs)
        limits = QWidget(); form = QVBoxLayout(limits); tabs.addTab(limits, "Limites e categorias")
        self.checks = {}
        for key, label in [("enabled", "Permitir avisos por iniciativa do V"), ("voice", "Também falar os avisos (respeita Respostas em voz alta)"),
                           ("reminders", "Lembretes locais por voz, texto ou nesta tela"),
                           ("alarms", "Alarmes locais com sinal sonoro, inclusive no horário de silêncio"),
                           ("appointments", "Compromissos: avisar 10 minutos antes"),
                           ("gmail", "Novos e-mails do Gmail (consulta a cada 30 s, sem ler o corpo)"),
                           ("messages", "Novas notificações de WhatsApp/Instagram capturadas pelo V"),
                           ("system", "Alertas de CPU, RAM, espaço em disco e bateria"),
                           ("completions", "Conclusões de pedidos demorados enquanto estou em outra janela"),
                           ("breaks", "Sugerir pausas durante o modo trabalho"), ("summaries", "Resumo local ao iniciar o V"),
                           ("quiet_enabled", "Não interromper no horário de silêncio")]:
            box = QCheckBox(label); self.checks[key] = box; form.addWidget(box)
        self.numbers = {}
        for key, label, low, high, suffix in [("quiet_start", "Silêncio começa às", 0, 23, "h"), ("quiet_end", "Termina às", 0, 23, "h"),
                    ("gap_seconds", "Intervalo mínimo entre avisos", 30, 3600, " s"), ("break_minutes", "Sugerir pausa a cada", 10, 180, " min")]:
            row = QHBoxLayout(); row.addWidget(QLabel(label)); spin = QSpinBox(); spin.setRange(low, high); spin.setSuffix(suffix)
            row.addWidget(spin); form.addLayout(row); self.numbers[key] = spin
        form.addWidget(QLabel("Horários iguais significam silêncio o dia todo. Horário local do Windows."))
        row = QHBoxLayout()
        for label, fn in [("Salvar limites", self.save), ("Pausar por 1 hora", lambda: self.pause(True)), ("Retomar", lambda: self.pause(False))]:
            button = QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        form.addLayout(row)
        end = QPushButton("Encerrar sugestões de pausa do modo trabalho"); end.clicked.connect(self.end_work); form.addWidget(end)
        form.addStretch()
        reminders = QWidget(); layout = QVBoxLayout(reminders); tabs.addTab(reminders, "Lembretes e histórico")
        self.title = QLineEdit(); self.title.setMaxLength(240); self.title.setPlaceholderText("Ex.: revisar o projeto às 16h"); layout.addWidget(self.title)
        self.due = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600)); self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy HH:mm")
        layout.addWidget(self.due)
        add = QPushButton("Cadastrar lembrete no V"); add.clicked.connect(self.add); layout.addWidget(add)
        self.events = QListWidget(); self.events.setWordWrap(True); layout.addWidget(self.events)
        self.monitor_status = QLabel(); self.monitor_status.setWordWrap(True); layout.addWidget(self.monitor_status)
        row = QHBoxLayout()
        for label, command in [('Consultar agenda de hoje', 'agenda de hoje'), ('Consultar listas', 'minhas listas')]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, command=command: self.query(command))
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        for label, fn in [("Adiar 10 min", lambda: self.change(True)), ("Cancelar aviso", lambda: self.change(False)), ("Atualizar", self.refresh)]:
            button = QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        layout.addLayout(row)
        self.status = QLabel(""); self.status.setWordWrap(True); outer.addWidget(self.status)
        try:
            cfg = self.store.snapshot()["settings"]
            for key, widget in self.checks.items(): widget.setChecked(cfg[key])
            for key, widget in self.numbers.items(): widget.setValue(cfg[key])
            self.refresh()
        except Exception as exc:
            self.status.setText("Não foi possível ler os avisos: " + str(exc))

    def query(self, command):
        self.parent().enqueue_command(command, source='text')
        self.accept()

    def save(self):
        try:
            changes = {key: box.isChecked() for key, box in self.checks.items()}
            changes.update({key: spin.value() for key, spin in self.numbers.items()})
            self.store.update_settings(changes)
            self.status.setText("Limites salvos. Avisos pendentes respeitarão estas opções.")
        except Exception as exc: self.status.setText(str(exc))

    def pause(self, active):
        try:
            self.store.update_settings({"paused_until": time.time() + 3600 if active else 0})
            self.refresh()
        except Exception as exc: self.status.setText(str(exc))

    def end_work(self):
        try:
            self.store.work_session(False); self.status.setText("Sugestões de pausa encerradas. Seus programas continuam abertos.")
        except Exception as exc: self.status.setText(str(exc))

    def add(self):
        try:
            self.store.add(self.title.text(), self.due.dateTime().toSecsSinceEpoch())
            self.title.clear(); self.refresh()
        except Exception as exc: self.status.setText(str(exc))

    def change(self, snooze):
        item = self.events.currentItem()
        if not item:
            self.status.setText("Selecione um aviso da lista."); return
        try:
            self.store.change_event(item.data(Qt.UserRole), due=time.time() + 600 if snooze else None)
            self.refresh()
        except Exception as exc: self.status.setText(str(exc))

    def refresh(self):
        service = getattr(getattr(self.parent(), 'orchestrator', None), '_live_notifications', None)
        if service is not None:
            with service.lock:
                lines = dict(service.status)
            self.monitor_status.setText('\n'.join(f'{name}: {value}' for name, value in lines.items()) or 'Monitores aguardando a primeira consulta.')
        else:
            self.monitor_status.setText('Monitores iniciam com o V aberto. Gmail precisa estar configurado em Conexões.')
        data = self.store.snapshot()
        self.events.clear()
        states = {"pending": "Pendente", "delivered": "Avisado", "cancelled": "Cancelado"}
        for event in sorted(data["events"], key=lambda e: e["due"], reverse=True):
            when = datetime.fromtimestamp(event["due"]).strftime("%d/%m %H:%M")
            item = QListWidgetItem(f"{states[event['state']]} · {when}\n{event['title']}", self.events)
            voice_state = event.get('voice_state')
            labels = {'pending': 'Fala pendente', 'spoken': 'Falado', 'failed': 'Falha na fala após três tentativas', 'cancelled': 'Fala cancelada'}
            if voice_state in labels:
                item.setText(item.text() + '\n' + labels[voice_state])
                if event.get('voice_error'):
                    item.setToolTip(event['voice_error'])
            item.setData(Qt.UserRole, event["id"])
        paused = data["settings"]["paused_until"]
        self.status.setText("Avisos pausados até " + datetime.fromtimestamp(paused).strftime("%H:%M") if paused > time.time() else "Avisos seguem os limites salvos. Atualizar recarrega o histórico.")
