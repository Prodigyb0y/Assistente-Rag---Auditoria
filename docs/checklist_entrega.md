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
- [ ] Lacuna do Gemini declarada no README (seção "Escopo e limitações conhecidas")
- [x] Preço do `gpt-6.1-terra` conferido na página oficial (aba Standard, contexto Short, captura de 2026-11-19): US$ 1,00 entrada / US$ 5,00 saída por 1M de tokens. Acima de 272 mil tokens: não verificado
- [ ] Limites de gasto mensais configurados nos consoles OpenAI e Anthropic
- [ ] `python -m pytest -q` passando na sua máquina após o último commit
- [ ] Nenhuma chave em código ou no histórico do Git (`git log -p | findstr /i "sk-"` sem resultado)
- [ ] Captura da demo salva em `docs/img/demo.png` (aparece no README)
- [ ] Redesign enviado ao GitHub (`origin`) **e** ao Space (`space`)
- [ ] Teste final no Space em janela anônima: resposta com fonte, cache, limite diário, download e troca de tema
- [ ] A página do GitHub mostra o README novo, sem a tabela de metadados no topo, e a imagem aparece
- [ ] A aba "Sobre o projeto" aparece na demo (Space) e os links dela abrem
- [x] Teto de gasto no código: US$ 4,00 por provedor (BUDGET_*_USD), parada automática antes de ultrapassar.
- [x] Teste final do Space em janela anônima: aprovado (informado pelo autor, 2026-11-19).
- [ ] Limite de gasto no console de cada provedor: não verificado.