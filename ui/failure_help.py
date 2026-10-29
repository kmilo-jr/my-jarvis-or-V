from app_paths import ROOT
from pathlib import Path
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from core.failure_help import explain


class FailureHelp(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('V / O que aconteceu?')
        self.resize(580, 340)
        layout = QVBoxLayout(self)
        self.message = QLabel(); self.message.setWordWrap(True); layout.addWidget(self.message)
        connections = QPushButton('Abrir Conexões para testar')
        connections.clicked.connect(window.show_connections_center); layout.addWidget(connections)
        for service, script in [('Groq', 'configurar_groq.bat'), ('Gemini', 'configurar_gemini.bat'), ('Ollama', 'configurar_ia.bat')]:
            button = QPushButton('Configurar ' + service)
            button.clicked.connect(lambda checked=False, file=script: self.configure(file))
            layout.addWidget(button)
        self.refresh()

    def refresh(self):
        engine = self.window.orchestrator
        report = getattr(engine, 'last_failure', None)
        if not report:
            error = getattr(getattr(engine, 'brain', None), 'last_error', '')
            report = explain(error) if error else {'message': 'Nenhuma falha de IA registrada nesta sessão. Use Conexões para testar os serviços.'}
        self.message.setText(report['message'])

    def configure(self, script):
        try:
            os.startfile(str(ROOT / script))
        except OSError:
            self.message.setText('Não consegui abrir o configurador. Confira o arquivo na pasta do V.')
