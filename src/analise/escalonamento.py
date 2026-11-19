"""Quanto custa e quanto demora ter um segundo provedor? Análise descritiva das execuções repetidas.

NÃO usa IA e não chama nenhuma API: lê docs/resultados/execucoes/*.json (30 perguntas de dados/perguntas.json por
execução) e agrupa por modo. Mede só o que está nesses arquivos: quantas perguntas chamaram o segundo provedor,
em que estado terminaram, por qual motivo, e o custo e a latência com e sem ele.

Limites (também impressos no relatório): 2 execuções por modo; a base de 30 perguntas é fácil e não provoca
escalonamento no `adaptativo`; falhas de rede (timeout, retry, fallback) não aparecem nesses dados.

Uso: python -m src.analise.escalonamento   # gera docs/resultados/escalonamento.md
"""
from __future__ import annotations

import statistics as st
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ..avaliacao.execucoes import PASTA, RAIZ, _f, carregar

SAIDA = RAIZ / "docs" / "resultados" / "escalonamento.md"


def _media(xs: list[float]) -> float | None:
    return st.mean(xs) if xs else None


def resumir(linhas: list[dict[str, Any]]) -> dict[str, Any]:
    com = [x for x in linhas if len(x.get("rota") or []) > 1]
    sem = [x for x in linhas if len(x.get("rota") or []) <= 1]
    return {
        "n": len(linhas), "com": len(com),
        "estados": Counter(x["status"] for x in linhas),
        "motivos": Counter(x.get("motivo_escalonamento") or "nenhum" for x in linhas),
        "tentativas": sum(x["tentativas"] for x in linhas),
        "custo_total": sum(x["custo_usd"] for x in linhas),
        "custo_com": _media([x["custo_usd"] for x in com]), "custo_sem": _media([x["custo_usd"] for x in sem]),
        "lat_com": _media([x["latencia_s"] for x in com]), "lat_sem": _media([x["latencia_s"] for x in sem]),
        "custo_medio": st.mean(x["custo_usd"] for x in linhas), "lat_media": st.mean(x["latencia_s"] for x in linhas),
    }


def _opt(x: float | None, casas: int) -> str:
    return "-" if x is None else _f(x, casas)


def _cont(c: Counter) -> str:
    return "; ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def gerar_markdown(dados: dict[str, list[tuple[int, list[dict[str, Any]]]]]) -> str:
    out = ["# Escalonamento: custo e latência do segundo provedor (gerado por script)", "",
           "> Gerado por `python -m src.analise.escalonamento` a partir de `docs/resultados/execucoes/*.json`. "
           "Análise **descritiva, sem IA**. Não editar à mão.", "",
           "A regra de quando escalar está em código (`src/orquestrador/politica.py`) e é descrita em "
           "[`docs/orquestracao.md`](../orquestracao.md). Este arquivo mede o que ela produziu nas 30 perguntas de "
           "`dados/perguntas.json`, em execuções repetidas de cada modo.", "",
           "## Por execução", "",
           "| Modo | Exec. | Perguntas com 2º provedor | Estados finais | Motivos | Tentativas (chamadas a agentes) | "
           "Custo total (US$) |", "|---|---|---|---|---|---|---|"]
    por_modo: dict[str, list[dict[str, Any]]] = {}
    for modo, execs in dados.items():
        for n, linhas in execs:
            r = resumir(linhas)
            por_modo.setdefault(modo, []).append(r)
            out.append(f"| {modo} | {n} | {r['com']}/{r['n']} | {_cont(r['estados'])} | {_cont(r['motivos'])} | "
                       f"{r['tentativas']} | {_f(r['custo_total'], 6)} |")
    out += ["", "## Com e sem o segundo provedor (média por pergunta)", "",
            "| Modo | Exec. | Custo sem 2º (US$) | Custo com 2º (US$) | Latência sem 2º (s) | Latência com 2º (s) |",
            "|---|---|---|---|---|---|"]
    for modo, rs in por_modo.items():
        for i, r in enumerate(rs, 1):
            out.append(f"| {modo} | {i} | {_opt(r['custo_sem'], 6)} | {_opt(r['custo_com'], 6)} | "
                       f"{_opt(r['lat_sem'], 2)} | {_opt(r['lat_com'], 2)} |")
    out += ["", "`-` = nenhuma pergunta nessa condição.", ""]
    if "adaptativo" in por_modo and "consenso" in por_modo:
        ca = st.mean(r["custo_medio"] for r in por_modo["adaptativo"])
        cc = st.mean(r["custo_medio"] for r in por_modo["consenso"])
        la = st.mean(r["lat_media"] for r in por_modo["adaptativo"])
        lc = st.mean(r["lat_media"] for r in por_modo["consenso"])
        out += ["## Preço de chamar o segundo provedor sempre", "",
                "Mesmas 30 perguntas, média das execuções de cada modo:", "",
                "| | `adaptativo` | `consenso` | Razão (`consenso` ÷ `adaptativo`) |", "|---|---|---|---|",
                f"| Custo por resposta (US$) | {_f(ca, 6)} | {_f(cc, 6)} | {_f(cc / ca, 1)}x |",
                f"| Latência média (s) | {_f(la, 2)} | {_f(lc, 2)} | {_f(lc / la, 1)}x |", ""]
    out += ["## Limites deste dado", "",
            "- 2 execuções por modo: serve para ver ordem de grandeza, não para estimar variância.",
            "- As 30 perguntas têm resposta na base; o `adaptativo` não escalou nelas. Os caminhos de escalonamento "
            "(segunda opinião, confirmação cruzada) foram observados nas perguntas O01–O10, em uma única execução, "
            "registrada em `docs/orquestracao.md` e em `docs/resultados/analise_roteamento.md`; isso é observação, "
            "não taxa.",
            "- Timeout, retry com espera exponencial e fallback entre provedores têm testes unitários, mas nenhuma "
            "dessas execuções os acionou (ver a coluna de tentativas: uma por pergunta no `adaptativo`).", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    dados = carregar(PASTA)
    if not dados:
        print(f"Nenhuma execução em {PASTA}")
        return 2
    SAIDA.write_text(gerar_markdown(dados), encoding="utf-8")
    print(f"Gerado {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
