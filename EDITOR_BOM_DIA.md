# Editor do bom dia — 03/10/2026

Reinicie o V e abra **Editar bom dia** na barra de controles. Salve as alterações; elas valem no próximo comando **bom dia** ou **resumo do dia**, sem alterar um resumo já em andamento.

- **Cidade:** pesquise o nome, escolha o resultado conferindo estado e país e salve. A previsão usa as coordenadas selecionadas e o fuso retornado pelo Open-Meteo. Nenhuma cidade é inferida; sem escolha, aparece orientação para configurar. Rio de Janeiro deixou de ser o padrão do resumo.
- **Assuntos:** palavras ou expressões separadas por vírgula, comparadas com manchete e trecho sem diferenciar acentos. Vazio aceita todos. Trata-se de filtro textual, não busca semântica.
- **Fontes:** g1 e/ou Agência Brasil. A seleção limita os feeds consultados; falha não provoca troca silenciosa por fontes não escolhidas.
- **Notícias:** 0 a 15. Zero desativa a consulta. A quantidade é um máximo: filtros, duplicatas e disponibilidade podem resultar em menos notícias.
- **E-mails:** 0 a 10 não lidos recentes. Zero evita consultar Gmail. Continua somente remetente e assunto, sem abrir o corpo nem marcar mensagens como lidas.
- **Ordem:** arraste os cartões ou use Subir/Descer. A saudação permanece primeiro. O cartão de música muda de lugar, mas a reprodução, quando habilitada, começa no início do comando.
- **Música:** ativar/desativar e teto de volume de 0% a 100%. Um volume atual mais baixo é preservado. A playlist já escolhida continua sendo usada.

Preferências ficam em `config/briefing_preferences.json`, com validação e gravação por arquivo temporário. A instalação sem esse arquivo começa com cidade não definida, 5 notícias, 3 e-mails, ambas as fontes e teto musical de 15%. Nenhuma conta ou credencial é gravada nesse arquivo.

Validação: testes de cidade, persistência, limites, ordem, opções desativadas sem acesso aos serviços, filtro de notícias, fontes, volume e interface. Busca real de cidades testada com Araguaína, sem salvar esse local como preferência. Captura do editor: `logs/editor_bom_dia_20261003/editor.png`.
