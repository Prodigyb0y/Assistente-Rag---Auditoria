"""Cobertura da base pelas perguntas: lógica e consistência com os dados reais do repositório."""
import json

from src.analise import cobertura


def test_calcula_as_secoes_sem_pergunta():
    base = {"POL-A": ["A-1", "A-2", "A-3"], "POL-B": ["B-1"]}
    usadas = {("POL-A", "A-2")}
    assert cobertura.calcular(base, usadas) == {"POL-A": ["A-1", "A-3"], "POL-B": ["B-1"]}


def test_le_os_dois_formatos_de_pergunta(tmp_path):
    g = tmp_path / "g.json"
    g.write_text(json.dumps([{"documento": "POL-A", "secao": "A-1"}]), encoding="utf-8")
    o = tmp_path / "o.json"
    o.write_text(json.dumps([{"fontes": [{"documento": "POL-B", "secao": "B-1"}]}]), encoding="utf-8")
    assert cobertura.secoes_citadas(g) == {("POL-A", "A-1")} and cobertura.secoes_citadas(o) == {("POL-B", "B-1")}
    assert cobertura.secoes_citadas(tmp_path / "nao_existe.json") == set()


def test_base_real_tem_45_secoes_e_o_gabarito_usa_26():
    base = cobertura.secoes_da_base()
    assert sum(len(v) for v in base.values()) == 45
    assert len(cobertura.secoes_citadas(cobertura.GABARITO)) == 26


def test_relatorio_lista_os_documentos_e_o_limite_da_leitura():
    base = cobertura.secoes_da_base()
    md = cobertura.gerar_markdown(base, cobertura.secoes_citadas(cobertura.GABARITO),
                                  cobertura.secoes_citadas(cobertura.GABARITO))
    assert "POL-ACE" in md and "sem IA" in md and "26 de 45" in md and "Não significa" in md
