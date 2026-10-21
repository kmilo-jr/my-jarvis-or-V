from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from integrations.gmail_reader import ACCOUNT_PATH, save_account, load_account


class GmailSettings(QWidget):
    def __init__(self, window):
        super().__init__()
        layout = QVBoxLayout(self)
        help_text = QLabel('Conecte o Gmail para listar mensagens e ouvi-las no V.\n'
                           'Ao dizer “bom dia”, o V lê remetente e assunto dos não lidos mais recentes. A quantidade é escolhida em Editar bom dia (padrão: três).\n'
                           'Use uma senha de app do Google (requer verificação em duas etapas).\n'
                           'A leitura mantém as mensagens como estão no Gmail.')
        help_text.setWordWrap(True); layout.addWidget(help_text)
        self.address = QLineEdit(); self.address.setPlaceholderText('Seu endereço do Gmail'); layout.addWidget(self.address)
        self.password = QLineEdit(); self.password.setPlaceholderText('Senha de app · 16 letras')
        self.password.setEchoMode(QLineEdit.Password); layout.addWidget(self.password)
        link = QLabel('<a href="https://myaccount.google.com/apppasswords">Criar senha de app no Google</a>')
        link.setOpenExternalLinks(True); layout.addWidget(link)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        save = QPushButton('Salvar conexão'); save.clicked.connect(self.save); layout.addWidget(save)
        read = QPushButton('Listar e ouvir meus e-mails')
        read.clicked.connect(lambda: window.enqueue_command('liste meus emails')); layout.addWidget(read)
        remove = QPushButton('Desconectar Gmail'); remove.clicked.connect(self.disconnect); layout.addWidget(remove)
        layout.addStretch()
        account = load_account()
        if account:
            self.address.setText(account['address']); self.status.setText('Configuração salva neste usuário do Windows.')

    def save(self):
        try:
            save_account(self.address.text(), self.password.text())
            self.password.clear()
            self.status.setText('Configuração salva e protegida pelo Windows. Clique em listar para testar a conexão.')
        except ValueError as exc:
            self.status.setText(str(exc))
        except Exception:
            self.status.setText('Não consegui proteger e salvar a configuração neste Windows.')

    def disconnect(self):
        try:
            ACCOUNT_PATH.unlink(missing_ok=True)
            self.address.clear(); self.password.clear(); self.status.setText('Configuração do Gmail removida deste V.')
        except OSError:
            self.status.setText('Não consegui remover a configuração. Confira o acesso ao arquivo.')
