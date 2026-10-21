from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QLineEdit, QPushButton, QSpinBox, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox)
from core.routines import RoutineStore, APPS


class RoutinesDialog(QDialog):
    def __init__(self, parent, store=None):
        super().__init__(parent)
        self.store = store or RoutineStore()
        self.setWindowTitle("V / Modo trabalho")
        self.setMinimumWidth(520)
        self.setStyleSheet("QDialog {background:#0c1620;color:#dcebf4;} QLabel,QCheckBox {color:#dcebf4;} QListWidget,QLineEdit,QComboBox,QSpinBox {background:#142535;color:#e6f3ff;padding:6px;} QPushButton {padding:8px;}")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Diga “V, modo trabalho” para executar estas ações.'))
        self.browser_enabled = QCheckBox("Abrir navegador")
        self.browser = QComboBox(); self.browser.addItems(["padrão", "chrome", "edge", "firefox"])
        row = QHBoxLayout(); row.addWidget(self.browser_enabled); row.addWidget(self.browser); layout.addLayout(row)
        self.folder_enabled = QCheckBox("Abrir pasta de projetos"); layout.addWidget(self.folder_enabled)
        self.folder = QLineEdit(); self.folder.setAccessibleName("Pasta de projetos")
        choose = QPushButton("Escolher pasta"); choose.clicked.connect(self.choose_folder)
        row = QHBoxLayout(); row.addWidget(self.folder, 1); row.addWidget(choose); layout.addLayout(row)
        layout.addWidget(QLabel("Pasta inicial: o projeto atual do V. Você pode escolher outra."))
        self.volume_enabled = QCheckBox("Ajustar volume")
        self.volume = QSpinBox(); self.volume.setRange(0, 100); self.volume.setSuffix("%")
        row = QHBoxLayout(); row.addWidget(self.volume_enabled); row.addWidget(self.volume); layout.addLayout(row)
        layout.addWidget(QLabel("Outros programas para abrir:"))
        self.apps = QListWidget(); self.apps.setMaximumHeight(170)
        for app in APPS:
            item = QListWidgetItem(app, self.apps)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable); item.setCheckState(Qt.Unchecked)
        layout.addWidget(self.apps)
        self.ask_priority = QCheckBox("Perguntar minha prioridade do dia"); layout.addWidget(self.ask_priority)
        self.status = QLabel(""); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        save = QPushButton("Salvar"); save.clicked.connect(self.save)
        run = QPushButton("Salvar e executar"); run.clicked.connect(self.run)
        close = QPushButton("Fechar"); close.clicked.connect(self.close)
        row.addWidget(save); row.addWidget(run); row.addWidget(close); layout.addLayout(row)
        try:
            cfg = self.store.load()
        except Exception as exc:
            cfg = self.store.defaults()
            self.status.setText(f"Não foi possível ler a rotina ({type(exc).__name__}). Revise e salve para reparar.")
        for name in ("browser_enabled", "folder_enabled", "volume_enabled", "ask_priority"):
            getattr(self, name).setChecked(cfg[name])
        self.browser.setCurrentText(cfg["browser"]); self.folder.setText(cfg["folder"]); self.volume.setValue(cfg["volume"])
        for i in range(self.apps.count()):
            item = self.apps.item(i); item.setCheckState(Qt.Checked if item.text() in cfg["apps"] else Qt.Unchecked)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Pasta de projetos", self.folder.text())
        if path:
            self.folder.setText(path)

    def save(self):
        cfg = {name: getattr(self, name).isChecked() for name in ("browser_enabled", "folder_enabled", "volume_enabled", "ask_priority")}
        cfg.update(browser=self.browser.currentText(), folder=self.folder.text().strip(), volume=self.volume.value(),
                   apps=[self.apps.item(i).text() for i in range(self.apps.count()) if self.apps.item(i).checkState() == Qt.Checked])
        try:
            self.store.save(cfg)
        except Exception as exc:
            self.status.setText("Não foi possível salvar: " + str(exc))
            return False
        self.status.setText("Modo trabalho salvo.")
        return True

    def run(self):
        if self.save():
            self.parent().enqueue_command("modo trabalho", source="text")
            self.accept()
