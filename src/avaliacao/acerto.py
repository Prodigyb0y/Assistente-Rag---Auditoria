"""Regra de acerto, determinística e auditável.

Uma resposta conta como CORRETA se, ao mesmo tempo:
  1. o agente respondeu (resposta presente e encontrado=true); e
  2. o texto contém todos os fatos-chave da pergunta (dados/fatos_chave.json), comparados sem acento
     e sem diferença de maiúsculas, em palavra inteira ("1 hora" não casa com "21 horas").

LIMITES (declarados no relatório): a regra confere a PRESENÇA dos fatos esperados, não a AUSÊNCIA de
fatos errados, e não entende negação nem paráfrase fora das alternativas listadas. Por isso o
relatório lista as respostas reprovadas e aprovadas para auditoria, e dados/acerto_manual.json
permite sobrescrever um veredito (cada sobrescrita é contada e aparece no relatório).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Mapping

from ..agentes.contrato import RespostaAuditoria

Fatos = list[list[str]]


def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower().replace(" ", " ")).strip()


def contem(texto_norm: str, alternativa: str) -> bool:
    padrao = r"(?<!\w)" + re.escape(normalizar(alternativa)) + r"(?!\w)"
    return re.search(padrao, texto_norm) is not None


def avaliar_acerto(resposta: RespostaAuditoria | None, fatos: Fatos) -> bool:
    if resposta is None or not resposta.encontrado:
        return False
    texto = normalizar(resposta.resposta)
    return all(any(contem(texto, alt) for alt in grupo) for grupo in fatos)


def cita_origem(resposta: RespostaAuditoria | None, documento: str, secao: str) -> bool:
    """A seção do gabarito está entre as citadas (métrica complementar à 'citação válida')."""
    return bool(resposta) and any(c.documento == documento and c.secao == secao for c in resposta.citacoes)


def carregar_fatos(caminho: Path) -> dict[str, Fatos]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))["fatos"]


def carregar_manual(caminho: Path) -> Mapping[str, bool]:
    """{"<modo>:<id>": true|false}. Arquivo opcional."""
    p = Path(caminho)
    if not p.exists():
        return {}
    bruto = json.loads(p.read_text(encoding="utf-8"))
    return {k: bool(v) for k, v in bruto.items() if not k.startswith("_")}
