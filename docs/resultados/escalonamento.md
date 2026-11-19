# Escalonamento: custo e latência do segundo provedor (gerado por script)

> Gerado por `python -m src.analise.escalonamento` a partir de `docs/resultados/execucoes/*.json`. Análise **descritiva, sem IA**. Não editar à mão.

A regra de quando escalar está em código (`src/orquestrador/politica.py`) e é descrita em [`docs/orquestracao.md`](../orquestracao.md). Este arquivo mede o que ela produziu nas 30 perguntas de `dados/perguntas.json`, em execuções repetidas de cada modo.

## Por execução

| Modo | Exec. | Perguntas com 2º provedor | Estados finais | Motivos | Tentativas (chamadas a agentes) | Custo total (US$) |
|---|---|---|---|---|---|---|
| adaptativo | 1 | 0/30 | aceita_no_primeiro: 30 | nenhum: 30 | 30 | 0,013841 |
| adaptativo | 2 | 0/30 | aceita_no_primeiro: 30 | nenhum: 30 | 30 | 0,014070 |
| consenso | 1 | 30/30 | aceita_por_consenso: 25; divergencia: 5 | nenhum: 30 | 60 | 0,074786 |
| consenso | 2 | 30/30 | aceita_por_consenso: 24; divergencia: 6 | nenhum: 30 | 60 | 0,074265 |

## Com e sem o segundo provedor (média por pergunta)

| Modo | Exec. | Custo sem 2º (US$) | Custo com 2º (US$) | Latência sem 2º (s) | Latência com 2º (s) |
|---|---|---|---|---|---|
| adaptativo | 1 | 0,000461 | - | 4,05 | - |
| adaptativo | 2 | 0,000469 | - | 3,24 | - |
| consenso | 1 | - | 0,002493 | - | 8,17 |
| consenso | 2 | - | 0,002475 | - | 7,77 |

`-` = nenhuma pergunta nessa condição.

## Preço de chamar o segundo provedor sempre

Mesmas 30 perguntas, média das execuções de cada modo:

| | `adaptativo` | `consenso` | Razão (`consenso` ÷ `adaptativo`) |
|---|---|---|---|
| Custo por resposta (US$) | 0,000465 | 0,002484 | 5,3x |
| Latência média (s) | 3,65 | 7,97 | 2,2x |

## Limites deste dado

- 2 execuções por modo: serve para ver ordem de grandeza, não para estimar variância.
- As 30 perguntas têm resposta na base; o `adaptativo` não escalou nelas. Os caminhos de escalonamento (segunda opinião, confirmação cruzada) foram observados nas perguntas O01–O10, em uma única execução, registrada em `docs/orquestracao.md` e em `docs/resultados/analise_roteamento.md`; isso é observação, não taxa.
- Timeout, retry com espera exponencial e fallback entre provedores têm testes unitários, mas nenhuma dessas execuções os acionou (ver a coluna de tentativas: uma por pergunta no `adaptativo`).
