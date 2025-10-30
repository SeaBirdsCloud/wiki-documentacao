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
import time
import json
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from markdown import markdown
from pygments.formatters import HtmlFormatter
from functools import wraps
import shutil
from pathlib import Path
from slugify import slugify
from config import Config
from storage import ensure_dirs_and_repo, list_docs, read_doc, save_doc, delete_doc, upload_file, DOCS_DIR
from datetime import datetime

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = Config.SECRET_KEY

# Use Config.* em todo o código:
DB_HOST = Config.DB_HOST
DB_USER = Config.DB_USER
DB_PASS = Config.DB_PASS
DB_NAME = Config.DB_NAME
ADMIN_USER = Config.ADMIN_USER
ADMIN_PASS = Config.ADMIN_PASS
DATA_DIR = Config.DATA_DIR
UPLOADS_DIR = Config.UPLOADS_DIR

# =========================
# MySQL: conexão & bootstrap
# =========================
def connect_mysql(db_required: bool = True):
    """
    Conecta no MySQL. Se db_required=False, conecta sem selecionar database (útil p/ criar DB).
    Retorna conexão aberta.
    """
    kwargs = dict(host=DB_HOST, user=DB_USER, password=DB_PASS, autocommit=False)
    if db_required:
        kwargs["database"] = DB_NAME
    return mysql.connector.connect(**kwargs)


def wait_mysql():
    """Espera o MySQL responder para evitar race ao subir com docker-compose."""
    for i in range(30):
        try:
            cnx = connect_mysql(db_required=False)
            cnx.close()
            return
        except mysql.connector.Error:
            print("⏳ Aguardando MySQL iniciar...")
            time.sleep(2)
    raise Exception("❌ Não foi possível conectar ao MySQL (timeout).")


def ensure_database():
    """
    Garante que o database exista.
    Observação: o usuário precisa ter permissão de CREATE DATABASE.
    Em setups padrão do MySQL oficial com MYSQL_USER/MYSQL_DATABASE isso não é necessário
    (o DB nasce junto com o container). Mas deixo aqui para cenários onde o volume já existia.
    """
    try:
        cnx = connect_mysql(db_required=False)
        cur = cnx.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cnx.commit()
    finally:
        try:
            cur.close()
            cnx.close()
        except Exception:
            pass


def ensure_tables_and_seed():
    """
    Cria as tabelas necessárias e faz seed do usuário admin, se não existir.
    """
    cnx = connect_mysql(db_required=True)
    cur = cnx.cursor()

    # Tabela de usuários
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(150) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            nivel ENUM('n1','n2','n3') DEFAULT 'n1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )


    # Seed do admin
    cur.execute("SELECT id FROM usuarios WHERE username=%s LIMIT 1;", (ADMIN_USER,))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO usuarios (username, password_hash, nivel) VALUES (%s, %s, 'n3');",
            (ADMIN_USER, generate_password_hash(ADMIN_PASS))
        )
        print(f"👑 Usuário admin criado: {ADMIN_USER}")

    cnx.commit()
    cur.close()
    cnx.close()


# Orquestra o bootstrap do banco
wait_mysql()
# Se o container mysql acabou de iniciar a primeira vez, o DB já existe por causa do compose.
# Se o volume foi recriado/limpo, a linha abaixo garante o DB:
ensure_database()
# Cria tabelas e faz seed
ensure_tables_and_seed()


# =========================
# Utilidades web
# =========================
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

def nivel_required(*nivels):
    """
    Exemplo:
      @nivel_required('n3')         -> apenas admin
      @nivel_required('n2','n3')    -> leitura privilegiada e admin
    """
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            nivel = session.get("nivel")
            if nivel not in nivels:
                flash("Você não tem permissão para acessar esta área.", "danger")
                return redirect(url_for("docs"))
            return f(*args, **kwargs)
        return wrap
    return decorator

# Executa setup de diretórios (docs/uploads)
ensure_dirs_and_repo()


