"""Avaliação da recuperação: recall@k contra o gabarito (dados/perguntas.json).

Definição de acerto: a pergunta é um acerto em k se a seção do gabarito (documento + id da seção)
aparece entre os k primeiros trechos recuperados. recall@k = acertos / total de perguntas.
Nível de avaliação: SEÇÃO, não resposta final.
"""
from __future__ import annotations

import time
from typing import Any

from ..custo import TabelaPrecos
from .buscador import Buscador, Resultado

KS_PADRAO = (1, 3, 5)


def posicao_do_gabarito(resultados: list[Resultado], documento: str, secao: str) -> int | None:
    for r in resultados:
        if r.doc_id == documento and r.secao_id == secao:
            return r.posicao
    return None


def calcular_recall(posicoes: list[int | None], ks: tuple[int, ...] = KS_PADRAO) -> dict[int, dict[str, float | int]]:
    n = len(posicoes)
    if n == 0:
        raise ValueError("Sem perguntas para avaliar")
    out = {}
    for k in ks:
        acertos = sum(1 for p in posicoes if p is not None and p <= k)
        out[k] = {"acertos": acertos, "total": n, "recall": acertos / n}
    return out


def avaliar(perguntas: list[dict], buscador: Buscador, tabela: TabelaPrecos,
            ks: tuple[int, ...] = KS_PADRAO) -> dict[str, Any]:
    k_max = max(ks)
    tokens_antes = buscador.tokens_consulta
    resultados = buscador.buscar_lote([q["pergunta"] for q in perguntas], k=k_max)
    posicoes = [posicao_do_gabarito(r, q["documento"], q["secao"]) for r, q in zip(resultados, perguntas)]
    tokens = buscador.tokens_consulta - tokens_antes
    modelo = buscador.embedder.modelo
    por_pergunta = [
        {"id": q["id"], "pergunta": q["pergunta"], "esperado": f'{q["documento"]}/{q["secao"]}',
         "posicao_do_gabarito": p, "top": [r.chunk_id for r in res[:3]],
         "scores_top": [round(r.score, 4) for r in res[:3]]}
        for q, p, res in zip(perguntas, posicoes, resultados)
    ]
    return {
        "data": time.strftime("%Y-%m-%d"),
        "modelo_embedding": modelo,
        "n_perguntas": len(perguntas),
        "n_trechos_indice": len(buscador.indice.chunks),
        "hash_indice": buscador.indice.hash,
        "k_maximo_recuperado": k_max,
        "recall": {str(k): v for k, v in calcular_recall(posicoes, ks).items()},
        "tokens_embedding_consultas": tokens,
        "custo_consultas_usd": tabela.get(modelo).custo(tokens, 0),
        "data_tabela_precos": tabela.data_consulta,
        "por_pergunta": por_pergunta,
    }


def gerar_relatorio_md(r: dict[str, Any]) -> str:
    linhas = [
        "# Avaliação da recuperação (recall@k)",
        "",
        f"Gerado por script em {r['data']}. Não editar à mão: rode `python -m src.recuperacao.avaliar`.",
        "",
        "## Resultado",
        "",
        "| k | acertos | total | recall@k |",
        "|---|---|---|---|",
    ]
    for k, v in r["recall"].items():
        linhas.append(f"| {k} | {v['acertos']} | {v['total']} | {v['recall']:.3f} |")
    linhas += [
        "",
        "## Método",
        "",
        f"- Base: {r['n_trechos_indice']} trechos de documentos fictícios da Gutenberg Systems, "
        "um trecho por seção (identificador de seção preservado). Hash do índice: "
        f"`{r['hash_indice'][:16]}`.",
        f"- Embeddings: modelo `{r['modelo_embedding']}` (OpenAI). O texto embedado de cada trecho é "
        "o código do documento, o id da seção, o título e o corpo da seção.",
        f"- Consulta: as {r['n_perguntas']} perguntas do gabarito são embedadas com o mesmo modelo; "
        "similaridade de cosseno; ordem decrescente; empate pela ordem do índice.",
        "- Acerto@k: a seção do gabarito (documento + id da seção) está entre os k primeiros trechos. "
        "recall@k = acertos ÷ total de perguntas.",
        "- Gabarito: 30 perguntas escritas e revisadas no Bloco 1, antes de qualquer teste.",
        "",
        "## Limitações",
        "",
        "- Apenas 30 perguntas e uma base pequena e fictícia; não generaliza para bases reais.",
        "- Mede só se a seção certa foi recuperada, não se a resposta final está correta.",
        "- Perguntas e documentos foram escritos pelo mesmo processo, então compartilham vocabulário; "
        "isso tende a favorecer a recuperação.",
        "",
        "## Perguntas em que a seção do gabarito ficou fora do top-3",
        "",
    ]
    erros = [p for p in r["por_pergunta"] if p["posicao_do_gabarito"] is None or p["posicao_do_gabarito"] > 3]
    if not erros:
        linhas.append("Nenhuma.")
    else:
        linhas += ["| id | esperado | posição | top-3 recuperado |", "|---|---|---|---|"]
        for p in erros:
            pos = p["posicao_do_gabarito"] if p["posicao_do_gabarito"] is not None else f">{r['k_maximo_recuperado']}"
            linhas.append(f"| {p['id']} | {p['esperado']} | {pos} | {', '.join(p['top'])} |")
    linhas += [
        "",
        "## Custo desta avaliação",
        "",
        f"- Tokens de embedding das consultas: {r['tokens_embedding_consultas']}.",
        f"- Custo: US$ {r['custo_consultas_usd']:.6f} (tabela de preços de {r['data_tabela_precos']}).",
        "",
    ]
    return "\n".join(linhas)
