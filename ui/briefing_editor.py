import threading
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                              QLineEdit, QComboBox, QPushButton, QSpinBox, QCheckBox,
                              QListWidget, QAbstractItemView)
from core.briefing_preferences import load, save, defaults, find_cities, SOURCES


class BriefingEditor(QDialog):
    cities_ready = Signal(object, str)

    def __init__(self, window, path=None):
        super().__init__(window)
        self.path = path
        self.setWindowTitle('Editar bom dia'); self.resize(720, 730)
        layout = QVBoxLayout(self)
        self.status = QLabel(); self.status.setWordWrap(True)
        try: settings = load(path) if path else load()
        except Exception:
            settings = defaults(); self.status.setText('Preferências inválidas. Revise as opções e salve para reparar.')
        search_row = QHBoxLayout(); layout.addLayout(search_row)
        self.query = QLineEdit(); self.query.setPlaceholderText('Nome da cidade, por exemplo Araguaína'); search_row.addWidget(self.query)
        self.search_button = QPushButton('Buscar cidade'); self.search_button.clicked.connect(self.search); search_row.addWidget(self.search_button)
        self.city = QComboBox(); self.city.addItem('Sem cidade escolhida', None)
        if settings['city']:
            self.city.addItem(settings['city']['label'], settings['city']); self.city.setCurrentIndex(1)
        layout.addWidget(self.city)
        self.topics = QLineEdit(settings['topics']); self.topics.setMaxLength(250)
        self.topics.setPlaceholderText('Ex.: tecnologia, ciência, futebol. Vazio = todos os assuntos.')
        form = QFormLayout(); layout.addLayout(form)
        form.addRow('Assuntos (palavras separadas por vírgula)', self.topics)
        self.news_count = QSpinBox(); self.news_count.setRange(0, 15); self.news_count.setValue(settings['news_count']); form.addRow('Notícias (0 desativa)', self.news_count)
        self.email_count = QSpinBox(); self.email_count.setRange(0, 10); self.email_count.setValue(settings['email_count']); form.addRow('E-mails não lidos (0 desativa)', self.email_count)
        self.sources = {}
        source_row = QHBoxLayout(); layout.addLayout(source_row); source_row.addWidget(QLabel('Fontes:'))
        for name in SOURCES:
            check = QCheckBox(name); check.setChecked(name in settings['sources']); self.sources[name] = check; source_row.addWidget(check)
        note = QLabel('O filtro busca palavras nas manchetes e nos trechos. Pode haver menos notícias disponíveis. '
                      'E-mails: somente remetente e assunto. A seleção de cidade não usa sua localização automática.')
        note.setWordWrap(True); layout.addWidget(note)
        self.music = QCheckBox('Iniciar música da playlist atual do bom dia'); self.music.setChecked(settings['music_enabled']); layout.addWidget(self.music)
        self.volume = QSpinBox(); self.volume.setRange(0, 100); self.volume.setSuffix('%'); self.volume.setValue(settings['music_volume'])
        form2 = QFormLayout(); form2.addRow('Volume máximo da música (preserva volume já mais baixo)', self.volume); layout.addLayout(form2)
        layout.addWidget(QLabel('Ordem dos cartões — arraste ou use as setas. A saudação fica primeiro.'))
        self.order = QListWidget(); self.order.addItems(settings['order']); self.order.setDragDropMode(QAbstractItemView.InternalMove); layout.addWidget(self.order)
        row = QHBoxLayout(); layout.addLayout(row)
        for text, direction in [('↑ Subir', -1), ('↓ Descer', 1)]:
            button = QPushButton(text); button.clicked.connect(lambda checked=False, d=direction: self.move(d)); row.addWidget(button)
        note2 = QLabel('A ordem muda a apresentação dos cartões. A música, quando ativada, começa junto com o comando. Alterações valem no próximo resumo.')
        note2.setWordWrap(True); layout.addWidget(note2)
        layout.addWidget(self.status)
        button = QPushButton('Salvar preferências do bom dia'); button.clicked.connect(self.save); layout.addWidget(button)
        self.cities_ready.connect(self.show_cities)

    def move(self, direction):
        index = self.order.currentRow(); target = index + direction
        if 0 <= index < self.order.count() and 0 <= target < self.order.count():
            item = self.order.takeItem(index); self.order.insertItem(target, item); self.order.setCurrentRow(target)

    def search(self):
        query = self.query.text().strip()
        if len(query) < 2:
            self.status.setText('Digite pelo menos duas letras.'); return
        self.search_button.setEnabled(False); self.status.setText('Buscando cidades…')
        def work():
            try: results, error = find_cities(query), ''
            except Exception: results, error = [], 'Não consegui buscar cidades. Confira a conexão e tente novamente; a cidade salva foi preservada.'
            try: self.cities_ready.emit(results, error)
            except RuntimeError: pass
        threading.Thread(target=work, daemon=True, name='V-CitySearch').start()

    def show_cities(self, results, error):
        self.search_button.setEnabled(True)
        if error or not results:
            self.status.setText(error or 'Nenhuma cidade encontrada. Tente apenas o nome da cidade.'); return
        previous = self.city.currentData()
        self.city.clear(); self.city.addItem('Selecione a cidade encontrada', None)
        if previous:
            self.city.addItem(previous['label'] + ' (seleção atual)', previous); self.city.setCurrentIndex(1)
        for city in results: self.city.addItem(city['label'], city)
        self.status.setText('Escolha a cidade e confira o estado/país antes de salvar.')

    def save(self):
        try:
            data = dict(city=self.city.currentData(), topics=self.topics.text().strip(),
                        news_count=self.news_count.value(), email_count=self.email_count.value(),
                        sources=[name for name, check in self.sources.items() if check.isChecked()],
                        music_enabled=self.music.isChecked(), music_volume=self.volume.value(),
                        order=[self.order.item(i).text() for i in range(self.order.count())])
            save(data, self.path) if self.path else save(data)
            self.status.setText('Preferências salvas. Valem no próximo “bom dia”.' + (' Escolha uma cidade para ativar o clima.' if data['city'] is None else ''))
        except Exception as exc:
            self.status.setText(f'Não consegui salvar: {exc}')
