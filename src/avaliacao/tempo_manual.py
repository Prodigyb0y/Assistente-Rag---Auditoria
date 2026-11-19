"""Cronometra a busca MANUAL de respostas na base fictícia, para comparar com a latência do sistema.

Protocolo (o que a medição significa):
  - Cenário fictício: um portal de documentos que só localiza por código ou título da norma (sem busca por significado).
    Para reproduzi-lo, procure SOMENTE pelo nome/código dos arquivos em `dados/documentos/` e abra os documentos; não use
    busca de texto em todos os arquivos, nem o assistente.
  - Para cada pergunta sorteada: o cronômetro começa no Enter, para no Enter seguinte (quando você achar o trecho) e você
    informa o documento e a seção encontrados. O gabarito não é mostrado durante a medição.
  - Limite conhecido: quem mede conhece a base, o que tende a SUBESTIMAR o tempo manual (o ganho medido fica conservador).
    São poucas perguntas e uma pessoa: o resultado é uma ordem de grandeza, não uma estatística.

Uso:
  python -m src.avaliacao.tempo_manual              # mede (interativo; retoma de onde parou)
  python -m src.avaliacao.tempo_manual --resumo     # mostra o resumo e compara com a latência do sistema
  python -m src.avaliacao.tempo_manual -n 10        # quantidade de perguntas sorteadas (padrão 10)

Saída: docs/resultados/tempo_manual.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

from ..config import RAIZ

PERGUNTAS = RAIZ / "dados" / "perguntas.json"
ARQUIVO = RAIZ / "docs" / "resultados" / "tempo_manual.json"
AVALIACAO = RAIZ / "docs" / "resultados" / "avaliacao.json"
SEMENTE = 2026


def sortear(perguntas: list[dict[str, Any]], n: int, semente: int = SEMENTE) -> list[dict[str, Any]]:
    """Sorteio reprodutível (mesma semente, mesma lista), sem repetição."""
    n = max(0, min(n, len(perguntas)))
    return random.Random(semente).sample(perguntas, n)


def registrar(pergunta: dict[str, Any], segundos: float, documento: str, secao: str) -> dict[str, Any]:
    doc, sec = documento.strip().upper(), secao.strip().upper()
    return {"pergunta_id": pergunta["id"], "segundos": round(segundos, 2), "documento_informado": doc,
            "secao_informada": sec, "acertou_secao": doc == pergunta["documento"] and sec == pergunta["secao"]}


def resumir(medicoes: list[dict[str, Any]]) -> dict[str, Any]:
    if not medicoes:
        return {"n": 0}
    s = [m["segundos"] for m in medicoes]
    return {"n": len(s), "acertos_secao": sum(1 for m in medicoes if m["acertou_secao"]),
            "mediana_s": round(statistics.median(s), 1), "media_s": round(statistics.mean(s), 1),
            "min_s": min(s), "max_s": max(s)}


def carregar(arquivo: Path = ARQUIVO) -> list[dict[str, Any]]:
    if not arquivo.exists():
        return []
    return json.loads(arquivo.read_text(encoding="utf-8")).get("medicoes", [])


def salvar(medicoes: list[dict[str, Any]], arquivo: Path = ARQUIVO) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    corpo = {"protocolo": "busca manual só por código/nome do arquivo, sem busca de texto; ver src/avaliacao/tempo_manual.py",
             "semente": SEMENTE, "resumo": resumir(medicoes), "medicoes": medicoes}
    arquivo.write_text(json.dumps(corpo, ensure_ascii=False, indent=1), encoding="utf-8")


def texto_resumo(medicoes: list[dict[str, Any]], avaliacao: dict[str, Any] | None) -> str:
    r = resumir(medicoes)
    if r["n"] == 0:
        return "Nenhuma medição registrada."
    linhas = [f"Busca manual (n={r['n']}, mesma pessoa que escreveu a base): mediana {r['mediana_s']} s, média {r['media_s']} s, "
              f"de {r['min_s']} a {r['max_s']} s; seção correta em {r['acertos_secao']}/{r['n']}."]
    for modo, resumo in (avaliacao or {}).get("resumos", {}).items():
        if "latencia_mediana_s" in resumo:
            linhas.append(f"Sistema, modo {modo}: mediana {resumo['latencia_mediana_s']:.1f} s, média {resumo['latencia_media_s']:.1f} s por pergunta.")
    linhas.append("Leitura: ordem de grandeza em uma base fictícia de 9 documentos, com medição de uma pessoa; "
                  "não é uma estatística nem vale para um portal real.")
    return "\n".join(linhas)


def medir(n: int = 10, *, arquivo: Path = ARQUIVO, perguntas: list[dict[str, Any]] | None = None,
          entrada: Callable[[str], str] = input, saida: Callable[[str], None] = print,
          relogio: Callable[[], float] = time.perf_counter) -> list[dict[str, Any]]:
    perguntas = perguntas if perguntas is not None else json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    medicoes = carregar(arquivo)
    feitas = {m["pergunta_id"] for m in medicoes}
    pendentes = [q for q in sortear(perguntas, n) if q["id"] not in feitas]
    saida("Busque SOMENTE pelo nome/código dos arquivos em dados/documentos/ (sem busca de texto, sem o assistente).")
    for i, q in enumerate(pendentes, 1):
        saida(f"\n[{i}/{len(pendentes)}] {q['pergunta']}")
        entrada("Enter para iniciar o cronômetro... ")
        t0 = relogio()
        entrada("Enter quando tiver achado o trecho... ")
        segundos = relogio() - t0
        doc = entrada("Documento encontrado (ex.: POL-ACE): ")
        sec = entrada("Seção encontrada (ex.: ACE-3): ")
        medicoes.append(registrar(q, segundos, doc, sec))
        salvar(medicoes, arquivo)
    return medicoes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=10, help="quantidade de perguntas sorteadas")
    ap.add_argument("--resumo", action="store_true")
    args = ap.parse_args(argv)
    avaliacao = json.loads(AVALIACAO.read_text(encoding="utf-8")) if AVALIACAO.exists() else None
    if args.resumo:
        print(texto_resumo(carregar(), avaliacao))
        return 0
    medicoes = medir(args.n)
    print("\n" + texto_resumo(medicoes, avaliacao))
    return 0


if __name__ == "__main__":
    sys.exit(main())
