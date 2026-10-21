import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QWidget,
    QSpinBox, QCheckBox, QComboBox, QPushButton, QListWidget, QListWidgetItem, QTextEdit)
from voice.preferences import VOICE_PRESETS, save_preferences, preset_defaults, save_xtts_voice, voice_speed


class TaskInteractionDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("V / Voz e tarefas")
        self.resize(610, 570)
        self.setStyleSheet("QDialog,QWidget {background:#0c1620;color:#dcebf4;} QListWidget,QTextEdit,QSpinBox {background:#142535;color:#e6f3ff;padding:6px;} QPushButton {padding:8px;background:#17374a;border:1px solid #427085;border-radius:5px;} QTabBar::tab {padding:9px;} QTabBar::tab:selected {background:#17374a;}")
        outer = QVBoxLayout(self); tabs = QTabWidget(); outer.addWidget(tabs)
        task = QWidget(); layout = QVBoxLayout(task); tabs.addTab(task, "Tarefa e fila")
        self.current = QLabel(); self.current.setWordWrap(True); layout.addWidget(self.current)
        self.stage = QLabel(); self.stage.setWordWrap(True); layout.addWidget(self.stage)
        self.elapsed = QLabel(); layout.addWidget(self.elapsed)
        layout.addWidget(QLabel("Pedidos aguardando:"))
        self.queue = QListWidget(); self.queue.setWordWrap(True); layout.addWidget(self.queue)
        row = QHBoxLayout()
        for label, handler in [("Remover selecionado", self.remove), ("Limpar fila", self.clear), ("Interromper fala", parent.interrupt_speech)]:
            button = QPushButton(label); button.clicked.connect(handler); row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel("Remover da fila não desfaz nem interrompe uma ação já em execução."))
        self.result = QTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(140); layout.addWidget(self.result)
        repeat = QPushButton("Repetir última resposta"); repeat.clicked.connect(parent.repeat_last_response); layout.addWidget(repeat)
        voice = QWidget(); form = QVBoxLayout(voice); tabs.addTab(voice, "Voz")
        form.addWidget(QLabel("Escolha uma assinatura vocal para o V. O perfil aproxima o clima, sem clonar uma voz específica."))
        self.preset = QComboBox(); self.preset.addItems([VOICE_PRESETS[key]["label"] for key in VOICE_PRESETS])
        self.preset_keys = list(VOICE_PRESETS)
        current = str(parent.voice_engine.config.get("tts_voice_preset", "jarvis"))
        self.preset.setCurrentIndex(self.preset_keys.index(current) if current in self.preset_keys else 0)
        self.preset.currentIndexChanged.connect(self.apply_preset_defaults)
        form.addWidget(self.preset)
        form.addWidget(QLabel("Voz de resposta"))
        self.xtts_voice = QComboBox()
        self.xtts_voice.addItem("V Prime · amostra atual", "v_prime")
        self.xtts_voice.addItem("V Alt · nova amostra", "v_alt")
        from voice.preferences import setup_voice_selector
        setup_voice_selector(self.xtts_voice, parent.voice_engine.config)
        form.addWidget(self.xtts_voice)
        self.speed = QSpinBox(); self.speed.setRange(90, 115); self.speed.setSuffix("%")
        self.speed.setValue(voice_speed(parent.voice_engine.config, self.xtts_voice.currentData()))
        row = QHBoxLayout(); row.addWidget(QLabel("Ritmo (100% = normal)")); row.addWidget(self.speed); form.addLayout(row)
        presets = QHBoxLayout()
        self.speed_buttons = []
        for label, value in [("Calmo · 95%", 95), ("Equilibrado · 100%", 100), ("Ágil · 110%", 110)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, value=value: self.speed.setValue(value)); presets.addWidget(button)
            self.speed_buttons.append(button)
        form.addLayout(presets)
        self.expressive = QCheckBox("Ritmo expressivo conforme a frase")
        self.expressive.setChecked(bool(parent.voice_engine.config.get("tts_dynamic_prosody", True))); form.addWidget(self.expressive)
        self.narrate = QCheckBox("Aviso curto por voz durante tarefas demoradas")
        self.narrate.setChecked(bool(parent.voice_engine.config.get("task_progress_voice", True))); form.addWidget(self.narrate)
        form.addWidget(QLabel("As mudanças valem para as próximas falas. A entonação depende da voz utilizada."))
        row = QHBoxLayout()
        save = QPushButton("Salvar ajustes"); save.clicked.connect(self.save); row.addWidget(save)
        test = QPushButton("Salvar e ouvir"); test.clicked.connect(self.preview); row.addWidget(test); form.addLayout(row)
        self.status = QLabel(""); self.status.setWordWrap(True); form.addWidget(self.status); form.addStretch()
        self.xtts_voice.currentIndexChanged.connect(self.change_sample)
        self.load_sample_speed()
        self.timer = QTimer(self); self.timer.setInterval(500); self.timer.timeout.connect(self.refresh); self.timer.start()
        self.refresh()

    def refresh(self):
        w = self.parent()
        active = not w._command_complete
        self.current.setText(("Em execução: " if active else "Último pedido: ") + (w._active_request or "Nenhum pedido ainda."))
        self.stage.setText(w._task_stage or "Aguardando seu pedido.")
        elapsed = time.perf_counter() - w._command_started_at if active and w._command_started_at else w._task_elapsed
        self.elapsed.setText(f"Tempo decorrido: {max(0, elapsed):.0f}s" + (" · sem estimativa de conclusão" if active else ""))
        selected = self.queue.currentItem().data(Qt.UserRole) if self.queue.currentItem() else None
        self.queue.clear()
        for text, source, meta, stamp in w.pending_commands:
            item = QListWidgetItem(text, self.queue); item.setData(Qt.UserRole, stamp)
            if stamp == selected: self.queue.setCurrentItem(item)
        if self.result.toPlainText() != w._last_result_text:
            self.result.setPlainText(w._last_result_text)

    def remove(self):
        item = self.queue.currentItem()
        if item:
            w = self.parent(); stamp = item.data(Qt.UserRole)
            w.pending_commands = type(w.pending_commands)(entry for entry in w.pending_commands if entry[3] != stamp)
            self.refresh()

    def clear(self):
        self.parent().pending_commands.clear(); self.refresh()

    def save(self):
        try:
            save_preferences(self.parent().voice_engine, self.speed.value(), self.expressive.isChecked(), self.narrate.isChecked(), preset=self.preset_keys[self.preset.currentIndex()], xtts_voice=self.xtts_voice.currentData())
            self.sync_sample_selector()
            self.status.setText("Ajustes salvos."); return True
        except Exception as exc:
            self.status.setText("Não foi possível salvar: " + str(exc)); return False

    def load_sample_speed(self):
        self.speed.setValue(voice_speed(self.parent().voice_engine.config, self.xtts_voice.currentData()))
        adjustable = self.xtts_voice.currentData() != 'qwen_alt'
        for control in [self.speed, self.preset, self.expressive, *self.speed_buttons]:
            control.setEnabled(adjustable)
            control.setToolTip('' if adjustable else 'A V Alt usa o ritmo e a entonação naturais da voz aprovada.')

    def sync_sample_selector(self):
        combo = getattr(self.parent(), "xtts_voice_combo", None)
        if combo is None:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(self.xtts_voice.currentData()))
        combo.blockSignals(False)

    def change_sample(self, index):
        try:
            save_xtts_voice(self.parent().voice_engine, self.xtts_voice.currentData())
            self.sync_sample_selector()
            self.load_sample_speed()
            self.status.setText("Amostra selecionada: " + self.xtts_voice.currentText())
        except Exception as exc:
            self.status.setText("Não foi possível trocar a amostra: " + str(exc))

    def apply_preset_defaults(self, index):
        key = self.preset_keys[index]
        defaults = preset_defaults(key)
        self.speed.setValue(int(defaults["speed"]))
        self.expressive.setChecked(bool(defaults["tts_dynamic_prosody"]))
        self.status.setText(f"Perfil {VOICE_PRESETS[key]['label']} selecionado. Salve para aplicar.")

    def preview(self):
        if not self.parent()._command_complete or self.parent().voice_engine.is_speaking():
            self.status.setText("Espere a tarefa ou a fala terminar para testar a voz."); return
        if self.save():
            w = self.parent(); w.processing_sound.stop(); w.set_state("SPEAKING")
            w.voice_engine.speak("Estou pronto. Vou acompanhar seu pedido e avisar se algo precisar da sua atenção. Por onde começamos?")
            QTimer.singleShot(180, w._settle_state_after_audio)

    def closeEvent(self, event):
        self.timer.stop(); super().closeEvent(event)
