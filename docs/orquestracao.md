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

Concordam quando (1) as seções citadas por uma contêm as da outra e (2) as duas respostas trazem os mesmos números,
**descontados os que já estavam na pergunta** (repetir o número da pergunta não diz nada sobre concordância). A decisão
do par grava no log as seções citadas, os números e a confiança de cada lado (`fontes_a/b`, `numeros_a/b`,
`confianca_a/b`), nunca o texto da resposta. Limite conhecido: **não compara o sentido do texto**, só fontes e números. Na dúvida a regra erra para o lado de
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
  resultado. O gabarito dessas perguntas foi revisado pelo autor (`revisado: true`, 2026-11-19).
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

# 3b. Só algumas perguntas do arquivo (por id)
python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --ids O06,O09 --modo adaptativo

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

- **Correção das respostas:** não foi checada contra o gabarito revisado. O gabarito de `perguntas_orquestracao.json` agora tem `revisado: true`.
- **Por que O06 ficou em melhor esforço e por que O09 divergiu:** ver a próxima seção.
- **Frequência:** uma execução de 10 perguntas não mede com que frequência cada caminho ocorre. A mesma pergunta O02
  gastou 8867/742 tokens em uma execução anterior no mesmo dia e 8835/667 nesta, o que mostra variação entre execuções.
- **Valor do consenso:** não foi medido se o consenso ou a divergência acertam mais que a resposta de um provedor só.
- **Modos `consenso` e `escalonar`, e a ordem `openai,anthropic`:** não executados.

### O que o `logs/roteamento.jsonl` mostra de O06 e O09 (mesma rodada)

- **O06:** a Anthropic se absteve (`nao_encontrado`); a OpenAI trouxe resposta válida, com confiança abaixo de `alta`
  (`confianca_baixa`). Um se absteve e o outro respondeu sem atingir a confiança mínima: não houve aceitação nem
  consenso, e o estado ficou `melhor_esforco` com a resposta da OpenAI. Decisão de projeto em aberto: tratar
  "um se abstém e o outro responde" como `divergencia` em vez de `melhor_esforco`.
- **O09:** a Anthropic respondeu válida com confiança abaixo de `alta`; a OpenAI respondeu válida e passou na regra
  (`motivo: null`). A concordância foi `divergem`, e o estado `divergencia` ficou com a resposta da OpenAI.
- **A causa da divergência de O09 não aparece nesse log**, porque a versão que rodou não gravava as seções citadas nem
  os números. Uma hipótese, **não verificada**: a comparação exigia números idênticos e uma das respostas pode ter
  repetido o R$ 500.000,00 da pergunta. Por isso a comparação passou a descontar os números da pergunta e o log passou a
  gravar a evidência. Só uma nova execução (`--ids O06,O09`) mostra o que de fato diferiu.

### Segunda execução de O06 e O09 (2026-11-19, 16:31, código do commit `336b1f6`)

Comando, executado pelo autor: `python -m src.orquestrador.executar --arquivo dados/perguntas_orquestracao.json --ids O06,O09 --modo adaptativo`
(confiança mínima `alta`, ordem `anthropic > openai`). Saída, sem retoques:

```
prompt=agente_resposta_v1 | ordem=anthropic > openai (preço de lista, tabela de 2026-11-19) | modo=adaptativo | confiança mínima=alta | tentativas=3
O06 melhor_esforco caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=7737/729 custo=0.003205 t=17.2s
O09 aceita_apos_escalonamento caminho=segunda_opiniao rota=anthropic>openai motivo=nao_encontrado concordancia=- tentativas=2 tokens=8914/527 custo=0.004486 t=11.9s
gasto acumulado openai: 0.187395 / teto 4.00 USD
gasto acumulado anthropic: 0.065387 / teto 4.00 USD
```

Evidência gravada em `logs/roteamento.jsonl` (evento `decidir_par`):

| Pergunta | Fontes (Anthropic) | Fontes (OpenAI) | Números (A / B) | Confiança (A / B) | Estado |
|---|---|---|---|---|---|
| O06 | nenhuma (abstenção) | ACE-1, ACE-3 | 12, 90 / 12, 90 | baixa / media | `melhor_esforco` |
| O09 | nenhuma (abstenção) | SFU-3 | 100000,00 e 3 / 100000,00 e 3 | baixa / alta | `aceita_apos_escalonamento` |

O que esta segunda rodada mostra e o que não mostra:

