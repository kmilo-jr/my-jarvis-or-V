from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                              QListWidgetItem, QLineEdit, QComboBox, QPlainTextEdit, QPushButton)


class MemoryCenter(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.store = window.orchestrator.memory
        self.setWindowTitle('Memórias do V')
        self.resize(740, 600)
        layout = QVBoxLayout(self)
        note = QLabel('Guarde fatos que ajudam nas próximas ações. Rotinas aqui são contexto, não agendamentos. '
                      'Ao corrigir ou esquecer, o contexto recente é reiniciado para não reutilizar o fato antigo.')
        note.setWordWrap(True); layout.addWidget(note)
        self.search = QLineEdit(); self.search.setPlaceholderText('Buscar nas memórias'); layout.addWidget(self.search)
        self.list = QListWidget(); layout.addWidget(self.list)
        self.category = QComboBox()
        for label, key in [('Geral', 'geral'), ('Preferências', 'preferencias'), ('Equipamentos', 'equipamentos'), ('Projetos', 'projetos'), ('Rotinas', 'rotinas')]:
            self.category.addItem(label, key)
        layout.addWidget(self.category)
        self.text = QPlainTextEdit(); self.text.setPlaceholderText('Ex.: meu computador tem uma GTX 1650 de 4 GB.'); layout.addWidget(self.text)
        row = QHBoxLayout(); layout.addLayout(row)
        for label, fn in [('Nova', self.new), ('Salvar', self.save), ('Esquecer selecionada', self.forget), ('Atualizar', self.refresh)]:
            button = QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.item_id = None
        self.search.textChanged.connect(self.refresh)
        self.list.currentItemChanged.connect(self.select)
        self.refresh()

    def refresh(self):
        self.list.clear(); self.new()
        query = self.search.text().casefold()
        for item in self.store.items():
            if query not in (item['text'] + ' ' + item.get('category', 'geral')).casefold():
                continue
            row = QListWidgetItem(f"#{item['id']} · {item.get('category', 'geral')} · {item['text']}")
            row.setData(Qt.UserRole, item); self.list.addItem(row)

    def new(self):
        self.item_id = None; self.text.clear(); self.category.setCurrentIndex(0)

    def select(self, current, previous=None):
        if current is None:
            return
        item = current.data(Qt.UserRole)
        self.item_id = item['id']; self.text.setPlainText(item['text'])
        self.category.setCurrentIndex(max(0, self.category.findData(item.get('category', 'geral'))))

    def available(self):
        thread = self.window.command_thread
        if thread is not None and thread.isRunning():
            self.status.setText('Aguarde a ação em andamento terminar antes de alterar a memória.')
            return False
        return True

    def save(self):
        if not self.available(): return
        try:
            text = self.text.toPlainText().strip()
            if not text: raise ValueError('Escreva o fato que deseja guardar.')
            if self.item_id is None:
                self.store.remember(text, category=self.category.currentData())
            else:
                self.store.update(self.item_id, text, self.category.currentData())
                self.window.orchestrator.reset_memory_context()
            self.refresh(); self.status.setText('Memória salva. Já será usada quando relevante nas próximas ações.')
        except Exception as exc:
            self.status.setText(f'Não foi possível salvar: {exc}')

    def forget(self):
        if not self.available(): return
        if self.item_id is None:
            self.status.setText('Selecione a memória que deseja esquecer.'); return
        try:
            self.store.forget_id(self.item_id)
            self.window.orchestrator.reset_memory_context()
            self.refresh(); self.status.setText('Memória removida e contexto recente reiniciado. O texto antigo pode continuar visível na conversa.')
        except Exception as exc:
            self.status.setText(f'Não foi possível esquecer: {exc}')
