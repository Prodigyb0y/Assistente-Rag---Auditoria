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
[Decisões de engenharia](#decisões-de-engenharia) · [Como rodar](#como-rodar) · [Limitações](#limitações) ·
[Próximos passos](#próximos-passos) · [Estrutura](#estrutura-do-repositório) · [Referências](#referências-públicas)

## Por que este projeto existe

Em auditoria interna, uma parte relevante de cada análise é localizar, entre vários documentos de política, o trecho que
sustenta uma conclusão, e depois conferir se ele foi lido e citado corretamente. O trabalho é repetitivo, e um erro de
citação (trecho errado, seção errada) enfraquece a evidência. Exemplo de pergunta: *"com que frequência os acessos
privilegiados são revisados e por quem?"*.

O sistema automatiza a **busca e a citação**, não a conclusão. O processo completo, os riscos (alucinação, citação
errada, vazamento de dados) e o que o sistema **não** faz estão em [`docs/processo.md`](../docs/processo.md).

**Sobre ganho de tempo, o que foi e o que não foi medido:**
- **Medido:** o tempo que o sistema leva para responder (latência média de 2,4 a 6,4 s por pergunta, conforme o modo; veja a tabela abaixo).
- **Não medido:** o tempo de uma busca manual equivalente. Por isso **este projeto não afirma nenhuma economia de tempo**.
  A medição está nos próximos passos: cronometrar a busca manual das mesmas perguntas na base fictícia, com método descrito.

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

A demo roda no Hugging Face Spaces, usado **somente como hospedagem**; os modelos continuam sendo OpenAI e Anthropic.
Limites ativos: 5 perguntas por visitante por dia, 60 por dia no total, teto de custo diário de US$ 0,25 e pergunta de até
300 caracteres. Respostas repetidas vêm do cache e não contam. Cada pergunta é independente (sem memória da conversa).

## Como rodar

Requer Python 3.11 e chaves próprias.

```bash
pip install -r requirements.txt
cp .env.example .env          # preencha OPENAI_API_KEY e ANTHROPIC_API_KEY; nunca versione o .env
python -m pytest -q           # 243 testes unitários, sem chamar API
python -m src.ingestao.ingerir            # cria o índice (custo de embeddings abaixo de US$ 0,001)
python -m src.recuperacao.avaliar         # recall@k nas 30 perguntas
python -m src.avaliacao.executar          # roda os 3 modos e gera docs/resultados/avaliacao.md
python app.py                             # demo local em http://127.0.0.1:7860
```

`python -m src.avaliacao.executar --so-relatorio` regenera a tabela sem chamar a API. Publicação da demo:
[`docs/deploy_hf_spaces.md`](../docs/deploy_hf_spaces.md).

## Limitações

- **Provedores:** só OpenAI e Anthropic. **O Gemini não está neste projeto; é uma lacuna a fechar depois.**
- A base é pequena (9 documentos, 45 seções) e fictícia; os resultados não se generalizam para documentos reais.
- 30 perguntas e uma execução por modo: sem intervalo de confiança nem repetição.
- A regra de acerto não detecta afirmações extras erradas; ainda não há conjunto de perguntas sem resposta na base.
- Perguntas fora do escopo são lentas e caras comparadas às normais (uma observação).
- Sem memória de conversa: perguntas de acompanhamento que dependem da resposta anterior não funcionam.
- Identificação de visitante por IP é de melhor esforço; as barreiras reais são o limite global e o teto de custo.
- O estado da demo (limites, cache) vive em disco efêmero e zera quando o Space reinicia. Por isso há limites de gasto
  nos consoles dos provedores.
- O Space roda em Python 3.10 e em hardware ZeroGPU por restrição da conta no Hugging Face; o app não usa GPU e contém
  uma função `@spaces.GPU` de marcação, nunca chamada, só para satisfazer a checagem da plataforma.
- A aparência da interface foi verificada manualmente pelo autor, em um navegador, nos temas claro e escuro. Não há teste
  visual automatizado; o teste com o Gradio real só confere que a tela monta sem erro.
- O sistema é apoio à busca e pode errar: confira sempre a fonte citada.

## Próximos passos

1. **Medir o ganho de tempo:** cronometrar a busca manual das mesmas perguntas na base fictícia (método e limites
   descritos) e comparar com a latência do sistema.
2. Ampliar o gabarito com perguntas difíceis e sem resposta na base, para a regra de roteamento ser exercitada e a escalada medida.
3. Repetir a avaliação várias vezes e reportar variação.
4. Detectar afirmações incorretas além da presença de fatos.
5. Conversa com memória (reformular a pergunta de acompanhamento antes de buscar).
6. Avaliar um terceiro provedor (Gemini), fora do escopo atual.

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
tests/                  243 testes unitários
```

## Referências públicas

- IIA, *Global Internal Audit Standards* (2024) e *The IIA's Three Lines Model* (2020).
- NIST, *AI Risk Management Framework 1.0* (2023).

A numeração exata das normas deve ser conferida na fonte oficial antes de citar seções específicas.
