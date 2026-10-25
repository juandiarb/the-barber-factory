#!/usr/bin/env python3
"""Servidor completo: sitio público, API REST e intranet. Solo librería estándar.

    python3 server/app.py          # puerto en $PORT (por defecto 8895), 0.0.0.0
"""
import json
import mimetypes
import os
import sqlite3
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import calendar_sync  # noqa: E402
import db  # noqa: E402
import pages  # noqa: E402
from router import ApiError, Request  # noqa: E402
from routes import ROUTERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BODY = 64 * 1024

# Lista blanca: solo estas carpetas se sirven como archivos estáticos.
STATIC_DIRS = {"css", "js", "images"}
PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/intranet": "intranet.html",
    "/intranet.html": "intranet.html",
    "/admin": "intranet.html",
    "/terminos": "terminos.html",
    "/terminos.html": "terminos.html",
    "/terminos-y-condiciones": "terminos.html",
}
ROOT_FILES = {"/favicon.ico": "images/favicon.ico",
              "/apple-touch-icon.png": "images/apple-touch-icon.png"}

CSP = ("default-src 'self'; img-src 'self' https: data:; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; script-src 'self'; "
       "connect-src 'self'; frame-src https://www.google.com https://maps.google.com; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")

mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("text/javascript", ".js")


class Handler(BaseHTTPRequestHandler):
    server_version = "Barberia"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ utilidades
    def _send(self, status, body, content_type, extra_headers=None, head_only=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Cache-Control": "no-store"}
        headers.update(extra_headers or {})
        self._send(status, body, "application/json; charset=utf-8", headers)

    def _error_page(self, status, message, head_only=False):
        self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8", head_only=head_only)

    def _client_ip(self):
        # En Render el cliente real viene en X-Forwarded-For.
        forwarded = self.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() or self.client_address[0]

    def _base_url(self):
        """URL pública: SITE_URL o sitio_url si existen; si no, el Host de la petición."""
        configured = os.environ.get("SITE_URL") or pages.business.DATA.get("sitio_url")
        if configured:
            return configured.rstrip("/")
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",")[0].strip()
        host = (self.headers.get("Host") or "localhost").strip()
        if not all(c.isalnum() or c in ".-:[]" for c in host):
            host = "localhost"
        return "{}://{}".format("https" if proto == "https" else "http", host)

    def log_message(self, fmt, *args):
        sys.stderr.write("[{}] {}\n".format(self.log_date_time_string(), fmt % args))

    # ----------------------------------------------------------- despacho
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PUT(self):
        self._dispatch("PUT")

    def _dispatch(self, method):
        parts = urlsplit(self.path)
        if parts.path.startswith("/api/"):
            self._api(method, parts.path.rstrip("/") or "/", parts.query)
        elif method in ("GET", "HEAD"):
            self._static(parts.path, head_only=method == "HEAD")
        else:
            self.close_connection = True
            self._error_page(405, "Método no permitido")

    # ----------------------------------------------------------------- API
    def _api(self, method, path, query):
        try:
            found = None
            for router in ROUTERS:
                found = router.match(method, path)
                if found:
                    break
            if not found:
                if any(r.knows(path) for r in ROUTERS):
                    raise ApiError(405, "Método no permitido.")
                raise ApiError(404, "Ruta no encontrada.")
            handler, params, public = found

            user = None
            header = self.headers.get("Authorization", "")
            if header.startswith("Bearer "):
                user = auth.verify_token(header[7:].strip())
            if not public and not user:
                raise ApiError(401, "Sesión no válida o vencida. Inicia sesión de nuevo.")

            body = {}
            if method in ("POST", "PATCH", "PUT"):
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    raise ApiError(400, "Content-Length no válido.")
                if length > MAX_BODY:
                    self.close_connection = True
                    raise ApiError(413, "El cuerpo de la petición es demasiado grande.")
                raw = self.rfile.read(length) if length else b""
                if raw:
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        raise ApiError(400, "El cuerpo debe ser JSON válido.")
                    if not isinstance(body, dict):
                        raise ApiError(400, "El cuerpo debe ser un objeto JSON.")

            req = Request(method, path, parse_qs(query), body, self._client_ip())
            req.params = params
            req.user = user
            status, payload = handler(req)
            self._json(status, payload)
        except ApiError as exc:
            if method not in ("GET", "HEAD"):
                # El cuerpo pudo quedar sin leer: no reutilizar la conexión.
                self.close_connection = True
            headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
            self._json(exc.status, {"error": exc.message}, headers)
        except sqlite3.IntegrityError:
            self._json(409, {"error": "Conflicto con datos existentes."})
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            self._json(500, {"error": "Error interno del servidor."})

    # ------------------------------------------------------------ estáticos
    def _static(self, raw_path, head_only=False):
        path = unquote(raw_path)
        if "\x00" in path or "\\" in path:
            return self._error_page(400, "Ruta no válida", head_only)

        if path in PAGES:
            html = pages.render(os.path.join(ROOT, PAGES[path]), self._base_url()).encode("utf-8")
            headers = {"Cache-Control": "no-cache", "Content-Security-Policy": CSP}
            if PAGES[path] == "intranet.html":
                headers["X-Robots-Tag"] = "noindex, nofollow"
                headers["Cache-Control"] = "no-store"
            return self._send(200, html, "text/html; charset=utf-8", headers, head_only)

        if path == "/sitemap.xml":
            return self._send(200, pages.sitemap(self._base_url()).encode("utf-8"),
                              "application/xml; charset=utf-8", {"Cache-Control": "no-cache"}, head_only)

        if path == "/robots.txt":
            with open(os.path.join(ROOT, "robots.txt"), encoding="utf-8") as fh:
                text = fh.read().replace("Sitemap: /sitemap.xml", "Sitemap: {}/sitemap.xml".format(self._base_url()))
            return self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8", {"Cache-Control": "no-cache"}, head_only)

        if path in ROOT_FILES:
            path = "/" + ROOT_FILES[path]

        relative = path.lstrip("/")
        top = relative.split("/", 1)[0]
        if top not in STATIC_DIRS:
            if ".." in path.split("/"):
                return self._error_page(403, "Prohibido", head_only)
            return self._error_page(404, "No encontrado", head_only)

        base = os.path.realpath(os.path.join(ROOT, top))
        target = os.path.realpath(os.path.join(ROOT, relative))
        if not target.startswith(base + os.sep):
            return self._error_page(403, "Prohibido", head_only)
        if any(part.startswith(".") for part in relative.split("/")) or not os.path.isfile(target):
            return self._error_page(404, "No encontrado", head_only)

        content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "image/svg+xml"):
            content_type += "; charset=utf-8"
        with open(target, "rb") as fh:
            data = fh.read()
        cache = "public, max-age=86400" if top == "images" else "no-cache"
        self._send(200, data, content_type, {"Cache-Control": cache}, head_only)


def main():
    first_run = db.init_db()
    if first_run:
        print("[db] Base de datos creada en {} con los datos iniciales.".format(db.DB_PATH), flush=True)
    auth.ensure_admin()
    port = int(os.environ.get("PORT", "8895"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    print("[server] Google Calendar: {}".format("activo" if calendar_sync.is_configured() else "no configurado (se omite)"))
    print("[server] Escuchando en http://0.0.0.0:{}  (intranet: /intranet)".format(port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
