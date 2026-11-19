# POL-BKP — Política de Backup e Recuperação

> Documento FICTÍCIO da Gutenberg Systems, criado para fins de demonstração. Versão 1.2.

## BKP-1 Objetivo

Assegurar que os dados dos sistemas da Gutenberg Systems possam ser recuperados após falhas, erros ou incidentes.

## BKP-2 Frequência dos backups

São realizados backups completos semanais, aos domingos, e backups incrementais diários. Bancos de dados críticos têm backup de logs de transação a cada 15 minutos.

## BKP-3 Retenção

Backups diários são retidos por 35 dias, backups semanais por 12 meses e backups mensais por 5 anos. As cópias são mantidas em região geográfica distinta da produção.

## BKP-4 Testes de restauração

O teste de restauração de sistemas críticos é feito a cada trimestre e o dos demais sistemas a cada semestre. Os resultados são registrados com o tempo medido de restauração.

## BKP-5 Metas de recuperação

Para sistemas críticos, a meta é RPO de 15 minutos e RTO de 4 horas.
