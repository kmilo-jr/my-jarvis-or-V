"""Shared crimson desktop styling and tiny locally rendered vector icons."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    'office': 'M3 3h18v18H3Z M3 12h18 M7 5v5 M11 5v5 M16 6l2 4 M7 15v4 M11 15v4 M16 15h2v4',
    'chat': 'M4 4h16v12H9l-5 4Z M8 8h8 M8 12h5',
    'stage': 'M12 3v4 M12 17v4 M3 12h4 M17 12h4 M8 8l8 8 M16 8l-8 8',
    'briefing': 'M5 5h14v16H5Z M9 3h6v4H9Z M8 11h8 M8 15h5',
    'connections': 'M8 7H5v5h4 M16 7h3v5h-4 M12 4v13 M6 20h12 M9 17h6',
    'memory': 'M8 4h8v16H8Z M4 8h4 M4 12h4 M4 16h4 M16 8h4 M16 12h4 M16 16h4',
    'projects': 'M3 7h7l2-3h9v16H3Z M3 10h18',
    'notices': 'M6 16V9a6 6 0 0 1 12 0v7l2 2H4Z M10 21h4',
    'monitor': 'M3 5h18v12H3Z M8 21h8 M12 17v4 M5 12h3l2-4 3 6 2-3h4',
    'settings': 'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6',
    'agenda': 'M4 5h16v16H4Z M8 2v6 M16 2v6 M4 10h16 M8 14h2 M14 14h2',
    'gmail': 'M3 5h18v14H3Z M3 6l9 7 9-7',
    'notícias': 'M4 3h16v18H4Z M8 7h8 M8 11h8 M8 15h3 M14 15h2',
    'clima': 'M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
}

def icon(name, color='#ef7084', size=22):
    path=PATHS.get(name, PATHS['stage'])
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pixmap=QPixmap(size*2,size*2); pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap); QSvgRenderer(QByteArray(svg.encode())).render(painter); painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

FUTURE_STYLE = '''
QWidget#desktopShell { background:#0c0c12; color:#eeeef5; }
QWidget#pageSurface { background:transparent; }
QFrame#navigation { background:qlineargradient(x1:0,y1:0,x2:0.8,y2:1,stop:0 #231722,stop:0.4 #14131c,stop:1 #101018); border:1px solid #392735; border-radius:18px; }
QLabel#brand { color:#fff3f5; font-size:42px; font-weight:700; letter-spacing:8px; }
QLabel#eyebrow { color:#d2798c; font-size:9px; letter-spacing:2px; font-weight:600; }
QLabel#pageTitle { color:#f9f4f6; font-size:34px; font-weight:650; letter-spacing:-1px; }
QLabel#sectionTitle { color:#eee9ee; font-size:17px; font-weight:600; }
QLabel#muted { color:#a8a2b4; font-size:12px; }
QLabel#metricValue { color:#fff0f4; font-size:32px; font-weight:650; }
QLabel#sessionChip { color:#e5b7c3; background:#241720; border:1px solid #54303e; border-radius:9px; padding:13px; font-size:10px; letter-spacing:1px; }
QPushButton { background:#211c28; border:1px solid #463244; color:#ddd4e1; border-radius:8px; padding:9px 13px; font-size:12px; }
QPushButton:hover { background:#36232f; border-color:#b34b68; color:#fff4f6; }
QPushButton:pressed { background:#461e30; }
QPushButton:focus { border-color:#ff879c; }
QPushButton:disabled { color:#766574; border-color:#332634; background:#16121b; }
QPushButton#navItem { text-align:left; padding:12px 10px; border:1px solid transparent; border-radius:8px; background:transparent; color:#b3aaba; font-size:12px; font-weight:500; }
QPushButton#navItem:hover { background:#291c28; border-color:#583247; }
QPushButton#navItem:checked { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5b2137,stop:1 #271824); border:1px solid #85415a; border-left:3px solid #ff637f; color:#fff1f5; }
QFrame#dashboardCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #231a28,stop:0.4 #1c1722,stop:1 #12121b); border:1px solid #453041; border-radius:15px; }
QFrame#heroCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:0.75,stop:0 #472033,stop:0.5 #271b2c,stop:1 #141521); border:1px solid #87405a; border-radius:18px; }
QLabel#heroTitle { font-size:28px; font-weight:650; color:#fff1f6; }
QLabel#heroMark { font-size:68px; font-weight:300; color:#f87594; padding:12px; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ec4e70,stop:1 #a42750); color:white; border:1px solid #fb829e; border-radius:9px; padding:12px 20px; font-weight:650; }
QPushButton#primary:hover { background:#e76587; border-color:#ffb0c3; }
QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:0; }
QLineEdit, QSpinBox, QComboBox { background:#13121b; color:#efe6ef; border:1px solid #493245; border-radius:7px; padding:9px; selection-background-color:#88364f; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color:#f07893; }
QComboBox QAbstractItemView { background:#211723; color:#f5e6ed; selection-background-color:#632e45; }
QTextEdit, QTextBrowser, QPlainTextEdit, QListWidget, QTableWidget { background:#14121d; color:#ded5e2; border:1px solid #3f2e40; border-radius:9px; padding:10px; selection-background-color:#722a46; }
QHeaderView::section { background:#2a1c2b; color:#dca6bb; border:0; padding:10px; }
QTabWidget::pane { background:#16141e; border:1px solid #443045; border-radius:10px; }
QTabBar::tab { background:#1a1520; color:#ac9cad; padding:12px 18px; border:0; }
QTabBar::tab:selected { background:#472337; color:#ffeaf1; border-bottom:2px solid #fa648b; }
QCheckBox { color:#c7baca; spacing:8px; padding:4px; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #805068; border-radius:4px; background:#19141f; }
QCheckBox::indicator:checked { background:#dd4d74; border-color:#ff98b2; }
QProgressBar { background:#251a2b; border:0; border-radius:3px; }
QProgressBar::chunk { background:#e55378; border-radius:3px; }
QScrollBar:vertical { background:transparent; width:7px; }
QScrollBar::handle:vertical { background:#64354d; border-radius:3px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:7px; }
QScrollBar::handle:horizontal { background:#64354d; border-radius:3px; min-width:30px; }
'''
