"""
Ciclone External — Gerador de Keys Local
Gera keys offline e salva em keys.txt
Execute: python3 gerar_keys.py
"""

import uuid, datetime, sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "ciclone.db")

PLANOS = {
    "3DIAS":   20,
    "SEMANA":  20,
    "MENSAL":  20,
    "LIFE":    20,
}

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
                note        TEXT DEFAULT NULL,
                plan        TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                username    TEXT PRIMARY KEY,
                password    TEXT,
                hwid        TEXT DEFAULT NULL,
                key_used    TEXT,
                plan        TEXT DEFAULT NULL,
                expires_at  TEXT DEFAULT NULL,
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

def gerar_key(plano: str) -> str:
    prefixo = {
        "3DIAS":  "CIC3D",
        "SEMANA": "CICSEM",
        "MENSAL": "CICMES",
        "LIFE":   "CICLIFE",
    }.get(plano, "CIC")
    return f"{prefixo}-{uuid.uuid4().hex[:5].upper()}-{uuid.uuid4().hex[:5].upper()}"

def main():
    init_db()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    todas = []

    with get_db() as db:
        for plano, qtd in PLANOS.items():
            keys_plano = []
            for _ in range(qtd):
                k = gerar_key(plano)
                db.execute(
                    "INSERT OR IGNORE INTO keys (key, created_at, note, plan) VALUES (?,?,?,?)",
                    (k, now, plano, plano)
                )
                keys_plano.append(k)
            todas.append((plano, keys_plano))
        db.commit()

    # Salva em arquivo txt
    output = []
    output.append("=" * 50)
    output.append("  CICLONE EXTERNAL — KEYS GERADAS")
    output.append(f"  {now} UTC")
    output.append("=" * 50)

    for plano, keys in todas:
        desc = {
            "3DIAS":  "3 Dias",
            "SEMANA": "1 Semana",
            "MENSAL": "1 Mes",
            "LIFE":   "Lifetime",
        }.get(plano, plano)

        output.append(f"\n[ {desc} — {len(keys)} keys ]")
        output.append("-" * 40)
        for k in keys:
            output.append(k)

    output.append("\n" + "=" * 50)

    txt = "\n".join(output)
    print(txt)

    with open(os.path.join(os.path.dirname(__file__), "keys.txt"), "w") as f:
        f.write(txt)

    print("\n[OK] Keys salvas em keys.txt e no banco ciclone.db")

if __name__ == "__main__":
    main()
