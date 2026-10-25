"""POST /api/auth/login (pública) y GET /api/auth/me."""
import auth
from router import ApiError, Router

router = Router()


@router.post(r"/api/auth/login", public=True)
def login(req):
    if auth.login_blocked(req.client_ip):
        raise ApiError(429, "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
    username = req.body.get("username")
    password = req.body.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        raise ApiError(400, "Usuario y contraseña son obligatorios.")
    user = auth.authenticate(username.strip()[:80], password[:200])
    if not user:
        auth.register_failure(req.client_ip)
        raise ApiError(401, "Usuario o contraseña incorrectos.")
    auth.clear_failures(req.client_ip)
    return 200, {"token": auth.make_token(user["username"], user["role"]),
                 "user": user, "expires_in": auth.TOKEN_TTL}


@router.get(r"/api/auth/me")
def me(req):
    return 200, {"user": req.user}
