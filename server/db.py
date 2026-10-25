"""SQLite: conexión, esquema con migraciones idempotentes y datos iniciales."""
import os
import sqlite3
from contextlib import contextmanager

import business

DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

STATUSES = ["pendiente", "confirmada", "completada", "cancelada", "no_asistio"]

# Una sola definición del esquema. Al arrancar se crea cada tabla si no existe y
# luego se agrega cualquier columna que falte, así una base vieja se actualiza
# sin perder datos. (ALTER TABLE ADD COLUMN no admite UNIQUE ni defaults no
# constantes: los únicos van como índices y created_at lo pone el código.)
SCHEMA = {
    "admins": [
        ("username", "TEXT NOT NULL DEFAULT ''"),
        ("salt", "TEXT NOT NULL DEFAULT ''"),
        ("password_hash", "TEXT NOT NULL DEFAULT ''"),
        ("role", "TEXT NOT NULL DEFAULT 'admin'"),
        ("created_at", "TEXT"),
    ],
    "services": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("description", "TEXT NOT NULL DEFAULT ''"),
        # NULL = precio sin publicar ("Precio en barbería").
        ("price", "INTEGER"),
        ("price_from", "INTEGER NOT NULL DEFAULT 0"),
        ("duration", "INTEGER NOT NULL DEFAULT 30"),
        ("categories", "TEXT NOT NULL DEFAULT ''"),
        ("image", "TEXT"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("sort_order", "INTEGER NOT NULL DEFAULT 0"),
        ("created_at", "TEXT"),
    ],
    "staff": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("phone", "TEXT"),
        ("email", "TEXT"),
        ("role", "TEXT"),
        ("color", "TEXT NOT NULL DEFAULT '#888888'"),
        ("sedes", "TEXT NOT NULL DEFAULT ''"),
        ("calendar_id", "TEXT"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("created_at", "TEXT"),
    ],
    "clients": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("phone", "TEXT NOT NULL DEFAULT ''"),
        ("email", "TEXT"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "appointments": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("phone", "TEXT NOT NULL DEFAULT ''"),
        ("service", "TEXT NOT NULL DEFAULT ''"),
        ("service_id", "INTEGER REFERENCES services(id) ON DELETE SET NULL"),
        ("price", "INTEGER"),
        ("duration", "INTEGER NOT NULL DEFAULT 30"),
        ("sede", "TEXT"),
        ("date", "TEXT NOT NULL DEFAULT ''"),
        ("time", "TEXT NOT NULL DEFAULT ''"),
        ("notes", "TEXT"),
        ("barber", "TEXT"),
        ("staff_id", "INTEGER REFERENCES staff(id) ON DELETE SET NULL"),
        ("client_id", "INTEGER REFERENCES clients(id) ON DELETE SET NULL"),
        ("status", "TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN ({}))".format(
            ",".join("'{}'".format(s) for s in STATUSES))),
        ("source", "TEXT NOT NULL DEFAULT 'web'"),
        ("created_at", "TEXT"),
        ("terms_accepted_at", "TEXT"),
    ],
    "inventory": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("quantity", "REAL NOT NULL DEFAULT 0"),
        ("unit", "TEXT"),
        ("min_stock", "REAL NOT NULL DEFAULT 0"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
    ],
    "expenses": [
        ("description", "TEXT NOT NULL DEFAULT ''"),
        ("category", "TEXT"),
        ("amount", "INTEGER NOT NULL DEFAULT 0"),
        ("date", "TEXT NOT NULL DEFAULT ''"),
        ("notes", "TEXT"),
        ("created_at", "TEXT"),
    ],
    "campaigns": [
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("channel", "TEXT"),
        ("message", "TEXT"),
        ("starts_on", "TEXT"),
        ("ends_on", "TEXT"),
        ("status", "TEXT NOT NULL DEFAULT 'borrador' "
                   "CHECK (status IN ('borrador','activa','finalizada'))"),
        ("created_at", "TEXT"),
    ],
    "discount_codes": [
        ("code", "TEXT NOT NULL DEFAULT ''"),
        ("description", "TEXT"),
        ("kind", "TEXT NOT NULL DEFAULT 'porcentaje' CHECK (kind IN ('porcentaje','monto'))"),
        ("value", "INTEGER NOT NULL DEFAULT 0"),
        ("starts_on", "TEXT"),
        ("expires_on", "TEXT"),
        ("max_uses", "INTEGER"),
        ("uses", "INTEGER NOT NULL DEFAULT 0"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("created_at", "TEXT"),
    ],
}

INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_admins_username ON admins(username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_phone ON clients(phone)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_discount_codes_code ON discount_codes(code)",
    "CREATE INDEX IF NOT EXISTS ix_appointments_slot ON appointments(date, time)",
]


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(immediate=False):
    """Conexión en una transacción; con immediate=True bloquea escrituras
    concurrentes (evita dos reservas en el mismo horario)."""
    conn = connect()
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def query(sql, params=()):
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Ejecuta una escritura; devuelve (lastrowid, rowcount)."""
    with transaction() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid, cur.rowcount


def now_str():
    return business.now().strftime("%Y-%m-%d %H:%M:%S")


def add_column_if_missing(conn, table, column, decl):
    try:
        conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, decl))
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise


def init_db():
    """Crea/actualiza el esquema y siembra los datos iniciales. Idempotente."""
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    first_run = not os.path.exists(DB_PATH)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        for table, columns in SCHEMA.items():
            cols = ", ".join("{} {}".format(c, d) for c, d in columns)
            conn.execute("CREATE TABLE IF NOT EXISTS {} (id INTEGER PRIMARY KEY AUTOINCREMENT, {})".format(table, cols))
            for column, decl in columns:
                add_column_if_missing(conn, table, column, decl)
        for sql in INDEXES:
            conn.execute(sql)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()
    return first_run


def _seed(conn):
    """Siembra servicios y profesionales de negocio.json una sola vez."""
    if conn.execute("SELECT 1 FROM meta WHERE key = 'seeded'").fetchone():
        return
    data = business.DATA
    photos = data.get("fotos_servicio", {})
    created = now_str()
    if not conn.execute("SELECT 1 FROM services LIMIT 1").fetchone():
        for i, s in enumerate(data.get("servicios", [])):
            price = s.get("precio")
            conn.execute(
                "INSERT INTO services (name, description, price, price_from, duration, categories, image, "
                "active, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (s["nombre"], s.get("descripcion", ""), int(price) if price is not None else None,
                 1 if s.get("precio_desde") else 0, int(s["duracion"]), ", ".join(s.get("categorias", [])),
                 photos.get(s.get("foto"), s.get("foto")), i, created),
            )
    if not conn.execute("SELECT 1 FROM staff LIMIT 1").fetchone():
        for p in data.get("profesionales", []):
            conn.execute(
                "INSERT INTO staff (name, role, color, sedes, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (p["nombre"], p.get("cargo"), p.get("color", "#888888"), ", ".join(p.get("sedes", [])), created),
            )
    conn.execute("INSERT INTO meta (key, value) VALUES ('seeded', ?)", (created,))
