# Avaliação da recuperação (recall@k)

Gerado por script em 2026-11-19. Não editar à mão: rode `python -m src.recuperacao.avaliar`.

## Resultado

| k | acertos | total | recall@k |
|---|---|---|---|
| 1 | 28 | 30 | 0.933 |
| 3 | 30 | 30 | 1.000 |
| 5 | 30 | 30 | 1.000 |

## Método

- Base: 45 trechos de documentos fictícios da Gutenberg Systems, um trecho por seção (identificador de seção preservado). Hash do índice: `1a730d2fc794e29f`.
- Embeddings: modelo `text-embedding-3-small` (OpenAI). O texto embedado de cada trecho é o código do documento, o id da seção, o título e o corpo da seção.
- Consulta: as 30 perguntas do gabarito são embedadas com o mesmo modelo; similaridade de cosseno; ordem decrescente; empate pela ordem do índice.
- Acerto@k: a seção do gabarito (documento + id da seção) está entre os k primeiros trechos. recall@k = acertos ÷ total de perguntas.
- Gabarito: 30 perguntas escritas e revisadas no Bloco 1, antes de qualquer teste.

## Limitações

- Apenas 30 perguntas e uma base pequena e fictícia; não generaliza para bases reais.
- Mede só se a seção certa foi recuperada, não se a resposta final está correta.
- Perguntas e documentos foram escritos pelo mesmo processo, então compartilham vocabulário; isso tende a favorecer a recuperação.

## Perguntas em que a seção do gabarito ficou fora do top-3

Nenhuma.

## Custo desta avaliação

- Tokens de embedding das consultas: 549.
- Custo: US$ 0.000011 (tabela de preços de 2026-11-19).
