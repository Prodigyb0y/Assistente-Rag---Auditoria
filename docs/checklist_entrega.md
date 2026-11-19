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
- [ ] Limites de gasto mensais configurados nos consoles OpenAI e Anthropic
- [ ] `python -m pytest -q` passando na sua máquina após o último commit (ambiente de revisão: 313 passando, 1 pulado, em `a3e8ecf`; o autor informou 315 na máquina dele, sem commit registrado: anote o commit ao conferir)
- [ ] Nenhuma chave em código ou no histórico do Git (`git log -p | findstr /i "sk-"` sem resultado)
- [ ] Captura da demo salva em `docs/img/demo.png` (aparece no README). A atual mostra o layout anterior a `bc5575b`: recapturar. O arquivo é Git LFS (necessário para o Hugging Face); em um clone sem `git lfs install` e `git lfs pull` ele aparece como ponteiro de 131 bytes. No GitHub o arquivo real (215.643 bytes) é servido
- [ ] Redesign enviado ao GitHub (`origin`) **e** ao Space (`space`)
- [x] Teste final no Space em janela anônima (resposta com fonte, cache, limite diário, download e troca de tema): nada falhou, no Space em `a3e8ecf` (informado pelo autor, 2026-11-19)
- [ ] A página do GitHub mostra o README novo, sem a tabela de metadados no topo, e a imagem aparece
- [ ] A aba "Sobre o projeto" aparece na demo (Space) e os links dela abrem
- [x] Abstenção com citação não é aceita como resposta (correção em contrato e política, com testes; 313 passando no ambiente de revisão)
- [x] Teto de gasto no código: US$ 4,00 por provedor (BUDGET_*_USD), parada automática antes de ultrapassar.
- [x] Teste final do Space refeito após o redeploy (Space em `a3e8ecf`, confirmado por `git ls-remote space HEAD` e pela API do Space): nada falhou (informado pelo autor, 2026-11-19). O aprovado anterior, feito na versão antiga, foi descartado.
- [ ] Limite de gasto no console de cada provedor: não verificado.- [ ] Revisar `dados/perguntas_orquestracao.json` (O01–O10, `revisado: false`). Até lá, nenhum número dos modos `adaptativo` e `consenso` entra como métrica
- [x] Variável `ORQUESTRACAO_MODO` no Space: não existe (informado pelo autor, 2026-11-19), logo a demo usa o padrão `adaptativo`
- [ ] Rodada completa dos modos `adaptativo` e `consenso` (30 perguntas, pelo menos duas repetições): não feita, por custo (roadmap)
