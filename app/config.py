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

from dotenv import load_dotenv
import os

# Caminho absoluto ou relativo para o .env
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)

class Config:
    DB_HOST = os.getenv("DB_HOST")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_NAME = os.getenv("DB_NAME")
    SECRET_KEY = os.getenv("SECRET_KEY")
    ADMIN_USER = os.getenv("ADMIN_USER")
    ADMIN_PASS = os.getenv("ADMIN_PASS")
    DATA_DIR = os.getenv("DATA_DIR", "/data")

    # Define caminhos derivados
    DOCS_DIR = os.path.join(DATA_DIR, "docs")
    UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
