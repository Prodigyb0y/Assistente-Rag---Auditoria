<div align="center">

# Assistente de busca em políticas de auditoria

**Responde perguntas de um auditor interno com a fonte citada, orquestrando OpenAI e Anthropic.**

![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![Gradio 6](https://img.shields.io/badge/UI-Gradio%206-F97316)
![Provedores](https://img.shields.io/badge/provedores-OpenAI%20%2B%20Anthropic-4F46E5)
![Dados](https://img.shields.io/badge/dados-100%25%20fict%C3%ADcios-success)

[**Abrir a demo**](https://huggingface.co/spaces/bEniac/Assistente_RAG) ·
[Processo](../docs/processo.md) ·
[Resultados](../docs/resultados/avaliacao.md) ·
[Deploy](../docs/deploy_hf_spaces.md)

<img src="../docs/img/demo.png" alt="Demo em formato de chat: pergunta, resposta com a fonte e o trecho citado, download do documento" width="860">

</div>

> **Todos os documentos, perguntas e dados são fictícios** (empresa fictícia Gutenberg Systems). Nenhum dado, sistema ou
> processo de empresa real foi usado. O sistema é **apoio à busca**: não toma decisão de auditoria, não emite parecer e
> não substitui a leitura do documento.

## Por que isso importa para um time de auditoria

O auditor gasta tempo localizando e conferindo o trecho da política que sustenta uma conclusão. Este sistema devolve a
resposta já com a **seção citada e verificada contra o que foi realmente recuperado**, para que a conferência leve
segundos, e deixa a decisão de auditoria com a pessoa.

## Sumário

[Por que existe](#por-que-este-projeto-existe) · [Resultados](#resultados-medidos) · [Arquitetura](#arquitetura) ·
[Decisões de engenharia](#decisões-de-engenharia) · [Como rodar](#como-rodar) ·
[Escopo e limitações](#escopo-e-limitações-conhecidas) · [Roadmap](#roadmap) · [Estrutura](#estrutura-do-repositório) · [Referências](#referências-públicas)

## Por que este projeto existe

Em auditoria interna, uma parte relevante de cada análise é localizar, entre vários documentos de política, o trecho que
sustenta uma conclusão, e depois conferir se ele foi lido e citado corretamente. O trabalho é repetitivo, e um erro de
citação (trecho errado, seção errada) enfraquece a evidência. Exemplo de pergunta: *"com que frequência os acessos
privilegiados são revisados e por quem?"*.

**O cenário.** Na Gutenberg Systems (fictícia), as políticas ficam em um portal de documentos cuja busca localiza apenas
pelo **código ou título da norma** (por exemplo, `POL-ACE`), sem busca por significado. Quem não sabe qual norma trata do
assunto precisa deduzir o código e abrir um documento de cada vez. Esta é a premissa do cenário fictício, não uma medição.

**Ilustração (premissa, não medida).** O tempo de achar a norma em um portal depende do portal e de quem busca, e **não foi
medido** neste projeto. Para dar a dimensão, a tabela mostra a economia por pergunta *se* a busca levasse T minutos, contra
a latência média medida do modo orquestrado (2,86 s). Não inclui o tempo de conferir a fonte citada, que continua sendo do
auditor.

| Se a busca manual levasse | Sistema (média medida) | Diferença por pergunta |
|---|---|---|
| 2 min | 2,9 s | cerca de 1 min 57 s |
| 5 min | 2,9 s | cerca de 4 min 57 s |
| 10 min | 2,9 s | cerca de 9 min 57 s |

O sistema automatiza a **busca e a citação**, não a conclusão. O processo completo, os riscos (alucinação, citação
errada, vazamento de dados) e o que o sistema **não** faz estão em [`docs/processo.md`](../docs/processo.md).

**O que o projeto mede:** o tempo que o sistema leva para responder (latência média de 2,4 a 6,4 s por pergunta, conforme o modo; veja a tabela abaixo). Não afirma, por ora, uma economia de tempo frente à busca manual: essa comparação faz parte do roadmap, com método descrito.

## Resultados medidos

Base: 30 perguntas com gabarito escrito **antes** dos testes e revisado pelo autor
([`dados/perguntas.json`](../dados/perguntas.json)). Execução única por modo, em **2026-11-19**, prompt `agente_resposta_v1`.
A tabela completa é gerada por script em [`docs/resultados/avaliacao.md`](../docs/resultados/avaliacao.md).

| Modo | Acerto | Citação válida | Custo por resposta | Latência média |
|---|---|---|---|---|
| Só OpenAI (`gpt-6.1-terra`) | 30/30 | 30/30 | US$ 0,002024 | 6,43 s |
| Só Anthropic (`claude-haiku-5-5`) | 30/30 | 30/30 | US$ 0,000467 | 3,41 s |
| Orquestrado | 30/30 | 30/30 | US$ 0,000469 | 2,86 s |

**Recuperação:** recall@3 = **30/30**, medido ao nível da seção (acerto quando a seção do gabarito, documento mais id,
aparece entre os 3 primeiros trechos).

<details>
<summary><b>Como cada métrica foi medida</b></summary>

- **Acerto:** respostas corretas ÷ 30. Uma regra automática exige `encontrado=true` e a presença de todos os fatos-chave
  da resposta esperada (`dados/fatos_chave.json`; sem acento, palavra inteira, com alternativas). Verifica a
  **presença** dos fatos, não a ausência de afirmações erradas.
- **Citação válida:** saída válida no schema e todas as citações entre os trechos recuperados naquela execução.
- **Custo por resposta:** tokens × preço de tabela (`config/precos.json`, 2026-11-19), somado sobre todas as tentativas
  e provedores, incluindo os embeddings da consulta. Preços por 1M de tokens (entrada / saída): `gpt-6.1-terra`
  US$ 1,00 / US$ 5,00, conferido na página oficial de preços da OpenAI (tabela Standard, contexto curto);
  `claude-haiku-5-5` US$ 0,10 / US$ 0,50 (página oficial da Anthropic). Os preços acima do limite de prompt
  (272 mil tokens no Terra) não foram conferidos; os prompts desta avaliação ficam muito abaixo dele.
- **Latência:** `time.perf_counter`, média por pergunta, incluindo retries.
</details>

**Como ler estes números (importante):**
- O acerto de **30/30 em todos os modos não discrimina** os modelos: a base é fácil para eles (efeito teto).
- No modo orquestrado **nenhuma pergunta escalou**: as 30 respostas finais vieram da Anthropic. A vantagem de latência
  do orquestrado sobre o "só Anthropic" (2,86 s contra 3,41 s) é variação entre execuções, não efeito da regra. A latência
  da primeira chamada é irregular (observei 25,8 s em uma execução e 6 a 8 s em outras).
- Gasto acumulado de desenvolvimento até esta medição: cerca de US$ 0,13 na OpenAI e US$ 0,045 na Anthropic.
- Observação isolada na demo (não é métrica): uma pergunta fora do escopo custou cerca de US$ 0,0052 (aprox. 11x o normal)
  e levou 24,3 s, com confiança baixa e sem citação; escalou para os dois provedores e foi exibida como "melhor
  esforço", sem entrar no cache.

## Arquitetura

```
 pergunta
    │
    ▼
 Interface (Gradio) ── limites por visitante/dia, global, teto de custo ── cache
    │
    ▼
 Orquestrador ── regra de roteamento em código (src/orquestrador/politica.py)
    │   ordem: provedor mais barato pelo preço de tabela → o outro
    │   escala se: erro | saída fora do schema | sem citação válida | confiança < "media"
    │   retry só em falha transitória, espera exponencial (1, 2, 4... máx. 8 s), prazo total por pergunta
    ▼
 Agente (OpenAI ou Anthropic), mesmo contrato de saída (JSON validado por schema)
    │   tool calling: buscar_trechos(consulta)
    ▼
 Recuperação: embeddings (text-embedding-3-small) + cosseno, top-k = 3, índice em disco
    ▲
 Ingestão idempotente: 9 documentos fictícios → 45 seções → 1 trecho por seção, com id de seção
```

## Decisões de engenharia

| Decisão | Como foi feita |
|---|---|
| **Saída estruturada** | `RespostaAuditoria` (resposta, encontrado, citações, confiança) validada por schema, igual nos dois provedores. |
| **Citação verificada em código** | Toda citação precisa ter sido de fato recuperada naquela execução; senão, a resposta é rejeitada pela regra. |
| **Roteamento testável** | A regra de escalada está em `politica.py` (código puro, com testes), não no prompt. |
| **Teto de gasto** | `ControleCusto` reserva o custo máximo antes de cada chamada e não chama se passaria do teto. Todo log registra tokens de entrada e saída. |
| **Prompt versionado** | `prompts/agente_resposta_v1.md`; a versão é registrada em cada resposta. |
| **Log de roteamento** | Cada decisão vai para `logs/roteamento.jsonl`, com a classe da exceção e o status HTTP, nunca a mensagem. |
| **Interface separada da regra** | `servico.py` (limites, cache, chamada ao orquestrador) e `chat.py` (mensagens, trecho da fonte, sugestões) são testados sem Gradio; `ui.py` só liga isso aos componentes. |

A demo tem a aba **Sobre o projeto**, que explica o que o assistente faz e por que existe. Ela roda no Hugging Face Spaces, usado **somente como hospedagem**; os modelos continuam sendo OpenAI e Anthropic.
Limites ativos: 5 perguntas por visitante por dia, 60 por dia no total, teto de custo diário de US$ 0,25 e pergunta de até
300 caracteres. Respostas repetidas vêm do cache e não contam. Cada pergunta é independente (sem memória da conversa).

## Como rodar

Requer Python 3.11 e chaves próprias.

```bash
pip install -r requirements.txt
cp .env.example .env          # preencha OPENAI_API_KEY e ANTHROPIC_API_KEY; nunca versione o .env
python -m pytest -q           # testes unitários, sem chamar API
python -m src.ingestao.ingerir            # cria o índice (custo de embeddings abaixo de US$ 0,001)
python -m src.recuperacao.avaliar         # recall@k nas 30 perguntas
python -m src.avaliacao.executar          # roda os 3 modos e gera docs/resultados/avaliacao.md
python app.py                             # demo local em http://127.0.0.1:7860
```

`python -m src.avaliacao.executar --so-relatorio` regenera a tabela sem chamar a API. Publicação da demo:
[`docs/deploy_hf_spaces.md`](../docs/deploy_hf_spaces.md).

## Escopo e limitações conhecidas

**Escopo.** Provedores: OpenAI e Anthropic. O Gemini não está neste projeto: é uma lacuna declarada, a ser fechada em uma
evolução futura. Base: 9 documentos fictícios (45 seções) e 30 perguntas de teste com gabarito.

**Como interpretar os resultados.**
- A base é pequena e fictícia; os números não se generalizam para documentos reais.
- 30 perguntas e uma execução por modo: sem intervalo de confiança nem repetição.
- A regra de acerto mede a presença dos fatos esperados, não a ausência de afirmações extras erradas.
- Perguntas fora do escopo são lentas e caras comparadas às normais (uma observação isolada).

**Comportamento do sistema.**
- Cada pergunta é independente (sem memória de conversa): perguntas de acompanhamento precisam ser completas.
- O sistema é apoio à busca e pode errar: confira sempre a fonte citada.

**Operação da demo.**
- A identificação de visitante por IP é de melhor esforço; as barreiras reais são o limite global e o teto de custo.
- O estado da demo (limites, cache) vive em disco efêmero e zera quando o Space reinicia; por isso há limites de gasto
  configurados nos consoles dos provedores.
- O Space roda em Python 3.10 e em hardware ZeroGPU por restrição da conta no Hugging Face; o app não usa GPU e contém uma
  função `@spaces.GPU` de marcação, nunca chamada, só para satisfazer a checagem da plataforma.
- A aparência da interface foi verificada manualmente, em um navegador, nos temas claro e escuro; o teste automatizado com
  o Gradio real confere que a tela monta sem erro.

## Roadmap

- **Ganho de tempo:** comparar a busca manual das mesmas perguntas na base fictícia, no cenário do portal acima, com a
  latência do sistema. Protocolo e ferramenta de cronometragem em [`src/avaliacao/tempo_manual.py`](../src/avaliacao/tempo_manual.py).
- **Avaliação mais exigente:** perguntas difíceis e sem resposta na base, para exercitar a regra de roteamento, e repetição
  das execuções para reportar variação.
- **Qualidade da resposta:** detectar afirmações incorretas além da presença de fatos.
- **Conversa com memória:** reformular a pergunta de acompanhamento antes de buscar.
- **Terceiro provedor:** Gemini.

## Estrutura do repositório

```
app.py                  ponto de entrada da demo (Gradio)
config/precos.json      tabela de preços por modelo, com data e fonte
dados/                  documentos fictícios, perguntas com gabarito e fatos-chave
docs/                   processo, deploy, resultados da avaliação e imagens
prompts/                prompts versionados
src/
  ingestao/             divisão em trechos, embeddings, índice idempotente
  recuperacao/          busca top-k e recall@k
  agentes/              um agente por provedor, mesmo contrato
  orquestrador/         regra de roteamento, retry, fallback, log
  avaliacao/            harness dos 3 modos e relatório gerado por script
  interface/            serviço, limites, cache, chat e tela
tests/                  testes unitários (não chamam API)
```

## Referências públicas

- IIA, *Global Internal Audit Standards* (2024) e *The IIA's Three Lines Model* (2020).
- NIST, *AI Risk Management Framework 1.0* (2023).

A numeração exata das normas deve ser conferida na fonte oficial antes de citar seções específicas.
