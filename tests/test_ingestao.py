import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.config import carregar_settings
from src.custo import ControleCusto, OrcamentoExcedido, TabelaPrecos
from src.ingestao.chunker import carregar_documentos, dividir_documento
from src.ingestao.embeddings import OpenAIEmbedder
from src.ingestao.indexador import carregar_indice, ingerir
from tests.fakes import FakeEmbedder

DOCS = Path("dados/documentos")
PERGUNTAS = Path("dados/perguntas.json")

DOC_EXEMPLO = """# POL-XYZ — Política de Exemplo

> aviso

## XYZ-1 Primeira seção

Texto da primeira seção.

## XYZ-2 Segunda seção

Texto da segunda seção,
em duas linhas.
"""


def test_chunker_preserva_id_de_secao():
    chunks = dividir_documento(DOC_EXEMPLO)
    assert [c.chunk_id for c in chunks] == ["POL-XYZ/XYZ-1", "POL-XYZ/XYZ-2"]
    assert chunks[1].texto == "Texto da segunda seção, em duas linhas."
    assert chunks[0].titulo == "Primeira seção"


def test_chunker_rejeita_documento_sem_secao():
    with pytest.raises(ValueError):
        dividir_documento("# POL-XYZ — sem seções\n\ntexto")


def test_base_real_tem_45_trechos_e_cobre_todo_o_gabarito():
    chunks = carregar_documentos(DOCS)
    assert len(chunks) == 45
    ids = {c.chunk_id for c in chunks}
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    faltando = [q["id"] for q in perguntas if f'{q["documento"]}/{q["secao"]}' not in ids]
    assert faltando == []


def test_ingestao_idempotente(tmp_path):
    chunks = dividir_documento(DOC_EXEMPLO)
    emb = FakeEmbedder()
    r1 = ingerir(chunks, tmp_path / "idx", emb)
    assert (r1.novos, r1.reaproveitados, r1.removidos) == (2, 0, 0)
    assert emb.chamadas == 1
    r2 = ingerir(chunks, tmp_path / "idx", emb)
    assert (r2.novos, r2.reaproveitados, r2.removidos) == (0, 2, 0)
    assert emb.chamadas == 1  # nenhuma chamada nova à API


def test_reingestao_so_embeda_o_que_mudou(tmp_path):
    emb = FakeEmbedder()
    ingerir(dividir_documento(DOC_EXEMPLO), tmp_path / "idx", emb)
    alterado = DOC_EXEMPLO.replace("Texto da primeira seção.", "Texto novo e diferente.")
    r = ingerir(dividir_documento(alterado), tmp_path / "idx", emb)
    assert (r.novos, r.reaproveitados, r.removidos) == (1, 1, 1)
    assert emb.textos_embedados[-1].endswith("Texto novo e diferente.")


def test_secao_removida_sai_do_indice(tmp_path):
    emb = FakeEmbedder()
    chunks = dividir_documento(DOC_EXEMPLO)
    ingerir(chunks, tmp_path / "idx", emb)
    r = ingerir(chunks[:1], tmp_path / "idx", emb)
    assert r.removidos == 1 and r.total == 1
    assert len(carregar_indice(tmp_path / "idx").chunks) == 1


def test_trocar_modelo_reembeda_tudo(tmp_path):
    chunks = dividir_documento(DOC_EXEMPLO)
    ingerir(chunks, tmp_path / "idx", FakeEmbedder("modelo-a"))
    r = ingerir(chunks, tmp_path / "idx", FakeEmbedder("modelo-b"))
    assert r.novos == 2 and r.reaproveitados == 0


def test_indice_salvo_e_carregado_igual(tmp_path):
    chunks = dividir_documento(DOC_EXEMPLO)
    ingerir(chunks, tmp_path / "idx", FakeEmbedder())
    idx = carregar_indice(tmp_path / "idx")
    assert idx.modelo == "fake-bow" and idx.matriz.shape == (2, 256)
    assert np.allclose(np.linalg.norm(idx.matriz, axis=1), 1.0, atol=1e-5)  # normalizado
    assert [c["chunk_id"] for c in idx.chunks] == ["POL-XYZ/XYZ-1", "POL-XYZ/XYZ-2"]


def test_indice_ausente_da_erro_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="ingestão"):
        carregar_indice(tmp_path / "nao-existe")


# --- embedder da OpenAI com cliente falso ---------------------------------------------------

class _ClienteEmbFalso:
    def __init__(self):
        self.chamadas = 0
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, *, model, input, encoding_format):
        self.chamadas += 1
        assert encoding_format == "float"
        # devolve fora de ordem de propósito: o embedder deve reordenar por `index`
        dados = [SimpleNamespace(index=i, embedding=[float(i), 1.0]) for i in range(len(input))]
        return SimpleNamespace(data=list(reversed(dados)), usage=SimpleNamespace(prompt_tokens=7 * len(input)))


@pytest.fixture
def controle(tmp_path):
    s = carregar_settings(env={}, usar_dotenv=False)
    return s, ControleCusto(TabelaPrecos.de_json("config/precos.json"), s.orcamentos(), tmp_path / "c.jsonl")


def test_embedder_reordena_em_lotes_e_registra_tokens(controle, tmp_path):
    s, c = controle
    cli = _ClienteEmbFalso()
    emb = OpenAIEmbedder(s, c, client=cli, lote=2)
    m, tokens = emb.embed(["a", "b", "c"])
    assert cli.chamadas == 2 and tokens == 7 * 3
    assert m[:, 0].tolist() == [0.0, 1.0, 0.0]  # ordem correta dentro de cada lote
    regs = [json.loads(l) for l in (tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["tokens_in"] for r in regs] == [14, 7] and all(r["tokens_out"] == 0 for r in regs)


def test_embedder_respeita_teto(tmp_path):
    s = carregar_settings(env={"BUDGET_OPENAI_USD": "0.000000001"}, usar_dotenv=False)
    c = ControleCusto(TabelaPrecos.de_json("config/precos.json"), s.orcamentos(), tmp_path / "c.jsonl")
    cli = _ClienteEmbFalso()
    with pytest.raises(OrcamentoExcedido):
        OpenAIEmbedder(s, c, client=cli).embed(["texto " * 100])
    assert cli.chamadas == 0
