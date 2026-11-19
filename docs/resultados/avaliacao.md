# Resultados da avaliação (gerado por script)

> Arquivo gerado por `python -m src.avaliacao.executar`. Não edite à mão: rode o script de novo.

- Data da execução: **2026-11-19**
- Prompt: `agente_resposta_v1` (sha `fa2fae0534e7`)
- Modelos: openai=`gpt-6.1-terra`, anthropic=`claude-haiku-5-5`
- Preços: tabela `config/precos.json` consultada em **2026-11-19**
- Base: dados **fictícios** (Gutenberg Systems), 30 perguntas com gabarito

## Tabela de resultados

| Modo | Acerto | Citação válida | Cita a seção do gabarito | Custo por resposta (US$) | Latência média (s) | Latência mediana (s) | Respondidas |
|---|---|---|---|---|---|---|---|
| Só OpenAI | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 0.002024 | 6.43 | 6.15 | 30/30 |
| Só Anthropic | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 0.000467 | 3.41 | 3.52 | 30/30 |
| Orquestrado | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 0.000469 | 2.86 | 2.96 | 30/30 |

| Modo | Custo total (US$) | Tokens de entrada | Tokens de saída | Latência máxima (s) | Respostas escalonadas | Tentativas extras (retry) | Resposta final por provedor |
|---|---|---|---|---|---|---|---|
| Só OpenAI | 0.060731 | 44277 | 3288 | 8.92 | 0 | 0 | openai: 30 |
| Só Anthropic | 0.014016 | 107939 | 6427 | 6.21 | 0 | 0 | anthropic: 30 |
| Orquestrado | 0.014067 | 107862 | 6543 | 4.85 | 0 | 0 | anthropic: 30 |

## Como cada métrica foi medida

- **Acerto**: respostas corretas ÷ perguntas do gabarito. Uma resposta é correta se o agente respondeu (`encontrado=true`) e o texto contém todos os fatos-chave da pergunta (`dados/fatos_chave.json`, derivados do gabarito), comparados sem acento e sem diferença de maiúsculas, em palavra inteira.
- **Citação válida**: saída em JSON conforme o schema e todas as citações entre os trechos que o agente de fato recuperou nessa execução. Não significa que a resposta esteja correta.
- **Cita a seção do gabarito**: a seção de origem do gabarito está entre as citadas.
- **Custo por resposta**: tokens de entrada e saída reais de cada chamada × preço da tabela (consulta em 2026-11-19), somando a busca (embedding da consulta) e **todas** as tentativas e provedores usados naquela pergunta, ÷ respostas obtidas.
- **Latência**: `time.perf_counter()` da chegada da pergunta até a resposta final, incluindo busca, chamadas ao modelo, esperas de retry e, no modo orquestrado, o segundo provedor quando chamado.
- Os três modos passam pelo mesmo orquestrador; os modos de provedor único têm retry, mas não fallback.

## Limites e ressalvas

- **Uma única execução por modo**: sem repetição, não há intervalo de confiança. Latência varia com a rede e a primeira chamada de uma execução costuma ser mais lenta (conexão fria). Prefira a mediana.
- A regra de acerto confere a **presença** dos fatos esperados, não a **ausência** de fatos errados, nem entende negação. A seção "Auditoria do acerto" lista cada resposta para revisão humana.
- Sobrescritas manuais de acerto (`dados/acerto_manual.json`): **0**.
- **O preço de `gpt-6.1-terra` (US$ 1.0/5.0 por 1M de tokens) NÃO foi confirmado na página oficial do provedor no momento desta execução.** Os custos da OpenAI e do modo orquestrado usam esse preço. Depois da execução, o autor conferiu a página oficial em 2026-11-19; a fonte está em `config/precos.json`.
- Base pequena, fictícia e com vocabulário compartilhado entre as perguntas e os documentos: os números não se generalizam para documentos reais.
- Gemini não faz parte deste projeto (restrição de escopo): é uma lacuna a fechar depois.

## Auditoria do acerto (por pergunta)

| Pergunta | Só OpenAI | Só Anthropic | Orquestrado |
|---|---|---|---|
| Q01 | ✓ | ✓ | ✓ ←anthropic |
| Q02 | ✓ | ✓ | ✓ ←anthropic |
| Q03 | ✓ | ✓ | ✓ ←anthropic |
| Q04 | ✓ | ✓ | ✓ ←anthropic |
| Q05 | ✓ | ✓ | ✓ ←anthropic |
| Q06 | ✓ | ✓ | ✓ ←anthropic |
| Q07 | ✓ | ✓ | ✓ ←anthropic |
| Q08 | ✓ | ✓ | ✓ ←anthropic |
| Q09 | ✓ | ✓ | ✓ ←anthropic |
| Q10 | ✓ | ✓ | ✓ ←anthropic |
| Q11 | ✓ | ✓ | ✓ ←anthropic |
| Q12 | ✓ | ✓ | ✓ ←anthropic |
| Q13 | ✓ | ✓ | ✓ ←anthropic |
| Q14 | ✓ | ✓ | ✓ ←anthropic |
| Q15 | ✓ | ✓ | ✓ ←anthropic |
| Q16 | ✓ | ✓ | ✓ ←anthropic |
| Q17 | ✓ | ✓ | ✓ ←anthropic |
| Q18 | ✓ | ✓ | ✓ ←anthropic |
| Q19 | ✓ | ✓ | ✓ ←anthropic |
| Q20 | ✓ | ✓ | ✓ ←anthropic |
| Q21 | ✓ | ✓ | ✓ ←anthropic |
| Q22 | ✓ | ✓ | ✓ ←anthropic |
| Q23 | ✓ | ✓ | ✓ ←anthropic |
| Q24 | ✓ | ✓ | ✓ ←anthropic |
| Q25 | ✓ | ✓ | ✓ ←anthropic |
| Q26 | ✓ | ✓ | ✓ ←anthropic |
| Q27 | ✓ | ✓ | ✓ ←anthropic |
| Q28 | ✓ | ✓ | ✓ ←anthropic |
| Q29 | ✓ | ✓ | ✓ ←anthropic |
| Q30 | ✓ | ✓ | ✓ ←anthropic |

