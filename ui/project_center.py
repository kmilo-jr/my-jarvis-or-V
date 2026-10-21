from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                              QLineEdit, QPlainTextEdit, QPushButton)


class ProjectCenter(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.store = window.orchestrator.projects
        self.setWindowTitle('Projetos / de onde paramos')
        self.resize(680, 620)
        layout = QVBoxLayout(self)
        note = QLabel('Registre o andamento explicitamente. Salvar torna este projeto ativo; '
                      'o V usa o registro como contexto, sem executar o próximo passo automaticamente.')
        note.setWordWrap(True); layout.addWidget(note)
        self.choice = QComboBox(); layout.addWidget(self.choice)
        self.name = QLineEdit(); self.name.setMaxLength(100)
        layout.addWidget(QLabel('Nome do projeto')); layout.addWidget(self.name)
        self.fields = []
        for label in ('Concluído', 'Pendente', 'Próximo passo'):
            layout.addWidget(QLabel(label))
            editor = QPlainTextEdit(); layout.addWidget(editor); self.fields.append(editor)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout(); layout.addLayout(row)
        for label, handler in [('Salvar e usar', self.save), ('Retomar selecionado', self.select), ('Esquecer selecionado', self.forget)]:
            button = QPushButton(label); button.clicked.connect(handler); row.addWidget(button)
        self.choice.currentTextChanged.connect(self.load_selected)
        self.refresh()

    def refresh(self):
        try:
            data = self.store.read()
            self.choice.blockSignals(True)
            self.choice.clear(); self.choice.addItem('Novo projeto', None)
            for key, item in data['projects'].items():
                self.choice.addItem(item['name'], key)
            index = self.choice.findData(data['active'])
            self.choice.setCurrentIndex(max(0, index)); self.choice.blockSignals(False)
            self.load_selected()
        except (OSError, ValueError) as exc:
            self.choice.blockSignals(False); self.status.setText(str(exc))

    def load_selected(self):
        try:
            item = self.store.read()['projects'].get(self.choice.currentData(), {})
            self.name.setText(item.get('name', ''))
            self.name.setReadOnly(bool(item))
            for editor, key in zip(self.fields, ('done', 'pending', 'next')):
                editor.setPlainText(item.get(key, ''))
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))

    def mutate(self, action):
        thread = getattr(self.window, 'command_thread', None)
        if thread is not None and thread.isRunning():
            self.status.setText('Aguarde o pedido atual terminar para alterar o projeto.'); return
        try:
            action()
            self.window.orchestrator.reset_memory_context()
            self.refresh(); self.status.setText('Registro atualizado.')
        except (OSError, ValueError) as exc:
            self.status.setText(str(exc))

    def save(self):
        self.mutate(lambda: self.store.save(self.name.text(), *(x.toPlainText() for x in self.fields)))

    def select(self):
        self.mutate(lambda: self.store.select(self.choice.currentText()))

    def forget(self):
        self.mutate(lambda: self.store.forget(self.choice.currentText()))
