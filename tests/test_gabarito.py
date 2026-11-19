"""Verifica a consistência do gabarito: cada pergunta aponta para uma seção
existente e o trecho de origem aparece literalmente nessa seção.

Uso: python3 -I tests/test_gabarito.py  (executar a partir da raiz do projeto)
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "dados" / "documentos"
PERGUNTAS = RAIZ / "dados" / "perguntas.json"


def carregar_secoes() -> dict[str, str]:
    secoes: dict[str, str] = {}
    for arq in sorted(DOCS.glob("*.md")):
        partes = re.split(r"^## ", arq.read_text(encoding="utf-8"), flags=re.M)[1:]
        for parte in partes:
            cabecalho, _, corpo = parte.partition("\n")
            sid = cabecalho.split()[0]
            assert sid not in secoes, f"secao duplicada: {sid}"
            secoes[sid] = " ".join(corpo.split())
    return secoes


def main() -> int:
    secoes = carregar_secoes()
    qs = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    erros: list[str] = []
    if len(qs) != 30:
        erros.append(f"esperado 30 perguntas, achei {len(qs)}")
    ids = [q["id"] for q in qs]
    if len(set(ids)) != len(ids):
        erros.append("ids de pergunta duplicados")
    for q in qs:
        corpo = secoes.get(q["secao"])
        if corpo is None:
            erros.append(f'{q["id"]}: secao {q["secao"]} nao existe')
        elif q["trecho_origem"] not in corpo:
            erros.append(f'{q["id"]}: trecho nao encontrado em {q["secao"]}')
        if not q["secao"].startswith(q["documento"].split("-")[1]):
            erros.append(f'{q["id"]}: secao/documento inconsistentes')
    n_docs = len(list(DOCS.glob("*.md")))
    print(f"documentos: {n_docs} | secoes: {len(secoes)} | perguntas: {len(qs)}")
    if erros:
        print("FALHOU:")
        for e in erros:
            print(" -", e)
        return 1
    print("OK: todas as perguntas apontam para trecho literal existente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
