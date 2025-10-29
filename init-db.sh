#!/bin/bash

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

set -e

echo "Gerando script SQL com variáveis de ambiente..."
envsubst < /docker-entrypoint-initdb.d/banco.sql.template > /docker-entrypoint-initdb.d/banco.sql

echo "Iniciando MySQL..."
exec docker-entrypoint.sh mysqld
