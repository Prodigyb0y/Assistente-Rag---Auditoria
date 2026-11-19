# Análise de dados do projeto

Dados deste projeto: o log de roteamento (`logs/roteamento.jsonl`, local), os resultados versionados em
`docs/resultados/`, a base de documentos e as perguntas de teste (`dados/`). Tudo é fictício, exceto os custos e as
latências medidos. Este documento separa o que **está implementado** (sem IA) do que é **proposta** (com IA, não
implementada).

## 1. Implementado, sem IA

Duas análises descritivas, em Python puro (sem rede, sem custo), com testes em `tests/test_analise_*.py`.

### 1.1 Log de roteamento (`python -m src.analise.roteamento`)

Conta as perguntas finais por estado, modo, motivo de escalonamento, caminho e provedor, e soma custo e latência.
Resultado completo: [`docs/resultados/analise_roteamento.md`](resultados/analise_roteamento.md), gerado a partir de uma
cópia do log local do autor (28 perguntas finais, 2026-11-19, 13:10 a 16:31, US$ 0,074811 no total).

| O que o log mostra | Valor |
|---|---|
| Perguntas que chamaram **um** provedor | 14; custo médio US$ 0,000512; latência média 4,2 s |
| Perguntas que chamaram **dois** provedores | 14; custo médio US$ 0,004831; latência média 15,4 s |
| Estados com dois provedores | `melhor_esforco` 7, `nao_encontrado_confirmado` 3, `aceita_apos_escalonamento` 2, `aceita_por_consenso` 1, `divergencia` 1 |
| Motivo que impediu aceitar a primeira resposta | `nao_encontrado` 6, `sem_citacao_valida` 5, `confianca_baixa` 3 |

Leitura: chamar o segundo provedor custou, em média, cerca de 9 vezes mais por pergunta nestas execuções (0,004831 contra
0,000512). **Essa comparação não é limpa:** as perguntas que chamam dois provedores são as de abstenção ou de baixa
confiança, ou seja, as mais difíceis, e não as mesmas perguntas. O número descreve estas execuções, não o custo esperado
do escalonamento em geral.

Limites do dado: o log mistura execuções de configurações diferentes e **não grava a confiança mínima** de cada uma;
13 das 28 perguntas vêm de versões do código sem os campos `modo` e `caminho`; perguntas repetidas contam mais de uma vez.

### 1.2 Cobertura da base pelas perguntas (`python -m src.analise.cobertura`)

Compara as seções dos documentos com as seções que as perguntas usam como fonte. Resultado completo:
[`docs/resultados/cobertura_perguntas.md`](resultados/cobertura_perguntas.md).

- As 30 perguntas do gabarito usam **26 das 45 seções** como fonte. As 10 perguntas de orquestração (gabarito ainda não
  revisado) elevam para 28 de 45.
- Das 19 seções sem pergunta no gabarito, 9 são seções de "Objetivo" (a primeira de cada documento). As outras 10 são de
  conteúdo: ACE-2, BKP-4, CPG-5, DAD-2, DAD-4, FOR-5, INC-2, LOG-2, LOG-4 e SFU-2.
- Consequência para a avaliação: o 30/30 não exercita essas 10 seções de conteúdo. Escrever perguntas para elas é o ganho
  mais barato de cobertura.

## 2. Propostas com IA (NÃO implementadas)

Nenhuma destas foi executada. Todas devem passar pelo `ControleCusto` (teto de gasto) e registrar tokens por chamada. O
custo de cada uma será estimado na implementação, com teto antes de rodar.

| Id | Pergunta que responde | Dados de entrada | Método com IA | Como validar | Principal risco |
|---|---|---|---|---|---|
| A | A resposta está certa em sentido, ou só contém os fatos-chave? A regra atual mede a presença dos fatos, não a ausência de afirmações extras erradas | Respostas em `docs/resultados/agentes_*.json` e o gabarito | Um modelo age como juiz: dado o gabarito e a resposta, classifica "correta", "parcial" ou "errada" com justificativa curta. O juiz é do **outro** provedor (a resposta da OpenAI é julgada pela Anthropic e vice-versa) | Rotular à mão 20 respostas e medir a concordância do juiz com você (por exemplo, índice kappa). Só usar o juiz se a concordância for aceitável, critério a fixar antes de rodar | Viés do juiz (preferir respostas longas ou do próprio provedor) |
| B | Por que as respostas não aceitas falharam? | Respostas não aceitas (futuras execuções de agente isolado gravam o texto; o log de roteamento não grava) | Um modelo classifica cada falha numa taxonomia fechada (pergunta ambígua, tema fora da base, citação vizinha, confiança mal calibrada, outro) | Classificar 20 casos à mão e comparar | Taxonomia que força cada caso numa caixa que não serve |
| C | A recuperação encontra a seção certa para perguntas parecidas? Quais temas a base cobre mal? | Perguntas dos arquivos de teste (fictícias) e as 45 seções, com os embeddings que o projeto já usa | Similaridade e agrupamento por embeddings: para cada pergunta, a seção mais próxima é a esperada? Que perguntas se agrupam e que seções ficam sem vizinhas? | Conferir com o gabarito: a seção esperada está entre as 3 mais próximas (como no recall@3 já medido) | Conjunto pequeno: agrupamentos instáveis |
| D | Há perguntas com custo ou latência fora do padrão? | `logs/roteamento.jsonl` e `logs/chamadas.jsonl` | Detecção de anomalias estatística (IQR ou desvio robusto). Não usa LLM | Revisar à mão os casos sinalizados | Com 28 eventos não há dado suficiente; só faz sentido com um log bem maior |
| E | O conjunto de teste é fácil demais? (30/30 em todos os modos) | Seções das 45, em especial as 10 sem pergunta | Um modelo propõe perguntas difíceis por seção (ambíguas, que combinam seções, quase fora da base). **Você** escreve ou revisa o gabarito de cada uma | Todo gabarito revisado por você antes de entrar no teste; descartar perguntas que o modelo gerou com resposta errada | Perguntas geradas parecidas com o texto da seção (fáceis demais) e gabarito errado |

Ordem sugerida: **E e A** primeiro (atacam o ponto fraco já conhecido: o conjunto fácil e a regra de acerto), depois B e C.
D só quando o log crescer.

### Regra de privacidade

A demo recebe texto livre de visitantes, e um visitante poderia digitar dado real. Por isso **o texto das perguntas dos
visitantes não é gravado pelo projeto**: o log de roteamento e o log de chamadas guardam só identificadores, tokens,
custo e latência, e a chave do cache é um hash. Duas ressalvas: o texto é enviado à OpenAI e à Anthropic para gerar a
resposta, e a resposta guardada no cache pode repetir termos da pergunta. Nenhuma proposta acima depende de gravar o
texto: elas usam só os arquivos de perguntas fictícias do repositório. Gravar perguntas de visitantes seria uma decisão
separada do autor, com aviso na interface.

## 3. O que esta análise não faz

- Não gera insight sobre documentos reais de nenhuma organização: os dados são fictícios.
- Não prova que o escalonamento compensa: as comparações de custo acima misturam perguntas diferentes.
- Não substitui a revisão do gabarito pelo autor.
