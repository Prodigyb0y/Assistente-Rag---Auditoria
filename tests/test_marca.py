"""A marca fictícia é enfeite: os SVGs precisam ser seguros e a demo nunca pode falhar por causa deles."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.interface.marca import ICONE, css_marca, icone_data_uri

PASTA = Path(__file__).resolve().parents[1] / "docs" / "img" / "marca"
ARQUIVOS = ["icone.svg", "logo-horizontal.svg", "logo-simbolo-fluxo.svg", "poster.svg"]


@pytest.mark.parametrize("nome", ARQUIVOS)
def test_svgs_da_marca_sao_xml_valido_e_sem_script_nem_link_externo(nome):
    texto = (PASTA / nome).read_text(encoding="utf-8")
    raiz = ET.fromstring(texto)                                    # XML bem formado
    assert raiz.tag.endswith("svg")
    baixo = texto.lower()
    assert "<script" not in baixo and "foreignobject" not in baixo
    assert not re.search(r'(?:xlink:)?href\s*=\s*["\']https?:', baixo)    # nada carregado de fora


def test_icone_vira_data_uri_pequeno_sem_o_bloco_de_metadados():
    uri = icone_data_uri()
    assert uri is not None and uri.startswith("data:image/svg+xml;base64,")
    assert len(uri) < 2000                                         # sem os ~7 KB do manifesto C2PA
    assert "background: url(" in css_marca() and "#cabecalho h1::before" in css_marca()


def test_sem_o_arquivo_a_demo_segue_sem_marca(tmp_path):
    assert icone_data_uri(tmp_path / "nao-existe.svg") is None
    assert css_marca(tmp_path / "nao-existe.svg") == ""


def test_svg_suspeito_e_recusado(tmp_path):
    ruim = tmp_path / "x.svg"
    ruim.write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8")
    assert icone_data_uri(ruim) is None
    assert ICONE.exists()
