"""Serviço da demo: valida a pergunta, consulta o cache, aplica limites e chama o orquestrador.

É a camada testável da interface: a tela Gradio só chama `perguntar` e mostra o resultado.
Ordem: validar -> cache (grátis) -> limite/teto -> orquestrador -> cache -> registrar custo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..orquestrador.orquestrador import Orquestrador
from .cache import CacheRespostas, chave_cache
from .limites import LimiteDiario

MENSAGENS = {
    "invalida": "Escreva uma pergunta (até {max} caracteres) sobre as políticas da Gutenberg Systems.",
    "limite_visitante": "Você atingiu o limite de perguntas de hoje nesta demo. Volte amanhã.",
    "limite_global": "A demo atingiu o limite diário de perguntas. Volte amanhã.",
    "teto_custo": "A demo atingiu o teto de custo de hoje. Volte amanhã.",
    "falha": "Não consegui obter resposta dos provedores agora. Sua pergunta não foi descontada. Tente de novo.",
}
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class RespostaDemo:
    status: str                       # ok | cache | invalida | limite_visitante | limite_global | teto_custo | falha
    mensagem: str = ""
    resposta: str | None = None
    encontrado: bool | None = None
    confianca: str | None = None
    citacoes: list[dict[str, str]] = field(default_factory=list)
    provedor: str | None = None
    aceita_pela_regra: bool = False
    status_orq: str = ""              # estado do orquestrador (ex.: aceita_por_consenso, divergencia)
    custo_usd: float = 0.0
    latencia_s: float = 0.0
    restantes_visitante: int = 0

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "cache")


def validar_pergunta(texto: str | None, max_chars: int) -> str | None:
    if not texto:
        return None
    limpo = " ".join(_CONTROLE.sub(" ", texto).split())
    return limpo if 0 < len(limpo) <= max_chars else None


class ServicoDemo:
    def __init__(self, orquestrador: Orquestrador, limites: LimiteDiario, cache: CacheRespostas, *,
                 prompt_versao: str, modelos: str, max_chars: int = 300):
        self.orq, self.limites, self.cache = orquestrador, limites, cache
        self.prompt_versao, self.modelos, self.max_chars = prompt_versao, modelos, max_chars

    def _bloqueio(self, status: str, restantes: int = 0) -> RespostaDemo:
        return RespostaDemo(status=status, mensagem=MENSAGENS[status].format(max=self.max_chars),
                            restantes_visitante=restantes)

    def restantes(self, visitante: str) -> int:
        """Perguntas que o visitante ainda pode fazer hoje (não reserva nada)."""
        return self.limites.consultar(visitante).restantes_visitante

    def perguntar(self, texto: str | None, visitante: str) -> RespostaDemo:
        pergunta = validar_pergunta(texto, self.max_chars)
        if pergunta is None:
            return self._bloqueio("invalida", self.limites.consultar(visitante).restantes_visitante)

        chave = chave_cache(pergunta, self.prompt_versao, self.modelos)
        guardado: dict[str, Any] | None = self.cache.obter(chave)
        if guardado is not None:   # cache hit: sem limite, sem custo
            return RespostaDemo(status="cache", restantes_visitante=self.limites.consultar(visitante).restantes_visitante,
                                custo_usd=0.0, **guardado)

        dec = self.limites.reservar(visitante)
        if not dec.permitido:
            return self._bloqueio(dec.motivo or "limite_global", dec.restantes_visitante)

        res = self.orq.responder(pergunta, "demo")
        self.limites.registrar_custo(res.custo_total_usd)   # gasto real, mesmo se a resposta falhar
        f = res.final
        if f is None or f.resposta is None:
            self.limites.estornar(visitante)
            return self._bloqueio("falha", dec.restantes_visitante + 1)

        dados: dict[str, Any] = {
            "resposta": f.resposta.resposta, "encontrado": f.resposta.encontrado, "confianca": f.resposta.confianca,
            "citacoes": [c.model_dump() for c in f.resposta.citacoes], "provedor": res.provedor_final,
            "aceita_pela_regra": res.aceito, "status_orq": res.status}
        if res.aceito:   # só guarda o que passou na regra
            self.cache.guardar(chave, dados)
        return RespostaDemo(status="ok", custo_usd=res.custo_total_usd, latencia_s=res.latencia_s,
                            restantes_visitante=dec.restantes_visitante, **dados)
