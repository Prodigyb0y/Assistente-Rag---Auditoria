from src.analise.escalonamento import gerar_markdown, resumir


def _l(i, custo, lat, rota, status="aceita_no_primeiro", motivo=None, tent=1):
    return {"pergunta_id": f"Q{i:02d}", "custo_usd": custo, "latencia_s": lat, "rota": list(rota),
            "status": status, "motivo_escalonamento": motivo, "tentativas": tent}


def test_resumo_separa_com_e_sem_segundo_provedor():
    r = resumir([_l(1, 0.001, 2.0, ["a"]), _l(2, 0.005, 10.0, ["a", "o"], "divergencia", "confianca_baixa", 2)])
    assert r["com"] == 1 and r["custo_sem"] == 0.001 and r["custo_com"] == 0.005
    assert r["tentativas"] == 3 and r["motivos"]["nenhum"] == 1


def test_markdown_razao_entre_modos():
    ad = [(1, [_l(1, 0.001, 2.0, ["a"])])]
    co = [(1, [_l(1, 0.005, 6.0, ["a", "o"], "aceita_por_consenso", None, 2)])]
    md = gerar_markdown({"adaptativo": ad, "consenso": co})
    assert "5,0x" in md and "3,0x" in md and "Limites deste dado" in md
