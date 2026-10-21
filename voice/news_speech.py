"""Render news notation for Portuguese speech without changing the displayed story."""
import html
import re
from datetime import date

from num2words import num2words


SOURCES = {
    'g1': 'gê um', 'g1.globo.com': 'gê um',
    'cnnbrasil.com.br': 'cê ene ene Brasil', 'cnn brasil': 'cê ene ene Brasil',
    'correiobraziliense.com.br': 'Correio Braziliense',
    'oglobo.globo.com': 'O Globo', 'o globo': 'O Globo',
    'poder360': 'Poder trezentos e sessenta',
    'poder360.com.br': 'Poder trezentos e sessenta',
}
ACRONYMS = {
    'MPF': 'Ministério Público Federal', 'STF': 'Supremo Tribunal Federal',
    'STJ': 'Superior Tribunal de Justiça', 'TSE': 'Tribunal Superior Eleitoral',
    'PIB': 'Produto Interno Bruto', 'OMS': 'Organização Mundial da Saúde',
    'ONU': 'Organização das Nações Unidas', 'EUA': 'Estados Unidos',
}
MONTHS = ('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
          'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro')


def number(raw):
    whole, *fraction = raw.replace('.', '').split(',')
    result = num2words(int(whole), lang='pt_BR').replace(',', '')
    if fraction:
        result += ' vírgula ' + ' '.join(num2words(int(d), lang='pt_BR') for d in fraction[0])
    return result


def news_text(text):
    text = html.unescape(str(text or ''))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    # Recognized domain names become the publication name; other domains
    # stay on screen instead of introducing punctuation and English tokens.
    for name, spoken in sorted(SOURCES.items(), key=lambda item: -len(item[0])):
        text = re.sub(r'(?<!\w)' + re.escape(name) + r'(?!\w)', lambda _: spoken, text, flags=re.I)
    text = re.sub(r'\b(?:[a-z0-9-]+\.)+(?:com|org|net|br)(?:\.br)?\b', '', text, flags=re.I)
    text = re.sub(r'\b(?:' + '|'.join(ACRONYMS) + r')\b', lambda m: ACRONYMS[m[0]], text)
    text = re.sub(r'\bbriefing\b', 'resumo', text, flags=re.I)
    text = re.sub(r'\bbets\b', 'casas de apostas', text, flags=re.I)

    def spoken_date(match):
        day, month, year = map(int, match.groups())
        try:
            date(year, month, day)
        except ValueError:
            return match[0]
        return f'{number(str(day))} de {MONTHS[month - 1]} de {number(str(year))}'

    text = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', spoken_date, text)
    def ordinal(match):
        value = num2words(int(match[1]), lang='pt_BR', to='ordinal')
        return re.sub(r'o\b', 'a', value) if match[2] == 'ª' else value
    text = re.sub(r'\b(\d{1,3})([ºª])(?!\w)', ordinal, text)
    text = re.sub(r'(?<![\w/])\d{1,3}(?:\.\d{3})+(?:,\d+)?%?|(?<![\w/])\d+(?:,\d+)?%?(?![\w/])',
                  lambda m: number(m[0].rstrip('%')) + (' por cento' if m[0].endswith('%') else ''), text)
    text = re.sub(r'\s*[;|]\s*(?:VÍDEO|FOTOS|VEJA)\s*$', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip(' .')


def news_source(source):
    return news_text(source)
