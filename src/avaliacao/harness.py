"""Harness: roda as perguntas nos modos e agrega as métricas. Nada é digitado à mão.

Modos:
  openai      -> só o agente da OpenAI (com retry, sem fallback)
  anthropic   -> só o agente da Anthropic (com retry, sem fallback)
  orquestrado -> regra de roteamento + retry + fallback (Bloco 5)
Os três passam pelo MESMO Orquestrador (os modos de provedor único usam uma rota de um item), então
timeout, retry e contabilidade são idênticos e a diferença medida é só o roteamento.

Métricas (denominador = nº de perguntas do gabarito, 30):
  acerto          regra de src/avaliacao/acerto.py (+ sobrescritas manuais contadas)
  citacao_valida  schema ok E todas as citações entre os trechos que o agente de fato recuperou
  cita_origem     a seção do gabarito está entre as citadas
  custo           tokens x preço de config/precos.json (com data), somando TODAS as tentativas e provedores
  latencia        time.perf_counter, da pergunta até a resposta final, incluindo esperas de backoff
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from ..agentes.contrato import RespostaAuditoria
from ..custo import TabelaPrecos
from ..orquestrador.orquestrador import Orquestrador, ResultadoOrquestrado
from .acerto import Fatos, avaliar_acerto, cita_origem

MODOS = ("openai", "anthropic", "orquestrado")


@dataclass
class Linha:
    modo: str
    pergunta_id: str
    executada: bool
    status: str
    provedor_final: str | None
    valido: bool
    acerto: bool
    acerto_origem: str          # "regra" | "manual"
    cita_origem: bool
    custo_usd: float
    tokens_in: int
    tokens_out: int
    latencia_s: float
    tentativas: int
    rota: list[str]
    motivo_escalonamento: str | None
    prompt_versao: str | None
    resposta: dict[str, Any] | None
    erro: str | None = None

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


def avaliar_resposta(resposta: dict[str, Any] | None, fatos: Fatos, documento: str, secao: str,
                     manual: bool | None) -> tuple[bool, str, bool]:
    """(acerto, origem, cita_origem) a partir da resposta salva. Reusável ao regenerar o relatório."""
    resp = RespostaAuditoria(**resposta) if resposta else None
    if manual is not None:
        return manual, "manual", cita_origem(resp, documento, secao)
    return avaliar_acerto(resp, fatos), "regra", cita_origem(resp, documento, secao)


def linha_de_resultado(modo: str, q: Mapping[str, Any], fatos: Fatos, res: ResultadoOrquestrado,
                       manual: Mapping[str, bool]) -> Linha:
    f = res.final
    resposta = f.resposta.model_dump() if f and f.resposta else None
    acerto, origem, cita = avaliar_resposta(resposta, fatos, q["documento"], q["secao"],
                                            manual.get(f"{modo}:{q['id']}"))
    return Linha(
        modo=modo, pergunta_id=q["id"], executada=f is not None, status=res.status,
        provedor_final=res.provedor_final, valido=bool(f and f.valido), acerto=acerto, acerto_origem=origem,
        cita_origem=cita, custo_usd=res.custo_total_usd, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        latencia_s=res.latencia_s, tentativas=len(res.tentativas), rota=list(res.rota),
        motivo_escalonamento=res.motivo_escalonamento, prompt_versao=f.prompt_versao if f else None,
        resposta=resposta, erro=f.erro if f else "nenhum provedor respondeu")


def executar_modo(modo: str, perguntas: list[Mapping[str, Any]], fatos: Mapping[str, Fatos],
                  orquestrador: Orquestrador, manual: Mapping[str, bool],
                  ao_terminar_pergunta: Callable[[Linha], None] | None = None) -> list[Linha]:
    linhas: list[Linha] = []
    for q in perguntas:
        res = orquestrador.responder(q["pergunta"], q["id"])
        linha = linha_de_resultado(modo, q, fatos[q["id"]], res, manual)
        linhas.append(linha)
        if ao_terminar_pergunta:
            ao_terminar_pergunta(linha)
    return linhas


def recalcular(linhas: list[dict[str, Any]], perguntas: list[Mapping[str, Any]], fatos: Mapping[str, Fatos],
               manual: Mapping[str, bool]) -> list[Linha]:
    """Reaplica a regra de acerto (e as sobrescritas) a linhas já salvas, sem chamar nenhuma API."""
    por_id = {q["id"]: q for q in perguntas}
    saida = []
    for d in linhas:
        q = por_id[d["pergunta_id"]]
        acerto, origem, cita = avaliar_resposta(d["resposta"], fatos[q["id"]], q["documento"], q["secao"],
                                                manual.get(f"{d['modo']}:{q['id']}"))
        saida.append(Linha(**{**d, "acerto": acerto, "acerto_origem": origem, "cita_origem": cita}))
    return saida


@dataclass
class Resumo:
    modo: str
    n_gabarito: int
    n_executadas: int
    acertos: int
    validas: int
    cita_origem: int
    sobrescritas_manuais: int
    custo_total_usd: float
    custo_por_resposta_usd: float
    tokens_in: int
    tokens_out: int
    latencia_media_s: float
    latencia_mediana_s: float
    latencia_max_s: float
    escalonadas: int = 0
    finais_por_provedor: dict[str, int] = field(default_factory=dict)
    tentativas_extras: int = 0

    @property
    def acerto(self) -> float:
        return self.acertos / self.n_gabarito

    @property
    def citacao_valida(self) -> float:
        return self.validas / self.n_gabarito

    @property
    def taxa_cita_origem(self) -> float:
        return self.cita_origem / self.n_gabarito


def agregar(modo: str, linhas: list[Linha], n_gabarito: int) -> Resumo:
    ex = [l for l in linhas if l.executada]
    lat = [l.latencia_s for l in ex]
    provs: dict[str, int] = {}
    for l in ex:
        provs[l.provedor_final or "?"] = provs.get(l.provedor_final or "?", 0) + 1
    return Resumo(
        modo=modo, n_gabarito=n_gabarito, n_executadas=len(ex),
        acertos=sum(l.acerto for l in linhas), validas=sum(l.valido for l in linhas),
        cita_origem=sum(l.cita_origem for l in linhas),
        sobrescritas_manuais=sum(l.acerto_origem == "manual" for l in linhas),
        custo_total_usd=sum(l.custo_usd for l in linhas),
        custo_por_resposta_usd=(sum(l.custo_usd for l in linhas) / len(ex)) if ex else 0.0,
        tokens_in=sum(l.tokens_in for l in linhas), tokens_out=sum(l.tokens_out for l in linhas),
        latencia_media_s=statistics.fmean(lat) if lat else 0.0,
        latencia_mediana_s=statistics.median(lat) if lat else 0.0,
        latencia_max_s=max(lat) if lat else 0.0,
        escalonadas=sum(len(l.rota) > 1 for l in linhas), finais_por_provedor=provs,
        tentativas_extras=sum(max(0, l.tentativas - max(1, len(l.rota))) for l in ex))


def precos_dos_modos(tabela: TabelaPrecos, modelos: Mapping[str, str]) -> list[dict[str, Any]]:
    """Preços usados, com a marca de verificação oficial, para o relatório."""
    saida = []
    for prov, modelo in modelos.items():
        p = tabela.get(modelo)
        saida.append({"provedor": prov, "modelo": modelo, "input_mtok": p.input_mtok,
                      "output_mtok": p.output_mtok, "verificado_oficial": p.verificado_oficial})
    return saida
