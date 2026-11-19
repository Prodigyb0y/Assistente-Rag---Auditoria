from src.interface.sobre import REPO, texto_sobre


def test_texto_sobre_explica_o_que_faz_por_que_existe_e_os_limites():
    t = texto_sobre(5)
    for trecho in ("O que este assistente faz", "Por que ele existe", "O que ele não faz", "fictícia",
                   "Não é decisão, parecer ou conclusão de auditoria", "Não tem memória"):
        assert trecho in t
    assert "5 perguntas por visitante por dia" in t and REPO in t


def test_texto_sobre_usa_o_limite_configurado():
    assert "12 perguntas por visitante por dia" in texto_sobre(12)


def test_texto_sobre_descreve_o_cenario_do_portal_como_premissa():
    t = texto_sobre(5)
    assert "código ou título da norma" in t and "premissa do cenário fictício" in t and "não uma\nmedição de tempo" in t


def test_tabela_ilustrativa_e_rotulada_como_premissa():
    from src.interface.sobre import tabela_ilustrativa
    tab = tabela_ilustrativa(2.86, (2, 5, 10))
    assert "| 5 min | 2.9 s | cerca de 4 min 57 s |" in tab and "| 2 min | 2.9 s | cerca de 1 min 57 s |" in tab
    assert "| 10 min | 2.9 s | cerca de 9 min 57 s |" in tab
    t = texto_sobre(5)
    assert "premissa, não medida" in t and "não\nfoi medido" in t and tab in t
