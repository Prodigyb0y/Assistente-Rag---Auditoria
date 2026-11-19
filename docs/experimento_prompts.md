# Experimento proposto: variantes de prompt (NÃO EXECUTADO)

Este documento é um **protocolo**. Nada aqui foi executado, e nenhum número abaixo é resultado: os únicos valores
citados são medidas já registradas (custos observados nos logs) e os limiares de decisão, que foram escritos **antes** de
rodar. Os limiares só podem mudar antes da primeira execução, com a alteração registrada no histórico do Git.

## Pergunta

O prompt `agente_resposta_v1` tem um comportamento de abstenção e de confiança que foi observado (ver
`docs/orquestracao.md`), mas nunca comparado com alternativas. Um prompt diferente aumenta a abstenção correta em
perguntas sem resposta na base, sem piorar o acerto nas perguntas com resposta?

## Por que as 30 perguntas atuais não servem

As 30 perguntas de `dados/perguntas.json` dão 30/30 nos dois provedores (efeito teto): não distinguem prompts. O
experimento usa um conjunto mais difícil.

## Conjunto de avaliação (20 perguntas)

| Origem | Perguntas | Resposta esperada |
|---|---|---|
| `dados/perguntas_escalonamento.json` E01 a E05 | 5 fora da base | Abstenção (`encontrado=false`, sem citação) |
| `dados/perguntas_orquestracao.json` O07, O08, O09, O10 | 4 vizinhas da base | Abstenção |
| `dados/perguntas_escalonamento.json` E06 a E10 | 5 na base | Resposta correta com a fonte |
| `dados/perguntas_orquestracao.json` O01 a O05 | 5 que combinam seções | Resposta correta com as fontes |
| `dados/perguntas_orquestracao.json` O06 | 1 ambígua | **Fora da pontuação** (a regra de O06 está em aberto) |

Pontuadas: 19 (9 de abstenção esperada, 10 respondíveis). **Pré-requisito:** o autor revisar o gabarito de O01 a O10
(`revisado: true`). Sem isso, o experimento não roda.

## Variantes

| Id | O que muda em relação à v1 |
|---|---|
| V0 | Controle: `agente_resposta_v1`, sem alteração |
| V1 | `agente_resposta_v2_exemplos`: v1 mais dois exemplos completos (um com resposta, um com abstenção). Os exemplos usam seções da base que **não** aparecem em nenhuma pergunta do conjunto, para não haver vazamento |
| V2 | `agente_resposta_v2_rubrica`: v1 com a rubrica de confiança reescrita em critérios objetivos (ex.: "alta" só quando um único trecho traz o valor pedido e a pergunta não exige combinar trechos) |

Fora desta primeira rodada: instrução de raciocínio passo a passo. Ela exigiria um campo novo no contrato de saída
(mudança de schema nos dois provedores) e fica para depois, se V1 ou V2 mostrarem ganho.

## O que medir (por variante, por provedor, agente isolado, sem orquestrador)

| Id | Medida | Como |
|---|---|---|
| M1 | Abstenção correta | Entre as 9 de abstenção esperada: quantas saíram com `encontrado=false` e nenhuma citação |
| M2 | Acerto | Entre as 10 respondíveis: quantas trazem todos os fatos-chave do gabarito revisado (mesma regra de `src/avaliacao/acerto.py`) |
| M3 | Citação válida | Entre as 19: quantas passam na verificação de citação |
| M4 | Confiança nas corretas | Entre as respostas corretas de M2: quantas vieram com "alta" |
| M5 | Custo e tokens | Média de tokens de entrada e saída e custo por pergunta, pela tabela de preços da data |

Cada combinação variante × provedor roda **3 vezes**, porque a mesma pergunta (O09) já seguiu caminhos diferentes em duas
execuções no mesmo dia. Relata-se o valor de cada repetição, não só a média.

## Critério de decisão (escrito antes de rodar)

Uma variante Vx vira a nova versão padrão **somente se todas** as condições valem:

1. **Sem regressão:** em M2, nenhuma repetição de Vx fica abaixo da pior repetição de V0, em nenhum dos dois provedores;
   e, numa execução de confirmação, as 30 perguntas da base continuam em 30/30 nos dois provedores.
2. **Ganho:** em M1, a média das 3 repetições de Vx é pelo menos 2 perguntas maior que a de V0 (de 9), em pelo menos um
   provedor, e não é menor no outro.
3. **Custo:** o custo médio por pergunta de Vx é no máximo 120% do de V0.

Se nenhuma variante cumprir, **fica a v1** e o resultado negativo é registrado. Uma variante que cumpra vira
`agente_resposta_v2` e a avaliação completa (`python -m src.avaliacao.executar`) é refeita com ela.

## Pré-requisitos de implementação (não feitos)

- Opção `--prompt-versao` nos executáveis (hoje só existe a v1 por padrão em `carregar_prompt`).
- Arquivos dos prompts V1 e V2.
- Um executável que rode só o agente isolado nas 20 perguntas e grave M1 a M5.

## Custo máximo estimado

180 execuções de agente por provedor (20 perguntas × 3 variantes × 3 repetições), 360 no total. O maior custo de uma
única pergunta nas rodadas registradas foi US$ 0,005805 (O10, com os dois provedores chamados); uma execução de um agente
sozinho não custa mais que isso. Limite superior: 360 × 0,005805 ≈ **US$ 2,09** no total, **US$ 1,05 por provedor** se o
pior caso se repetisse em todas. É um teto de segurança, não uma previsão: o gasto real tende a ser menor. Os exemplos da
V1 aumentam os tokens de entrada, então o gasto acumulado deve ser conferido durante a execução. O teto de US$ 4,00 por
provedor continua valendo.

## Limitações previstas

- 19 perguntas pontuadas é pouco: diferenças de 1 ou 2 perguntas podem ser variação.
- O conjunto difícil foi desenhado depois de ver as falhas do orquestrador (viés de seleção).
- Os dados são fictícios; o resultado não vale para documentos reais.
- Dois provedores, um modelo de cada: o resultado não generaliza para outros modelos.
