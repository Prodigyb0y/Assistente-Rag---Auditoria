# Checklist de entrega (definição de pronto)

Estado verificado em 2026-11-19. `[x]` = verificado; `[ ]` = pendente. Itens "informado pelo autor" não foram verificados pelo repositório.

## Entrega

- [x] Repositório público e organizado: `.env`, `logs/` e `indice/` não aparecem em `git ls-files`
- [x] README completo no GitHub (`.github/README.md`) e README curto com o bloco YAML no topo do Space (`README.md` da raiz)
- [x] Demo acessível sem instalação, testada em janela anônima (resposta com fonte, cache, limite diário, download, troca de tema, aba "Sobre o projeto"): nada falhou (informado pelo autor)
- [x] Dados fictícios identificados como tais (README, demo, `dados/`)
- [x] Medida de acerto (30/30 por modo, método descrito)
- [x] Medida de custo por resposta (data da tabela de preços anotada)
- [x] Medida de latência (`time.perf_counter`)
- [x] Frase de impacto para um time de auditoria no README
- [x] Escopo declarado (OpenAI e Anthropic); Gemini registrado como lacuna de projeto futuro no README e em `docs/processo.md`
- [x] Captura da demo em `docs/img/demo.png` (Git LFS; em um clone sem `git lfs pull` aparece como ponteiro de texto)
- [x] GitHub (`origin`) e Space (`space`) no mesmo commit, `ae4f0ad`, conferido por `git ls-remote` (informado pelo autor, 2026-11-19). Histórico do Space sem nomes de empresas reais (busca em `git log -p`, sem resultado)

## Qualidade e segurança

- [x] `python -m pytest -q`: 326 passed na máquina do autor, commit `ae4f0ad` (informado pelo autor, 2026-11-19); no ambiente de desenvolvimento do repositório: 324 passed e 1 pulado
- [x] Nenhuma chave em código ou no histórico do Git: busca por padrões de chave real (`sk-` seguido de 20 ou mais caracteres) em todo o histórico, sem resultado. As ocorrências de `sk-` são placeholders de teste
- [x] Nenhum nome de empresa real no repositório nem no histórico (histórico reescrito em 2026-11-19; commits antigos podem continuar acessíveis por hash em forks e clones até o GitHub os expirar)
- [x] Teto de gasto no código: US$ 4,00 por provedor (`BUDGET_*_USD`), com parada automática antes de ultrapassar; teto diário da demo: US$ 0,25
- [x] Abstenção com citação não é aceita como resposta (contrato e política, com testes)

## Dados e preços

- [x] Preço do `gpt-6.1-terra` conferido na página oficial (aba Standard, contexto Short, captura de 2026-11-19): US$ 1,00 entrada / US$ 5,00 saída por 1M de tokens. Acima de 272 mil tokens: não verificado
- [x] Gabarito `dados/perguntas_orquestracao.json` (O01–O10) revisado (`revisado: true`, informado pelo autor)
- [x] Variável `ORQUESTRACAO_MODO` não existe no Space (informado pelo autor); a demo usa o padrão `adaptativo`
- [x] Bloco 4 (saída válida: schema e citações entre os trechos recuperados): aprovado com ressalva. Evidência: 30/30 com saída válida e citação válida nos modos só OpenAI e só Anthropic (`docs/resultados/avaliacao.md`). Ressalva: a checagem é estrutural, confirma que a seção citada foi recuperada, não que sustenta a resposta; uma execução por modo

- [x] Rodada completa dos modos `adaptativo` e `consenso` (30 perguntas, 2 execuções cada, 2026-11-19): `docs/resultados/execucoes.md`, gerado por `python -m src.avaliacao.execucoes`
- [x] Análise de escalonamento (custo e latência do segundo provedor) em `docs/resultados/escalonamento.md`, gerada por `python -m src.analise.escalonamento` a partir das execuções repetidas