- **Variação entre execuções, observada:** a mesma pergunta O09 seguiu caminhos diferentes. Na primeira rodada a
  Anthropic respondeu com confiança abaixo de `alta` e o par divergiu; agora a Anthropic se absteve e a OpenAI foi
  aceita. A causa da divergência da primeira rodada **continua desconhecida**: ela não se repetiu, e o log daquela
  rodada não tinha a evidência.
- **O06 repetiu:** nas duas execuções a Anthropic se absteve e a OpenAI respondeu com confiança abaixo de `alta`, e o
  resultado foi `melhor_esforco`. Duas execuções não bastam para falar em regularidade.
- **Abstenção com conteúdo:** o texto da abstenção da Anthropic traz os mesmos números (12 e 90 em O06; 100000,00 em
  O09) que a resposta da OpenAI, embora declare `encontrado=false`. Em O06 os dois lados dizem, em termos de números e de
  seções da base, o mesmo; o estado `melhor_esforco` vem de a regra não comparar uma abstenção com uma resposta.
- **Número "3" em O09:** aparece nos dois lados e não é um valor da política. Provavelmente vem do identificador `SFU-3`
  escrito no texto (hipótese; o texto não é gravado). Por isso `numeros` passou a ignorar identificadores de seção, o que
  evita uma divergência falsa quando só um dos lados escreve o identificador.
- Custo desta rodada: US$ 0,007691 (soma das duas perguntas, conferida pela variação do gasto acumulado).

### Linhas do log que sustentam a tabela acima

`logs/roteamento.jsonl` é local (está no `.gitignore`) e não vem com o repositório. As duas linhas abaixo foram
copiadas, sem retoques, da saída que o autor colou do terminal (evento `decidir_par`, execução de 16:31). Os campos
`numeros_*` são números extraídos por expressão regular do texto de cada resposta, sem os que a pergunta já continha;
o texto da resposta não é gravado.

```
{"ts": "2026-11-19T16:31:38-0300", "evento": "decisao", "pergunta_id": "O06", "provedor": "openai", "acao": "decidir_par", "motivo": "nao_encontrado", "para": null, "status": "melhor_esforco", "concordancia": null, "fontes_a": [], "fontes_b": ["POL-ACE/ACE-1", "POL-ACE/ACE-3"], "numeros_a": ["12", "90"], "numeros_b": ["12", "90"], "confianca_a": "baixa", "confianca_b": "media"}
{"ts": "2026-11-19T16:31:50-0300", "evento": "decisao", "pergunta_id": "O09", "provedor": "openai", "acao": "decidir_par", "motivo": "nao_encontrado", "para": null, "status": "aceita_apos_escalonamento", "concordancia": null, "fontes_a": [], "fontes_b": ["POL-SFU/SFU-3"], "numeros_a": ["100000,00", "3"], "numeros_b": ["100000,00", "3"], "confianca_a": "baixa", "confianca_b": "alta"}
```

Estas duas linhas são a única evidência de que a abstenção da Anthropic trouxe os mesmos números que a resposta da OpenAI
em O06 e O09. As linhas do log da primeira rodada (sem a evidência de comparação) não foram preservadas aqui.

## Correção aplicada depois da segunda rodada (2026-11-19)

Revisão do código encontrou um defeito: uma abstenção (`encontrado=false`) que trazia citação de um trecho recuperado
passava na regra e era aceita como resposta (`aceita_no_primeiro`), e podia virar `aceita_por_consenso` com a
resposta de quem encontrou. Isso não tinha teste e não estava documentado.

Correção:
- `src/agentes/contrato.py`: `encontrado=false` com citação passa a ser saída inválida (`citacoes_ok=false`).
- `src/orquestrador/politica.py`: a regra também trata abstenção com citação como `sem_citacao_valida` (defesa extra,
  caso a saída chegue marcada como válida).
- Testes novos: `tests/test_contrato.py` (abstenção com citação é inválida) e `tests/test_cooperacao.py` (abstenção que
  cita não é aceita sozinha nem vira consenso).

Verificação offline: suíte completa com 313 testes passando e 1 pulado (o teste do Gradio, que depende da biblioteca
instalada) no ambiente de desenvolvimento do repositório (a máquina do autor reportou 322 passando, em `dc65568`).

**Efeito esperado, não medido:** perguntas fora da base em que o modelo cite trecho passam a escalar, em vez de serem
aceitas. Nenhuma chamada paga foi feita para verificar isso; a próxima rodada com chave mostra o efeito real.
