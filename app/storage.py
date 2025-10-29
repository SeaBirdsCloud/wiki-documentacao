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

import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from markdown import markdown
from markupsafe import Markup
import uuid
from werkzeug.utils import secure_filename

import frontmatter
from slugify import slugify

# =========================
# Caminhos e constantes
# =========================
DATA_DIR = os.getenv("DATA_DIR", "/data")
DOCS_DIR = os.path.join(DATA_DIR, "docs")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")  # fallback legado
REPO_DIR = DATA_DIR  # versiona tudo em /data
TRASH_DIR = os.path.join(DATA_DIR, "trash")

FRONT_MATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
BRT = timezone(timedelta(hours=-3))

# =========================
# Infra: diretórios
# =========================
def ensure_dirs_and_repo():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(TRASH_DIR, exist_ok=True)
    if not os.path.exists(os.path.join(REPO_DIR)):
        Repo.init(REPO_DIR)

# =========================
# Helpers de caminho
# =========================
def _doc_dir(slug: str) -> str:
    """Diretório da doc nova: /data/docs/<slug>"""
    return os.path.join(DOCS_DIR, slug)


def _doc_md_path_new(slug: str) -> str:
    """Caminho novo do md: /data/docs/<slug>/doc.md"""
    return os.path.join(_doc_dir(slug), "doc.md")


def _doc_md_path_legacy(slug: str) -> str:
    """Caminho antigo do md: /data/docs/<slug>.md (compat)"""
    return os.path.join(DOCS_DIR, f"{slug}.md")


# =========================
# Leitura / Listagem
# =========================
def read_doc(slug):
    """
    Lê a doc como frontmatter.Post.
    Suporta:
      - /data/docs/<slug>/doc.md  (novo)
      - /data/docs/<slug>.md      (legado)
    Se encontrar apenas o legado e não existir o novo, migra automaticamente.
    """
    ensure_dirs_and_repo()
    slug = (slug or "").strip()  # não forçamos lower() para não conflitar com pasta já existente

    new_path = _doc_md_path_new(slug)
    legacy_path = _doc_md_path_legacy(slug)

    # Novo formato primeiro
    if os.path.exists(new_path):
        try:
            return frontmatter.load(new_path)
        except Exception as e:
            print(f"[read_doc] ERRO lendo novo '{new_path}': {e}")

    # Legado
    if os.path.exists(legacy_path):
        # Migra automaticamente para o novo formato
        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.copy2(legacy_path, new_path)
            return frontmatter.load(new_path)
        except Exception as e:
            print(f"[read_doc] ERRO migrando '{legacy_path}' -> '{new_path}': {e}")
            try:
                return frontmatter.load(legacy_path)
            except Exception as e2:
                print(f"[read_doc] ERRO lendo legado '{legacy_path}': {e2}")

    return None


def _safe_frontmatter_load(path: str):
    """
    Tenta carregar via python-frontmatter.
    Em caso de erro de parsing, tenta leitura bruta e cria um Post mínimo.
    """
    try:
        return frontmatter.load(path)
    except Exception as e:
        print(f"[list_docs] ERRO lendo '{path}': {e}")
        # fallback bem simples
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            post = frontmatter.Post("")
            # tenta extrair algo de título do front matter bruto
            m = FRONT_MATTER_RE.match(raw or "")
            title = None
            if m:
                fm = m.group(1)
                for line in fm.splitlines():
                    if line.lower().startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
            if not title:
                # primeira linha como fallback
                for line in (raw or "").splitlines():
                    line = line.strip()
                    if line and not line.startswith("---"):
                        title = line[2:].strip() if line.startswith("# ") else line
                        break
            post["title"] = title or os.path.basename(os.path.dirname(path)) or os.path.splitext(os.path.basename(path))[0]
            post["description"] = ""
            post["tags"] = []
            post["icon_url"] = ""
            post.content = ""
            return post
        except Exception as e2:
            print(f"[list_docs] FALHA no fallback de '{path}': {e2}")
            return None


