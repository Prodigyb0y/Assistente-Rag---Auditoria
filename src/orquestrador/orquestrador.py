"""Orquestrador: tenta o provedor mais barato, escala para o outro conforme a regra de código.

Três modos (Politica.modo), todos com a decisão em código:
  escalonar  : o fluxo abaixo (regra original).
  adaptativo : aceita direto quando o primeiro passa na regra; senão pede ao segundo uma segunda opinião
               (primeiro se absteve ou falhou) ou uma confirmação cruzada (confiança abaixo da mínima), e
               decide por `politica.decidir_par`.
  consenso   : os dois provedores sempre respondem; `decidir_par` compara fontes e números.

Fluxo do modo escalonar, por pergunta:
  para cada provedor da rota (mais barato primeiro):
      tenta até `max_tentativas` vezes, com espera exponencial, SOMENTE em falha transitória;
      OrcamentoExcedido nunca é repetido: o provedor é pulado e o outro assume;
      se o resultado passa na regra (politica.motivo_escalonamento) -> aceita e para;
      senão -> registra a decisão e segue para o próximo provedor.
  se ninguém foi aceito: devolve o melhor resultado disponível (status "melhor_esforco").

Timeout: cada chamada HTTP já tem timeout no cliente do SDK (TIMEOUT_S, max_retries=0). Além disso
há um prazo total por pergunta (`prazo_total_s`), conferido ANTES de cada nova tentativa ou
provedor; ele não interrompe uma chamada em andamento.
Um retry refaz a resposta inteira (busca + chamadas ao modelo); as chamadas que já tinham
terminado ficam no custo, porque o provedor já cobrou.
O log de roteamento (logs/roteamento.jsonl) NÃO grava mensagens de exceção, só o nome da classe e o
status HTTP, para nunca vazar trechos de chave ou de resposta do provedor.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..agentes.contrato import Agente, ResultadoAgente
from ..custo import OrcamentoExcedido
from .politica import (ACEITA_APOS_ESCALONAMENTO, ACEITA_NO_PRIMEIRO, ACEITA_POR_CONSENSO, DIVERGENCIA, FALHA,  # noqa: F401
                       MELHOR_ESFORCO, NAO_ENCONTRADO_CONFIRMADO, STATUS_ACEITOS, Falha, Motivo, Politica,
                       classificar_falha, decidir_par, detalhe_comparacao, espera_backoff, melhor, motivo_escalonamento,
                       valida_ordem)


class LogRoteamento:
    """JSONL com cada decisão de roteamento (tentativa, retry, escalonamento, final)."""

    def __init__(self, caminho: Path | None):
        self.caminho = Path(caminho) if caminho else None
        if self.caminho:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)

    def gravar(self, evento: str, **campos: Any) -> None:
        if not self.caminho:
            return
        reg = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "evento": evento, **campos}
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")


@dataclass
class Tentativa:
    provedor: str
    numero: int
    resultado: ResultadoAgente | None   # None = chamada bloqueada pelo teto de gasto
    falha: Falha | None = None
    erro_tipo: str | None = None


@dataclass
class ResultadoOrquestrado:
    pergunta_id: str
    pergunta: str
    status: str = FALHA
    final: ResultadoAgente | None = None
    rota: list[str] = field(default_factory=list)            # provedores que devolveram resultado
    motivo_escalonamento: str | None = None                  # por que o primeiro não bastou
    tentativas: list[Tentativa] = field(default_factory=list)
    latencia_s: float = 0.0                                  # total, incluindo esperas de backoff
    modo: str = "escalonar"
    caminho: str = ""                                        # direto | segunda_opiniao | confirmacao_cruzada | segundo_indisponivel | esgotado
    concordancia: str | None = None                          # concordam | divergem (quando os dois responderam)

    @property
    def provedor_final(self) -> str | None:
        return self.final.provedor if self.final else None

    @property
    def escalou(self) -> bool:
        return len(self.rota) > 1

    @property
    def aceito(self) -> bool:
        return self.status in STATUS_ACEITOS

    def _resultados(self) -> list[ResultadoAgente]:
        return [t.resultado for t in self.tentativas if t.resultado is not None]

    @property
    def custo_total_usd(self) -> float:
        return sum(r.custo_total_usd for r in self._resultados())

    @property
    def tokens_in(self) -> int:
        return sum(r.tokens_in for r in self._resultados())

    @property
    def tokens_out(self) -> int:
        return sum(r.tokens_out for r in self._resultados())


def _tipo(exc: BaseException | None) -> str | None:
    return type(exc).__name__ if exc is not None else None


def _status_http(exc: BaseException | None) -> int | None:
    s = getattr(exc, "status_code", None)
    return s if isinstance(s, int) else None


class Orquestrador:
    def __init__(self, agentes: Mapping[str, Agente], ordem: Sequence[str], politica: Politica,
                 log: LogRoteamento | None = None, *,
                 dormir: Callable[[float], None] = time.sleep,
                 relogio: Callable[[], float] = time.perf_counter):
        self.agentes = dict(agentes)
        self.ordem = valida_ordem(ordem, list(self.agentes))
        self.politica = politica
        self.log = log or LogRoteamento(None)
        self._dormir = dormir
        self._relogio = relogio

    # -- execução de um provedor, com retry -------------------------------------------------
    def _falha_inesperada(self, ag: Agente, pergunta: str, pid: str, exc: Exception) -> ResultadoAgente:
        # Contrato dos agentes: não levantam exceção (exceto OrcamentoExcedido). Se levantarem, é bug.
        return ResultadoAgente(provedor=ag.provedor, modelo=ag.modelo, prompt_versao="?", prompt_sha="?",
                               pergunta_id=pid, pergunta=pergunta, erro=f"{type(exc).__name__}: {exc}",
                               excecao=exc)

    def _tentar_provedor(self, prov: str, pergunta: str, pid: str, res: ResultadoOrquestrado,
                         inicio: float) -> ResultadoAgente | None:
        ag = self.agentes[prov]
        pol = self.politica
        r: ResultadoAgente | None = None
        for n in range(1, pol.max_tentativas + 1):
            try:
                r = ag.responder(pergunta, pid)
            except OrcamentoExcedido:
                res.tentativas.append(Tentativa(prov, n, None, None, "OrcamentoExcedido"))
                self.log.gravar("orcamento_bloqueado", pergunta_id=pid, provedor=prov, tentativa=n)
                return None
            except Exception as exc:  # noqa: BLE001
                r = self._falha_inesperada(ag, pergunta, pid, exc)

            falha = classificar_falha(r.excecao) if r.excecao is not None else None
            res.tentativas.append(Tentativa(prov, n, r, falha, _tipo(r.excecao)))
            motivo = motivo_escalonamento(r, pol.confianca_minima)
            self.log.gravar(
                "tentativa", pergunta_id=pid, provedor=prov, modelo=r.modelo, tentativa=n,
                prompt_versao=r.prompt_versao, valido=r.valido,
                motivo=motivo.value if motivo else None, falha=falha.value if falha else None,
                erro_tipo=_tipo(r.excecao), status_http=_status_http(r.excecao),
                tokens_in=r.tokens_in, tokens_out=r.tokens_out, custo_usd=round(r.custo_total_usd, 8),
                latencia_s=round(r.latencia_s, 4))

            if falha is not Falha.TRANSITORIA:
                return r
            if n == pol.max_tentativas:
                self.log.gravar("retries_esgotados", pergunta_id=pid, provedor=prov, tentativas=n)
                return r
            espera = espera_backoff(n, pol.espera_base_s, pol.espera_max_s)
            if (self._relogio() - inicio) + espera >= pol.prazo_total_s:
                self.log.gravar("prazo_excedido", pergunta_id=pid, provedor=prov, antes_de="retry",
                                prazo_total_s=pol.prazo_total_s)
                return r
            self.log.gravar("retry", pergunta_id=pid, provedor=prov, proxima_tentativa=n + 1,
                            espera_s=espera, erro_tipo=_tipo(r.excecao), status_http=_status_http(r.excecao))
            self._dormir(espera)
        return r

    # -- roteamento -------------------------------------------------------------------------
    def responder(self, pergunta: str, pergunta_id: str = "") -> ResultadoOrquestrado:
        inicio = self._relogio()
        res = ResultadoOrquestrado(pergunta_id=pergunta_id, pergunta=pergunta, modo=self.politica.modo)
        if self.politica.modo != "escalonar" and len(self.ordem) >= 2:
            self._responder_cooperativo(pergunta, pergunta_id, res, inicio)
        else:
            self._responder_escalonando(pergunta, pergunta_id, res, inicio)
        res.latencia_s = self._relogio() - inicio
        self.log.gravar(
            "final", pergunta_id=pergunta_id, status=res.status, provedor_final=res.provedor_final,
            rota=res.rota, motivo_escalonamento=res.motivo_escalonamento, modo=res.modo, caminho=res.caminho,
            concordancia=res.concordancia, prompt_versao=res.final.prompt_versao if res.final else None,
            tentativas=len(res.tentativas), tokens_in=res.tokens_in, tokens_out=res.tokens_out,
            custo_usd=round(res.custo_total_usd, 8), latencia_s=round(res.latencia_s, 4))
        return res

    # -- modos adaptativo e consenso -------------------------------------------------------------
    def _obter(self, prov: str, pergunta: str, pid: str, res: ResultadoOrquestrado, inicio: float,
               *, checar_prazo: bool) -> ResultadoAgente | None:
        if checar_prazo and (self._relogio() - inicio) >= self.politica.prazo_total_s:
            self.log.gravar("prazo_excedido", pergunta_id=pid, provedor=prov, antes_de="provedor",
                            prazo_total_s=self.politica.prazo_total_s)
            return None
        r = self._tentar_provedor(prov, pergunta, pid, res, inicio)
        if r is None:   # teto de gasto
            self.log.gravar("decisao", pergunta_id=pid, provedor=prov, acao="pular_provedor",
                            motivo="orcamento_excedido", para=None)
            return None
        res.rota.append(prov)
        return r

    def _responder_cooperativo(self, pergunta: str, pid: str, res: ResultadoOrquestrado, inicio: float) -> None:
        minima = self.politica.confianca_minima
        p1, p2 = self.ordem[0], self.ordem[1]
        a = self._obter(p1, pergunta, pid, res, inicio, checar_prazo=False)
        if a is None:   # primeiro bloqueado pelo teto: o segundo assume sozinho, pela regra de aceitação
            res.motivo_escalonamento = "orcamento_excedido"
            b = self._obter(p2, pergunta, pid, res, inicio, checar_prazo=True)
            if b is None:
                res.status, res.caminho = FALHA, "esgotado"
                return
            res.final, res.caminho = b, "segunda_opiniao"
            res.status = ACEITA_APOS_ESCALONAMENTO if motivo_escalonamento(b, minima) is None else MELHOR_ESFORCO
            self.log.gravar("decisao", pergunta_id=pid, provedor=p2, acao="assumir", motivo="orcamento_excedido",
                            para=None)
            return

        motivo = motivo_escalonamento(a, minima)
        res.motivo_escalonamento = motivo.value if motivo else None
        if motivo is None and self.politica.modo == "adaptativo":
            res.final, res.status, res.caminho = a, ACEITA_NO_PRIMEIRO, "direto"
            self.log.gravar("decisao", pergunta_id=pid, provedor=p1, acao="aceitar", motivo=None, para=None)
            return

        # segunda chamada: segunda opinião (abstenção/falha) ou confirmação cruzada (confiança baixa, modo consenso)
        caminho = "confirmacao_cruzada" if (motivo is None or motivo is Motivo.CONFIANCA_BAIXA) else "segunda_opiniao"
        self.log.gravar("decisao", pergunta_id=pid, provedor=p1, acao=caminho, motivo=res.motivo_escalonamento,
                        para=p2)
        b = self._obter(p2, pergunta, pid, res, inicio, checar_prazo=True)
        d = decidir_par(a, b, minima)
        res.final = a if d.escolhido == "a" else b
        res.status, res.caminho = d.status, caminho if b is not None else "segundo_indisponivel"
        res.concordancia = d.concordancia.value if d.concordancia else None
        detalhe = detalhe_comparacao(a, b) if b is not None else {}
        self.log.gravar("decisao", pergunta_id=pid, provedor=res.final.provedor if res.final else None,
                        acao="decidir_par", motivo=d.motivo, para=None, status=d.status,
                        concordancia=res.concordancia, **detalhe)

    # -- modo escalonar (regra original) -----------------------------------------------------------
    def _responder_escalonando(self, pergunta: str, pergunta_id: str, res: ResultadoOrquestrado,
                               inicio: float) -> None:
        obtidos: list[ResultadoAgente] = []
        aceito: ResultadoAgente | None = None
        res.caminho = "direto"

        for i, prov in enumerate(self.ordem):
            if i > 0 and (self._relogio() - inicio) >= self.politica.prazo_total_s:
                self.log.gravar("prazo_excedido", pergunta_id=pergunta_id, provedor=prov, antes_de="provedor",
                                prazo_total_s=self.politica.prazo_total_s)
                break
            proximo = self.ordem[i + 1] if i + 1 < len(self.ordem) else None
            r = self._tentar_provedor(prov, pergunta, pergunta_id, res, inicio)
            if r is None:   # teto de gasto: provedor pulado
                if i == 0:
                    res.motivo_escalonamento = "orcamento_excedido"
                self.log.gravar("decisao", pergunta_id=pergunta_id, provedor=prov, acao="pular_provedor",
                                motivo="orcamento_excedido", para=proximo)
                continue
            res.rota.append(prov)
            obtidos.append(r)
            motivo = motivo_escalonamento(r, self.politica.confianca_minima)
            if motivo is None:
                aceito = r
                self.log.gravar("decisao", pergunta_id=pergunta_id, provedor=prov, acao="aceitar", motivo=None,
                                para=None)
                break
            if i == 0:
                res.motivo_escalonamento = motivo.value
            self.log.gravar("decisao", pergunta_id=pergunta_id, provedor=prov,
                            acao="escalar" if proximo else "sem_proximo_provedor", motivo=motivo.value,
                            para=proximo)

        if aceito is not None:
            res.final = aceito
            res.status = ACEITA_NO_PRIMEIRO if aceito.provedor == self.ordem[0] else ACEITA_APOS_ESCALONAMENTO
        elif obtidos:
            escolhido = obtidos[0]
            for outro in obtidos[1:]:
                escolhido = melhor(escolhido, outro, self.politica.confianca_minima)
            res.final = escolhido
            res.status = MELHOR_ESFORCO
        else:
            res.status = FALHA
        if len(res.rota) > 1:
            res.caminho = "segunda_opiniao"
