import json
from pathlib import Path

import pytest

from src.agentes.contrato import (SCHEMA_BUSCA, SCHEMA_RESPOSTA, RespostaAuditoria, interpretar_saida)
from src.agentes.prompts import carregar_prompt

RECUP = {("POL-ACE", "ACE-3"), ("POL-ACE", "ACE-4")}


def _json(**sobre):
    base = {"resposta": "A cada 90 dias.", "encontrado": True,
            "citacoes": [{"documento": "POL-ACE", "secao": "ACE-3"}], "confianca": "alta"}
    base.update(sobre)
    return json.dumps(base)


def test_schema_manual_bate_com_modelo_pydantic():
    gerado = RespostaAuditoria.model_json_schema()
    assert set(SCHEMA_RESPOSTA["properties"]) == set(gerado["properties"])
    assert set(SCHEMA_RESPOSTA["required"]) == set(gerado["required"])
    assert SCHEMA_RESPOSTA["additionalProperties"] is False
    assert SCHEMA_RESPOSTA["properties"]["confianca"]["enum"] == ["alta", "media", "baixa"]


def test_schemas_sao_compativeis_com_modo_estrito():
    # modo estrito: todo objeto com additionalProperties=false e todas as propriedades em required
    def objetos(s):
        if isinstance(s, dict):
            if s.get("type") == "object":
                yield s
            for v in s.values():
                yield from objetos(v)
        elif isinstance(s, list):
            for v in s:
                yield from objetos(v)

    for schema in (SCHEMA_RESPOSTA, SCHEMA_BUSCA):
        for obj in objetos(schema):
            assert obj["additionalProperties"] is False
            assert set(obj["required"]) == set(obj["properties"])
        assert "$ref" not in json.dumps(schema)


def test_saida_valida():
    i = interpretar_saida(_json(), RECUP)
    assert (i.schema_ok, i.citacoes_ok, i.erro) == (True, True, None)
    assert i.resposta.confianca == "alta"


def test_json_invalido():
    i = interpretar_saida("não sou json", RECUP)
    assert not i.schema_ok and "JSON" in i.erro


@pytest.mark.parametrize("sobre", [
    {"confianca": "certa"},          # fora do enum
    {"resposta": ""},                # vazia
    {"citacoes": [{"documento": "POL-ACE"}]},  # falta secao
    {"extra": 1},                    # campo extra
])
def test_fora_do_schema(sobre):
    i = interpretar_saida(_json(**sobre), RECUP)
    assert not i.schema_ok and i.resposta is None and "schema" in i.erro


def test_campo_obrigatorio_ausente():
    bruto = json.loads(_json())
    del bruto["encontrado"]
    assert not interpretar_saida(json.dumps(bruto), RECUP).schema_ok


def test_citacao_fora_dos_trechos_recuperados():
    i = interpretar_saida(_json(citacoes=[{"documento": "POL-CPG", "secao": "CPG-2"}]), RECUP)
    assert i.schema_ok and not i.citacoes_ok and "POL-CPG/CPG-2" in i.erro


def test_encontrado_sem_citacao_e_invalido():
    i = interpretar_saida(_json(citacoes=[]), RECUP)
    assert i.schema_ok and not i.citacoes_ok


def test_nao_encontrado_sem_citacao_e_valido():
    i = interpretar_saida(_json(encontrado=False, citacoes=[], confianca="baixa", resposta="Não consta."), RECUP)
    assert i.schema_ok and i.citacoes_ok


def test_prompt_versionado():
    p = carregar_prompt("agente_resposta", "v1", Path("prompts"))
    assert p.versao == "agente_resposta_v1" and len(p.sha) == 12
    assert "buscar_trechos" in p.texto and "decisão de auditoria" in p.texto
    with pytest.raises(FileNotFoundError):
        carregar_prompt("agente_resposta", "v99", Path("prompts"))
