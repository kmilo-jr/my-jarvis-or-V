"""Local reflection prompts and explicit learning modes."""
import random
from core.project_progress import normalized

REFLECTIONS = [
    ('Estoicismo', 'Cuide da sua ação; nem todo resultado depende de você.', 'O que está ao seu alcance hoje?'),
    ('Questionamento socrático', 'Uma boa pergunta pode valer mais que uma resposta apressada.', 'Qual certeza sua merece ser examinada?'),
    ('Ética das virtudes', 'O caráter cresce nas escolhas que você repete.', 'Qual pequeno hábito expressa quem você quer ser?'),
    ('Existencialismo', 'Suas escolhas dão forma ao caminho que você percorre.', 'Qual decisão você está adiando?'),
    ('Pragmatismo', 'Teste uma ideia também pelas consequências de colocá-la em prática.', 'Que experiência pequena ajudaria você a aprender?'),
    ('Ceticismo', 'Reconhecer a dúvida abre espaço para investigar melhor.', 'O que faria você mudar de opinião?'),
    ('Epicurismo', 'Uma vida agradável também se constrói com prazeres simples.', 'Que coisa simples você pode apreciar hoje?'),
    ('Ética do cuidado', 'Atenção às necessidades do outro também é uma escolha moral.', 'Quem precisa ser ouvido por você?'),
    ('Filosofia do diálogo', 'Escutar não exige concordar; exige tentar compreender.', 'Você consegue explicar com justiça uma opinião diferente?'),
    ('Filosofia da ciência', 'Uma explicação fica mais forte quando aceita ser testada.', 'Que evidência sustenta sua conclusão?'),
]

TUTOR_PROMPTS = {
    'english': 'MODO INGLÊS: seja um tutor paciente. Pergunte nível e objetivo apenas se ainda desconhecidos no contexto. Use exercícios curtos e conversação gradual. Corrija com explicação breve em português, dê exemplos em inglês e espere a tentativa do aluno. Não afirme avaliar pronúncia a partir apenas da transcrição. Adapte-se ao nível demonstrado.',
    'study': 'MODO ESTUDOS: ajude com faculdade e aprendizagem. Descubra tema, enunciado, critérios e prazo quando relevantes e ausentes; não repita perguntas respondidas. Explique raciocínio, dê exemplos, organize roteiro e revise textos. Diferencie sugestão de resultado verificado. Nunca invente bibliografia, páginas, DOI, citações, dados ou experimentos. Para fontes atuais, use pesquisa disponível e indique limites. Não afirme ter lido arquivos não fornecidos.',
}


def philosophy(text, previous=None):
    n = normalized(text).rstrip('.!?')
    if n not in ('qual a filosofia de hoje', 'qual e a filosofia de hoje', 'filosofia de hoje',
                 'filosofia do dia', 'outra filosofia', 'me diga uma filosofia', 'uma reflexao filosofica'):
        return None
    options = [i for i in range(len(REFLECTIONS)) if i != previous]
    index = random.choice(options)
    school, thought, question = REFLECTIONS[index]
    return index, f'Reflexão inspirada em {school}, em palavras próprias: {thought}\nPara pensar: {question}'


def learning_request(text):
    n = normalized(text)
    if n.rstrip('.!?') in ('sair do modo ingles', 'sair do modo estudos', 'encerrar estudo'):
        return 'off'
    if any(x in n for x in ('aprender ingles', 'praticar ingles', 'estudar ingles', 'modo ingles')):
        return 'english'
    if any(x in n for x in ('trabalho da faculdade', 'trabalho de faculdade', 'modo estudos', 'ajuda para estudar')):
        return 'study'
    return None
