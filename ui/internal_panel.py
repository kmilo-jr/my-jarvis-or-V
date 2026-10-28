from __future__ import annotations

import datetime as _dt
import difflib
import html
import io
import re
import threading
import urllib.parse

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QLinearGradient, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


_URL_RE = re.compile(r"https?://[^\s<>\"']+", flags=re.I)


class VInternalPanel(QFrame):
    """Janela interna do V com HUD + modo apresentação.

    Notas de versão:
    - notícias abrem em um HUD compacto na lateral esquerda;
    - um card por matéria (fonte, manchete, resumo e imagem);
    - imagens usam feed -> matéria real -> busca por título como fallback;
    - navegação anterior/próxima, pausa e alternância SLIDE/LISTA;
    - a MainWindow sincroniza a troca do slide com a fala do V.
    """

    slideManualRequested = Signal(int)
    slideshowPauseChanged = Signal(bool)
    previewReady = Signal(int, int, bytes)

    def __init__(self, accent="#50d8ff", border="rgba(56, 173, 231, 160)", parent=None):
        super().__init__(parent)
        self._accent = accent
        self._border = border
        self._last_plain_text = ""
        self._last_items: list[dict] = []
        self._expanded = False
        self._normal_min = QSize(650, 405)
        self._normal_max = QSize(1040, 640)
        self._news_min = QSize(590, 340)
        self._news_max = QSize(760, 455)
        self._compact_news = False
        self._slide_index = 0
        self._slide_paused = False
        self._slide_speaking = False
        self._preview_cache: dict[int, QPixmap] = {}
        self._preview_loading: set[int] = set()
        self._preview_generation = 0
        self._content_kind = ""

        self.setObjectName("vInternalPanel")
        self.setMinimumSize(self._normal_min)
        self.setMaximumSize(self._normal_max)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(self._style_sheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 15, 18, 15)
        outer.setSpacing(10)

        # Cabeçalho HUD.
        header = QHBoxLayout()
        header.setSpacing(9)
        self.live_dot = QLabel("●")
        self.live_dot.setObjectName("vPanelLiveDot")
        self.title_label = QLabel("V // INTELLIGENCE")
        self.title_label.setObjectName("vPanelTitle")
        self.kind_badge = QLabel("INTERNAL")
        self.kind_badge.setObjectName("vPanelBadge")
        self.time_label = QLabel("")
        self.time_label.setObjectName("vPanelMeta")

        self.view_btn = QPushButton("LISTA")
        self.view_btn.setObjectName("vPanelAction")
        self.view_btn.setToolTip("Alternar entre apresentação e lista")
        self.view_btn.clicked.connect(self._toggle_view)

        self.expand_btn = QPushButton("EXPANDIR")
        self.expand_btn.setObjectName("vPanelAction")
        self.expand_btn.setToolTip("Expandir ou reduzir a janela interna")
        self.expand_btn.clicked.connect(self._toggle_expand)
        self.copy_btn = QPushButton("COPIAR")
        self.copy_btn.setObjectName("vPanelAction")
        self.copy_btn.setToolTip("Copiar o conteúdo da janela")
        self.copy_btn.clicked.connect(self._copy_content)
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("vPanelClose")
        self.close_btn.setToolTip("Fechar (Esc)")
        self.close_btn.clicked.connect(self.hide)

        header.addWidget(self.live_dot)
        header.addWidget(self.title_label)
        header.addSpacing(4)
        header.addWidget(self.kind_badge)
        header.addStretch(1)
        header.addWidget(self.time_label)
        header.addSpacing(5)
        header.addWidget(self.view_btn)
        header.addWidget(self.expand_btn)
        header.addWidget(self.copy_btn)
        header.addWidget(self.close_btn)
        outer.addLayout(header)

        self.hint_label = QLabel("PAINEL INTERNO // AGUARDANDO DADOS")
        self.hint_label.setObjectName("vPanelHint")
        outer.addWidget(self.hint_label)

        self.body_stack = QStackedWidget()
        self.body_stack.setObjectName("vPanelStack")
        outer.addWidget(self.body_stack, 1)

        # ------------------------------------------------------------------
        # SLIDE MODE: layout editorial, semelhante a um feed de notícias.
        # ------------------------------------------------------------------
        self.slide_page = QFrame()
        self.slide_page.setObjectName("vSlidePage")
        slide_outer = QVBoxLayout(self.slide_page)
        slide_outer.setContentsMargins(0, 0, 0, 0)
        slide_outer.setSpacing(10)

        self.slide_card = QFrame()
        self.slide_card.setObjectName("vSlideCard")
        card = QHBoxLayout(self.slide_card)
        self._card_layout = card
        card.setContentsMargins(18, 16, 18, 16)
        card.setSpacing(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(9)
        self.slide_source = QLabel("V NEWS NETWORK")
        self.slide_source.setObjectName("vSlideSource")
        self.slide_source.setWordWrap(True)
        self.slide_title = QLabel("Aguardando briefing...")
        self.slide_title.setObjectName("vSlideTitle")
        self.slide_title.setWordWrap(True)
        self.slide_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.slide_meta = QLabel("")
        self.slide_meta.setObjectName("vSlideMeta")
        self.slide_meta.setWordWrap(True)
        self.slide_snippet = QLabel("")
        self.slide_snippet.setObjectName("vSlideSnippet")
        self.slide_snippet.setWordWrap(True)
        self.slide_snippet.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.open_btn = QPushButton("ABRIR FONTE  ↗")
        self.open_btn.setObjectName("vSlideOpen")
        self.open_btn.clicked.connect(self._open_current_source)
        text_col.addWidget(self.slide_source)
        text_col.addWidget(self.slide_title)
        text_col.addWidget(self.slide_meta)
        text_col.addWidget(self.slide_snippet, 1)
        text_col.addWidget(self.open_btn, 0, Qt.AlignLeft)
        card.addLayout(text_col, 58)

        image_frame = QFrame()
        image_frame.setObjectName("vSlideImageFrame")
        image_layout = QVBoxLayout(image_frame)
        image_layout.setContentsMargins(5, 5, 5, 5)
        self.slide_image = QLabel("V // LIVE\nVISUAL FEED")
        self.slide_image.setObjectName("vSlideImage")
        self.slide_image.setAlignment(Qt.AlignCenter)
        self.slide_image.setMinimumSize(205, 128)
        self.slide_image.setMaximumSize(285, 180)
        self.slide_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        image_layout.addWidget(self.slide_image)
        card.addWidget(image_frame, 42, Qt.AlignCenter)
        slide_outer.addWidget(self.slide_card, 1)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.prev_btn = QPushButton("‹  ANTERIOR")
        self.prev_btn.setObjectName("vSlideNav")
        self.prev_btn.clicked.connect(self._manual_prev)
        self.pause_btn = QPushButton("PAUSAR")
        self.pause_btn.setObjectName("vSlideNav")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.next_btn = QPushButton("PRÓXIMA  ›")
        self.next_btn.setObjectName("vSlideNav")
        self.next_btn.clicked.connect(self._manual_next)
        self.slide_counter = QLabel("01 / 01")
        self.slide_counter.setObjectName("vSlideCounter")
        self.slide_state = QLabel("● APRESENTANDO")
        self.slide_state.setObjectName("vSlideState")
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.pause_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(self.slide_state)
        nav.addSpacing(8)
        nav.addWidget(self.slide_counter)
        slide_outer.addLayout(nav)

        self.slide_progress = QProgressBar()
        self.slide_progress.setObjectName("vSlideProgress")
        self.slide_progress.setTextVisible(False)
        self.slide_progress.setRange(0, 1000)
        self.slide_progress.setValue(0)
        slide_outer.addWidget(self.slide_progress)
        self.body_stack.addWidget(self.slide_page)

        # ------------------------------------------------------------------
        # LIST MODE: preserva o HUD detalhado da 1.8.1.
        # ------------------------------------------------------------------
        self.body = QTextBrowser()
        self.body.setObjectName("vPanelBody")
        self.body.setOpenExternalLinks(True)
        self.body.setOpenLinks(True)
        self.body.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.body.setPlaceholderText("Aguardando conteúdo...")
        self.body_stack.addWidget(self.body)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.footer_left = QLabel("V LIVE DATA LINK")
        self.footer_left.setObjectName("vPanelFooterAccent")
        self.footer_right = QLabel("ESC  FECHAR")
        self.footer_right.setObjectName("vPanelFooter")
        footer.addWidget(self.footer_left)
        footer.addStretch(1)
        footer.addWidget(self.footer_right)
        outer.addLayout(footer)

        self.previewReady.connect(self._apply_preview_bytes)
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._escape_shortcut.activated.connect(self.hide)
        self.hide()

    def _style_sheet(self) -> str:
        return f"""
        QFrame#vInternalPanel {{
            background-color: rgba(2, 7, 16, 250);
            border: 1px solid {self._border};
            border-radius: 16px;
        }}
        QLabel {{ border: 0px; background: transparent; }}
        QLabel#vPanelLiveDot {{ color: {self._accent}; font-size: 11px; padding: 0px 1px; }}
        QLabel#vPanelTitle {{
            color: #eafaff; font-family: 'Segoe UI'; font-size: 11pt;
            font-weight: 700; letter-spacing: 2px;
        }}
        QLabel#vPanelBadge {{
            color: {self._accent}; background: rgba(9, 26, 40, 210);
            border: 1px solid {self._border}; border-radius: 8px; padding: 3px 8px;
            font-family: 'Segoe UI'; font-size: 7pt; font-weight: 700; letter-spacing: 1px;
        }}
        QLabel#vPanelMeta {{ color: rgba(159, 192, 210, 190); font-family: 'Consolas'; font-size: 7.5pt; }}
        QLabel#vPanelHint {{
            color: rgba(126, 171, 195, 205); font-family: 'Consolas'; font-size: 7.5pt;
            font-weight: 600; letter-spacing: 1px; padding: 1px 3px 5px 3px;
        }}
        QStackedWidget#vPanelStack {{ background: transparent; border: 0px; }}
        QFrame#vSlidePage {{ background: transparent; border: 0px; }}
        QFrame#vSlideCard {{
            background-color: rgba(4, 12, 23, 235);
            border: 1px solid rgba(100, 185, 225, 58);
            border-radius: 14px;
        }}
        QLabel#vSlideSource {{
            color: {self._accent}; font-family: 'Segoe UI'; font-size: 8.5pt;
            font-weight: 700; letter-spacing: 1px;
        }}
        QLabel#vSlideTitle {{
            color: #f1fbff; font-family: 'Segoe UI'; font-size: 15.5pt;
            font-weight: 650; line-height: 1.2;
        }}
        QLabel#vSlideMeta {{ color: #7899ab; font-family: 'Segoe UI'; font-size: 8.3pt; }}
        QLabel#vSlideSnippet {{ color: #bdd4df; font-family: 'Segoe UI'; font-size: 9.2pt; }}
        QFrame#vSlideImageFrame {{
            background: rgba(0, 3, 10, 205); border: 1px solid rgba(100, 185, 225, 64);
            border-radius: 12px;
        }}
        QLabel#vSlideImage {{
            background-color: rgba(3, 15, 28, 235); color: rgba(124, 188, 218, 150);
            border: 0px; border-radius: 9px; font-family: 'Consolas'; font-size: 10pt;
            font-weight: 700; letter-spacing: 2px;
        }}
        QPushButton#vSlideOpen {{
            background: rgba(6, 27, 43, 230); border: 1px solid {self._border};
            border-radius: 10px; padding: 7px 12px; color: {self._accent};
            font-family: 'Segoe UI'; font-size: 8pt; font-weight: 700;
        }}
        QPushButton#vSlideOpen:hover {{ background: rgba(12, 48, 70, 240); color: white; }}
        QPushButton#vSlideNav {{
            background: rgba(7, 25, 39, 225); border: 1px solid rgba(111, 188, 225, 72);
            border-radius: 9px; padding: 6px 11px; color: rgba(203, 233, 247, 215);
            font-family: 'Segoe UI'; font-size: 7.5pt; font-weight: 700;
        }}
        QPushButton#vSlideNav:hover {{ color: {self._accent}; border-color: {self._border}; }}
        QLabel#vSlideCounter {{ color: #dff7ff; font-family: 'Consolas'; font-size: 8pt; font-weight: 700; }}
        QLabel#vSlideState {{ color: {self._accent}; font-family: 'Consolas'; font-size: 7.5pt; font-weight: 700; }}
        QProgressBar#vSlideProgress {{
            min-height: 3px; max-height: 3px; background: rgba(69, 120, 145, 42);
            border: 0px; border-radius: 1px;
        }}
        QProgressBar#vSlideProgress::chunk {{ background: {self._accent}; border-radius: 1px; }}
        QTextBrowser#vPanelBody {{
            background-color: rgba(0, 3, 10, 150); border: 1px solid rgba(100, 185, 225, 52);
            border-radius: 11px; color: #d9f4ff; padding: 12px;
            font-family: 'Segoe UI'; font-size: 9.5pt; selection-background-color: {self._accent};
        }}
        QScrollBar:vertical {{ background: rgba(0,0,0,0); width: 9px; margin: 6px 2px 6px 0px; }}
        QScrollBar::handle:vertical {{ background: {self._accent}; min-height: 34px; border-radius: 4px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QPushButton#vPanelAction {{
            background: rgba(7, 25, 39, 225); border: 1px solid rgba(111, 188, 225, 80);
            border-radius: 9px; padding: 5px 9px; color: rgba(203, 233, 247, 215);
            font-family: 'Segoe UI'; font-size: 7.5pt; font-weight: 700;
        }}
        QPushButton#vPanelAction:hover {{ color: {self._accent}; border-color: {self._border}; background: rgba(13, 45, 66, 235); }}
        QPushButton#vPanelClose {{
            background: rgba(35, 12, 17, 205); border: 1px solid rgba(235, 91, 111, 100);
            border-radius: 10px; min-width: 25px; max-width: 25px; min-height: 25px;
            max-height: 25px; color: #ff9aaa; font-size: 13pt; font-weight: 700; padding: 0px;
        }}
        QPushButton#vPanelClose:hover {{ background: rgba(78, 20, 30, 235); border-color: #ff7189; color: white; }}
        QLabel#vPanelFooterAccent {{ color: {self._accent}; font-family: 'Consolas'; font-size: 7pt; font-weight: 700; letter-spacing: 1px; }}
        QLabel#vPanelFooter {{ color: rgba(126, 159, 178, 165); font-family: 'Consolas'; font-size: 7pt; }}
        """

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            w, h = self.width(), self.height()
            accent = QColor(self._accent)
            grad = QLinearGradient(20, 0, max(21, w - 20), 0)
            grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            grad.setColorAt(0.25, QColor(accent.red(), accent.green(), accent.blue(), 35))
            grad.setColorAt(0.50, QColor(accent.red(), accent.green(), accent.blue(), 125))
            grad.setColorAt(0.75, QColor(accent.red(), accent.green(), accent.blue(), 35))
            grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            p.setPen(QPen(grad, 1.4))
            p.drawLine(QPointF(28, 2), QPointF(w - 28, 2))
            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 150), 1.2)
            p.setPen(pen)
            m, arm = 7.0, 17.0
            p.drawLine(QPointF(m, m + arm), QPointF(m, m)); p.drawLine(QPointF(m, m), QPointF(m + arm, m))
            p.drawLine(QPointF(w - m - arm, m), QPointF(w - m, m)); p.drawLine(QPointF(w - m, m), QPointF(w - m, m + arm))
            p.drawLine(QPointF(m, h - m - arm), QPointF(m, h - m)); p.drawLine(QPointF(m, h - m), QPointF(m + arm, h - m))
            p.drawLine(QPointF(w - m - arm, h - m), QPointF(w - m, h - m)); p.drawLine(QPointF(w - m, h - m), QPointF(w - m, h - m - arm))
        finally:
            p.end()

    def sizeHint(self):
        parent = self.parentWidget()
        if parent is not None and parent.width() > 0 and parent.height() > 0:
            if self._expanded:
                return QSize(max(760, min(1240, int(parent.width() * 0.88))), max(510, min(780, int(parent.height() * 0.84))))
            if self._compact_news:
                return QSize(max(610, min(735, int(parent.width() * 0.40))), max(350, min(425, int(parent.height() * 0.43))))
            return QSize(max(720, min(1010, int(parent.width() * 0.72))), max(440, min(625, int(parent.height() * 0.70))))
        if self._expanded:
            return QSize(1140, 700)
        return QSize(700, 390) if self._compact_news else QSize(920, 560)

    def _restore_normal_limits(self):
        if self._compact_news:
            self.setMinimumSize(self._news_min)
            self.setMaximumSize(self._news_max)
        else:
            self.setMinimumSize(self._normal_min)
            self.setMaximumSize(self._normal_max)

    def _notify_reposition(self):
        try:
            win = self.window()
            if win is not None and hasattr(win, "_position_internal_panel"):
                QTimer.singleShot(0, win._position_internal_panel)
        except Exception:
            pass

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.setMinimumSize(720, 470); self.setMaximumSize(1280, 800); self.expand_btn.setText("REDUZIR")
        else:
            self._restore_normal_limits(); self.expand_btn.setText("EXPANDIR")
        self.resize(self.sizeHint()); self.updateGeometry(); self._notify_reposition()

    def _toggle_view(self):
        if self.body_stack.currentWidget() is self.slide_page and self._last_items:
            self.body_stack.setCurrentWidget(self.body)
            self.view_btn.setText("SLIDES")
            self.footer_right.setText("SLIDE MODE DISPONÍVEL  //  ESC FECHAR")
        else:
            self.body_stack.setCurrentWidget(self.slide_page)
            self.view_btn.setText("LISTA")
            self.footer_right.setText("APRESENTAÇÃO  //  ESC FECHAR")
            self._refresh_slide()

    def _linkify(self, text: str) -> str:
        raw = str(text or "")
        out = []
        last = 0
        for match in _URL_RE.finditer(raw):
            start, end = match.span()
            url = match.group(0).rstrip(".,);]}")
            real_end = start + len(url)
            out.append(html.escape(raw[last:start], quote=True))
            safe_url = html.escape(url, quote=True)
            out.append(f'<a style="color:{self._accent};text-decoration:none;font-weight:600" href="{safe_url}">{safe_url}</a>')
            if real_end < end:
                out.append(html.escape(raw[real_end:end], quote=True))
            last = end
        out.append(html.escape(raw[last:], quote=True))
        return "".join(out).replace("\n", "<br>")

    @staticmethod
    def _strip_source_block(text: str) -> str:
        return str(text or "").split("FONTES:", 1)[0].strip()

    @staticmethod
    def _news_intro(text: str) -> str:
        cleaned = VInternalPanel._strip_source_block(text)
        lines = [x.strip() for x in cleaned.splitlines() if x.strip()]
        if not lines:
            return "Dados recebidos pelo V."
        if lines[0].lower().startswith("briefing de notícias"):
            return lines[0].rstrip(":") + "."
        return cleaned

    def _items_html(self, items: list[dict]) -> str:
        blocks = []
        for idx, item in enumerate(items[:12], 1):
            title_raw = str(item.get("title", "") or f"Resultado {idx}").strip()
            title = html.escape(title_raw, quote=True)
            source = html.escape(str(item.get("source", "") or "FONTE WEB"), quote=True)
            published = html.escape(str(item.get("published", "") or "").strip(), quote=True)
            snippet = html.escape(str(item.get("snippet", "") or "").strip(), quote=True)
            url = str(item.get("url", "") or "").strip()
            meta = source.upper()
            if published:
                meta += f" &nbsp; <span style='color:#587487'>•</span> &nbsp; {published}"
            safe_url = html.escape(url, quote=True) if url else ""
            if safe_url:
                title_html = f'<a href="{safe_url}" style="color:#ecfaff;text-decoration:none"><b>{title}</b></a>'
                action = f'<a href="{safe_url}" style="color:{self._accent};text-decoration:none;font-weight:700">ABRIR FONTE&nbsp;&nbsp;↗</a>'
            else:
                title_html = f"<b>{title}</b>"; action = ""
            snippet_html = ""
            if snippet:
                if len(snippet) > 460: snippet = snippet[:457].rstrip() + "..."
                snippet_html = f'<div style="color:#a9c6d6;margin-top:7px;line-height:1.35">{snippet}</div>'
            blocks.append(
                '<table width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 11px 0;background-color:#07111c;border:1px solid #153349;">'
                '<tr><td style="padding:11px 12px"><table width="100%" cellspacing="0" cellpadding="0"><tr>'
                f'<td width="34" valign="top"><span style="color:{self._accent};font-size:8pt;">{idx:02d}</span></td><td>'
                f'<div style="font-size:10.2pt;color:#ecfaff;line-height:1.22">{title_html}</div>'
                f'<div style="font-size:7.7pt;color:#7396aa;margin-top:5px">{meta}</div>{snippet_html}'
                f'<div style="margin-top:8px;font-size:8pt">{action}</div></td></tr></table></td></tr></table>'
            )
        return "".join(blocks)

    def _build_html(self, text: str, items: list[dict] | None = None, kind: str = "") -> str:
        items = [dict(x) for x in (items or []) if isinstance(x, dict)]
        kind_l = str(kind or "").lower()
        intro = self._news_intro(text) if items and "news" in kind_l else self._strip_source_block(text) if items else str(text or "")
        intro_html = self._linkify(intro)
        content = '<div style="line-height:1.35"><div style="color:#688da0;font-size:7.5pt;font-weight:700;letter-spacing:1px;">RESUMO // V</div>'
        content += f'<div style="color:#d9f4ff;margin:6px 0 14px 0;line-height:1.40">{intro_html}</div>'
        if items:
            content += f'<div style="color:{self._accent};font-size:7.5pt;font-weight:700;letter-spacing:1px;margin-bottom:8px">FONTES // {len(items):02d}</div>'
            content += self._items_html(items)
        return content + "</div>"

    # ------------------------------------------------------------------
    # Slide / apresentação
    # ------------------------------------------------------------------
    def _manual_prev(self):
        if not self._last_items: return
        self.set_paused(True)
        self.set_slide_index((self._slide_index - 1) % len(self._last_items), speaking=False)
        self.slideManualRequested.emit(self._slide_index)

    def _manual_next(self):
        if not self._last_items: return
        self.set_paused(True)
        self.set_slide_index((self._slide_index + 1) % len(self._last_items), speaking=False)
        self.slideManualRequested.emit(self._slide_index)

    def _toggle_pause(self):
        self.set_paused(not self._slide_paused)
        self.slideshowPauseChanged.emit(self._slide_paused)

    def set_paused(self, paused: bool):
        self._slide_paused = bool(paused)
        self.pause_btn.setText("CONTINUAR" if self._slide_paused else "PAUSAR")
        if self._slide_paused:
            self.slide_state.setText("Ⅱ PAUSADO")
        else:
            self.slide_state.setText("● LENDO" if self._slide_speaking else "● APRESENTANDO")

    def set_slide_index(self, index: int, speaking: bool = False):
        if not self._last_items:
            return
        self._slide_index = max(0, min(int(index), len(self._last_items) - 1))
        self._slide_speaking = bool(speaking)
        self._refresh_slide()

    def current_slide_index(self) -> int:
        return self._slide_index

    def slide_count(self) -> int:
        return len(self._last_items)

    def _refresh_slide(self):
        if not self._last_items:
            return
        item = self._last_items[self._slide_index]
        title = str(item.get("title", "") or "Notícia sem título").strip()
        source = str(item.get("source", "") or self._domain(item.get("url", "")) or "FONTE WEB").strip()
        published = str(item.get("published", "") or "").strip()
        snippet = self._clean_snippet(str(item.get("snippet", "") or ""), title)
        url = str(item.get("url", "") or "").strip()

        self.slide_source.setText(f"● {source.upper()}")
        self.slide_title.setText(title)
        self.slide_meta.setText((published + "  //  LIVE SOURCE") if published else "LIVE SOURCE // V NEWS LINK")
        self.slide_snippet.setText(snippet or "O V está apresentando esta manchete. Use ABRIR FONTE para ver a matéria completa.")
        self.open_btn.setEnabled(bool(url))
        self.slide_counter.setText(f"{self._slide_index + 1:02d} / {len(self._last_items):02d}")
        self.slide_progress.setValue(int(((self._slide_index + 1) / max(1, len(self._last_items))) * 1000))
        if self._slide_paused:
            self.slide_state.setText("Ⅱ PAUSADO")
        else:
            self.slide_state.setText("● LENDO" if self._slide_speaking else "● APRESENTANDO")

        pix = self._preview_cache.get(self._slide_index)
        if pix and not pix.isNull():
            self._set_image_pixmap(pix)
        else:
            self._set_image_placeholder(source)
            self._load_preview_async(self._slide_index, item)
        # Enquanto o V lê a atual, prepara as próximas imagens.
        for off in (1, 2):
            nxt = self._slide_index + off
            if nxt < len(self._last_items):
                self._load_preview_async(nxt, self._last_items[nxt])

    @staticmethod
    def _clean_snippet(snippet: str, title: str = "") -> str:
        s = re.sub(r"\s+", " ", str(snippet or "")).strip()
        title = re.sub(r"\s+", " ", str(title or "")).strip()
        if not s:
            return ""
        # Google News frequentemente envia description = manchete + nome da fonte.
        # Nesses casos não há resumo real; escondemos a duplicata em vez de o V ler
        # a mesma manchete duas vezes.
        if title:
            def norm(x):
                import unicodedata
                x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii").lower()
                return re.sub(r"[^a-z0-9]+", " ", x).strip()
            nt, ns = norm(title), norm(s)
            if ns.startswith(nt):
                residue = ns[len(nt):].strip()
                if len(residue) < 95:
                    return ""
                s = s[len(title):].lstrip(" -–—|:")
            else:
                head = ns[: max(len(nt) + 70, 120)]
                ratio = difflib.SequenceMatcher(None, nt, head[:max(len(nt), 1)]).ratio() if nt else 0.0
                title_tokens = set(nt.split())
                head_tokens = set(head.split())
                overlap = (len(title_tokens & head_tokens) / max(1, len(title_tokens)))
                if ratio >= 0.78 or (overlap >= 0.82 and len(ns) <= len(nt) + 110):
                    return ""
        if len(s) > 500:
            s = s[:497].rstrip() + "..."
        return s

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urllib.parse.urlparse(str(url or "")).netloc.removeprefix("www.")
        except Exception:
            return ""

    def _open_current_source(self):
        if not self._last_items:
            return
        url = str(self._last_items[self._slide_index].get("url", "") or "").strip()
        if not url:
            return
        try:
            import webbrowser
            webbrowser.open(url, new=2)
        except Exception:
            pass

    def _set_image_placeholder(self, source: str):
        self.slide_image.setPixmap(QPixmap())
        clean = re.sub(r"[^A-Za-z0-9]", "", str(source or "V"))[:14].upper() or "V"
        self.slide_image.setText(f"V // LIVE\n{clean}")

    def _set_image_pixmap(self, pix: QPixmap):
        self.slide_image.setText("")
        target = self.slide_image.size()
        if target.width() < 80 or target.height() < 80:
            target = QSize(330, 210)
        scaled = pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.slide_image.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pix = self._preview_cache.get(self._slide_index)
        if pix and not pix.isNull() and self.body_stack.currentWidget() is self.slide_page:
            self._set_image_pixmap(pix)

    def _load_preview_async(self, index: int, item: dict):
        if index in self._preview_loading or index in self._preview_cache:
            return
        self._preview_loading.add(index)
        snapshot = dict(item)
        generation = self._preview_generation

        def run():
            data = b""
            try:
                data = self._fetch_preview_bytes(snapshot)
            except Exception:
                data = b""
            self.previewReady.emit(generation, index, data)

        threading.Thread(target=run, name=f"V-NewsPreview-{index}", daemon=True).start()

    @staticmethod
    def _unwrap_ddg_href(href: str) -> str:
        if not href:
            return ""
        if href.startswith("//"):
            href = "https:" + href
        try:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            if qs.get("uddg"):
                return urllib.parse.unquote(qs["uddg"][0])
        except Exception:
            pass
        return href

    @staticmethod
    def _publisher_search_title(title: str, source: str) -> str:
        t = re.sub(r"\s+", " ", str(title or "")).strip()
        src = re.sub(r"\s+", " ", str(source or "")).strip()
        # RSS costuma anexar " - Nome da fonte" no próprio título.
        if src and t.lower().endswith((" - " + src).lower()):
            t = t[:-(len(src) + 3)].strip()
        return t

    def _find_publisher_page(self, requests, BeautifulSoup, title: str, source: str, headers: dict) -> str:
        title = self._publisher_search_title(title, source)
        if not title:
            return ""
        try:
            query = f'"{title}" {source}'.strip()
            r = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=(2.5, 5.5))
            if not r.ok:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a.result__a")[:8]:
                url = self._unwrap_ddg_href(str(a.get("href", "") or ""))
                host = self._domain(url).lower()
                if not url.startswith("http") or not host:
                    continue
                if host.endswith("google.com") or host == "news.google.com" or "duckduckgo.com" in host:
                    continue
                return url
        except Exception:
            pass
        return ""

    @staticmethod
    def _og_image_from_page(requests, BeautifulSoup, page_url: str, headers: dict) -> str:
        if not page_url:
            return ""
        try:
            r = requests.get(page_url, headers=headers, timeout=(2.5, 5.5), allow_redirects=True)
            if not r.ok or "text/html" not in str(r.headers.get("content-type", "")).lower():
                return ""
            # Não use a arte genérica do próprio Google News como thumbnail.
            final_host = urllib.parse.urlparse(r.url).netloc.lower()
            if final_host == "news.google.com":
                return ""
            soup = BeautifulSoup(r.text[:1_800_000], "html.parser")
            candidates = [
                soup.find("meta", attrs={"property": "og:image"}),
                soup.find("meta", attrs={"name": "twitter:image"}),
                soup.find("meta", attrs={"property": "twitter:image"}),
                soup.find("link", attrs={"rel": "image_src"}),
            ]
            for tag in candidates:
                if not tag:
                    continue
                raw = tag.get("content") or tag.get("href")
                if raw:
                    return urllib.parse.urljoin(r.url, str(raw).strip())
        except Exception:
            pass
        return ""

    def _bing_image_fallback(self, requests, title: str, source: str, headers: dict) -> str:
        title = self._publisher_search_title(title, source)
        if not title:
            return ""
        try:
            r = requests.get("https://www.bing.com/images/search", params={"q": f"{title} {source}".strip()}, headers=headers, timeout=(2.5, 5.5))
            if not r.ok:
                return ""
            text = r.text
            patterns = [r'murl&quot;:&quot;(https?://[^&]+)&quot;', r'"murl":"(https?://[^"\]+)"']
            for pattern in patterns:
                for match in re.finditer(pattern, text, flags=re.I):
                    url = html.unescape(match.group(1)).replace("\\/", "/")
                    if url.startswith("http"):
                        return url
        except Exception:
            pass
        return ""

    @staticmethod
    def _download_image_bytes(requests, image_url: str, headers: dict) -> bytes:
        if not image_url:
            return b""
        try:
            r = requests.get(image_url, headers=headers, timeout=(2.5, 6.0), stream=True, allow_redirects=True)
            if not r.ok:
                return b""
            ctype = str(r.headers.get("content-type", "")).lower()
            if "image" not in ctype and not re.search(r"\.(jpg|jpeg|png|webp)(?:\?|$)", r.url, flags=re.I):
                return b""
            chunks, total = [], 0
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 5_000_000:
                    return b""
                chunks.append(chunk)
            raw = b"".join(chunks)
            if not raw:
                return b""
            # Converte WebP/AVIF/JPEG/etc. para PNG; QPixmap passa a receber um
            # formato previsível mesmo em instalações Qt com poucos codecs.
            try:
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                im.thumbnail((900, 620))
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGB")
                out = io.BytesIO()
                im.save(out, format="PNG", optimize=True)
                return out.getvalue()
            except Exception:
                return raw
        except Exception:
            return b""

    def _fetch_preview_bytes(self, item: dict) -> bytes:
        """Feed -> matéria real -> busca do artigo -> busca de imagem."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except Exception:
            return b""

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }
        image_url = str(item.get("image_url", "") or "").strip()
        page_url = str(item.get("url", "") or "").strip()
        title = str(item.get("title", "") or "").strip()
        source = str(item.get("source", "") or "").strip()

        # 1) Thumbnail já fornecida pelo feed.
        data = self._download_image_bytes(requests, image_url, headers) if image_url else b""
        if data:
            return data

        # 2) Matéria direta (somente se não for a página genérica do Google News).
        host = self._domain(page_url).lower()
        if page_url and host != "news.google.com":
            image_url = self._og_image_from_page(requests, BeautifulSoup, page_url, headers)
            data = self._download_image_bytes(requests, image_url, headers) if image_url else b""
            if data:
                return data

        # 3) Google News esconde o publisher atrás de redirect. Localizamos a
        # matéria pela manchete e usamos o og:image do site original.
        publisher = self._find_publisher_page(requests, BeautifulSoup, title, source, headers)
        if publisher:
            image_url = self._og_image_from_page(requests, BeautifulSoup, publisher, headers)
            data = self._download_image_bytes(requests, image_url, headers) if image_url else b""
            if data:
                return data

        # 4) Último fallback: imagem relacionada à manchete.
        image_url = self._bing_image_fallback(requests, title, source, headers)
        return self._download_image_bytes(requests, image_url, headers) if image_url else b""

    def _apply_preview_bytes(self, generation: int, index: int, data: bytes):
        if generation != self._preview_generation:
            return
        self._preview_loading.discard(index)
        if not data:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        self._preview_cache[index] = pix
        if index == self._slide_index:
            self._set_image_pixmap(pix)

    def _copy_content(self):
        try:
            QApplication.clipboard().setText(self._last_plain_text)
            self.copy_btn.setText("COPIADO")
            QTimer.singleShot(950, lambda: self.copy_btn.setText("COPIAR"))
        except Exception:
            pass

    def show_content(self, title: str, text: str, hint: str = "INTERNAL WINDOW", items: list[dict] | None = None, kind: str = ""):
        raw_title = str(title or "V / PANEL").upper().replace("V /", "V //")
        self.title_label.setText(raw_title)
        self._content_kind = str(kind or hint or "").lower()
        self._last_items = [dict(x) for x in (items or []) if isinstance(x, dict)]
        item_count = len(self._last_items)
        self.view_btn.setEnabled(item_count > 0)
        shown_hint = str(hint or "INTERNAL WINDOW").upper()
        self.kind_badge.setText("LIVE" if item_count else "LOCAL")
        self.hint_label.setText(
            f"{shown_hint}  //  {item_count:02d} FONTE(S)  //  DADOS RECEBIDOS" if item_count else f"{shown_hint}  //  DADOS RECEBIDOS"
        )
        self.time_label.setText(_dt.datetime.now().strftime("%H:%M:%S"))
        self._last_plain_text = str(text or "")
        self.body.setHtml(self._build_html(text, self._last_items, shown_hint))
        self.footer_left.setText(f"V LIVE DATA LINK  //  {item_count:02d} SOURCE(S)" if item_count else "V INTERNAL DATA LINK")

        self._slide_index = 0
        self._slide_speaking = False
        self._slide_paused = False
        self.pause_btn.setText("PAUSAR")
        self._preview_generation += 1
        self._preview_cache.clear()
        self._preview_loading.clear()

        # Notícias entram direto em modo apresentação e usam um HUD menor para
        # caber no espaço livre entre SYSTEM (topo) e COMMAND MONITOR (base).
        is_news = item_count > 0 and (
            "news" in self._content_kind or "briefing" in self._content_kind or
            "notícia" in raw_title.lower() or "noticia" in raw_title.lower()
        )
        self._compact_news = bool(is_news)
        if self._expanded:
            self._expanded = False
        self._restore_normal_limits()
        self.expand_btn.setText("EXPANDIR")

        if is_news:
            self.body_stack.setCurrentWidget(self.slide_page)
            self.view_btn.setText("LISTA")
            self.footer_right.setText("APRESENTAÇÃO SINCRONIZADA  //  ESC FECHAR")
            self._refresh_slide()
            for i in range(min(3, item_count)):
                self._load_preview_async(i, self._last_items[i])
        else:
            self.body_stack.setCurrentWidget(self.body)
            self.view_btn.setText("SLIDES" if item_count else "LISTA")
            self.footer_right.setText("ESC  FECHAR")

        self.resize(self.sizeHint())
        self.updateGeometry()
        self.show(); self.raise_(); self.activateWindow(); self.setFocus(Qt.OtherFocusReason)
        self._notify_reposition()
        try:
            self.body.verticalScrollBar().setValue(0)
        except Exception:
            pass

