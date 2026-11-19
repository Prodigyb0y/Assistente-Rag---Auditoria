"""Fakes para testes offline.

FakeEmbedder: vetores determinísticos por 'saco de palavras' com hash. Serve só para testar a lógica
do pipeline; NÃO representa a qualidade do modelo real, e nenhum número obtido com ele vale como
métrica do projeto.

OpenAIRoteirizado / AnthropicRoteirizado: clientes que devolvem respostas pré-definidas e guardam
os pedidos recebidos, para verificar o que o agente enviou.
"""
import copy
import json
import re
import zlib
from types import SimpleNamespace

import numpy as np


class FakeEmbedder:
    def __init__(self, modelo: str = "fake-bow", dim: int = 256):
        self.modelo = modelo
        self.dim = dim
        self.chamadas = 0
        self.textos_embedados: list[str] = []

    def embed(self, textos, proposito="embedding"):
        self.chamadas += 1
        self.textos_embedados.extend(textos)
        m = np.zeros((len(textos), self.dim), dtype=np.float32)
        for i, t in enumerate(textos):
            for palavra in re.findall(r"\w+", t.lower()):
                m[i, zlib.crc32(palavra.encode()) % self.dim] += 1.0
        return m, sum(len(t.split()) for t in textos)


# --- OpenAI (Responses API) ---------------------------------------------------------------

def openai_resp(*, id, chamadas=(), texto="", tin=100, tout=20, status="completed"):
    """chamadas: lista de (call_id, dict_de_argumentos)."""
    itens = [SimpleNamespace(type="function_call", name="buscar_trechos", call_id=cid, arguments=json.dumps(args))
             for cid, args in chamadas]
    return SimpleNamespace(id=id, output=itens, output_text=texto, status=status,
                           usage=SimpleNamespace(input_tokens=tin, output_tokens=tout))


class OpenAIRoteirizado:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.pedidos.append(copy.copy(kw))
        return self.respostas.pop(0)


# --- Anthropic (Messages API) -------------------------------------------------------------

def anthropic_msg(*, stop_reason, blocos, tin=100, tout=20):
    """blocos: lista de ('tool_use', id, dict_input) ou ('text', texto)."""
    conteudo = []
    for b in blocos:
        if b[0] == "tool_use":
            conteudo.append(SimpleNamespace(type="tool_use", id=b[1], name="buscar_trechos", input=b[2]))
        else:
            conteudo.append(SimpleNamespace(type="text", text=b[1]))
    return SimpleNamespace(stop_reason=stop_reason, content=conteudo,
                           usage=SimpleNamespace(input_tokens=tin, output_tokens=tout))


class AnthropicRoteirizado:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        kw = dict(kw)
        kw["messages"] = list(kw["messages"])  # foto da conversa neste instante
        self.pedidos.append(kw)
        return self.respostas.pop(0)
