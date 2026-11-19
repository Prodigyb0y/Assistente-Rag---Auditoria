# Checklist de entrega (definição de pronto)

Marque só o que você verificou. Itens com [ ] ainda dependem de você.

- [ ] Repositório público e organizado: `.env`, `logs/` e `indice/` não aparecem em `git ls-files`
- [ ] README completo no GitHub (`.github/README.md`, que o GitHub mostra no lugar do da raiz) e README curto com o bloco YAML no topo do Space (`README.md` da raiz)
- [ ] Demo acessível sem instalação (verificada em janela anônima: resposta, cache e limite diário)
- [ ] Dados fictícios identificados como tais (README, demo, `dados/`)
- [ ] Medida de acerto (30/30 por modo, método descrito)
- [ ] Medida de custo por resposta (data da tabela de preços anotada)
- [ ] Medida de latência (`time.perf_counter`)
- [ ] Frase de impacto para um time de auditoria no README
- [ ] Escopo declarado (OpenAI e Anthropic) e Gemini registrado como lacuna de projeto futuro, no README (seção "Escopo e limitações conhecidas") e em `docs/processo.md`
- [x] Preço do `gpt-6.1-terra` conferido na página oficial (aba Standard, contexto Short, captura de 2026-11-19): US$ 1,00 entrada / US$ 5,00 saída por 1M de tokens. Acima de 272 mil tokens: não verificado
- [ ] Limites de gasto mensais nos consoles OpenAI e Anthropic: dispensado pelo autor (2026-11-19), não verificado. A proteção fica no código (US$ 4,00 por provedor) e no teto diário da demo (US$ 0,25)
- [x] `python -m pytest -q` passando na máquina do autor: 315 passed (informado pelo autor, 2026-11-19; commit não anotado). Ambiente de revisão: 313 passando, 1 pulado
- [x] Nenhuma chave em código ou no histórico do Git: busca por padrões de chave real (`sk-` seguido de 20 ou mais caracteres) em todo o histórico, sem resultado (verificado em 2026-11-19). As ocorrências de `sk-` do `findstr` do autor são placeholders de teste
- [x] Captura da demo salva em `docs/img/demo.png` e exibida no README do GitHub (verificado em 2026-11-19). O arquivo é Git LFS; em um clone sem `git lfs install` e `git lfs pull` ele aparece como ponteiro de texto
- [x] Redesign enviado ao GitHub (`origin`) **e** ao Space (`space`): o autor informou `git ls-remote space HEAD` igual ao hash do GitHub após cada envio (2026-11-19). O histórico foi reescrito em 2026-11-19, a partir de `7950938`, para remover nomes de empresas reais de um commit de documentação; depois disso, confira que `git ls-remote origin HEAD` e `git ls-remote space HEAD` devolvem o mesmo hash
- [x] Teste final no Space em janela anônima (resposta com fonte, cache, limite diário, download e troca de tema): nada falhou, no Space em `a3e8ecf` (informado pelo autor, 2026-11-19)
- [x] A página do GitHub mostra o README novo, sem a tabela de metadados no topo, e a imagem aparece (verificado em 2026-11-19)
- [x] A aba "Sobre o projeto" aparece na demo (Space) e os links dela abrem (informado pelo autor, 2026-11-19)
- [x] Abstenção com citação não é aceita como resposta (correção em contrato e política, com testes; 313 passando no ambiente de revisão)
- [x] Teto de gasto no código: US$ 4,00 por provedor (BUDGET_*_USD), parada automática antes de ultrapassar.
- [x] Teste final do Space refeito após o redeploy (Space em `a3e8ecf`, confirmado por `git ls-remote space HEAD` e pela API do Space): nada falhou (informado pelo autor, 2026-11-19). O aprovado anterior, feito na versão antiga, foi descartado.
- [ ] Limite de gasto no console de cada provedor: não verificado (dispensado pelo autor).
- [x] Gabarito `dados/perguntas_orquestracao.json` (O01–O10) revisado pelo autor (`revisado: true`, 2026-11-19, informado). Os números dos modos `adaptativo` e `consenso` continuam fora das métricas até a rodada completa
- [x] Variável `ORQUESTRACAO_MODO` no Space: não existe (informado pelo autor, 2026-11-19), logo a demo usa o padrão `adaptativo`
- [ ] Rodada completa dos modos `adaptativo` e `consenso` (30 perguntas, pelo menos duas repetições): autorizada pelo autor (2026-11-19), a executar no PC; não feita ainda
- [x] Bloco 4 (saída válida: schema e citações entre os trechos recuperados): aprovado com ressalva. O autor autorizou o assistente, por escrito no chat (2026-11-19), a registrar a aprovação. Evidência: 30/30 com saída válida e citação válida nos modos só OpenAI e só Anthropic (`docs/resultados/avaliacao.md`). Ressalva: a checagem é estrutural, confirma que a seção citada foi recuperada, não que sustenta a resposta; uma execução por modo
