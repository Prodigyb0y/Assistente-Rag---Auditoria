# Checklist de entrega (definição de pronto)

Marque só o que você verificou. Itens com [ ] ainda dependem de você.

- [ ] Repositório público e organizado: `.env`, `logs/` e `indice/` não aparecem em `git ls-files`
- [ ] README completo no GitHub **e** no Space, com o bloco YAML no topo do README do Space
- [ ] Demo acessível sem instalação (verificada em janela anônima: resposta, cache e limite diário)
- [ ] Dados fictícios identificados como tais (README, demo, `dados/`)
- [ ] Medida de acerto (30/30 por modo, método descrito)
- [ ] Medida de custo por resposta (data da tabela de preços anotada)
- [ ] Medida de latência (`time.perf_counter`)
- [ ] Frase de impacto para um time de auditoria no README
- [ ] Lacuna do Gemini declarada no README
- [ ] Preço do `gpt-6.1-terra` (tabela **Standard**, por 1M tokens) confirmado por você na página oficial. Fontes secundárias
      dizem US$ 1,00 entrada / US$ 5,00 saída; uma leitura automática da página oficial devolveu US$ 0,50 / US$ 2,50 (pode
      ser outra tabela). Se o valor oficial for diferente, atualize `config/precos.json` e **reexecute a avaliação** (o custo
      de cada linha é salvo na execução e não é recalculado por `--so-relatorio`), ou remova a razão de custo do texto
- [ ] Limites de gasto mensais configurados nos consoles OpenAI e Anthropic
- [ ] `python -m pytest -q` passando na sua máquina após o último commit
- [ ] Nenhuma chave em código ou no histórico do Git (`git log -p | findstr /i "sk-"` sem resultado)
- [ ] Captura da demo salva em `docs/img/demo.png` (aparece no README)
- [ ] Redesign enviado ao GitHub (`origin`) **e** ao Space (`space`)
- [ ] Teste final no Space em janela anônima: resposta com fonte, cache, limite diário, download e troca de tema
