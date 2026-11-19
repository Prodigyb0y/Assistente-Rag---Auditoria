# Orquestração: modos, decisões e como exercitar cada caminho

Todos os dados são fictícios (Gutenberg Systems). Este documento descreve o que está **implementado e testado
offline** e o que ainda **não foi medido** com os modelos reais.

## Por que mudar a orquestração

A rodada de 2026-11-19 (`dados/perguntas_escalonamento.json`, `CONFIANCA_MINIMA=alta`) mostrou duas coisas:

1. As 5 perguntas fora da base escalaram da Anthropic para a OpenAI e terminaram em `melhor_esforco`, com custo de
   cerca de US$ 0,006 cada. Para uma pergunta fora da base, **a resposta correta é "não encontrado"**. A regra
   original tratava essa abstenção correta como falha, pagava o segundo provedor e a resposta não entrava no cache.
2. As 5 perguntas da base foram aceitas no primeiro provedor. A OpenAI nunca teve uma resposta aceita pelo
   orquestrador, e o escalonamento por confiança não foi exercitado.

O caminho era binário: o primeiro basta, ou pergunta ao outro e fica com o que vier. Os novos modos dão ao
orquestrador mais de dois caminhos, escolhidos pelo sinal que a primeira resposta devolve.

## Modos (`ORQUESTRACAO_MODO` ou `--modo`)

| Modo | O que faz | Chamadas por pergunta |
|---|---|---|
| `escalonar` | Regra original: pergunta ao outro provedor se o primeiro não passa na regra. | 1 ou 2 |
| `adaptativo` (padrão) | Escolhe o caminho pelo sinal da primeira resposta (tabela abaixo). | 1 ou 2 |
| `consenso` | Os dois provedores sempre respondem; as respostas são comparadas. | 2 |

Modos de provedor único (usados na avaliação "só OpenAI" e "só Anthropic") sempre seguem a regra original.

### Caminhos do modo adaptativo

| Sinal da 1ª resposta | Caminho | Resultado possível |
|---|---|---|
| Válida, com citação, confiança ≥ mínima | `direto` (não chama o 2º) | `aceita_no_primeiro` |
| Abstenção (`encontrado=false`, sem citação) | `segunda_opiniao` | `aceita_apos_escalonamento` (o 2º achou), `nao_encontrado_confirmado` (os dois se abstiveram) |
| Erro, saída fora do schema ou citação inventada | `segunda_opiniao` | `aceita_apos_escalonamento` ou `melhor_esforco` |
| Válida, mas confiança abaixo da mínima | `confirmacao_cruzada` | `aceita_por_consenso` (concordam), `divergencia` (diferem) |

No modo `consenso` o 2º provedor responde sempre, inclusive quando o 1º já passou na regra.

### Como duas respostas são comparadas (`politica.comparar`)

Concordam quando (1) as seções citadas por uma contêm as da outra e (2) as duas respostas trazem os mesmos números.
Limite conhecido: **não compara o sentido do texto**, só fontes e números. Na dúvida a regra erra para o lado de
divergir (pede revisão humana), nunca para o de aceitar. Duas respostas com confiança "baixa" não formam consenso.

### Estados finais

`aceita_no_primeiro`, `aceita_apos_escalonamento`, `aceita_por_consenso` e `nao_encontrado_confirmado` contam como
aceitos (entram no cache da demo). `divergencia`, `melhor_esforco` e `falha` não. A demo mostra um aviso próprio para
cada um (`src/interface/chat.py`).

## O que foi verificado e o que não foi

- **Verificado (offline, agentes falsos):** cada linha das tabelas acima tem teste em `tests/test_cooperacao.py`,
  inclusive o caminho em que a OpenAI é aceita depois de a Anthropic se abster. A suíte inteira passa na minha
  execução local de 2026-11-19 (Python 3.13, sem as bibliotecas dos provedores e sem Gradio).
- **Não verificado:** o comportamento dos modelos reais nesses caminhos. As perguntas em
  `dados/perguntas_orquestracao.json` foram escritas para provocá-los, mas `caminho_visado` é **hipótese**, não
  resultado. O gabarito dessas perguntas tem `revisado: false` até o autor revisar.
- **Não executado:** nenhuma chamada paga foi feita para esta mudança. A CLI (`--modo`, `--ordem`) não tem teste
  automatizado porque monta os agentes reais.
- A avaliação publicada em `docs/resultados/avaliacao.md` foi gerada com a regra original (`escalonar`) e continua
  valendo para esse modo. Nenhuma execução da avaliação completa foi feita no modo `adaptativo`.
- O rótulo do motivo mudou: uma abstenção agora aparece como `nao_encontrado` (antes `sem_citacao_valida`) em
  `logs/roteamento.jsonl`.

## Como exercitar cada caminho (com chamadas pagas: rode só com sua autorização)

O teto de US$ 4,00 por provedor continua valendo. `consenso` e `--ordem openai,anthropic` gastam mais por pergunta,
porque chamam o modelo mais caro. Comece com `--limite 3`.

```
# 1. Caminhos adaptativos nas perguntas de orquestração (PowerShell: $env:CONFIANCA_MINIMA="alta")
python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --modo adaptativo --limite 10

# 2. Os dois provedores em todas as perguntas (consenso)
python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --modo consenso --limite 10

# 3. OpenAI como primeiro provedor: as respostas dela passam a ser aceitas ou recusadas pela regra
python -m src.orquestrador.executar --arquivo dados/perguntas_escalonamento.json --ordem openai,anthropic --limite 10

# 4. Regra original, para comparar
python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --modo escalonar --limite 10
```

