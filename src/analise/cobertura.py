"""Cobertura da base pelas perguntas de teste: quais seções dos documentos nenhuma pergunta usa como fonte.

Análise descritiva, sem IA. Lê os cabeçalhos `## XXX-n` de dados/documentos e os campos de seção de dois formatos:
`dados/perguntas.json` (campos `documento` e `secao`) e `dados/perguntas_orquestracao.json` (lista `fontes`).

Uso:
  python -m src.analise.cobertura
  python -m src.analise.cobertura --saida docs/resultados/cobertura_perguntas.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..config import RAIZ

DOCS = RAIZ / "dados" / "documentos"
GABARITO = RAIZ / "dados" / "perguntas.json"
ORQUESTRACAO = RAIZ / "dados" / "perguntas_orquestracao.json"


def secoes_da_base(diretorio: Path = DOCS) -> dict[str, list[str]]:
    base: dict[str, list[str]] = {}
    for md in sorted(Path(diretorio).glob("POL-*.md")):
        codigo = md.name.split("_")[0]
        base[codigo] = re.findall(r"^## ([A-Z]{3}-\d+)", md.read_text(encoding="utf-8"), re.M)
    return base


def secoes_citadas(arquivo: Path) -> set[tuple[str, str]]:
    if not Path(arquivo).exists():
        return set()
    usadas: set[tuple[str, str]] = set()
    for q in json.loads(Path(arquivo).read_text(encoding="utf-8")):
        if "fontes" in q:
            usadas |= {(f["documento"], f["secao"]) for f in q["fontes"]}
        elif "documento" in q and "secao" in q:
            usadas.add((q["documento"], q["secao"]))
    return usadas


def calcular(base: dict[str, list[str]], usadas: set[tuple[str, str]]) -> dict[str, list[str]]:
    """Seções de cada documento que nenhuma pergunta usa."""
    return {doc: [s for s in secs if (doc, s) not in usadas] for doc, secs in base.items()}


def gerar_markdown(base: dict[str, list[str]], gabarito: set[tuple[str, str]], todas: set[tuple[str, str]]) -> str:
    total = sum(len(s) for s in base.values())
    sem_gab, sem_todas = calcular(base, gabarito), calcular(base, todas)
    out = ["# Cobertura da base pelas perguntas de teste (gerada por script)", "",
           "> Gerado por `python -m src.analise.cobertura`. Análise descritiva, sem IA: compara as seções dos documentos "
           "com as seções que cada pergunta usa como fonte.", "",
           f"- Seções na base: {total} em {len(base)} documentos.",
           f"- Usadas como fonte pelas 30 perguntas do gabarito (`dados/perguntas.json`): "
           f"{total - sum(len(v) for v in sem_gab.values())} de {total}.",
           f"- Usadas pelo gabarito e pelas 10 perguntas de orquestração (`dados/perguntas_orquestracao.json`, "
           f"gabarito ainda não revisado): {total - sum(len(v) for v in sem_todas.values())} de {total}.", "",
           "| Documento | Seções | Sem pergunta (só o gabarito de 30) | Sem pergunta (gabarito + orquestração) |",
           "|---|---|---|---|"]
    for doc, secs in base.items():
        out.append(f"| {doc} | {len(secs)} | {', '.join(sem_gab[doc]) or '-'} | {', '.join(sem_todas[doc]) or '-'} |")
    out += ["", "Leitura: seção sem pergunta é parte da base que a avaliação nunca exercita. Não significa que a seção "
            "seja menos importante.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args(argv)
    base = secoes_da_base()
    gab = secoes_citadas(GABARITO)
    md = gerar_markdown(base, gab, gab | secoes_citadas(ORQUESTRACAO))
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(md, encoding="utf-8")
        print(f"Relatório gravado em {args.saida}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
