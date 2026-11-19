# POL-LOG — Política de Registro e Retenção de Logs

> Documento FICTÍCIO da Gutenberg Systems, criado para fins de demonstração. Versão 2.2.

## LOG-1 Objetivo

Garantir que eventos relevantes de segurança sejam registrados, protegidos e revisados.

## LOG-2 Eventos registrados

Devem ser registrados autenticações (sucesso e falha), alterações de permissão, acessos a dados confidenciais e ações de contas privilegiadas.

## LOG-3 Retenção

Logs de segurança são retidos por 13 meses, sendo 90 dias em armazenamento de consulta rápida. Logs de contas privilegiadas são retidos por 24 meses.

## LOG-4 Proteção dos logs

Logs são gravados em repositório central com acesso somente leitura para os administradores dos sistemas de origem. A sincronização dos relógios usa uma fonte de tempo única.

## LOG-5 Alertas e revisão

Alertas de 5 ou mais falhas de autenticação consecutivas em 10 minutos geram chamado automático para o time de segurança, que o analisa em até 1 dia útil.
