# Cobertura da base pelas perguntas de teste (gerada por script)

> Gerado por `python -m src.analise.cobertura`. Análise descritiva, sem IA: compara as seções dos documentos com as seções que cada pergunta usa como fonte.

- Seções na base: 45 em 9 documentos.
- Usadas como fonte pelas 30 perguntas do gabarito (`dados/perguntas.json`): 26 de 45.
- Usadas pelo gabarito e pelas 10 perguntas de orquestração (`dados/perguntas_orquestracao.json`, gabarito ainda não revisado): 28 de 45.

| Documento | Seções | Sem pergunta (só o gabarito de 30) | Sem pergunta (gabarito + orquestração) |
|---|---|---|---|
| POL-ACE | 5 | ACE-1, ACE-2 | ACE-2 |
| POL-BKP | 5 | BKP-1, BKP-4 | BKP-1, BKP-4 |
| POL-CPG | 5 | CPG-1, CPG-5 | CPG-1, CPG-5 |
| POL-DAD | 5 | DAD-1, DAD-2, DAD-4 | DAD-1, DAD-2, DAD-4 |
| POL-FOR | 5 | FOR-1, FOR-5 | FOR-1, FOR-5 |
| POL-GMU | 5 | GMU-1 | GMU-1 |
| POL-INC | 5 | INC-1, INC-2 | INC-1 |
| POL-LOG | 5 | LOG-1, LOG-2, LOG-4 | LOG-1, LOG-2, LOG-4 |
| POL-SFU | 5 | SFU-1, SFU-2 | SFU-1, SFU-2 |

Leitura: seção sem pergunta é parte da base que a avaliação nunca exercita. Não significa que a seção seja menos importante.
