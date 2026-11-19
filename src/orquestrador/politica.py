"""Regras puras do orquestrador: quando escalar, quando repetir, quanto esperar, quem vai primeiro.

Nada aqui chama rede nem SDK. Tudo é função de dados, para ser testado sem custo. A regra mora em
código (não no prompt), como pede o Bloco 5.

REGRA DE ROTEAMENTO (ordem de verificação; a primeira que vale decide):
  1. ERRO                -> não há saída utilizável (exceção, truncamento, limite de rodadas).
  2. SAIDA_INVALIDA      -> há texto, mas não é JSON conforme o schema.
  3. SEM_CITACAO_VALIDA  -> JSON ok, mas sem citação, ou com citação fora dos trechos recuperados.
                            Inclui encontrado=false (não há citação a validar).
  4. CONFIANCA_BAIXA     -> confiança do agente abaixo da mínima configurada.
  Nenhuma das quatro -> ACEITA. Qualquer uma -> ESCALA para o outro provedor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from ..agentes.contrato import ResultadoAgente
from ..config import Settings
from ..custo import TabelaPrecos

NIVEL_CONFIANCA = {"baixa": 0, "media": 1, "alta": 2}


class Motivo(str, Enum):
    ERRO = "erro"
    SAIDA_INVALIDA = "saida_invalida"
    SEM_CITACAO_VALIDA = "sem_citacao_valida"
    CONFIANCA_BAIXA = "confianca_baixa"


class Falha(str, Enum):
    TRANSITORIA = "transitoria"   # vale repetir a chamada
    DEFINITIVA = "definitiva"     # repetir não adianta; ir para o outro provedor


@dataclass(frozen=True)
class Politica:
    confianca_minima: str = "media"
    max_tentativas: int = 3
    espera_base_s: float = 1.0
    espera_max_s: float = 8.0
    prazo_total_s: float = 120.0

    def __post_init__(self) -> None:
        if self.confianca_minima not in NIVEL_CONFIANCA:
            raise ValueError(f"confianca_minima inválida: {self.confianca_minima}")
        if self.max_tentativas < 1:
            raise ValueError("max_tentativas deve ser >= 1")

    @classmethod
    def de_settings(cls, s: Settings) -> "Politica":
        return cls(s.confianca_minima, s.max_tentativas, s.espera_base_s, s.espera_max_s, s.prazo_total_s)


def motivo_escalonamento(r: ResultadoAgente, confianca_minima: str = "media") -> Motivo | None:
    """None = resposta aceita. Caso contrário, o motivo para tentar o outro provedor."""
    if not r.schema_ok:
        return Motivo.SAIDA_INVALIDA if r.saida_bruta else Motivo.ERRO
    if r.resposta is None:  # defensivo: schema_ok sem resposta não deveria ocorrer
        return Motivo.ERRO
    if not r.citacoes_ok or not r.resposta.citacoes:
        return Motivo.SEM_CITACAO_VALIDA
    if NIVEL_CONFIANCA[r.resposta.confianca] < NIVEL_CONFIANCA[confianca_minima]:
        return Motivo.CONFIANCA_BAIXA
    return None


def espera_backoff(tentativa: int, base_s: float, max_s: float) -> float:
    """Espera ANTES da próxima tentativa, dado o número da tentativa que acabou de falhar (1, 2, ...).
    Exponencial base 2, com teto. Sem jitter: o projeto tem um único cliente, sem rajada simultânea."""
    return min(max_s, base_s * (2 ** (tentativa - 1)))


# Status HTTP que o próprio SDK trata como repetíveis (documentação dos SDKs): 408, 409, 429 e >= 500.
_STATUS_TRANSITORIOS = frozenset({408, 409, 429})
_NOMES_TRANSITORIOS = frozenset({"APITimeoutError", "APIConnectionError"})


def classificar_falha(exc: BaseException) -> Falha:
    """Transitória = timeout, rede, 408/409/429 e 5xx (inclui 529 'overloaded'). O resto é definitiva
    (400/401/403/404/422, bug nosso). 429 por cota esgotada (insufficient_quota) é definitiva:
    repetir não resolve e só gasta tempo. Usa nomes de classe e atributos, sem importar os SDKs."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return Falha.TRANSITORIA
    if _NOMES_TRANSITORIOS & {c.__name__ for c in type(exc).__mro__}:
        return Falha.TRANSITORIA
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        if status == 429 and getattr(exc, "code", None) == "insufficient_quota":
            return Falha.DEFINITIVA
        if status in _STATUS_TRANSITORIOS or status >= 500:
            return Falha.TRANSITORIA
    return Falha.DEFINITIVA


def _qualidade(r: ResultadoAgente, confianca_minima: str) -> tuple[bool, bool, int]:
    nivel = NIVEL_CONFIANCA[r.resposta.confianca] if r.resposta else -1
    return (motivo_escalonamento(r, confianca_minima) is None, r.valido, nivel)


def melhor(a: ResultadoAgente, b: ResultadoAgente, confianca_minima: str = "media") -> ResultadoAgente:
    """Escolhe entre dois resultados quando nenhum foi aceito: aceitável > válido > maior confiança.
    Empate fica com `a` (o primeiro provedor da rota)."""
    return b if _qualidade(b, confianca_minima) > _qualidade(a, confianca_minima) else a


def ordem_por_preco(tabela: TabelaPrecos, modelos: dict[str, str]) -> tuple[str, ...]:
    """Provedores do mais barato ao mais caro: preço de lista de entrada + saída por 1M de tokens,
    na faixa base. Empate: ordem alfabética. É preço de lista, não custo medido."""
    def chave(prov: str) -> tuple[float, str]:
        p = tabela.get(modelos[prov])
        return (p.input_mtok + p.output_mtok, prov)
    return tuple(sorted(modelos, key=chave))


def valida_ordem(ordem: Sequence[str], disponiveis: Sequence[str]) -> tuple[str, ...]:
    ordem = tuple(ordem)
    if not ordem or len(set(ordem)) != len(ordem) or not set(ordem) <= set(disponiveis):
        raise ValueError(f"ordem de provedores inválida: {ordem}")
    return ordem
