---
title: Busca em políticas de auditoria (demo)
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.30.0
python_version: "3.11"
app_file: app.py
pinned: false
short_description: RAG de auditoria com OpenAI e Anthropic (dados fictícios)
---

# Assistente de busca em políticas de auditoria

Orquestração entre **OpenAI** e **Anthropic** para responder perguntas de apoio a um auditor interno, **citando a seção
de origem**. Projeto de portfólio. **Todos os documentos, perguntas e dados são fictícios (empresa fictícia Gutenberg
Systems).** Nenhum dado, sistema ou processo de empresa real foi usado.

- **Demo (sem instalação):** https://huggingface.co/spaces/bEniac/Assistente_RAG
- **Código:** https://github.com/Prodigyb0y/Assistente-Rag---Auditoria

> **Por que isso importa para um time de auditoria:** o auditor gasta tempo localizando e conferindo o trecho da
> política que sustenta uma conclusão; este sistema devolve a resposta já com a seção citada e verificada contra o que
> foi realmente recuperado, para que a conferência leve segundos, e deixa a decisão de auditoria com a pessoa.

## 1. Problema

Um auditor interno precisa responder perguntas como "com que frequência os acessos privilegiados são revisados e por
quem?" lendo vários documentos de política. O sistema busca nos documentos e responde com a fonte, como **apoio à
busca**. Ele **não** toma decisão de auditoria, não emite parecer e não substitui a leitura do documento.
Detalhes do processo, riscos e limites: [`docs/processo.md`](docs/processo.md).

## 2. Demo

A demo roda no Hugging Face Spaces, usada **somente como hospedagem**. Os modelos continuam sendo OpenAI e Anthropic.

![Demo em formato de chat, com a resposta, o trecho da fonte e os documentos para baixar](docs/img/demo.png)

Recursos da interface (Gradio, em formato de chat):
- resposta com a **fonte citada** e o **trecho original** da seção (documento · seção, título);
- botão para copiar cada resposta e a conversa inteira;
- download do documento citado e de toda a base de documentos fictícios;
- sugestões de perguntas, iniciais e de continuação, tiradas do gabarito e sem repetir o que já foi perguntado;
- temas claro, escuro e automático;
- contador de perguntas restantes no dia.

Cada pergunta é respondida de forma independente: **não há memória da conversa**.

Limites ativos: 5 perguntas por visitante por dia, 60 por dia no total, teto de custo diário de US$ 0,25 e pergunta de
até 300 caracteres. Respostas repetidas vêm do cache e não contam. Os contadores ficam em disco do Space, que é
efêmero (veja Limitações).

## 3. Arquitetura

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

Módulos separados em `src/`: `ingestao`, `recuperacao`, `agentes`, `orquestrador`, `avaliacao`, `interface`, `custo`.
Na interface, a regra fica em `servico.py` (limites, cache, chamada ao orquestrador) e a apresentação do chat
(mensagens, trecho da fonte, sugestões, arquivos) em `chat.py`, ambos testados sem Gradio; `ui.py` só liga isso aos
componentes.

Decisões que valem destacar:
- **Saída estruturada:** `RespostaAuditoria` (resposta, encontrado, citações, confiança) validada por schema.
- **Citação verificada em código:** toda citação precisa ter sido de fato recuperada naquela execução.
- **Teto de gasto:** `ControleCusto` reserva o custo máximo antes de cada chamada e não chama se passaria do teto.
  Todo log registra tokens de entrada e saída.
- **Prompt versionado:** `prompts/agente_resposta_v1.md`; a versão é registrada em cada resposta.
- **Log de roteamento:** cada decisão vai para `logs/roteamento.jsonl`, com a classe da exceção e o status HTTP, nunca
  a mensagem.

## 4. Como rodar

Requer Python 3.11 e chaves próprias.

```bash
pip install -r requirements.txt
cp .env.example .env          # preencha OPENAI_API_KEY e ANTHROPIC_API_KEY; nunca versione o .env
python -m pytest -q           # testes unitários (não chamam API)
python -m src.ingestao.ingerir            # cria o índice (custo de embeddings abaixo de US$ 0,001)
python -m src.recuperacao.avaliar         # recall@k nas 30 perguntas
python -m src.avaliacao.executar          # roda os 3 modos e gera docs/resultados/avaliacao.md
python app.py                             # demo local em http://127.0.0.1:7860
```

`python -m src.avaliacao.executar --so-relatorio` regenera a tabela sem chamar a API. Publicação da demo:
[`docs/deploy_hf_spaces.md`](docs/deploy_hf_spaces.md).

## 5. Resultados medidos

Base: 30 perguntas com gabarito escrito **antes** dos testes e revisado pelo autor ([`dados/perguntas.json`](dados/perguntas.json)).
Execução única por modo, em **2026-11-19**, prompt `agente_resposta_v1`. A tabela completa é gerada por script em
`docs/resultados/avaliacao.md`.

**Recuperação.** recall@3 = **30/30**, medido ao nível da seção: acerto quando a seção do gabarito (documento + id)
aparece entre os 3 primeiros trechos.

