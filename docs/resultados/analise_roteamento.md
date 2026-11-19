# Análise do log de roteamento (gerada por script)

> Gerado por `python -m src.analise.roteamento` a partir de `logs/roteamento.jsonl` (cópia do log local do autor, 2026-11-19). Análise **descritiva, sem IA**: conta eventos `final` e soma custo e latência. Não testa hipótese nem prevê outras perguntas.

## Escopo do dado

- Linhas lidas: 112 (inválidas ignoradas: 0); perguntas finais (`final`): 28.
- Período: 2026-11-19T13:10:13-0300 a 2026-11-19T16:31:50-0300.
- Custo total dessas perguntas: US$ 0.074811; tokens: 192741 de entrada e 12202 de saída.

## Por estado final

| Estado | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| aceita_no_primeiro | 14 | 0.007172 | 0.000512 | 4.2 |
| melhor_esforco | 7 | 0.035306 | 0.005044 | 16.1 |
| nao_encontrado_confirmado | 3 | 0.015695 | 0.005232 | 16.6 |
| aceita_apos_escalonamento | 2 | 0.008921 | 0.004461 | 12.7 |
| aceita_por_consenso | 1 | 0.004435 | 0.004435 | 12.5 |
| divergencia | 1 | 0.003281 | 0.003281 | 16.2 |

## Por modo e estado final

| Modo / estado | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| (sem registro) / aceita_no_primeiro | 8 | 0.003810 | 0.000476 | 3.9 |
| adaptativo / aceita_no_primeiro | 6 | 0.003362 | 0.000560 | 4.6 |
| (sem registro) / melhor_esforco | 5 | 0.029041 | 0.005808 | 17.2 |
| adaptativo / nao_encontrado_confirmado | 3 | 0.015695 | 0.005232 | 16.6 |
| adaptativo / aceita_apos_escalonamento | 2 | 0.008921 | 0.004461 | 12.7 |
| adaptativo / melhor_esforco | 2 | 0.006265 | 0.003133 | 13.2 |
| adaptativo / aceita_por_consenso | 1 | 0.004435 | 0.004435 | 12.5 |
| adaptativo / divergencia | 1 | 0.003281 | 0.003281 | 16.2 |

## Por motivo de escalonamento (o que impediu aceitar a primeira resposta)

| Motivo | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| nenhum (aceito no primeiro) | 14 | 0.007172 | 0.000512 | 4.2 |
| nao_encontrado | 6 | 0.026446 | 0.004408 | 14.7 |
| sem_citacao_valida | 5 | 0.029041 | 0.005808 | 17.2 |
| confianca_baixa | 3 | 0.012152 | 0.004051 | 14.0 |

## Por caminho

| Caminho | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| (sem registro) | 13 | 0.032851 | 0.002527 | 9.0 |
| direto | 6 | 0.003362 | 0.000560 | 4.6 |
| segunda_opiniao | 6 | 0.026446 | 0.004408 | 14.7 |
| confirmacao_cruzada | 3 | 0.012152 | 0.004051 | 14.0 |

## Por provedor da resposta final

| Provedor | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| anthropic | 23 | 0.056343 | 0.002450 | 9.0 |
| openai | 5 | 0.018467 | 0.003693 | 13.6 |

## Custo de chamar mais de um provedor

| Provedores chamados | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |
|---|---|---|---|---|
| 1 | 14 | 0.007172 | 0.000512 | 4.2 |
| 2 | 14 | 0.067638 | 0.004831 | 15.4 |

## Comparação entre os dois provedores (eventos `decidir_par`)

| Resultado | Eventos |
|---|---|
| não comparado | 7 |
| concordam | 1 |
| divergem | 1 |

## Limites desta análise

- O log acumula execuções de datas, modos e configurações diferentes; a confiança mínima de cada execução não é gravada, então não dá para separar execuções feitas com `media` das feitas com `alta`.
- A mesma pergunta pode aparecer mais de uma vez (execuções repetidas) e é contada cada vez.
- Eventos sem os campos `modo` e `caminho` aparecem como "(sem registro)" e vêm de versões anteriores do código.
- Os grupos são pequenos; as médias descrevem estas execuções e não permitem concluir sobre a frequência esperada em outras perguntas.
