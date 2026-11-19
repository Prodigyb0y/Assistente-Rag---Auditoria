# Processo: apoio à busca de evidências em documentos de auditoria

> **Aviso:** todos os documentos, perguntas e a empresa (Gutenberg Systems) deste projeto são **fictícios**. Nada aqui descreve processos, sistemas ou dados de uma organização real.

## 1. Problema de auditoria

Durante um trabalho de auditoria interna, o auditor precisa encontrar, em muitos documentos (políticas, procedimentos, normas internas), o trecho exato que sustenta ou contradiz um ponto em análise. Exemplo: "Qual a periodicidade exigida para revisão de acessos privilegiados?". Hoje isso é lento e sujeito a erro: o auditor pode não achar o trecho, ou citar a versão ou a seção errada.

O sistema resolve **a recuperação de informação com citação verificável**. Ele não analisa, não conclui e não decide nada de auditoria.

## 2. Usuário

Auditor interno (da empresa fictícia Gutenberg Systems), que:
- conhece o tema, mas não decorou todos os documentos;
- precisa de rastreabilidade: cada afirmação deve apontar para documento e seção;
- continua sendo o responsável por qualquer conclusão.

## 3. Entradas

| Entrada | Descrição |
|---|---|
| Base documental | 8 a 10 documentos fictícios de políticas da Gutenberg Systems (ex.: controle de acesso, conciliação de pagamentos, gestão de mudanças), com identificadores de seção |
| Pergunta | Texto livre do auditor, em português |

## 4. Saídas esperadas

Resposta estruturada (JSON validado por schema) com:
- **resposta** curta, baseada apenas nos trechos recuperados;
- **trechos citados**: documento + identificador de seção;
- **nível de confiança** (alto, médio, baixo);
- **"não encontrado"** quando a base não sustenta a resposta (isso é uma saída válida e desejável);
- versão do prompt usada e metadados de custo (tokens de entrada e saída).

## 5. Etapas: hoje versus com o sistema

| Etapa | Hoje (manual) | Com o sistema |
|---|---|---|
| Localizar documentos relevantes | Busca manual em pastas e leitura | Recuperação por similaridade (top-k) |
| Achar o trecho exato | Leitura integral ou busca por palavra-chave | Trechos candidatos já com seção |
| Formular a resposta | Auditor redige | Sistema propõe resposta com citação |
| Verificar a fonte | Auditor confere ao escrever | Auditor **continua conferindo**; o sistema facilita ao apontar a seção |
| Concluir e documentar | Auditor | Auditor (fora do escopo do sistema) |

## 6. O que o sistema NÃO faz (limitações explícitas)

- **Não toma decisão de auditoria**: não classifica achados, não avalia severidade, não conclui sobre conformidade.
- **Não substitui o julgamento nem a verificação do auditor.**
- Não busca fora da base fornecida; não usa conhecimento geral do modelo como evidência.
- Não valida se o documento é a versão vigente além do que estiver na base.
- Não trata documentos reais, sigilosos ou de qualquer organização.
- Neste projeto usa **apenas OpenAI e Anthropic**. O Gemini está fora do escopo; é uma lacuna a ser fechada em projeto futuro.
- Os resultados valem para a base fictícia e as 30 perguntas do gabarito; não são extrapolação para bases reais.

## 7. Riscos e mitigações

| Risco | Descrição | Mitigação planejada |
|---|---|---|
| Alucinação | Resposta sem respaldo nos trechos | Instrução de responder só com base nos trechos; opção "não encontrado"; escalonamento quando a confiança é baixa |
| Citação errada | Seção citada não contém a informação | Validação em código: a seção citada deve existir e ter sido recuperada; métrica de citação válida no harness |
| Vazamento de dados | Dados sensíveis enviados a provedores externos | Somente dados fictícios; chaves em variáveis de ambiente, nunca no repositório; `.env` no `.gitignore` |
| Excesso de confiança do usuário | Auditor aceita sem conferir | Citações obrigatórias, confiança explícita, avisos na interface e no README |
| Custo descontrolado | Chamadas além do orçamento | Teto rígido em código: a chamada que ultrapassaria o limite não é feita e o erro é registrado |
| Resultado enganoso | Métricas sem método | Toda métrica registrada com método, data e tabela de preços usada |

## 8. Referências públicas

Conceitos de auditoria interna (verificar numeração exata na fonte oficial antes de citar no README):
- IIA, *Global Internal Audit Standards* (2024), em especial os princípios sobre conduzir o trabalho e coletar informações para análise e avaliação, e sobre documentação do trabalho.
- IIA, *The IIA's Three Lines Model* (2020).

Gestão de risco de IA:
- NIST, *AI Risk Management Framework 1.0* (2023), usado como referência geral para os riscos da seção 7.

> Esta seção lista só fontes públicas. Nenhuma norma interna de empresa real é usada.

## 9. Critério de pronto do Bloco 0

- [x] Documento escrito
- [x] Sem nenhum dado interno (verificado em 2026-11-19 por busca de nomes de empresas reais no repositório, sem ocorrências; os nomes buscados não são reproduzidos aqui de propósito)
- [ ] Aprovado por você
