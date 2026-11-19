"""Chamada de teste a cada provedor, imprimindo os tokens usados.

Uso (na raiz do projeto, com .env preenchido):  python -m src.teste_provedores
Custo esperado: frações de centavo de dólar por provedor.
"""
from __future__ import annotations

import sys

from .config import ConfigError, carregar_settings
from .custo import ControleCusto, TabelaPrecos
from .provedores import chamar_anthropic, chamar_openai

PROMPT = "Responda apenas com a palavra: ok."


def main() -> int:
    try:
        s = carregar_settings()
    except ConfigError as e:
        print(f"ERRO de configuração: {e}")
        return 2
    controle = ControleCusto(TabelaPrecos.de_json(s.precos_path), s.orcamentos(), s.log_dir / "chamadas.jsonl")
    falhas = 0
    for nome, fn in (("openai", chamar_openai), ("anthropic", chamar_anthropic)):
        try:
            r = fn(PROMPT, s, controle)
            print(f"[{nome}] modelo={r.modelo} tokens_in={r.tokens_in} tokens_out={r.tokens_out} "
                  f"custo_usd={r.custo_usd:.6f} latencia_s={r.latencia_s:.2f} texto={r.texto.strip()!r}")
        except Exception as e:  # mostra tipo e mensagem; nunca a chave
            falhas += 1
            print(f"[{nome}] FALHOU: {type(e).__name__}: {e}")
    for p in ("openai", "anthropic"):
        print(f"gasto acumulado {p}: {controle.gasto(p):.6f} / teto {controle.orcamentos[p]:.2f} USD")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
