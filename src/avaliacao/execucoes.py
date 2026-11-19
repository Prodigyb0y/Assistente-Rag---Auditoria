"""Resume as execuções repetidas dos modos de orquestração (docs/resultados/execucoes/*.json).

Uso: python -m src.avaliacao.execucoes
Lê os arquivos `<modo>_<n>.json` (um por execução de 30 perguntas) e gera docs/resultados/execucoes.md.
Todos os números vêm dos arquivos; nada é digitado à mão.
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent.parent
PASTA = RAIZ / "docs" / "resultados" / "execucoes"
SAIDA = RAIZ / "docs" / "resultados" / "execucoes.md"


def resumir_execucao(linhas: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(linhas)
    lat = [x["latencia_s"] for x in linhas]
    return {
        "n": n,
        "acertos": sum(bool(x["acerto"]) for x in linhas),
        "validas": sum(bool(x["valido"]) for x in linhas),
        "custo_resp": sum(x["custo_usd"] for x in linhas) / n,
        "lat_media": st.mean(lat),
        "lat_mediana": st.median(lat),
        "lat_max": max(lat),
        "dois_provedores": sum(len(x.get("rota") or []) > 1 for x in linhas),
        "divergencias": sorted(x["pergunta_id"] for x in linhas if x.get("status") == "divergencia"),
    }


def carregar(pasta: Path = PASTA) -> dict[str, list[tuple[int, list[dict[str, Any]]]]]:
    por_modo: dict[str, list[tuple[int, list[dict[str, Any]]]]] = defaultdict(list)
    for arq in sorted(pasta.glob("*.json")):
        m = re.fullmatch(r"(?P<modo>[a-z]+)_(?P<n>\d+)", arq.stem)
        if not m:
            continue
        por_modo[m["modo"]].append((int(m["n"]), json.loads(arq.read_text(encoding="utf-8"))))
    return {k: sorted(v) for k, v in por_modo.items()}


def _f(x: float, casas: int) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def gerar_markdown(dados: dict[str, list[tuple[int, list[dict[str, Any]]]]]) -> str:
    out = ["# Execuções repetidas dos modos de orquestração",
           "",
           "Gerado por script (`python -m src.avaliacao.execucoes`) a partir de `docs/resultados/execucoes/*.json`. "
           "Não editar à mão.",
           "",
           "Cada linha é uma execução completa das 30 perguntas de `dados/perguntas.json`. Custo por resposta = soma dos "
           "custos das chamadas (todas as tentativas e provedores, mais a busca) ÷ 30. Latência medida com "
           "`time.perf_counter`, por pergunta, incluindo todas as chamadas da pergunta.",
           "",
           "| Modo | Execução | Acerto | Citação válida | Custo por resposta (US$) | Latência média (s) | "
           "Latência mediana (s) | Latência máxima (s) | Perguntas com os 2 provedores | Divergências |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    medias = []
    for modo, execs in dados.items():
        rs = []
        for n, linhas in execs:
            r = resumir_execucao(linhas)
            rs.append(r)
            div = ", ".join(r["divergencias"]) or "nenhuma"
            out.append(f"| {modo} | {n} | {r['acertos']}/{r['n']} | {r['validas']}/{r['n']} | {_f(r['custo_resp'], 6)} | "
                       f"{_f(r['lat_media'], 2)} | {_f(r['lat_mediana'], 2)} | {_f(r['lat_max'], 2)} | "
                       f"{r['dois_provedores']}/{r['n']} | {div} |")
        medias.append((modo, rs))
    out += ["", "## Média entre execuções", "",
            "| Modo | Execuções | Custo por resposta (US$) | Latência média (s) |", "|---|---|---|---|"]
    for modo, rs in medias:
        out.append(f"| {modo} | {len(rs)} | {_f(st.mean(r['custo_resp'] for r in rs), 6)} | "
                   f"{_f(st.mean(r['lat_media'] for r in rs), 2)} |")
    out += ["", "Com 2 execuções por modo, a média é só um resumo: a variação entre execuções (principalmente de "
            "latência, com picos isolados na primeira chamada) é parte do resultado e está na tabela acima.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    dados = carregar()
    if not dados:
        print(f"Nenhuma execução em {PASTA}")
        return 2
    SAIDA.write_text(gerar_markdown(dados), encoding="utf-8")
    print(f"Gerado {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
