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

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY app/ /app/

RUN apt-get update

RUN pip install --no-cache-dir -r requirements.txt

ENV DATA_DIR=/data
EXPOSE 80

# Gunicorn: pronto pra produção
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:80", "app:app"]
