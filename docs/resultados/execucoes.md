# Execuções repetidas dos modos de orquestração

Gerado por script (`python -m src.avaliacao.execucoes`) a partir de `docs/resultados/execucoes/*.json`. Não editar à mão.

Cada linha é uma execução completa das 30 perguntas de `dados/perguntas.json`. Custo por resposta = soma dos custos das chamadas (todas as tentativas e provedores, mais a busca) ÷ 30. Latência medida com `time.perf_counter`, por pergunta, incluindo todas as chamadas da pergunta.

| Modo | Execução | Acerto | Citação válida | Custo por resposta (US$) | Latência média (s) | Latência mediana (s) | Latência máxima (s) | Perguntas com os 2 provedores | Divergências |
|---|---|---|---|---|---|---|---|---|---|
| adaptativo | 1 | 30/30 | 30/30 | 0,000461 | 4,05 | 2,98 | 25,02 | 0/30 | nenhuma |
| adaptativo | 2 | 30/30 | 30/30 | 0,000469 | 3,24 | 3,07 | 6,78 | 0/30 | nenhuma |
| consenso | 1 | 30/30 | 30/30 | 0,002493 | 8,17 | 7,69 | 14,68 | 30/30 | Q01, Q12, Q15, Q19, Q21 |
| consenso | 2 | 30/30 | 30/30 | 0,002475 | 7,77 | 7,58 | 12,27 | 30/30 | Q01, Q02, Q19, Q21, Q23, Q28 |

## Média entre execuções

| Modo | Execuções | Custo por resposta (US$) | Latência média (s) |
|---|---|---|---|
| adaptativo | 2 | 0,000465 | 3,65 |
| consenso | 2 | 0,002484 | 7,97 |

Com 2 execuções por modo, a média é só um resumo: a variação entre execuções (principalmente de latência, com picos isolados na primeira chamada) é parte do resultado e está na tabela acima.