**Resposta ponta a ponta:**

| Modo | Acerto | Citação válida | Custo por resposta | Latência média |
|---|---|---|---|---|
| Só OpenAI (`gpt-6.1-terra`) | 30/30 | 30/30 | US$ 0,002024 | 6,43 s |
| Só Anthropic (`claude-haiku-5-5`) | 30/30 | 30/30 | US$ 0,000467 | 3,41 s |
| Orquestrado | 30/30 | 30/30 | US$ 0,000469 | 2,86 s |

Como cada métrica foi medida:
- **Acerto:** respostas corretas ÷ 30. Uma regra automática exige `encontrado=true` e a presença de todos os fatos-chave
  da resposta esperada (`dados/fatos_chave.json`; sem acento, palavra inteira, com alternativas). Verifica a
  **presença** dos fatos, não a ausência de afirmações erradas.
- **Citação válida:** saída válida no schema e todas as citações entre os trechos recuperados naquela execução.
- **Custo por resposta:** tokens × preço de tabela (`config/precos.json`, consultado em 2026-11-19), somado sobre todas
  as tentativas e provedores. Inclui o custo do modelo de resposta e o dos embeddings da consulta de busca.
- **Latência:** `time.perf_counter`, média por pergunta, incluindo retries.

**Como ler estes números (importante):**
- O acerto de **30/30 em todos os modos não discrimina** os modelos: a base é fácil para eles (efeito teto).
- No modo orquestrado **nenhuma pergunta escalou**: as 30 respostas finais vieram da Anthropic. A vantagem de latência
  do orquestrado sobre o "só Anthropic" (2,86 s contra 3,41 s) é variação entre execuções, não efeito da regra.
  Latência de primeira chamada é irregular (observei 25,8 s em uma execução e 6 a 8 s em outras).
- A razão de custo de cerca de 4,3x entre OpenAI e Anthropic depende do preço do `gpt-6.1-terra`, que **não foi
  confirmado na página oficial** (`verificado_oficial: false` em `config/precos.json`; veio de fontes secundárias).
  **Confirme em developers.openai.com antes de citar essa razão.**
- Gasto acumulado de desenvolvimento até esta medição: cerca de US$ 0,13 na OpenAI e US$ 0,045 na Anthropic.
- Uma observação isolada na demo (não é métrica): uma pergunta fora do escopo custou cerca de US$ 0,0052 (aprox. 11x o
  normal) e levou 24,3 s, com confiança baixa e sem citação; escalou para os dois provedores e foi exibida como
  "melhor esforço", sem entrar no cache.

## 6. Limitações

- **Provedores:** só OpenAI e Anthropic. **O Gemini não está neste projeto; é uma lacuna a fechar depois.**
- A base é pequena (9 documentos, 45 seções) e fictícia; resultados não se generalizam para documentos reais.
- 30 perguntas, uma execução por modo: sem intervalo de confiança nem repetição. O gabarito tem poder limitado de
  discriminar.
- A regra de acerto não detecta afirmações extras erradas; não há ainda conjunto de perguntas sem resposta na base.
- Perguntas fora do escopo são lentas e caras comparadas às normais (uma observação).
- Identificação de visitante por IP é de melhor esforço; as barreiras reais são o limite global e o teto de custo.
- O estado da demo (limites, cache) vive em disco efêmero e zera quando o Space reinicia. Por isso há limites de gasto
  recomendados nos consoles dos provedores; confirme que estão ativos antes de divulgar a demo.
- O Space roda em Python 3.10 e em hardware ZeroGPU por restrição da conta no Hugging Face; o app não usa GPU e contém
  uma função `@spaces.GPU` de marcação, nunca chamada, apenas para satisfazer a checagem da plataforma.
- Sem memória de conversa: perguntas de acompanhamento que dependem da resposta anterior ("e para terceiros?") não
  funcionam; cada pergunta precisa ser completa.
- A aparência da interface foi verificada manualmente pelo autor, em um navegador, nos temas claro e escuro. Não há teste
  visual automatizado; o teste com o Gradio real só confere que a tela monta sem erro.
- O sistema é apoio à busca e não faz decisão de auditoria. Pode errar: confira sempre a fonte citada.

## 7. Próximos passos

1. Confirmar o preço oficial do `gpt-6.1-terra` e reexecutar a avaliação.
2. Ampliar o gabarito com perguntas difíceis e sem resposta na base (com revisão do gabarito antes de testar), para
   a regra de roteamento ser exercitada e a escalada medida.
3. Repetir a avaliação várias vezes e reportar variação.
4. Detectar afirmações incorretas além da presença de fatos.
5. Conversa com memória (reformular a pergunta de acompanhamento antes de buscar).
6. Avaliar um terceiro provedor (Gemini), fora do escopo atual.

## 8. Referências públicas

- IIA, *Global Internal Audit Standards* (2024) e *The IIA's Three Lines Model* (2020).
- NIST, *AI Risk Management Framework 1.0* (2023).

A numeração exata das normas deve ser conferida na fonte oficial antes de citar seções específicas.
