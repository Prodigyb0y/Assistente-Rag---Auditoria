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
- [ ] Preço do `gpt-6.1-terra` confirmado na página oficial **ou** a razão de custo OpenAI/Anthropic removida do texto
- [ ] Limites de gasto mensais configurados nos consoles OpenAI e Anthropic
- [ ] `python -m pytest -q` passando na sua máquina após o último commit
- [ ] Nenhuma chave em código ou no histórico do Git (`git log -p | findstr /i "sk-"` sem resultado)
