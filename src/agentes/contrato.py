"""Contrato comum dos agentes: schema da resposta, validação e estrutura do resultado.

Os dois provedores recebem o MESMO schema (JSON Schema escrito à mão, sem $ref, compatível com os
modos estritos de saída estruturada). A saída é validada duas vezes em código:
  1. schema: JSON válido e conforme o modelo pydantic (extra="forbid");
  2. citações: cada (documento, seção) citado precisa ter sido devolvido pela ferramenta de busca
     NESTA execução. Citar algo que o agente não recuperou invalida a resposta.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

NOME_FERRAMENTA = "buscar_trechos"
MAX_PASSOS_FERRAMENTA = 4   # rodadas de ferramenta antes da resposta final
K_BUSCA = 3                 # trechos devolvidos por busca (mesmo k do recall@3 medido no Bloco 3)


class Citacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documento: str = Field(min_length=1)
    secao: str = Field(min_length=1)


class RespostaAuditoria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str = Field(min_length=1, max_length=1500)
    encontrado: bool
    citacoes: list[Citacao]
    confianca: Literal["alta", "media", "baixa"]


SCHEMA_RESPOSTA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resposta": {"type": "string", "description": "Resposta curta em português, só com base nos trechos."},
        "encontrado": {"type": "boolean", "description": "true se os trechos respondem à pergunta."},
        "citacoes": {
            "type": "array",
            "description": "Trechos que sustentam a resposta.",
            "items": {
                "type": "object",
                "properties": {
                    "documento": {"type": "string", "description": "Código do documento, ex.: POL-ACE."},
                    "secao": {"type": "string", "description": "Identificador da seção, ex.: ACE-3."},
                },
                "required": ["documento", "secao"],
                "additionalProperties": False,
            },
        },
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
    },
    "required": ["resposta", "encontrado", "citacoes", "confianca"],
    "additionalProperties": False,
}

SCHEMA_BUSCA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "consulta": {"type": "string", "description": "Texto da busca, em português, sobre o que se procura."},
    },
    "required": ["consulta"],
    "additionalProperties": False,
}

DESCRICAO_FERRAMENTA = (
    "Busca, na base de políticas da Gutenberg Systems, os trechos mais relevantes para a consulta. "
    f"Devolve até {K_BUSCA} trechos, cada um com documento, secao, titulo e texto."
)


@dataclass(frozen=True)
class Interpretacao:
    resposta: RespostaAuditoria | None
    schema_ok: bool
    citacoes_ok: bool
    erro: str | None


def interpretar_saida(texto: str, recuperados: set[tuple[str, str]]) -> Interpretacao:
    """Valida o texto final do modelo contra o schema e contra os trechos realmente recuperados."""
    try:
        resposta = RespostaAuditoria.model_validate(json.loads(texto))
    except json.JSONDecodeError:
        return Interpretacao(None, False, False, "saída não é JSON válido")
    except ValidationError as exc:
        campos = sorted({".".join(str(p) for p in e["loc"]) or "(raiz)" for e in exc.errors()})
        return Interpretacao(None, False, False, f"saída fora do schema: {', '.join(campos)}")

    if resposta.encontrado and not resposta.citacoes:
        return Interpretacao(resposta, True, False, "encontrado=true sem nenhuma citação")
    if not resposta.encontrado and resposta.citacoes:
        return Interpretacao(resposta, True, False, "encontrado=false com citação: abstenção não cita trecho")
    fora = [f"{c.documento}/{c.secao}" for c in resposta.citacoes if (c.documento, c.secao) not in recuperados]
    if fora:
        return Interpretacao(resposta, True, False, f"citação fora dos trechos recuperados: {', '.join(fora)}")
    return Interpretacao(resposta, True, True, None)


@dataclass
class ResultadoAgente:
    provedor: str
    modelo: str
    prompt_versao: str
    prompt_sha: str
    pergunta_id: str
    pergunta: str
    resposta: RespostaAuditoria | None = None
    saida_bruta: str = ""
    schema_ok: bool = False
    citacoes_ok: bool = False
    erro: str | None = None
    buscas: list[str] = field(default_factory=list)
    trechos_recuperados: list[str] = field(default_factory=list)
    n_chamadas_llm: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    custo_llm_usd: float = 0.0
    tokens_embedding: int = 0
    custo_busca_usd: float = 0.0
    latencia_s: float = 0.0
    # Exceção original, quando a falha veio do SDK/rede. Não é serializada; o orquestrador a usa
    # para decidir entre retry (transitória) e fallback imediato (definitiva).
    excecao: BaseException | None = field(default=None, repr=False, compare=False)

    @property
    def valido(self) -> bool:
        return self.erro is None and self.schema_ok and self.citacoes_ok

    @property
    def custo_total_usd(self) -> float:
        return self.custo_llm_usd + self.custo_busca_usd

    def para_dict(self) -> dict[str, Any]:
        return {
            "provedor": self.provedor, "modelo": self.modelo, "prompt_versao": self.prompt_versao,
            "prompt_sha": self.prompt_sha, "pergunta_id": self.pergunta_id, "pergunta": self.pergunta,
            "resposta": self.resposta.model_dump() if self.resposta else None,
            "saida_bruta": self.saida_bruta, "schema_ok": self.schema_ok, "citacoes_ok": self.citacoes_ok,
            "valido": self.valido, "erro": self.erro, "buscas": self.buscas,
            "trechos_recuperados": self.trechos_recuperados, "n_chamadas_llm": self.n_chamadas_llm,
            "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
            "custo_llm_usd": round(self.custo_llm_usd, 8), "tokens_embedding": self.tokens_embedding,
            "custo_busca_usd": round(self.custo_busca_usd, 8),
            "custo_total_usd": round(self.custo_total_usd, 8), "latencia_s": round(self.latencia_s, 4),
        }


class Agente(Protocol):
    provedor: str
    modelo: str

    def responder(self, pergunta: str, pergunta_id: str = "") -> ResultadoAgente: ...
