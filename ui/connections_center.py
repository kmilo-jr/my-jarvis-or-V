import threading
from datetime import datetime
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from core.connections import NAMES, ACTIONS, configured, probe


class ConnectionsCenter(QDialog):
    completed = Signal(object)
    finished = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.brain = getattr(window.orchestrator, 'brain', None)
        self.running = False
        self.setWindowTitle('Central de conexões')
        self.resize(1180, 680)
        layout = QVBoxLayout(self)
        intro = QLabel('Configuração salva não significa conexão ativa. Os testes são somente leitura e não enviam mensagens, '
                       'tocam música ou carregam modelos na GPU. Último teste se refere a esta sessão.')
        intro.setWordWrap(True); layout.addWidget(intro)
        self.table = QTableWidget(len(NAMES), 6)
        self.table.setHorizontalHeaderLabels(['Serviço', 'Configurado', 'Estado', 'Último teste', 'Resultado / erro', 'Próxima ação'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        for col, width in enumerate((125, 95, 130, 145)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.status = QLabel('Selecione um serviço ou teste todos.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout(); layout.addLayout(row)
        self.test_button = QPushButton('Testar selecionado'); self.test_button.clicked.connect(self.test_selected); row.addWidget(self.test_button)
        self.all_button = QPushButton('Testar todos'); self.all_button.clicked.connect(lambda: self.start(NAMES)); row.addWidget(self.all_button)
        gmail = QPushButton('Configurar Gmail'); gmail.clicked.connect(self.gmail); row.addWidget(gmail)
        for index, name in enumerate(NAMES):
            try: ready = configured(name, self.brain, self.remote())
            except Exception: ready = False
            self.fill(index, [name, 'Sim' if ready else 'Não', 'Configurado' if ready else 'Não configurado', 'Nunca', 'Ainda não testado.', ACTIONS[name]])
        self.table.selectRow(0)
        self.completed.connect(self.show_result)
        self.finished.connect(self.finish)

    def remote(self):
        provider = getattr(self.window, 'remote_diagnostics_provider', None)
        return provider() if provider else None

    def fill(self, row, values):
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value)); item.setToolTip(str(value)); self.table.setItem(row, col, item)
        self.table.resizeRowToContents(row)

    def test_selected(self):
        index = self.table.currentRow()
        if index >= 0: self.start([NAMES[index]])

    def start(self, names):
        if self.running: return
        try: remote = self.remote()
        except Exception: remote = None
        self.running = True; self.test_button.setEnabled(False); self.all_button.setEnabled(False)
        self.status.setText('Testando… Você pode continuar usando o V; os resultados aparecem abaixo.')
        for name in names:
            self.table.setItem(NAMES.index(name), 2, QTableWidgetItem('Testando…'))
        brain = self.brain
        def work():
            try:
                for name in names:
                    self.completed.emit(probe(name, brain, remote))
            except RuntimeError:
                pass  # Parent window destroyed while a bounded probe was running.
            finally:
                try:
                    self.finished.emit()
                except RuntimeError:
                    pass
        threading.Thread(target=work, daemon=True, name='V-ConnectionTests').start()

    def show_result(self, result):
        timestamp = datetime.fromisoformat(result.checked_at).strftime('%d/%m/%Y\n%H:%M:%S')
        self.fill(NAMES.index(result.name), [result.name, 'Sim' if result.configured else 'Não', result.state,
                  timestamp, result.detail, result.next_action])

    def finish(self):
        self.running = False; self.test_button.setEnabled(True); self.all_button.setEnabled(True)
        self.status.setText('Testes concluídos. Confira o alcance de cada teste e a próxima ação na tabela.')

    def gmail(self):
        if not hasattr(self, 'gmail_dialog'):
            from .gmail_settings import GmailSettings
            self.gmail_dialog = QDialog(self); self.gmail_dialog.setWindowTitle('Configurar Gmail')
            layout = QVBoxLayout(self.gmail_dialog); layout.addWidget(GmailSettings(self.window))
        self.gmail_dialog.show(); self.gmail_dialog.raise_()
