"""Desktop navigation and briefing overview; uses the existing V services."""
from datetime import datetime
from PySide6.QtCore import Qt, QSize
from .future_style import FUTURE_STYLE, icon
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea, QLineEdit, QTextBrowser, QLayout)

STYLE = '''
QWidget#desktopShell {background:#100c11; color:#f8edf0;}
QFrame#navigation {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #26151d,stop:1 #150d14); border:1px solid #63303f; border-radius:16px;}
QLabel#brand {font-size:28px; font-weight:600; letter-spacing:6px; color:#ffe8ee;}
QLabel#eyebrow {color:#c88599; font-size:10px; letter-spacing:2px;}
QLabel#pageTitle {font-size:32px; font-weight:700; color:#fff2f5;}
QLabel#sectionTitle {font-size:19px; font-weight:650; color:#fff0f3;}
QLabel#muted {color:#c39ba9; font-size:12px;}
QLabel#metricValue {font-size:28px; font-weight:700; color:#fff0f3;}
QPushButton#navItem {text-align:left; padding:11px 12px; border:1px solid transparent; border-radius:9px; background:transparent; color:#d6b6c2; font-size:13px;}
QPushButton#navItem:hover {background:#351b27; border-color:#784052;}
QPushButton#navItem:checked {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7b1b36,stop:1 #381724); border-color:#d25070; color:#fff4f6;}
QFrame#dashboardCard {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #311721,stop:1 #1b1019); border:1px solid #663042; border-radius:13px;}
QPushButton#primary {background:#af2e50; color:#fff3f6; border:1px solid #f77d9b; border-radius:8px; padding:10px 18px;}
QScrollArea {border:0; background:transparent;}
QLineEdit {background:#21121b; border:1px solid #794255; color:#fff2f5; padding:12px; border-radius:9px;}
'''


def label(text, role='muted'):
    item = QLabel(text); item.setObjectName(role); item.setWordWrap(True)
    item.setTextFormat(Qt.PlainText)
    return item


def card(title):
    frame = QFrame(); frame.setObjectName('dashboardCard')
    layout = QVBoxLayout(frame); layout.setContentsMargins(20,18,20,18); layout.setSpacing(10)
    layout.addWidget(label(title, 'sectionTitle'))
    return frame, layout


