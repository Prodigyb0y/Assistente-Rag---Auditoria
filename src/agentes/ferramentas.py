"""Ferramenta de busca exposta aos agentes (tool calling).

Em vez de colocar a base inteira no prompt, o modelo chama `buscar_trechos(consulta)` e recebe só
os top-k trechos. A ferramenta registra quais trechos foram devolvidos: é contra esse conjunto que
as citações do agente são validadas. Também contabiliza tokens e custo dos embeddings de consulta.
"""
from __future__ import annotations

import json

from ..custo import TabelaPrecos
from ..recuperacao.buscador import Buscador
from .contrato import K_BUSCA

MAX_CHARS_CONSULTA = 500


class FerramentaBusca:
    def __init__(self, buscador: Buscador, tabela: TabelaPrecos, k: int = K_BUSCA):
        self.buscador = buscador
        self.tabela = tabela
        self.k = k
        self.consultas: list[str] = []
        self.recuperados: set[tuple[str, str]] = set()
        self.ordem_recuperados: list[str] = []
        self.tokens_embedding = 0
        self.custo_usd = 0.0

    def executar(self, consulta: object) -> str:
        """Devolve sempre uma string JSON (o resultado da ferramenta para o modelo)."""
        if not isinstance(consulta, str) or not consulta.strip():
            return json.dumps({"erro": "consulta vazia ou inválida"}, ensure_ascii=False)
        consulta = consulta.strip()[:MAX_CHARS_CONSULTA]
        antes = self.buscador.tokens_consulta
        resultados = self.buscador.buscar(consulta, k=self.k)
        gastos = self.buscador.tokens_consulta - antes
        self.tokens_embedding += gastos
        self.custo_usd += self.tabela.get(self.buscador.embedder.modelo).custo(gastos, 0)
        self.consultas.append(consulta)
        trechos = []
        for r in resultados:
            par = (r.doc_id, r.secao_id)
            if par not in self.recuperados:
                self.recuperados.add(par)
                self.ordem_recuperados.append(r.chunk_id)
            trechos.append({"documento": r.doc_id, "secao": r.secao_id, "titulo": r.titulo, "texto": r.texto})
        return json.dumps({"trechos": trechos}, ensure_ascii=False)