def list_docs(query: str = "", tags: list[str] | None = None, nivel: str = "n1"):
    """
    Lista documentos percorrendo:
      - Novo formato: subpastas de /data/docs contendo doc.md
      - Antigo formato: arquivos /data/docs/<slug>.md

    Retorna lista de dicts (compatível com app.py):
      { "slug", "title", "description", "tags", "icon_url", "cover_url",
        "category", "created_by", "created_at", "last_edited_by", "last_edited_at" }

    Filtros:
      - query (titulo/descrição/tags/conteúdo)
      - tags (interseção)
    """
    ensure_dirs_and_repo()
    results = []

    q = (query or "").strip().lower()
    want_tags = set([t.strip().lower() for t in (tags or []) if t.strip()])

    # --- Novo formato: pastas com doc.md ---
    if os.path.isdir(DOCS_DIR):
        for slug in sorted(os.listdir(DOCS_DIR)):
            dir_path = _doc_dir(slug)
            md_path = _doc_md_path_new(slug)
            if not os.path.isdir(dir_path) or not os.path.exists(md_path):
                continue

            post = _safe_frontmatter_load(md_path)
            if not post:
                continue

            title = post.get("title", slug)
            description = post.get("description", "")
            category = post.get("category", "")
            ptags = post.get("tags", [])
            if isinstance(ptags, str):
                ptags = [ptags]
            ptags = [str(t).strip() for t in ptags if str(t).strip()]

            icon_url = post.get("icon_url") or f"/docs/{slug}/logo.png"
            cover_url = post.get("cover_url", "")

            created_by = post.get("created_by")
            created_at = post.get("created_at")
            last_edited_by = post.get("last_edited_by")
            last_edited_at = post.get("last_edited_at")

            # Filtro textual
            if q:
                hay = " ".join(
                    [
                        (title or ""),
                        (description or ""),
                        " ".join(ptags),
                        (post.content or ""),
                    ]
                ).lower()
                if q not in hay:
                    continue

            # Filtro por tags
            if want_tags:
                if not (set([t.lower() for t in ptags]) & want_tags):
                    continue

            # --- Gerar resumo formatado do body ---
            body_preview = ""
            if hasattr(post, "content") and post.content:
                # Converte markdown para HTML, preservando listas e quebras
                html = markdown(
                    post.content,
                    extensions=["fenced_code", "tables", "sane_lists", "nl2br"]
                )
                # Remove tags perigosas e limita tamanho
                clean = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
                clean = re.sub(r"(?is)<style.*?>.*?</style>", "", clean)
                body_preview = clean[:600] + ("..." if len(clean) > 600 else "")

            # Se não houver description no front matter, usa o corpo
            final_desc = (post.get("description", "") or "").strip() or body_preview

            results.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": description or Markup(final_desc),
                    "category": category,
                    "tags": ptags,
                    "icon_url": icon_url,
                    "cover_url": cover_url,
                    "created_by": created_by,
                    "created_at": created_at,
                    "last_edited_by": last_edited_by,
                    "last_edited_at": last_edited_at,
                    "body": post.content or "",
                }
            )

    # --- Formato legado: /data/docs/*.md (somente os que não estão no novo) ---
    if os.path.isdir(DOCS_DIR):
        for f in sorted(os.listdir(DOCS_DIR)):
            if not f.endswith(".md"):
                continue
            legacy_slug = f[:-3]
            if any(d["slug"] == legacy_slug for d in results):
                continue

            legacy_path = _doc_md_path_legacy(legacy_slug)
            post = _safe_frontmatter_load(legacy_path)
            if not post:
                continue

            title = post.get("title", legacy_slug)
            description = post.get("description", "")
            category = post.get("category", "")
            ptags = post.get("tags", [])
            if isinstance(ptags, str):
                ptags = [ptags]
            ptags = [str(t).strip() for t in ptags if str(t).strip()]
            icon_url = post.get("icon_url", "")
            cover_url = post.get("cover_url", "")

            created_by = post.get("created_by")
            created_at = post.get("created_at")
            last_edited_by = post.get("last_edited_by")
            last_edited_at = post.get("last_edited_at")

            if q:
                hay = " ".join(
                    [
                        (title or ""),
                        (description or ""),
                        " ".join(ptags),
                        (post.content or ""),
                    ]
                ).lower()
                if q not in hay:
                    continue

            if want_tags:
                if not (set([t.lower() for t in ptags]) & want_tags):
                    continue

            results.append(
                {
                    "slug": legacy_slug,
                    "title": title,
                    "description": description,
                    "category": category,
                    "tags": ptags,
                    "icon_url": icon_url,
                    "cover_url": cover_url,
                    "created_by": created_by,
                    "created_at": created_at,
                    "last_edited_by": last_edited_by,
                    "last_edited_at": last_edited_at,
                }
            )

    return results


