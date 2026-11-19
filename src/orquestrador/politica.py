"""Regras puras do orquestrador: quando escalar, quando repetir, quanto esperar, quem vai primeiro.

Nada aqui chama rede nem SDK. Tudo é função de dados, para ser testado sem custo. A regra mora em
código (não no prompt), como pede o Bloco 5.

REGRA DE ROTEAMENTO (ordem de verificação; a primeira que vale decide):
  1. ERRO                -> não há saída utilizável (exceção, truncamento, limite de rodadas).
  2. SAIDA_INVALIDA      -> há texto, mas não é JSON conforme o schema.
  3. NAO_ENCONTRADO      -> JSON ok, encontrado=false e nenhuma citação: o agente se absteve.
  4. SEM_CITACAO_VALIDA  -> JSON ok, mas sem citação, ou com citação fora dos trechos recuperados.
  5. CONFIANCA_BAIXA     -> confiança do agente abaixo da mínima configurada.
  Nenhuma das cinco -> ACEITA. Qualquer uma -> a resposta não basta sozinha.

O que fazer quando não basta depende do MODO de orquestração (Politica.modo):
  escalonar  -> pergunta ao outro provedor e fica com o primeiro aceito (regra original).
  adaptativo -> o caminho depende do sinal: aceita direto; pede segunda opinião quando o primeiro
                se absteve ou falhou; pede confirmação cruzada quando a confiança ficou abaixo da mínima.
  consenso   -> os dois provedores sempre respondem e as respostas são comparadas.
A decisão sobre o par de respostas é a função pura `decidir_par`, testada sem rede.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Sequence

from ..agentes.contrato import ResultadoAgente
from ..config import Settings
from ..custo import TabelaPrecos

NIVEL_CONFIANCA = {"baixa": 0, "media": 1, "alta": 2}

# Estados finais de uma pergunta orquestrada.
ACEITA_NO_PRIMEIRO = "aceita_no_primeiro"
ACEITA_APOS_ESCALONAMENTO = "aceita_apos_escalonamento"
ACEITA_POR_CONSENSO = "aceita_por_consenso"             # dois provedores, mesmas fontes e mesmos valores
NAO_ENCONTRADO_CONFIRMADO = "nao_encontrado_confirmado"  # os dois se abstiveram: a base não traz a resposta
DIVERGENCIA = "divergencia"                              # dois provedores válidos, fontes ou valores diferentes
MELHOR_ESFORCO = "melhor_esforco"
FALHA = "falha"
STATUS_ACEITOS = frozenset({ACEITA_NO_PRIMEIRO, ACEITA_APOS_ESCALONAMENTO, ACEITA_POR_CONSENSO,
                            NAO_ENCONTRADO_CONFIRMADO})

Modo = Literal["escalonar", "adaptativo", "consenso"]
MODOS = ("escalonar", "adaptativo", "consenso")


class Motivo(str, Enum):
    ERRO = "erro"
    SAIDA_INVALIDA = "saida_invalida"
    NAO_ENCONTRADO = "nao_encontrado"
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
    modo: str = "escalonar"

    def __post_init__(self) -> None:
        if self.modo not in MODOS:
            raise ValueError(f"modo inválido: {self.modo}")
        if self.confianca_minima not in NIVEL_CONFIANCA:
            raise ValueError(f"confianca_minima inválida: {self.confianca_minima}")
        if self.max_tentativas < 1:
            raise ValueError("max_tentativas deve ser >= 1")

    @classmethod
    def de_settings(cls, s: Settings) -> "Politica":
        return cls(s.confianca_minima, s.max_tentativas, s.espera_base_s, s.espera_max_s, s.prazo_total_s,
                   s.orquestracao_modo)


def eh_abstencao(r: ResultadoAgente) -> bool:
    """O agente respondeu, com schema válido e sem erro, que a base não traz a informação (encontrado=false,
    nenhuma citação). É a resposta correta para uma pergunta fora da base, não uma falha."""
    return bool(r.erro is None and r.schema_ok and r.resposta is not None
                and not r.resposta.encontrado and not r.resposta.citacoes)


def motivo_escalonamento(r: ResultadoAgente, confianca_minima: str = "media") -> Motivo | None:
    """None = resposta aceita. Caso contrário, o motivo para tentar o outro provedor."""
    if not r.schema_ok:
        return Motivo.SAIDA_INVALIDA if r.saida_bruta else Motivo.ERRO
    if r.resposta is None:  # defensivo: schema_ok sem resposta não deveria ocorrer
        return Motivo.ERRO
    if eh_abstencao(r):
        return Motivo.NAO_ENCONTRADO
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


# --- decisão sobre um par de respostas (modos adaptativo e consenso) ----------------------------

class Concordancia(str, Enum):
    CONCORDAM = "concordam"
    DIVERGEM = "divergem"


_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def numeros(texto: str) -> frozenset[str]:
    """Números que aparecem no texto; o ponto de milhar é removido (100.000 e 100000 contam como iguais)."""
    return frozenset(n.replace(".", "") for n in _NUMERO.findall(texto))


def citados(r: ResultadoAgente) -> frozenset[tuple[str, str]]:
    return frozenset((c.documento, c.secao) for c in r.resposta.citacoes) if r.resposta else frozenset()


def _numeros_da_resposta(r: ResultadoAgente) -> frozenset[str]:
    """Números da resposta, sem os que já estavam na pergunta: repetir o número da pergunta não informa nada
    sobre se as duas respostas concordam."""
    if r.resposta is None:
        return frozenset()
    return numeros(r.resposta.resposta) - numeros(r.pergunta)


def comparar(a: ResultadoAgente, b: ResultadoAgente) -> Concordancia:
    """Concordam quando (1) o conjunto de seções citadas de um contém o do outro e (2) as duas respostas
    trazem os mesmos números (descontados os que a pergunta já continha). Limite conhecido: não compara o
    sentido do texto, só fontes e números; na dúvida, a regra erra para o lado de DIVERGIR (pede revisão
    humana), nunca para o de aceitar."""
    ca, cb = citados(a), citados(b)
    mesmas_fontes = bool(ca) and bool(cb) and (ca <= cb or cb <= ca)
    mesmos_numeros = a.resposta is not None and b.resposta is not None \
        and _numeros_da_resposta(a) == _numeros_da_resposta(b)
    return Concordancia.CONCORDAM if mesmas_fontes and mesmos_numeros else Concordancia.DIVERGEM


def detalhe_comparacao(a: ResultadoAgente, b: ResultadoAgente) -> dict[str, object]:
    """Evidência da comparação para o log: só identificadores de seção, números e confiança (nunca o texto)."""
    def fontes(r: ResultadoAgente) -> list[str]:
        return sorted(f"{d}/{s}" for d, s in citados(r))
    return {"fontes_a": fontes(a), "fontes_b": fontes(b),
            "numeros_a": sorted(_numeros_da_resposta(a)), "numeros_b": sorted(_numeros_da_resposta(b)),
            "confianca_a": a.resposta.confianca if a.resposta else None,
            "confianca_b": b.resposta.confianca if b.resposta else None}


@dataclass(frozen=True)
class Decisao:
    status: str
    escolhido: Literal["a", "b"]
    motivo: str | None = None                 # o que impediu a aceitação direta do primeiro (ou None)
    concordancia: Concordancia | None = None


def _encontrada_valida(r: ResultadoAgente) -> bool:
    return bool(r.valido and r.resposta is not None and r.resposta.encontrado and r.resposta.citacoes)


def decidir_par(a: ResultadoAgente, b: ResultadoAgente | None, confianca_minima: str = "media") -> Decisao:
    """Decide o estado final a partir da resposta do primeiro provedor (a) e, se houve, do segundo (b).
    Função pura: não chama rede nem SDK. `b is None` = o segundo provedor não respondeu (teto de gasto,
    prazo)."""
    va = motivo_escalonamento(a, confianca_minima)
    motivo_a = va.value if va else None
    if b is None:
        return Decisao(ACEITA_NO_PRIMEIRO if va is None else MELHOR_ESFORCO, "a", motivo_a)
    vb = motivo_escalonamento(b, confianca_minima)

    if va is None and vb is None:                       # os dois passaram na regra: compara
        conc = comparar(a, b)
        if conc is Concordancia.DIVERGEM:
            return Decisao(DIVERGENCIA, "a" if melhor(a, b, confianca_minima) is a else "b", None, conc)
        return Decisao(ACEITA_POR_CONSENSO, "a" if melhor(a, b, confianca_minima) is a else "b", None, conc)
    # Quando os dois trouxeram resposta válida com citação, a concordância é sempre calculada e registrada,
    # mesmo que só um deles tenha passado na regra (a confirmação cruzada precisa aparecer no log).
    ambos = _encontrada_valida(a) and _encontrada_valida(b)
    conc_par = comparar(a, b) if ambos else None
    if va is None:                                      # só o primeiro passou: o segundo não confirmou
        return Decisao(ACEITA_NO_PRIMEIRO, "a", None, conc_par)
    if vb is None:                                      # só o segundo passou
        if conc_par is Concordancia.DIVERGEM:
            return Decisao(DIVERGENCIA, "b", motivo_a, conc_par)   # a tinha resposta válida e diferente
        return Decisao(ACEITA_APOS_ESCALONAMENTO, "b", motivo_a, conc_par)

    # nenhum dos dois passou na regra sozinho
    if eh_abstencao(a) and eh_abstencao(b):
        return Decisao(NAO_ENCONTRADO_CONFIRMADO, "a", motivo_a)
    if _encontrada_valida(a) and _encontrada_valida(b) \
            and "baixa" not in (a.resposta.confianca, b.resposta.confianca):
        conc = comparar(a, b)
        escolhido = "a" if melhor(a, b, confianca_minima) is a else "b"
        if conc is Concordancia.CONCORDAM:              # confiança abaixo da mínima nos dois, mas independentes e iguais
            return Decisao(ACEITA_POR_CONSENSO, escolhido, motivo_a, conc)
        return Decisao(DIVERGENCIA, escolhido, motivo_a, conc)
    return Decisao(MELHOR_ESFORCO, "a" if melhor(a, b, confianca_minima) is a else "b", motivo_a)
