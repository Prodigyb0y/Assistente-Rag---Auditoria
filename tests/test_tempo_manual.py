from src.avaliacao import tempo_manual as tm

P = [{"id": f"Q{i:02d}", "pergunta": f"p{i}", "documento": "POL-ACE", "secao": "ACE-3"} for i in range(1, 31)]


def test_sorteio_reprodutivel_sem_repeticao_e_limitado():
    a, b = tm.sortear(P, 10), tm.sortear(P, 10)
    assert a == b and len({q["id"] for q in a}) == 10
    assert len(tm.sortear(P, 99)) == 30 and tm.sortear(P, 0) == []


def test_registrar_normaliza_e_confere_a_secao():
    ok = tm.registrar(P[0], 12.345, " pol-ace ", "ace-3")
    assert ok["acertou_secao"] is True and ok["segundos"] == 12.35 and ok["documento_informado"] == "POL-ACE"
    assert tm.registrar(P[0], 5, "POL-ACE", "ACE-4")["acertou_secao"] is False


def test_resumir():
    m = [{"segundos": s, "acertou_secao": a} for s, a in [(10, True), (20, True), (60, False)]]
    r = tm.resumir(m)
    assert r == {"n": 3, "acertos_secao": 2, "mediana_s": 20, "media_s": 30, "min_s": 10, "max_s": 60}
    assert tm.resumir([]) == {"n": 0}


def test_medir_grava_e_retoma_sem_repetir(tmp_path):
    arq = tmp_path / "t.json"
    tempos = iter([0, 7, 10, 25])           # duas perguntas: 7 s e 15 s
    respostas = iter(["", "", "POL-ACE", "ACE-3", "", "", "POL-ACE", "ACE-9"])
    med = tm.medir(2, arquivo=arq, perguntas=P, entrada=lambda _: next(respostas), saida=lambda _: None,
                   relogio=lambda: next(tempos))
    assert [m["segundos"] for m in med] == [7, 15] and [m["acertou_secao"] for m in med] == [True, False]
    chamadas = []
    tm.medir(2, arquivo=arq, perguntas=P, entrada=lambda p: chamadas.append(p) or "", saida=lambda _: None)
    assert chamadas == [] and len(tm.carregar(arq)) == 2        # já medidas: nada a perguntar


def test_texto_resumo_inclui_sistema_e_ressalva():
    m = [{"segundos": 30, "acertou_secao": True}]
    t = tm.texto_resumo(m, {"resumos": {"orquestrado": {"latencia_mediana_s": 2.5, "latencia_media_s": 2.86}}})
    assert "mediana 30" in t and "orquestrado" in t and "não é uma estatística" in t
    assert tm.texto_resumo([], None) == "Nenhuma medição registrada."