class DesktopShell(QWidget):
    def __init__(self, window, stage):
        super().__init__()
        self.window, self.stage = window, stage
        self.setObjectName('desktopShell'); self.setStyleSheet(FUTURE_STYLE)
        self.pages, self.buttons, self.dialogs = {}, {}, {}
        outer = QHBoxLayout(self); outer.setContentsMargins(14,14,14,14); outer.setSpacing(18)
        nav_scroll = QScrollArea(); nav_scroll.setWidgetResizable(True); nav_scroll.setFixedWidth(228)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav = QFrame(); nav.setObjectName('navigation'); nav_scroll.setWidget(nav)
        menu = QVBoxLayout(nav); menu.setContentsMargins(15,22,15,16); menu.setSpacing(6)
        menu.addWidget(label('V /', 'brand')); menu.addWidget(label('PERSONAL INTELLIGENCE', 'eyebrow')); menu.addSpacing(12)
        for section, rows in [
            ('VISÃO GERAL', [('chat','Chat','Converse, pesquise e execute'),('stage','V','Voz e painel imersivo'),('office','Escritório','O escritório 2.5D do V'),('briefing','Briefing','Agenda, e-mails, notícias e clima')]),
            ('DADOS E AUTOMAÇÃO',[('connections','Fontes de dados','Conexões e contas'),('memory','Memórias','Preferências e continuidade'),('projects','Projetos','Organize seus trabalhos'),('notices','Notificações','E-mails, mensagens e agenda')]),
            ('SISTEMA',[('monitor','Monitoramento','Recursos e diagnóstico'),('settings','Configurações','Voz, escuta e preferências')])]:
            menu.addSpacing(12); menu.addWidget(label(section,'eyebrow'))
            for key, title, subtitle in rows:
                b = QPushButton(title); b.setObjectName('navItem'); b.setCheckable(True); b.setToolTip(subtitle)
                b.setIcon(icon(key)); b.setIconSize(QSize(20,20)); b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda checked=False, name=key: self.select(name)); menu.addWidget(b); self.buttons[key]=b
        menu.addStretch(); self.session_status=label('●  V DISPONÍVEL\n\nSeu espaço pessoal de IA','sessionChip'); menu.addWidget(self.session_status)
        outer.addWidget(nav_scroll)
        self.stack=QStackedWidget(); outer.addWidget(self.stack,1)
        self.add_page('stage', stage)
        self._build_chat(); self._build_briefing(); self._build_settings()
        self.select('briefing')

    def add_page(self,key,widget):
        self.pages[key]=widget; self.stack.addWidget(widget)

    def page(self,key,title,subtitle):
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        content=QWidget(); content.setObjectName('pageSurface'); layout=QVBoxLayout(content); layout.setContentsMargins(22,26,26,26); layout.setSpacing(18)
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        header=QHBoxLayout(); breadcrumb=label('V  /  '+title.upper(),'eyebrow'); breadcrumb.setWordWrap(False)
        header.addWidget(breadcrumb); header.addStretch()
        header.addWidget(label(datetime.now().strftime('%d . %m . %Y'),'eyebrow')); layout.addLayout(header)
        layout.addWidget(label(title,'pageTitle')); layout.addWidget(label(subtitle))
        scroll.setWidget(content); self.add_page(key,scroll)
        return layout

    def _build_chat(self):
        layout=self.page('chat','Como posso ajudar?','Converse com o V, pesquise ou execute um comando.')
        suggestions=QHBoxLayout()
        for title,command in [('Meu dia','resumo do dia'),('Minha agenda','agenda de hoje'),('Notícias','notícias de hoje')]:
            b=QPushButton(title); b.clicked.connect(lambda checked=False, text=command: self.window.enqueue_command(text,source='text')); suggestions.addWidget(b)
        suggestions.addStretch(); layout.addLayout(suggestions)
        # The original conversation widget keeps all command/voice history.
        self.window.control_tabs.removeTab(self.window.control_tabs.indexOf(self.window.chat))
        layout.addWidget(self.window.chat,1)
        self.chat_input=QLineEdit(); self.chat_input.setPlaceholderText('Pergunte ao V…')
        self.chat_input.returnPressed.connect(self.submit)
        row=QHBoxLayout(); row.addWidget(self.chat_input,1)
        send=QPushButton('Enviar'); send.setObjectName('primary'); send.clicked.connect(self.submit); row.addWidget(send)
        layout.addLayout(row)

    def submit(self):
        text=self.chat_input.text().strip()
        if text:
            self.chat_input.clear(); self.window.enqueue_command(text,source='text')

    def _build_briefing(self):
        layout=self.page('briefing','Seu dia, em perspectiva.','O que importa agora, reunido em um só lugar.')
        row=QHBoxLayout(); row.addStretch()
        configure=QPushButton('Personalizar meu dia'); configure.setIcon(icon('settings')); configure.clicked.connect(lambda: self.select('editor')); row.addWidget(configure)
        layout.addLayout(row)
        grid=QGridLayout(); grid.setSpacing(14); self.metrics={}
        for i,(key,title) in enumerate([('agenda','Agenda'),('gmail','E-mails'),('notícias','Notícias'),('clima','Clima')]):
            f,box=card(title); value=label('—','metricValue'); note=label('Ainda não consultado')
            heading=box.takeAt(0).widget()
            cap=QHBoxLayout(); glyph=QLabel(); glyph.setPixmap(icon(key,size=28).pixmap(28,28)); cap.addWidget(glyph)
            cap.addStretch(); cap.addWidget(label('0'+str(i+1),'eyebrow')); box.insertLayout(0,cap)
            box.insertWidget(1,heading)
            box.addWidget(value); box.addWidget(note); grid.addWidget(f,0,i); self.metrics[key]=(value,note)
        layout.addLayout(grid)
        hero,box=card('Briefing matinal'); hero.setObjectName('heroCard')
        box.itemAt(0).widget().setObjectName('heroTitle')
        box.insertWidget(0,label('SUA CENTRAL MATINAL  /  VOZ + VISUAL','eyebrow'))
        box.addWidget(label('Agenda, e-mails, notícias e clima reunidos em uma apresentação com voz e cartões.'))
        self.summary=label('Gere o resumo para consultar suas fontes e apresentar os dados do dia.'); box.addWidget(self.summary)
        actions=QHBoxLayout(); generate=QPushButton('Gerar agora'); generate.setObjectName('primary')
        generate.clicked.connect(lambda: self.window.enqueue_command('resumo do dia',source='text'))
        actions.addWidget(generate); actions.addStretch(); box.addSpacing(20); box.addLayout(actions); layout.addWidget(hero)
        generate.setIcon(icon('stage','#fff4f6'))
        panels=QGridLayout(); panels.setSpacing(14); self.detail_labels={}
        for i,(key,title) in enumerate([('agenda','Agenda consolidada'),('gmail','Caixa de entrada'),('notícias','Radar de notícias'),('clima','Clima e localidade')]):
            f,box=card(title); body=QTextBrowser(); body.setPlainText('Os dados aparecerão após gerar o briefing.')
            body.setMinimumHeight(100); body.setStyleSheet('background:transparent; border:0; color:#d7bac5; font-size:12px;')
            box.addWidget(body); panels.addWidget(f,i//2,i%2); self.detail_labels[key]=body
        layout.addLayout(panels); layout.addStretch()

    def update_briefing(self,items):
        self.summary.setText('Última consulta: '+datetime.now().strftime('%d/%m às %H:%M')+' · Os cartões refletem essa consulta.')
        for kind,(value,note) in self.metrics.items():
            matches=[x for x in items if x.get('kind')==kind]
            if not matches:
                value.setText('—'); note.setText('Não incluído no resumo'); self.detail_labels[kind].setPlainText('Módulo não incluído nesta consulta.'); continue
            valid=[x for x in matches if x.get('ok',True)]
            first=matches[0]
            value.setText((str(first.get('metric') or ('Consultada' if kind=='agenda' else len(valid)))) if valid else 'Indisponível')
            note.setText(first.get('title',''))
            self.detail_labels[kind].setPlainText('\n\n'.join(x.get('title','')+'\n'+x.get('body','') for x in matches))

    def _build_settings(self):
        layout=self.page('settings','Configurações','Voz, microfone e preferências do V.')
        voice_page=self.window.control_tabs.widget(0)
        old=voice_page.layout()
        while old.count(): old.takeAt(0)
        grid=QGridLayout(); grid.setSpacing(16); old.addLayout(grid)
        microphone, mic=card('Microfone e escuta')
        for widget in (self.window.mic_combo,self.window.voice_toggle,self.window.voice_status,self.window.test_mic): mic.addWidget(widget)
        mic.addStretch()
        playback, sound=card('Voz do assistente')
        for widget in (self.window.tts_toggle,self.window.test_voice,self.window.process_sound_toggle,self.window.process_sound_status): sound.addWidget(widget)
        sound.addStretch()
        grid.addWidget(microphone,0,0); grid.addWidget(playback,0,1)
        old.addWidget(self.window.mode_switch_btn); old.addStretch()
        layout.addWidget(self.window.control_tabs)
        b=QPushButton('Configurar briefing'); b.clicked.connect(lambda: self.select('editor')); layout.addWidget(b)

    def select(self,key):
        if key not in self.pages:
            if key == 'office': self._build_office()
            else: self._build_connected_page(key)
        self.stack.setCurrentWidget(self.pages[key])
        dialog=self.dialogs.get(key)
        if dialog is not None:
            dialog.show()
            refresh=getattr(dialog,'refresh',None)
            if callable(refresh): refresh()
        for name,b in self.buttons.items(): b.setChecked(name==key or (key=='editor' and name=='briefing'))
        self.window._position_reference()
        game=getattr(self.window,'game_mode',None)
        if game is not None: game.refresh_rendering()

    def _build_office(self):
        from .pixel_office import PixelOffice
        layout = self.page('office', 'O escritório do V.',
                           'Seu escritório isométrico: clique nos móveis para interagir. O V acompanha seus pedidos e descansa no tempo livre.')
        self.office_status = label('V está disponível no escritório.', 'sectionTitle')
        layout.addWidget(self.office_status)
        self.office = PixelOffice(self.window)
        self.office.activityChanged.connect(self.office_status.setText)
        layout.addWidget(self.office, 1)
        layout.addWidget(label('Clique na estante, mesa ou rádio para preparar um pedido; sofá e cama para descansar. Setas e Enter também funcionam.'))
        row = QHBoxLayout()
        self.office_input = QLineEdit(); self.office_input.setPlaceholderText('Converse sem sair do escritório…')
        def submit():
            text = self.office_input.text().strip()
            if text:
                self.office_input.clear(); self.window.enqueue_command(text, source='text')
        self.office_input.returnPressed.connect(submit)
        send = QPushButton('Enviar'); send.setObjectName('primary'); send.clicked.connect(submit)
        row.addWidget(self.office_input, 1); row.addWidget(send); layout.addLayout(row)
        def interact(key):
            prompts={'books':'Quero estudar sobre ', 'desk':'Me ajude a organizar ',
                     'calendar':'O que tenho na agenda hoje?', 'music':'Toque uma música '}
            if key in prompts:
                if not self.office_input.text().strip():
                    self.office_input.setText(prompts[key])
                self.office_input.setFocus()
                self.office_status.setText('Complete seu pedido e pressione Enviar. Seu rascunho foi preservado.')
        self.office.objectActivated.connect(interact)


    def _build_connected_page(self,key):
        if key=='editor':
            from .briefing_editor import BriefingEditor
            dialog=BriefingEditor(self.window); title='Configurar briefing'
        elif key=='connections':
            from .connections_center import ConnectionsCenter
            dialog=ConnectionsCenter(self.window); title='Fontes de dados'; self.window._connections_center=dialog
        elif key=='memory':
            from .memory_center import MemoryCenter
            dialog=MemoryCenter(self.window); title='Memórias'; self.window._memory_center=dialog
        elif key=='projects':
            from .project_center import ProjectCenter
            dialog=ProjectCenter(self.window); title='Projetos'; self.window._project_center=dialog
        elif key=='notices':
            from .notification_center import NotificationCenter
            dialog=getattr(self.window,'_notification_center',None) or NotificationCenter(self.window)
            self.window._notification_center=dialog; title='Notificações'
        elif key=='monitor':
            layout=self.page(key,'Monitoramento','Uso atual do computador e diagnóstico dos serviços.')
            for widget in (self.window.cpu,self.window.ram,self.window.ai_status,self.window.latency_status):
                layout.addWidget(widget)
            button=QPushButton('Abrir diagnóstico'); button.clicked.connect(self.window.show_diagnostics); layout.addWidget(button); layout.addStretch(); return
        else: raise ValueError(key)
        layout=self.page(key,title,'Preferências e dados do seu V.')
        dialog.setWindowFlags(Qt.Widget); dialog.setMinimumSize(0,0)
        dialog.setStyleSheet('')
        if key=='editor': self._polish_editor(dialog)
        layout.addWidget(dialog); self.dialogs[key]=dialog
        refresh=getattr(dialog,'refresh',None)
        if callable(refresh): refresh()
        dialog.show()

    def _polish_editor(self, editor):
        """Arrange existing controls in sections, retaining their handlers."""
        from PySide6.QtWidgets import QFormLayout
        save=next(b for b in editor.findChildren(QPushButton) if b.text()=='Salvar preferências do bom dia')
        moves=[b for b in editor.findChildren(QPushButton) if b.text() in ('↑ Subir','↓ Descer')]
        layout=editor.layout()
        editor._previous_layout_items=[]
        while layout.count(): editor._previous_layout_items.append(layout.takeAt(0))
        for widget in editor.findChildren(QWidget, options=Qt.FindDirectChildrenOnly): widget.hide()
        def place(box,widget): box.addWidget(widget); widget.show()
        location,box=card('01  /  Localidade')
        box.addWidget(label('Escolha a cidade usada na previsão do tempo.'))
        row=QHBoxLayout(); place(row,editor.query); place(row,editor.search_button); box.addLayout(row); place(box,editor.city)
        layout.addWidget(location)
        news,box=card('02  /  Notícias e e-mails')
        form=QFormLayout(); form.setSpacing(12)
        for title,widget in [('Assuntos',editor.topics),('Quantidade de notícias',editor.news_count),('Quantidade de e-mails',editor.email_count)]:
            form.addRow(title,widget); widget.show()
        box.addLayout(form); row=QHBoxLayout()
        for widget in editor.sources.values(): place(row,widget)
        box.addLayout(row); box.addWidget(label('E-mails: apenas remetente e assunto. As fontes filtram as notícias do briefing.'))
        layout.addWidget(news)
        music,box=card('03  /  Música e apresentação')
        place(box,editor.music)
        form=QFormLayout(); form.addRow('Volume máximo da música',editor.volume); editor.volume.show(); box.addLayout(form)
        box.addWidget(label('Arraste os assuntos para escolher a ordem do seu dia.'))
        editor.order.setFixedHeight(170); place(box,editor.order)
        row=QHBoxLayout()
        for widget in moves: place(row,widget)
        box.addLayout(row); layout.addWidget(music)
        place(layout,editor.status); save.setObjectName('primary'); place(layout,save)