Cada linha de saída traz `status`, `caminho`, `rota`, `motivo`, `concordancia`, tokens, custo e latência. As decisões
completas ficam em `logs/roteamento.jsonl`.

Critério para dizer que um caminho foi exercitado: aparecer ao menos uma vez na saída com o `status` e o `caminho`
esperados. Um único caso não mede frequência.

## Primeira observação real (2026-11-19)

Comando, executado pelo autor na máquina dele, com `CONFIANCA_MINIMA=alta` (o `.env` do autor), ordem `anthropic > openai`
(preço de lista), prompt `agente_resposta_v1`, uma única execução, código no commit `93faaa1`:

```
python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --modo adaptativo --limite 10
```

Saída, sem retoques:

```
prompt=agente_resposta_v1 | ordem=anthropic > openai (preço de lista, tabela de 2026-11-19) | modo=adaptativo | confiança mínima=alta | tentativas=3
O01 aceita_no_primeiro caminho=direto rota=anthropic motivo=- concordancia=- tentativas=1 tokens=4159/380 custo=0.000606 t=7.0s
O02 aceita_por_consenso caminho=confirmacao_cruzada rota=anthropic>openai motivo=confianca_baixa concordancia=concordam tentativas=2 tokens=8835/667 custo=0.004435 t=12.5s
O03 aceita_no_primeiro caminho=direto rota=anthropic motivo=- concordancia=- tentativas=1 tokens=3783/367 custo=0.000563 t=3.6s
O04 aceita_no_primeiro caminho=direto rota=anthropic motivo=- concordancia=- tentativas=1 tokens=3616/311 custo=0.000518 t=2.5s
O05 aceita_no_primeiro caminho=direto rota=anthropic motivo=- concordancia=- tentativas=1 tokens=3656/304 custo=0.000518 t=2.3s
O06 melhor_esforco caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=7705/582 custo=0.003060 t=9.2s
O07 nao_encontrado_confirmado caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=9910/533 custo=0.005664 t=16.1s
O08 nao_encontrado_confirmado caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=8612/559 custo=0.004226 t=18.4s
O09 divergencia caminho=confirmacao_cruzada rota=anthropic>openai motivo=confianca_baixa concordancia=divergem tentativas=2 tokens=7875/719 custo=0.003281 t=16.2s
O10 nao_encontrado_confirmado caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=10278/590 custo=0.005805 t=15.2s
gasto acumulado openai: 0.181398 / teto 4.00 USD
gasto acumulado anthropic: 0.063693 / teto 4.00 USD
```

### Caminhos observados

| Caminho / estado | Perguntas |
|---|---|
| `direto` → `aceita_no_primeiro` | O01, O03, O04, O05 |
| `confirmacao_cruzada` → `aceita_por_consenso` | O02 |
| `confirmacao_cruzada` → `divergencia` | O09 |
| `segunda_opiniao` → `nao_encontrado_confirmado` | O07, O08, O10 |
| `segunda_opiniao` → `melhor_esforco` | O06 |

Os quatro estados novos apareceram ao menos uma vez, e a resposta da OpenAI foi aceita em O02 (consenso).

### Hipótese (`caminho_visado`) contra o observado

| Pergunta | Tipo | Hipótese | Observado |
|---|---|---|---|
| O01, O03, O04, O05 | combina seções | confirmação cruzada | `direto`: a Anthropic respondeu com confiança alta |
| O02 | combina seções | confirmação cruzada | confirmação cruzada, consenso |
| O06 | ambígua | confirmação cruzada ou divergência | segunda opinião, melhor esforço |
| O07, O08, O10 | vizinha da base | segunda opinião | segunda opinião, não encontrado confirmado |
| O09 | vizinha da base | segunda opinião | confirmação cruzada, divergência |

A hipótese se confirmou em 4 das 10 perguntas (O02, O07, O08, O10). Perguntas que combinam seções não bastaram para
baixar a confiança do modelo na maioria dos casos.

### Custo observado

Soma das 10 perguntas: US$ 0,028676 (conferida com a variação do gasto acumulado: OpenAI de 0,159925 para 0,181398 e
Anthropic de 0,056490 para 0,063693, medidas entre a rodada de 3 perguntas e esta). Os casos `direto` custaram
US$ 0,000518 a 0,000606; os que chamaram os dois provedores, US$ 0,003060 a 0,005805. Com 10 perguntas e uma execução,
isso descreve estas perguntas, não uma média esperada.

### O que esta observação não prova

- **Correção das respostas:** não foi checada. O gabarito de `perguntas_orquestracao.json` segue com `revisado: false`.
- **Por que O06 ficou em melhor esforço e por que O09 divergiu:** a saída resumida não mostra. O detalhe está em
  `logs/roteamento.jsonl` e não foi analisado.
- **Frequência:** uma execução de 10 perguntas não mede com que frequência cada caminho ocorre. A mesma pergunta O02
  gastou 8867/742 tokens em uma execução anterior no mesmo dia e 8835/667 nesta, o que mostra variação entre execuções.
- **Valor do consenso:** não foi medido se o consenso ou a divergência acertam mais que a resposta de um provedor só.
- **Modos `consenso` e `escalonar`, e a ordem `openai,anthropic`:** não executados.