# =========================
# Escrita / Upload / Delete
# =========================
def save_doc(
    title: str,
    body,
    author_name: str,
    author_email: str,
    slug: str | None = None,
    icon_url: str | None = None,
    description: str | None = None,
    tags: str | list[str] | None = None,
    category: str | None = None,
    cover_url: str | None = None,
    access_level: str | None = None,
):
    """
    Cria/atualiza a doc no NOVO formato: /data/docs/<slug>/doc.md
    - Mantém compatibilidade ao ler docs antigas (migra ao salvar/ler).
    - Normaliza body para str.
    - Atualiza front matter com description, icon_url, cover_url, category e tags.
    """
    ensure_dirs_and_repo()
    if not slug:
        slug = slugify(title or "documento")

    doc_dir = _doc_dir(slug)
    md_path_new = _doc_md_path_new(slug)
    os.makedirs(doc_dir, exist_ok=True)

    now = datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S %Z")

    # body -> str
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    else:
        body = str(body or "")

    # tags -> lista
    if isinstance(tags, str):
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, (list, tuple, set)):
        tags_list = [str(t).strip() for t in tags if str(t).strip()]
    else:
        tags_list = None

    legacy_path = _doc_md_path_legacy(slug)
    if os.path.exists(md_path_new):
        post = frontmatter.load(md_path_new)
        action = "update"
    elif os.path.exists(legacy_path):
        post = frontmatter.load(legacy_path)
        action = "migrate"
    else:
        post = frontmatter.Post("")
        action = "create"

    # Metadados
    if access_level is not None:
        post["access_level"] = access_level
    elif "access_level" not in post:
        post["access_level"] = "d1"  # padrão se não existir ainda
    post["title"] = title or post.get("title", slug)
    post["last_edited_at"] = now
    post["last_edited_by"] = author_name
    if "created_at" not in post:
        post["created_at"] = now
    if "created_by" not in post:
        post["created_by"] = author_name

    if description is not None:
        post["description"] = description
    elif not post.get("description"):
        # se não havia descrição, cria uma automática do início do corpo
        post["description"] = body.strip()[:300]
    if icon_url is not None:
        post["icon_url"] = icon_url
    if cover_url is not None:
        post["cover_url"] = cover_url
    if category is not None:
        post["category"] = category
    if tags_list is not None:
        post["tags"] = tags_list

    post.content = body

    content = frontmatter.dumps(post)
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="ignore")

    with open(md_path_new, "w", encoding="utf-8") as f:
        f.write(content)

    return slug

def upload_file(file_storage, slug: str, filename_override: str | None = None, title: str | None = None) -> str:
    """
    Salva arquivo dentro de /data/docs/<title>/<filename>
    Retorna: /docs/<title>/<filename>
    """
    ensure_dirs_and_repo()

    # Define base_dir e base_url de forma simples e direta
    base_name = slugify(title) if title else slug
    if not base_name:
        raise ValueError("É necessário informar o slug ou o título do documento.")

    base_dir = os.path.join(DOCS_DIR, base_name)
    base_url = f"/docs/{base_name}"
    os.makedirs(base_dir, exist_ok=True)

    # Define o nome final com mínimo de I/O
    if filename_override:
        filename = filename_override
    else:
        orig = secure_filename(file_storage.filename or "file")
        name, ext = os.path.splitext(orig)
        ext = ext.lower() or ""
        safe_name = slugify(name) or "file"

        # Evita loop e checagens no disco — usa UUID curto
        unique_suffix = uuid.uuid4().hex[:6]
        filename = f"{safe_name}-{unique_suffix}{ext}"

    # Caminho final
    final_path = os.path.join(base_dir, filename)

    # Salva direto (streamed)
    file_storage.save(final_path)

    return f"{base_url}/{filename}"

def delete_file(slug: str, filename: str, author_name="System", author_email="system@local") -> bool:
    """
    Exclui um arquivo específico dentro da pasta da doc.
    """
    path = os.path.join(_doc_dir(slug), filename)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

def delete_doc(slug: str, author_name="System", author_email="system@local") -> bool:
    """
    Move a documentação para a lixeira em vez de apagar imediatamente.
    Após 7 dias, um job pode limpá-la de forma permanente.
    """
    ensure_dirs_and_repo()
    doc_dir = _doc_dir(slug)
    legacy_path = _doc_md_path_legacy(slug)

    # Novo formato
    if os.path.isdir(doc_dir):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        trash_name = f"{slug}_{timestamp}"
        trash_path = os.path.join(TRASH_DIR, trash_name)
        shutil.move(doc_dir, trash_path)
        return True

    # Legado
    if os.path.exists(legacy_path):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        trash_name = f"{slug}_{timestamp}.md"
        shutil.move(legacy_path, os.path.join(TRASH_DIR, trash_name))
        return True

    return False

def clean_trash(older_than_days: int = 7):
    """
    Remove permanentemente documentos da lixeira mais antigos que `older_than_days`.
    Pode ser chamado manualmente ou via cron.
    """
    ensure_dirs_and_repo()
    now = datetime.utcnow()
    removed = []

    if not os.path.isdir(TRASH_DIR):
        return removed

    for name in os.listdir(TRASH_DIR):
        path = os.path.join(TRASH_DIR, name)
        if not os.path.exists(path):
            continue

        mtime = datetime.utcfromtimestamp(os.path.getmtime(path))
        age_days = (now - mtime).days
        if age_days >= older_than_days:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                removed.append(name)
            except Exception as e:
                print(f"[clean_trash] Falha ao remover {name}: {e}")

    return removed

# =========================
# Compat: extração de título (fallback)
# =========================
def extract_title(content: str) -> str | None:
    """
    Usado apenas para compat/listagem legada.
    No novo formato, o título vem do front matter do doc.md.
    """
    m = FRONT_MATTER_RE.match(content or "")
    if m:
        fm = m.group(1)
        for line in fm.splitlines():
            if line.lower().startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    for line in (content or "").splitlines():
        line = line.strip()
        if line and not line.startswith("---"):
            if line.startswith("# "):
                return line[2:].strip()
            return line
    return None
