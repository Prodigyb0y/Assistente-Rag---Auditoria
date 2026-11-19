"""Texto da aba "Sobre o projeto" da demo: o que o assistente faz e por que existe. Separado da tela para ser testável."""
from __future__ import annotations

REPO = "https://github.com/Prodigyb0y/Assistente-Rag---Auditoria"
LATENCIA_ORQUESTRADO_S = 2.86   # média medida em 2026-11-19 (tabela de resultados do README)
PREMISSAS_MIN = (2, 5, 10)      # premissas ilustrativas, NÃO medidas


def _mmss(segundos: float) -> str:
    m, s = divmod(round(segundos), 60)
    return f"{m} min {s:02d} s"


def tabela_ilustrativa(latencia_s: float = LATENCIA_ORQUESTRADO_S, minutos: tuple[int, ...] = PREMISSAS_MIN) -> str:
    """Tabela "se a busca manual levasse T minutos": só aritmética sobre premissas rotuladas, sem afirmar fato."""
    linhas = ["| Se a busca manual levasse | Sistema (média medida) | Diferença por pergunta |", "|---|---|---|"]
    for m in minutos:
        linhas.append(f"| {m} min | {latencia_s:.1f} s".replace(".", ",") + f" | cerca de {_mmss(m * 60 - latencia_s)} |")
    return "\n".join(linhas)


def texto_sobre(por_visitante_dia: int) -> str:
    return f"""## O que este assistente faz

Responde perguntas sobre as políticas da **Gutenberg Systems**, uma empresa **fictícia**, e mostra junto da resposta a
**seção de origem com o trecho original**, para você conferir na fonte.

## Por que ele existe

Em auditoria interna, localizar o trecho de política que sustenta uma conclusão, e conferir se ele foi citado
corretamente, é um trabalho repetitivo e sujeito a erro de citação. O assistente automatiza a **busca e a citação**.
A conclusão continua sendo do auditor.

**O cenário desta demo.** A Gutenberg Systems (fictícia) guarda suas políticas em um portal de documentos cuja busca
localiza apenas pelo **código ou título da norma** (por exemplo, `POL-ACE`), sem busca por significado. Quem não sabe
qual norma trata do assunto precisa deduzir o código e abrir um documento de cada vez. Aqui a pergunta é feita em
linguagem natural e a resposta já traz a norma e a seção. Esta descrição é a **premissa do cenário fictício**, não uma
medição de tempo.

**Ilustração (premissa, não medida).** O tempo de achar a norma em um portal depende do portal e de quem busca, e **não
foi medido** neste projeto. Para dar a dimensão, a tabela mostra a economia por pergunta *se* a busca levasse T minutos,
contra a latência média medida do sistema. Não inclui o tempo de conferir a fonte citada, que continua sendo do auditor.

{tabela_ilustrativa()}

## Como funciona

1. Sua pergunta é comparada, por significado, com as 45 seções dos 9 documentos da base.
2. Um modelo responde usando **somente** os trechos encontrados. O sistema começa pelo provedor mais barato (Anthropic ou
   OpenAI) e passa para o outro se a resposta vier sem citação válida ou com confiança baixa.
3. O sistema confere, em código, se cada fonte citada foi de fato recuperada naquela pergunta.

## O que ele não faz

- Não é decisão, parecer ou conclusão de auditoria. Confira sempre a fonte citada.
- Não tem memória: cada pergunta é respondida de forma independente e precisa ser completa.
- Responde só com base nos 9 documentos fictícios. Fora deles, pode informar que não encontrou, e pode errar.

## Limites desta demo

{por_visitante_dia} perguntas por visitante por dia, um teto de custo diário e cache para perguntas repetidas (que não
contam no limite). Não digite dados reais de nenhuma empresa.

## Documentação e código

- Código, arquitetura e resultados medidos: [repositório no GitHub]({REPO})
- Método e números da avaliação: [resultados]({REPO}/blob/main/docs/resultados/avaliacao.md)
- Processo de auditoria apoiado e riscos: [processo]({REPO}/blob/main/docs/processo.md)
- Os documentos fictícios podem ser baixados em **Base de documentos**, na barra lateral da aba Conversa.
"""
