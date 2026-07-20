"""
Ciclone External — API Backend
Roda em: http://31.97.255.112:5555
"""

from flask import Flask, request, jsonify, send_from_directory
import sqlite3, uuid, hashlib, datetime, os, functools

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────
DB_PATH     = os.path.join(os.path.dirname(__file__), "ciclone.db")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "ciclone_admin_secret")
PAINEL_DIR  = os.path.join(os.path.dirname(__file__), "painel")

# ── Database setup ────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS keys (
                key         TEXT PRIMARY KEY,
                used        INTEGER DEFAULT 0,
                used_by     TEXT DEFAULT NULL,
                created_at  TEXT,
                used_at     TEXT DEFAULT NULL,
                note        TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                username    TEXT PRIMARY KEY,
                password    TEXT,
                hwid        TEXT DEFAULT NULL,
                key_used    TEXT,
                created_at  TEXT,
                banned      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                action      TEXT,
                username    TEXT DEFAULT NULL,
                ip          TEXT DEFAULT NULL,
                detail      TEXT DEFAULT NULL,
                created_at  TEXT
            );
        """)
        db.commit()

init_db()

# ── Helpers ───────────────────────────────────────────────────────────────
def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def log(action: str, username: str = None, detail: str = None):
    ip = request.remote_addr if request else None
    with get_db() as db:
        db.execute(
            "INSERT INTO logs (action, username, ip, detail, created_at) VALUES (?,?,?,?,?)",
            (action, username, ip, detail, now())
        )
        db.commit()

def require_admin(f):
    """Decorator — requer header Authorization: Bearer <ADMIN_TOKEN>"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

# ═════════════════════════════════════════════════════════════════════════
#  ROTAS PUBLICAS (cheat)
# ═════════════════════════════════════════════════════════════════════════

@app.route("/api/cheat/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    key      = (data.get("key")      or "").strip()
    hwid     = (data.get("hwid")     or "").strip()

    if not username or not password or not key:
        return jsonify({"message": "Preencha todos os campos."}), 400

    with get_db() as db:
        # Verifica key
        row = db.execute("SELECT * FROM keys WHERE key=?", (key,)).fetchone()
        if not row:
            log("register_fail", username, "key invalida")
            return jsonify({"message": "Key invalida."}), 400
        if row["used"]:
            log("register_fail", username, "key ja usada")
            return jsonify({"message": "Key ja utilizada."}), 400

        # Verifica se usuario ja existe
        if db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            log("register_fail", username, "usuario ja existe")
            return jsonify({"message": "Usuario ja existe."}), 409

        # Cria usuario e marca key como usada
        db.execute(
            "INSERT INTO users (username, password, hwid, key_used, created_at) VALUES (?,?,?,?,?)",
            (username, hash_pass(password), hwid, key, now())
        )
        db.execute(
            "UPDATE keys SET used=1, used_by=?, used_at=? WHERE key=?",
            (username, now(), key)
        )
        db.commit()

    log("register_ok", username)
    return jsonify({"message": "success"}), 200


@app.route("/api/cheat/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    hwid     = (data.get("hwid")     or "").strip()

    if not username or not password:
        return jsonify({"message": "Preencha todos os campos."}), 400

    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            log("login_fail", username, "usuario nao encontrado")
            return jsonify({"message": "Usuario nao encontrado."}), 404
        if row["banned"]:
            log("login_fail", username, "banido")
            return jsonify({"message": "Conta banida."}), 403
        if row["password"] != hash_pass(password):
            log("login_fail", username, "senha errada")
            return jsonify({"message": "Senha incorreta."}), 401

        # Atualiza HWID se mudou
        if hwid and row["hwid"] != hwid:
            db.execute("UPDATE users SET hwid=? WHERE username=?", (hwid, username))
            db.commit()

    log("login_ok", username)
    return jsonify({"message": "success", "username": username}), 200


# ═════════════════════════════════════════════════════════════════════════
#  ROTAS ADMIN (bot Discord + painel)
# ═════════════════════════════════════════════════════════════════════════

@app.route("/admin/key/generate", methods=["POST"])
@require_admin
def generate_key():
    data  = request.get_json(silent=True) or {}
    note  = data.get("note", "")
    count = int(data.get("count", 1))
    count = min(count, 50)  # max 50 por vez

    keys = []
    with get_db() as db:
        for _ in range(count):
            k = "CIC-" + uuid.uuid4().hex[:6].upper() + "-" + uuid.uuid4().hex[:6].upper()
            db.execute(
                "INSERT INTO keys (key, created_at, note) VALUES (?,?,?)",
                (k, now(), note)
            )
            keys.append(k)
        db.commit()

    log("key_generated", detail=f"{count} keys | note={note}")
    return jsonify({"keys": keys}), 200


@app.route("/admin/key/revoke", methods=["POST"])
@require_admin
def revoke_key():
    data = request.get_json(silent=True) or {}
    key  = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "key required"}), 400

    with get_db() as db:
        row = db.execute("SELECT * FROM keys WHERE key=?", (key,)).fetchone()
        if not row:
            return jsonify({"error": "Key nao encontrada"}), 404
        db.execute("DELETE FROM keys WHERE key=?", (key,))
        db.commit()

    log("key_revoked", detail=key)
    return jsonify({"message": "Key revogada"}), 200


@app.route("/admin/user/ban", methods=["POST"])
@require_admin
def ban_user():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "username required"}), 400

    with get_db() as db:
        db.execute("UPDATE users SET banned=1 WHERE username=?", (username,))
        db.commit()

    log("user_banned", username)
    return jsonify({"message": f"{username} banido"}), 200


@app.route("/admin/user/unban", methods=["POST"])
@require_admin
def unban_user():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    with get_db() as db:
        db.execute("UPDATE users SET banned=0 WHERE username=?", (username,))
        db.commit()
    log("user_unbanned", username)
    return jsonify({"message": f"{username} desbanido"}), 200


@app.route("/admin/logs", methods=["GET"])
@require_admin
def get_logs():
    limit = int(request.args.get("limit", 50))
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/admin/users", methods=["GET"])
@require_admin
def get_users():
    with get_db() as db:
        rows = db.execute("SELECT username, hwid, key_used, created_at, banned FROM users").fetchall()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/admin/keys", methods=["GET"])
@require_admin
def get_keys():
    with get_db() as db:
        rows = db.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows]), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "online"}), 200


# ═════════════════════════════════════════════════════════════════════════
#  PAINEL WEB ADMIN
# ═════════════════════════════════════════════════════════════════════════

@app.route("/painel")
@app.route("/painel/")
def painel_index():
    return send_from_directory(PAINEL_DIR, "index.html")

@app.route("/painel/<path:filename>")
def painel_static(filename):
    return send_from_directory(PAINEL_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5555, debug=False)
