"""Contraseñas (PBKDF2-HMAC-SHA256) y tokens de sesión firmados con HMAC."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

import db

ITERATIONS = 200_000
TOKEN_TTL = 12 * 3600

# La clave se genera al iniciar el servidor: reiniciar cierra todas las sesiones.
# Opcional: SESSION_SECRET la fija para que las sesiones sobrevivan reinicios.
SECRET = os.environ.get("SESSION_SECRET", "").encode() or secrets.token_bytes(32)

# Hash de relleno para que un usuario inexistente tarde lo mismo que uno real.
_DUMMY_SALT = secrets.token_hex(16)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS)
    return salt, digest.hex()


def verify_password(password, salt, expected_hash):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_hash)


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload):
    return _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())


def make_token(username, role):
    payload = _b64(json.dumps({"u": username, "r": role, "exp": int(time.time()) + TOKEN_TTL}).encode())
    return payload + "." + _sign(payload)


def verify_token(token):
    """Devuelve el usuario {'username', 'role'} si el token es válido y vigente."""
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    user = db.query_one("SELECT username, role FROM admins WHERE username = ?", (data.get("u"),))
    return user


def authenticate(username, password):
    user = db.query_one("SELECT username, salt, password_hash, role FROM admins WHERE username = ?", (username,))
    if not user:
        verify_password(password, _DUMMY_SALT, "0" * 64)
        return None
    if not verify_password(password, user["salt"], user["password_hash"]):
        return None
    return {"username": user["username"], "role": user["role"]}


DEFAULT_PASSWORD = "admin"


def ensure_admin():
    """Crea el usuario de la intranet en el primer arranque.

    Por defecto es admin / admin (pedido del negocio). Con ADMIN_USER y
    ADMIN_PASSWORD definidos, crea o actualiza ese usuario con esa contraseña
    en cada arranque: úsalo en producción para no dejar admin/admin.
    """
    username = os.environ.get("ADMIN_USER", "").strip() or "admin"
    env_password = os.environ.get("ADMIN_PASSWORD", "")
    exists = db.query_one("SELECT id FROM admins WHERE username = ?", (username,))
    if env_password:
        salt, digest = hash_password(env_password)
        if exists:
            db.execute("UPDATE admins SET salt = ?, password_hash = ? WHERE id = ?", (salt, digest, exists["id"]))
        else:
            db.execute("INSERT INTO admins (username, salt, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
                       (username, salt, digest, db.now_str()))
        print("[auth] Usuario '{}' configurado desde ADMIN_PASSWORD.".format(username))
        return
    if db.query_one("SELECT id FROM admins LIMIT 1"):
        return
    salt, digest = hash_password(DEFAULT_PASSWORD)
    db.execute("INSERT INTO admins (username, salt, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
               (username, salt, digest, db.now_str()))
    bar = "=" * 64
    print("\n{0}\n  Usuario de la intranet creado: {1} / {2}\n"
          "  AVISO: es una contraseña pública. Antes de publicar el sitio,\n"
          "  arranca con ADMIN_PASSWORD='otra-clave' para cambiarla.\n{0}\n"
          .format(bar, username, DEFAULT_PASSWORD), flush=True)


# Límite de intentos de login: 5 fallos por IP en 10 minutos.
_failures = {}
_lock = threading.Lock()
MAX_FAILURES = 5
WINDOW = 600


def login_blocked(ip):
    with _lock:
        recent = [t for t in _failures.get(ip, []) if t > time.time() - WINDOW]
        _failures[ip] = recent
        return len(recent) >= MAX_FAILURES


def register_failure(ip):
    with _lock:
        _failures.setdefault(ip, []).append(time.time())


def clear_failures(ip):
    with _lock:
        _failures.pop(ip, None)
