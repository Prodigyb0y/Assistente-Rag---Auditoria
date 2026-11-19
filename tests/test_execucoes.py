from src.avaliacao.execucoes import gerar_markdown, resumir_execucao


def _l(i, acerto=True, custo=0.001, lat=2.0, rota=("anthropic",), status="aceita_no_primeiro"):
    return {"pergunta_id": f"Q{i:02d}", "acerto": acerto, "valido": True, "custo_usd": custo,
            "latencia_s": lat, "rota": list(rota), "status": status}


def test_resumo_basico():
    linhas = [_l(1), _l(2, acerto=False, custo=0.003, lat=4.0, rota=("anthropic", "openai"), status="divergencia")]
    r = resumir_execucao(linhas)
    assert (r["n"], r["acertos"], r["validas"]) == (2, 1, 2)
    assert r["custo_resp"] == 0.002 and r["lat_media"] == 3.0 and r["lat_max"] == 4.0
    assert r["dois_provedores"] == 1 and r["divergencias"] == ["Q02"]


def test_markdown_tem_linhas_e_media():
    md = gerar_markdown({"consenso": [(1, [_l(1)]), (2, [_l(1, custo=0.003)])]})
    assert "| consenso | 1 | 1/1 |" in md and "| consenso | 2 | 1/1 |" in md
    assert "Média entre execuções" in md and "0,002000" in md
