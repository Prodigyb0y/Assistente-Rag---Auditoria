import json
from pathlib import Path

import numpy as np
import pytest

from src.custo import TabelaPrecos
from src.ingestao.chunker import carregar_documentos
from src.ingestao.indexador import Indice, carregar_indice, ingerir
from src.recuperacao.avaliacao import avaliar, calcular_recall, gerar_relatorio_md, posicao_do_gabarito
from src.recuperacao.buscador import Buscador, Resultado
from tests.fakes import FakeEmbedder


class EmbedderFixo:
    """Mapeia texto -> vetor fixo, para controlar a ordem esperada do top-k."""
    modelo = "fixo"

    def __init__(self, mapa):
        self.mapa = mapa

    def embed(self, textos, proposito="x"):
        return np.asarray([self.mapa[t] for t in textos], dtype=np.float32), len(textos)


def _indice():
    chunks = [{"chunk_id": f"D/S{i}", "doc_id": "D", "secao_id": f"S{i}", "titulo": "t", "texto": "x", "hash": str(i)}
              for i in range(3)]
    m = np.array([[1, 0], [0.8, 0.6], [0, 1]], dtype=np.float32)
    return Indice(modelo="fixo", chunks=chunks, matriz=m)


def test_topk_ordenado_por_cosseno():
    b = Buscador(_indice(), EmbedderFixo({"q": [1, 0.1]}))
    res = b.buscar("q", k=3)
    assert [r.secao_id for r in res] == ["S0", "S1", "S2"]
    assert [r.posicao for r in res] == [1, 2, 3]
    assert res[0].score > res[1].score > res[2].score


def test_k_maior_que_indice_nao_quebra():
    b = Buscador(_indice(), EmbedderFixo({"q": [1, 0]}))
    assert len(b.buscar("q", k=10)) == 3


def test_modelo_diferente_do_indice_e_recusado():
    with pytest.raises(ValueError, match="Índice feito com"):
        Buscador(_indice(), FakeEmbedder("outro"))


def test_busca_em_lote_chama_o_embedder_uma_vez(tmp_path):
    emb = FakeEmbedder()
    chunks = carregar_documentos(Path("dados/documentos"))
    ingerir(chunks[:5], tmp_path / "idx", emb)
    b = Buscador(carregar_indice(tmp_path / "idx"), emb)
    antes = emb.chamadas
    b.buscar_lote(["a", "b", "c"], k=2)
    assert emb.chamadas == antes + 1


def _res(posicao, doc, secao):
    return Resultado(posicao, f"{doc}/{secao}", doc, secao, "t", "x", 0.5)


def test_posicao_do_gabarito_exige_documento_e_secao():
    r = [_res(1, "A", "S1"), _res(2, "B", "S1"), _res(3, "B", "S2")]
    assert posicao_do_gabarito(r, "B", "S1") == 2
    assert posicao_do_gabarito(r, "C", "S1") is None


def test_recall_calculado_na_mao():
    posicoes = [1, 2, 3, 4, None, 1, 7, 3, 2, None]  # 10 perguntas
    r = calcular_recall(posicoes, ks=(1, 3, 5))
    assert r[1]["acertos"] == 2 and r[1]["recall"] == pytest.approx(0.2)
    assert r[3]["acertos"] == 6 and r[3]["recall"] == pytest.approx(0.6)
    assert r[5]["acertos"] == 7 and r[5]["recall"] == pytest.approx(0.7)


def test_recall_sem_perguntas_levanta_erro():
    with pytest.raises(ValueError):
        calcular_recall([])


def test_pipeline_completo_roda_na_base_real_com_embedder_falso(tmp_path):
    """Só verifica que o pipeline roda e o relatório é gerado. NÃO afirma valor de recall."""
    emb = FakeEmbedder()
    ingerir(carregar_documentos(Path("dados/documentos")), tmp_path / "idx", emb)
    buscador = Buscador(carregar_indice(tmp_path / "idx"), emb)
    perguntas = json.loads(Path("dados/perguntas.json").read_text(encoding="utf-8"))
    tabela = TabelaPrecos.de_json("config/precos.json")
    # o modelo fake não está na tabela de preços; usa o preço do embedding só para testar o cálculo
    tabela._precos["fake-bow"] = tabela.get("text-embedding-3-small")
    r = avaliar(perguntas, buscador, tabela)
    assert r["n_perguntas"] == 30 and r["n_trechos_indice"] == 45
    assert set(r["recall"]) == {"1", "3", "5"}
    assert 0.0 <= r["recall"]["3"]["recall"] <= 1.0
    assert r["recall"]["1"]["recall"] <= r["recall"]["3"]["recall"] <= r["recall"]["5"]["recall"]
    md = gerar_relatorio_md(r)
    assert "## Método" in md and "recall@k" in md and "Não editar à mão" in md
