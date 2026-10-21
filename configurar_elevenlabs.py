from voice.eleven_auth import save_key


def graphical(voice_id=None):
    import json
    from pathlib import Path
    import requests
    from voice.eleven_auth import load_key
    from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QLabel, QVBoxLayout, QMessageBox
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication([])
    dialog = QDialog()
    dialog.setWindowTitle("V / Configurar ElevenLabs")
    dialog.setMinimumWidth(520)
    dialog.setStyleSheet("QDialog { background:#0c1620; color:#dcebf4; } QLabel { color:#dcebf4; } QLineEdit { background:#142535; color:#ffffff; padding:9px; }")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Cole a chave ElevenLabs abaixo. O campo aceita Ctrl+V e fica oculto."))
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setPlaceholderText("sk_...")
    field.setClearButtonEnabled(True)
    layout.addWidget(field)
    config_path = Path(__file__).resolve().parent / 'config/default.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    layout.addWidget(QLabel('Voice ID da voz existente (não é necessário criar outra voz):'))
    voice_field = QLineEdit(voice_id or config.get('voice', {}).get('tts_eleven_voice_id', ''))
    layout.addWidget(voice_field)
    field.setPlaceholderText('Chave da conta da voz; vazio mantém a chave salva')
    status = QLabel('A voz será validada antes de ativar o ElevenLabs.')
    status.setWordWrap(True)
    layout.addWidget(status)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    def activate():
        key = field.text().strip() or load_key(config.get('voice', {}))
        selected = voice_field.text().strip()
        if not key or not selected:
            status.setText('Informe a chave e o Voice ID.')
            return
        if not selected.isalnum():
            status.setText('Cole somente o Voice ID, sem o link.')
            return
        try:
            response = requests.get('https://api.elevenlabs.io/v1/voices/' + selected,
                                    headers={'xi-api-key': key}, timeout=12)
            if response.status_code != 200:
                status.setText(f'A voz não pôde ser validada (HTTP {response.status_code}). Confira o ID e a chave da mesma conta.')
                return
            if field.text().strip():
                save_key(key)
            updated = json.loads(config_path.read_text(encoding='utf-8'))
            updated.setdefault('voice', {}).update(tts_profile='elevenlabs_custom',
                tts_xtts_enabled=False, tts_eleven_voice_id=selected,
                tts_eleven_model='eleven_flash_v2_5', tts_eleven_language_code='pt',
                tts_eleven_speed=1.0, tts_dynamic_prosody=False, tts_eleven_fallback_edge=False)
            temp = config_path.with_suffix('.tmp')
            temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
            temp.replace(config_path)
        except Exception as exc:
            status.setText('Não foi possível salvar/validar: ' + type(exc).__name__)
            return
        dialog.accept()
    buttons.accepted.connect(activate)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.Accepted:
        return 1
    QMessageBox.information(dialog, "Voz configurada", "ElevenLabs ativado com sua voz. Reinicie o V para aplicar.")
    return 0


def main():
    try:
        raise SystemExit(graphical())
    except Exception:
        # Fallback for a machine without the Qt runtime.
        from getpass import getpass
        key = getpass("Digite sua chave ElevenLabs (não será exibida): ").strip()
        result = save_key(key)
        print(f"Chave salva em {result['path']} ({'protegida pelo Windows' if result['protected'] else 'arquivo local'}).")


if __name__ == "__main__":
    main()