# =========================
# Auth com MySQL
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        cnx = connect_mysql()
        cur = cnx.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE username = %s LIMIT 1;", (username,))
        user = cur.fetchone()
        cur.close()
        cnx.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            session["nivel"] = user["nivel"]  # aqui
            flash(f"Bem-vindo, {username}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Usuário ou senha incorretos.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# Assets (uploads)
# =========================
@app.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@app.route("/delete_image", methods=["POST"])
@login_required
def delete_image():
    data = request.get_json()
    url = data.get("url", "")

    if not url:
        return jsonify({"success": False, "error": "URL não fornecida"}), 400

    try:
        # Exemplo de URL: /data/docs/api-usuarios/imagem.png
        # Remove prefixos que não pertencem ao caminho real do servidor
        clean_url = url.lstrip("/")
        relative_path = clean_url.replace("data/docs/", "", 1)  # remove o prefixo
        # divide o slug e o nome do arquivo
        parts = relative_path.split("/", 1)
        if len(parts) != 2:
            return jsonify({"success": False, "error": "URL de imagem inválida"}), 400

        slug, filename = parts
        doc_dir = os.path.join(DATA_DIR, slug)
        file_path = os.path.join(doc_dir, filename)

        # segurança: garante que o arquivo está dentro de data/docs/
        if not os.path.abspath(file_path).startswith(os.path.abspath(DATA_DIR)):
            return jsonify({"success": False, "error": "Caminho inválido"}), 403

        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/docs/<slug>/delete_icon", methods=["POST"])
@login_required
def delete_icon(slug):
    """
    Remove a linha 'icon_url:' do front matter do Markdown
    e apaga o arquivo de ícone se existir.
    """
    try:
        from storage import _doc_md_path_new

        md_path = _doc_md_path_new(slug)
        if not os.path.exists(md_path):
            return jsonify({"success": False, "error": "Documento não encontrado"}), 404

        # lê todo o markdown
        with open(md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # filtra fora a linha do icon_url
        new_lines = [line for line in lines if not line.strip().startswith("icon_url:")]

        with open(md_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        # opcional: apaga o arquivo do ícone, se existir
        from storage import _doc_dir
        doc_dir = _doc_dir(slug)
        for fname in os.listdir(doc_dir):
            if fname.startswith("logo") or "icon" in fname:
                fpath = os.path.join(doc_dir, fname)
                try:
                    os.remove(fpath)
                except Exception:
                    pass

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =========================
# Index
# =========================
@app.route("/")
@login_required
def home():
    return render_template("index.html")

# =========================
# Docs
# =========================
@app.route("/projetos")
@login_required
def docs():
    q = request.args.get("q", "").strip()
    raw_items = list_docs(q)  # não passe nivel aqui

    def pick(obj, name, default=None):
        # aceita dict ou objeto
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)


    items = []
    for d in raw_items:
        title = pick(d, "title", "") or pick(d, "name", "") or "Sem título"
        slug = pick(d, "slug", "")
        cover_url = pick(d, "cover_url")
        icon_url = pick(d, "icon_url")
        category = pick(d, "category")
        description = pick(d, "description")
        tags = pick(d, "tags", [])

        if not description:
            description = (
                pick(d, "excerpt")
                or pick(d, "summary")
                or pick(d, "snippet")
                or pick(d, "content", "")
            )

        meta = {
            "cover_url": cover_url,
            "icon_url": icon_url,
            "tags": tags,
            "created_by": pick(d, "created_by"),
            "created_at": pick(d, "created_at"),
            "last_edited_by": pick(d, "last_edited_by"),
            "last_edited_at": pick(d, "last_edited_at"),
        }

        items.append({
            "title": title,
            "slug": slug,
            "category": category,
            "description": description,
            "meta": meta,
            "content": pick(d, "content")
        })

    # FILTRO DE VISIBILIDADE POR NÍVEL
    user_nivel = session.get("nivel", "n1")

    if user_nivel == "n1":
        # só mostra docs públicas
        items = [i for i in items if i["category"] in (None, "", "d1")]
    elif user_nivel == "n2":
        # pode ver d1 e d2
        items = [i for i in items if i["category"] in (None, "", "d1", "d2")]
    # n3 (admin) vê tudo → não precisa filtrar

    print("DEBUG -> slugs dos documentos:")
    for i, d in enumerate(items, start=1):
        print(f"{i}. {d['title']} | slug={d['slug']!r}")

    return render_template("docs_list.html", items=items, q=q)

from pathlib import Path

@app.route("/docs/new", methods=["GET", "POST"])
@login_required
@nivel_required('n3')
def new_doc():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")
        description = request.form.get("description", "").strip()
        tags_raw = request.form.get("tags", "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        cover_url = request.form.get("cover_url", "").strip()
        access_level = request.form.get("access_level", "d1")

        if not title:
            flash("Título é obrigatório", "warning")
            return redirect(url_for("new_doc"))

        slug = slugify(title)

        # Caminho onde o markdown seria salvo
        md_path_new = os.path.join(DOCS_DIR, slug, "doc.md")


        # ⚠️ Verifica se já existe doc com mesmo slug
        if Path(md_path_new).exists():
            flash(f"⚠️ Já existe uma documentação com o título '{title}'.", "warning")
            return redirect(url_for("new_doc"))

        # Upload opcional de ícone
        icon_url = None
        if "icon" in request.files and request.files["icon"].filename:
            try:
                icon_url = upload_file(request.files["icon"], slug)
            except Exception as e:
                flash(f"Erro ao enviar ícone: {e}", "danger")

        try:
            slug = save_doc(
                title=title,
                body=body,
                description=description,
                tags=tags,
                icon_url=None,
                author_name=session["user"],
                author_email=f"{session['user']}@local",
                slug=slug,
                access_level=access_level
            )

            flash("📘 Documentação criada com sucesso!", "success")
            return redirect(url_for("view_doc", slug=slug))

        except Exception as e:
            flash(f"❌ Erro ao criar documentação: {e}", "danger")
            return redirect(url_for("new_doc"))

    return render_template("doc_edit.html", mode="new", title="", body="")

@app.route("/docs/<slug>")
@login_required
def view_doc(slug):
    post = read_doc(slug)
    if post is None:
        flash("Documento não encontrado", "danger")
        return redirect(url_for("docs"))

    # Converte Markdown para HTML com extensões completas
    html = markdown(
        post.content,
        extensions=[
            "fenced_code",
            "codehilite",
            "toc",
            "tables",
            "abbr",
            "admonition",
            "sane_lists"
        ]
    )

    # Gera CSS para syntax highlight do Pygments
    css = HtmlFormatter().get_style_defs(".codehilite")

    comments_path = os.path.join(DATA_DIR, "docs", slug, "comments.json")

    comments = []
    if os.path.exists(comments_path):
        with open(comments_path, "r", encoding="utf-8") as f:
            comments = json.load(f)

        # Garante que todos tenham um ID (para compatibilidade retroativa)
        from datetime import datetime
        changed = False
        for c in comments:
            if "id" not in c:
                c["id"] = int(datetime.now().timestamp())
                changed = True

        if changed:
            with open(comments_path, "w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
    
    # Renderiza template passando HTML + CSS
    return render_template(
        "doc_view.html",
        html=html,
        code_css=css,
        slug=slug,
        comments=comments,
        meta=post.metadata
    )

@app.route("/docs/<slug>/<path:filename>")
@login_required
def docs_file(slug, filename):
    from storage import DATA_DIR
    return send_from_directory(os.path.join(DATA_DIR, "docs", slug), filename)

@app.route("/docs/<slug>/edit", methods=["GET", "POST"])
@login_required
@nivel_required('n3')
def edit_doc(slug):
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")
        description = request.form.get("description", "").strip()
        tags_raw = request.form.get("tags", "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        cover_url = request.form.get("cover_url", "").strip()
        access_level = request.form.get("access_level", "d1")

        if not title:
            flash("Título é obrigatório", "warning")
            return redirect(url_for("edit_doc", slug=slug))

        icon_url = None
        if "icon" in request.files and request.files["icon"].filename:
            try:
                icon_url = upload_file(request.files["icon"], slug)
            except Exception as e:
                flash(f"Erro ao enviar ícone: {e}", "danger")

        save_doc(
            title=title,
            body=body,
            description=description,
            tags=tags,
            icon_url=icon_url,
            author_name=session["user"],
            author_email=f"{session['user']}@local",
            slug=slug,
            category=access_level
        )

        flash("✅ Documento atualizado com sucesso!", "success")
        return redirect(url_for("view_doc", slug=slug))

    # CASO GET: renderiza a página de edição
    post = read_doc(slug)
    if post is None:
        flash("Documento não encontrado", "danger")
        return redirect(url_for("docs"))

    return render_template(
        "doc_edit.html",
        mode="edit",
        title=post.get("title", ""),
        body=post.content,
        description=post.get("description", ""),
        tags=", ".join(post.get("tags", [])),
        icon_url=post.get("icon_url", ""),
        cover_url=post.get("cover_url", ""),
        slug=slug
    )

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []
app.jinja_env.globals.update(load_json=load_json)

@app.route("/add_comment/<slug>", methods=["POST"])
@nivel_required("n2", "n3")
def add_comment(slug):
    from datetime import datetime

    justificativa = request.form.get("justificativa")
    conteudo = request.form.get("conteudo")

    # aqui, use a mesma chave que você usa no login
    usuario = session.get("usuario") or session.get("user") or session.get("username")

    if not usuario:
        flash("Não foi possível identificar o usuário logado.", "danger")
        return redirect(url_for("view_doc", slug=slug))

    if not justificativa or not conteudo:
        flash("Preencha todos os campos para enviar o comentário.", "warning")
        return redirect(url_for("view_doc", slug=slug))

    comments_path = os.path.join(DATA_DIR, "docs", slug, "comments.json")

    comentarios = []
    if os.path.exists(comments_path):
        with open(comments_path, "r", encoding="utf-8") as f:
            comentarios = json.load(f)

    comentarios.append({
        "usuario": usuario,
        "justificativa": justificativa.strip(),
        "conteudo": conteudo.strip(),
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": int(datetime.now().timestamp())  # gera ID único simples
    })

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(comentarios, f, ensure_ascii=False, indent=2)

    flash("Comentário adicionado com sucesso!", "success")
    return redirect(url_for("view_doc", slug=slug))

@app.route("/add_reply/<slug>/<int:comment_id>", methods=["POST"])
@nivel_required("n2", "n3")
def add_reply(slug, comment_id):
    from datetime import datetime

    conteudo = request.form.get("conteudo")
    usuario = session.get("usuario") or session.get("user") or session.get("username")

    if not usuario or not conteudo:
        flash("Preencha o conteúdo da resposta.", "warning")
        return redirect(url_for("view_doc", slug=slug))

    comments_path = os.path.join(DATA_DIR, "docs", slug, "comments.json")

    comentarios = []
    if os.path.exists(comments_path):
        with open(comments_path, "r", encoding="utf-8") as f:
            comentarios = json.load(f)

    # Encontra o comentário original
    for c in comentarios:
        if c["id"] == comment_id:
            if "replies" not in c:
                c["replies"] = []
            c["replies"].append({
                "usuario": usuario,
                "conteudo": conteudo.strip(),
                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "id": int(datetime.now().timestamp())
            })
            break

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(comentarios, f, ensure_ascii=False, indent=2)

    flash("Resposta adicionada com sucesso!", "success")
    return redirect(url_for("view_doc", slug=slug))

@app.route("/delete_comment/<slug>/<int:comment_id>", methods=["POST"])
@nivel_required("n2", "n3")
def delete_comment(slug, comment_id):
    usuario = session.get("user") or session.get("usuario") or session.get("username")
    nivel = session.get("nivel")

    comments_path = os.path.join(DATA_DIR, "docs", slug, "comments.json")
    if not os.path.exists(comments_path):
        flash("Nenhum comentário encontrado.", "warning")
        return redirect(url_for("view_doc", slug=slug))

    with open(comments_path, "r", encoding="utf-8") as f:
        comentarios = json.load(f)

    # Filtro: admin (n3) pode apagar todos; n2 apenas os próprios
    novos = []
    apagou = False
    for c in comentarios:
        if c["id"] == comment_id:
            if nivel == "n3" or c["usuario"] == usuario:
                apagou = True
                continue  # não inclui no novo arquivo (remove)
        novos.append(c)

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(novos, f, ensure_ascii=False, indent=2)

    if apagou:
        flash("Comentário excluído com sucesso!", "success")
    else:
        flash("Você não tem permissão para apagar este comentário.", "danger")

    return redirect(url_for("view_doc", slug=slug))

@app.route("/delete_reply/<slug>/<int:comment_id>/<int:reply_id>", methods=["POST"])
@nivel_required("n2", "n3")
def delete_reply(slug, comment_id, reply_id):
    usuario = session.get("user") or session.get("usuario") or session.get("username")
    nivel = session.get("nivel")

    comments_path = os.path.join(DATA_DIR, "docs", slug, "comments.json")
    if not os.path.exists(comments_path):
        flash("Nenhum comentário encontrado.", "warning")
        return redirect(url_for("view_doc", slug=slug))

    with open(comments_path, "r", encoding="utf-8") as f:
        comentarios = json.load(f)

    apagou = False

    # Percorre os comentários e suas respostas
    for c in comentarios:
        if c.get("id") == comment_id and "replies" in c:
            novas_replies = []
            for r in c["replies"]:
                if r.get("id") == reply_id:
                    if nivel == "n3" or r.get("usuario") == usuario:
                        apagou = True
                        continue  # pula (remove)
                novas_replies.append(r)
            c["replies"] = novas_replies

    with open(comments_path, "w", encoding="utf-8") as f:
        json.dump(comentarios, f, ensure_ascii=False, indent=2)

    if apagou:
        flash("Resposta excluída com sucesso!", "success")
    else:
        flash("Você não tem permissão para apagar esta resposta.", "danger")

    return redirect(url_for("view_doc", slug=slug))

@app.route("/docs/<slug>/delete", methods=["POST"])
@login_required
@nivel_required('n3')
def remove_doc(slug):
    delete_doc(slug, author_name=session["user"], author_email=f"{session['user']}@local")
    flash("Documento removido", "info")
    return redirect(url_for("docs"))

@app.route("/admin/clean_trash")
@login_required
@nivel_required('n3')
def admin_clean_trash():
    from storage import clean_trash
    removed = clean_trash(7)
    flash(f"Lixeira limpa ({len(removed)} itens removidos).", "info")
    return redirect(url_for("docs"))

@app.route("/admin/users")
@login_required
@nivel_required('n3')
def admin_users():
    """
    Lista todos os usuários e permite editar/excluir.
    """
    cnx = connect_mysql()
    cur = cnx.cursor(dictionary=True)
    cur.execute("SELECT id, username, nivel, created_at FROM usuarios ORDER BY id ASC;")
    users = cur.fetchall()
    cur.close()
    cnx.close()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@nivel_required('n3')
def edit_user(user_id):
    cnx = connect_mysql()
    cur = cnx.cursor(dictionary=True)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nivel = request.form.get("nivel", "n1")

        if not username:
            flash("Nome de usuário é obrigatório.", "warning")
            return redirect(url_for("edit_user", user_id=user_id))

        if password:
            cur.execute(
                "UPDATE usuarios SET username=%s, password_hash=%s, nivel=%s WHERE id=%s;",
                (username, generate_password_hash(password), nivel, user_id),
            )
        else:
            cur.execute(
                "UPDATE usuarios SET username=%s, nivel=%s WHERE id=%s;",
                (username, nivel, user_id),
            )
        cnx.commit()
        cur.close()
        cnx.close()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("admin_users"))

    cur.execute("SELECT * FROM usuarios WHERE id=%s;", (user_id,))
    user = cur.fetchone()
    cur.close()
    cnx.close()

    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin_users"))

    return render_template("edit_user.html", user=user)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@nivel_required('n3')
def delete_user(user_id):
    cnx = connect_mysql()
    cur = cnx.cursor()
    cur.execute("DELETE FROM usuarios WHERE id=%s;", (user_id,))
    cnx.commit()
    cur.close()
    cnx.close()
    flash("Usuário excluído com sucesso!", "info")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required
@nivel_required('n3')
def new_user():
    """
    Cria um novo usuário (apenas admin).
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nivel = request.form.get("nivel", "n1")

        if not username or not password:
            flash("Preencha todos os campos obrigatórios.", "warning")
            return redirect(url_for("new_user"))

        cnx = connect_mysql()
        cur = cnx.cursor(dictionary=True)

        # Verifica duplicidade
        cur.execute("SELECT id FROM usuarios WHERE username=%s LIMIT 1;", (username,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            cnx.close()
            flash("❌ Este nome de usuário já existe!", "danger")
            return redirect(url_for("new_user"))

        # Insere novo usuário
        cur.execute(
            "INSERT INTO usuarios (username, password_hash, nivel) VALUES (%s, %s, %s);",
            (username, generate_password_hash(password), nivel)
        )
        cnx.commit()
        cur.close()
        cnx.close()

        flash(f"✅ Usuário '{username}' criado com sucesso!", "success")
        return redirect(url_for("admin_users"))

    return render_template("new_user.html")

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    """
    Faz upload de arquivos de imagem ou mídia.
    Se o diretório do documento não existir, cria usando o título fornecido.
    """

    f = request.files.get("file")
    slug = request.form.get("slug") or request.args.get("slug")
    title = request.form.get("title") or request.args.get("title")

    print(f"DEBUG -> upload(): slug='{slug}', title='{title}', file={f.filename if f else None}")

    if not f:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    if not slug and not title:
        return jsonify({"error": "Slug ou título são obrigatórios"}), 400

    # Cria diretório caso ainda não exista
    try:
        base_dir = os.path.join(DOCS_DIR, slugify(title or slug))
        os.makedirs(base_dir, exist_ok=True)
    except Exception as e:
        print(f"ERRO -> falha ao criar diretório: {e}")
        return jsonify({"error": f"Erro ao criar diretório: {str(e)}"}), 500

    # Faz upload com prioridade para o título
    try:
        url = upload_file(f, slug=slug, title=title)
        print(f"DEBUG -> upload concluído: {url}")
        return jsonify({"url": url})
    except Exception as e:
        print(f"ERRO -> falha no upload: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/trash")
@login_required
@nivel_required('n3')
def trash():
    """
    Lista todos os itens na lixeira (/data/trash)
    """
    from storage import TRASH_DIR
    items = []
    if os.path.isdir(TRASH_DIR):
        for name in sorted(os.listdir(TRASH_DIR)):
            path = os.path.join(TRASH_DIR, name)
            if not os.path.exists(path):
                continue
            deleted_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(os.path.getmtime(path)))
            items.append({"name": name, "deleted_at": deleted_at})
    return render_template("trash.html", items=items)

@app.route("/trash/restore", methods=["POST"])
@login_required
@nivel_required('n3')
def restore_doc():
    """
    Restaura uma documentação da lixeira, verificando duplicidade.
    """
    from storage import TRASH_DIR, DOCS_DIR, _doc_md_path_new, _doc_md_path_legacy
    name = request.form.get("name", "").strip()
    if not name:
        flash("Nome inválido.", "danger")
        return redirect(url_for("trash"))

    src = os.path.join(TRASH_DIR, name)
    if not os.path.exists(src):
        flash("Item não encontrado.", "warning")
        return redirect(url_for("trash"))

    # Tenta recuperar o slug original (antes do _timestamp)
    base_name = name.split("_")[0].replace(".md", "")
    dest_dir = os.path.join(DOCS_DIR, base_name)

    # ⚠️ Verificação de conflito: já existe doc com o mesmo nome
    new_path = _doc_md_path_new(base_name)
    legacy_path = _doc_md_path_legacy(base_name)
    if os.path.exists(new_path) or os.path.exists(legacy_path) or os.path.exists(dest_dir):
        flash(f"⚠️ Já existe uma documentação chamada '{base_name}'. Restauração cancelada.", "warning")
        return redirect(url_for("trash"))

    # ✅ Sem conflito → prossegue com restauração
    try:
        shutil.move(src, dest_dir)
        flash(f"📦 Documentação '{base_name}' restaurada com sucesso!", "success")
    except Exception as e:
        flash(f"❌ Erro ao restaurar: {e}", "danger")

    return redirect(url_for("trash"))

@app.route("/trash/purge", methods=["POST"])
@login_required
@nivel_required('n3')
def purge_doc():
    """
    Exclui permanentemente um item da lixeira.
    """
    from storage import TRASH_DIR
    name = request.form.get("name", "").strip()
    if not name:
        flash("Nome inválido.", "danger")
        return redirect(url_for("trash"))

    path = os.path.join(TRASH_DIR, name)
    if not os.path.exists(path):
        flash("Item não encontrado.", "warning")
        return redirect(url_for("trash"))

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        flash(f"'{name}' excluído permanentemente.", "info")
    except Exception as e:
        flash(f"Erro ao excluir permanentemente: {e}", "danger")
    return redirect(url_for("trash"))

# -------------- Run --------------
if __name__ == "__main__":
    # dev
    app.run(host="0.0.0.0", port=80, debug=True)
