"""Cálculo de custo e teto rígido de gasto por provedor.

Regras:
- Antes de cada chamada, `reservar()` estima o pior caso (entrada estimada + max_tokens de saída).
  Se gasto acumulado + pior caso > teto, levanta OrcamentoExcedido: a chamada NÃO é feita e o
  bloqueio é registrado.
- Depois da chamada, `registrar()` grava tokens de entrada e saída reais e o custo.
- O gasto acumulado é lido do arquivo de log (JSONL) ao iniciar, então o teto vale entre execuções.
- Limitação: se uma chamada falha no meio (timeout) o provedor pode ter cobrado sem que saibamos
  os tokens; esse caso é registrado como status "erro" com custo 0 e NÃO entra na soma.
  Por isso o teto padrão (4 USD) deixa margem sobre o orçamento (5 USD).
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Estimativa conservadora de tokens a partir de caracteres (texto em português; o tokenizer
# novo da Anthropic gera ~30% mais tokens). 2 caracteres/token superestima de propósito.
CARACTERES_POR_TOKEN_PIOR_CASO = 2.0


class OrcamentoExcedido(RuntimeError):
    """A chamada não foi feita porque ultrapassaria o teto de gasto configurado."""


class ModeloSemPreco(RuntimeError):
    """O modelo não está na tabela de preços; sem preço não há como garantir o teto."""


@dataclass(frozen=True)
class Preco:
    modelo: str
    provedor: str
    input_mtok: float
    output_mtok: float
    limite_prompt_tokens: int | None = None
    input_mtok_acima: float | None = None
    output_mtok_acima: float | None = None
    verificado_oficial: bool = False
    fonte: str = ""

    def custo(self, tokens_in: int, tokens_out: int) -> float:
        acima = self.limite_prompt_tokens is not None and tokens_in > self.limite_prompt_tokens
        p_in = self.input_mtok_acima if acima and self.input_mtok_acima is not None else self.input_mtok
        p_out = self.output_mtok_acima if acima and self.output_mtok_acima is not None else self.output_mtok
        return tokens_in / 1_000_000 * p_in + tokens_out / 1_000_000 * p_out


class TabelaPrecos:
    def __init__(self, precos: dict[str, Preco], data_consulta: str):
        self._precos = precos
        self.data_consulta = data_consulta

    @classmethod
    def de_json(cls, caminho: Path) -> "TabelaPrecos":
        bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))
        precos = {nome: Preco(modelo=nome, **campos) for nome, campos in bruto["modelos"].items()}
        return cls(precos, bruto["data_consulta"])

    def get(self, modelo: str) -> Preco:
        if modelo not in self._precos:
            raise ModeloSemPreco(f"Modelo '{modelo}' não está em config/precos.json.")
        return self._precos[modelo]


def estimar_tokens_entrada(caracteres: int) -> int:
    return math.ceil(caracteres / CARACTERES_POR_TOKEN_PIOR_CASO)


class ControleCusto:
    def __init__(self, tabela: TabelaPrecos, orcamentos: dict[str, float], log_path: Path):
        self.tabela = tabela
        self.orcamentos = dict(orcamentos)
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._gasto: dict[str, float] = {p: 0.0 for p in self.orcamentos}
        self._carregar_historico()

    def _carregar_historico(self) -> None:
        if not self.log_path.exists():
            return
        for linha in self.log_path.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            reg = json.loads(linha)
            if reg.get("status") == "ok":
                self._gasto[reg["provedor"]] = self._gasto.get(reg["provedor"], 0.0) + reg["custo_usd"]

    def gasto(self, provedor: str) -> float:
        return self._gasto.get(provedor, 0.0)

    def restante(self, provedor: str) -> float:
        return self.orcamentos[provedor] - self.gasto(provedor)

    def _gravar(self, registro: dict[str, Any]) -> None:
        registro = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **registro}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    def reservar(self, provedor: str, modelo: str, caracteres_prompt: int, max_tokens_saida: int,
                 proposito: str = "") -> float:
        """Verifica o teto ANTES da chamada. Devolve o custo de pior caso estimado."""
        preco = self.tabela.get(modelo)
        est_in = estimar_tokens_entrada(caracteres_prompt)
        pior_caso = preco.custo(est_in, max_tokens_saida)
        if self.gasto(provedor) + pior_caso > self.orcamentos[provedor]:
            self._gravar({
                "provedor": provedor, "modelo": modelo, "status": "bloqueado_orcamento",
                "tokens_in": 0, "tokens_out": 0, "custo_usd": 0.0, "proposito": proposito,
                "pior_caso_usd": round(pior_caso, 8), "gasto_acumulado_usd": round(self.gasto(provedor), 8),
                "teto_usd": self.orcamentos[provedor],
            })
            raise OrcamentoExcedido(
                f"{provedor}: gasto {self.gasto(provedor):.4f} + pior caso {pior_caso:.4f} "
                f"> teto {self.orcamentos[provedor]:.2f} USD. Chamada não realizada."
            )
        return pior_caso

    def registrar(self, provedor: str, modelo: str, tokens_in: int, tokens_out: int,
                  latencia_s: float, proposito: str = "", **meta: Any) -> float:
        custo = self.tabela.get(modelo).custo(tokens_in, tokens_out)
        self._gasto[provedor] = self.gasto(provedor) + custo
        self._gravar({
            "provedor": provedor, "modelo": modelo, "status": "ok", "tokens_in": tokens_in,
            "tokens_out": tokens_out, "custo_usd": round(custo, 8), "latencia_s": round(latencia_s, 4),
            "proposito": proposito, "preco_data_consulta": self.tabela.data_consulta, **meta,
        })
        return custo

    def registrar_erro(self, provedor: str, modelo: str, erro: Exception, latencia_s: float,
                       proposito: str = "") -> None:
        self._gravar({
            "provedor": provedor, "modelo": modelo, "status": "erro", "tokens_in": 0, "tokens_out": 0,
            "custo_usd": 0.0, "latencia_s": round(latencia_s, 4), "proposito": proposito,
            "erro_tipo": type(erro).__name__,
        })
