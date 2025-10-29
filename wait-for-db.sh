#!/bin/sh

##############################################################
# Desenvolvido por: Lucas Perdigão de Oliveira
# Data: 29-10-2025
#
# Descrição:
# Wiki para criação e gerenciamento de documentações, com suporte à:
#  - Adição e gerenciamento de usuários e suas hierarquias
#  - Criação e organização de hierarquias de documentações
#  - Adição, edição e exclusão de documentações
#  - Retenção automática de documentações excluídas por até 7 dias
#
##############################################################

echo "Aguardando MySQL iniciar..."
until nc -z "$DB_HOST" 3306; do
  sleep 2
  echo "$DB_HOST"
done
echo "MySQL está pronto — iniciando aplicação Flask."
exec "$@"
