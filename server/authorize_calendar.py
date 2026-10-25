"""Autoriza Google Calendar UNA vez y guarda el refresh token.

Pasos:
 1. En https://console.cloud.google.com crea un proyecto, habilita "Google
    Calendar API" y crea credenciales OAuth de tipo "App de escritorio".
    En la pantalla de consentimiento agrega tu cuenta como usuario de prueba.
 2. En tu terminal:
        export GOOGLE_CLIENT_ID=...  GOOGLE_CLIENT_SECRET=...
        python3 server/authorize_calendar.py
 3. Se abre el navegador; acepta con la cuenta dueña del calendario del negocio.
 4. El token queda en server/google_token.json (ignorado por git). En Render,
    copia el refresh_token a la variable GOOGLE_REFRESH_TOKEN.
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.events"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_token.json")


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Define GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET antes de correr este script.")

    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if query.get("state", [""])[0] != state:
                result["error"] = "state no coincide"
            elif "code" in query:
                result["code"] = query["code"][0]
            else:
                result["error"] = query.get("error", ["sin código"])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Listo. Ya puedes cerrar esta pestaña y volver a la terminal.".encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Callback)
    redirect_uri = "http://127.0.0.1:{}/".format(server.server_port)
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print("Abriendo el navegador. Si no se abre, visita:\n" + url)
    webbrowser.open(url)
    while not result:
        server.handle_request()
    server.server_close()
    if "error" in result:
        sys.exit("Autorización fallida: " + result["error"])

    body = urllib.parse.urlencode({
        "code": result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=15) as resp:
        tokens = json.load(resp)
    if "refresh_token" not in tokens:
        sys.exit("Google no devolvió refresh_token. Revoca el acceso en tu cuenta y repite.")
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        json.dump({"refresh_token": tokens["refresh_token"]}, fh)
    os.chmod(TOKEN_FILE, 0o600)
    print("Token guardado en {}. Reinicia el servidor.".format(TOKEN_FILE))


if __name__ == "__main__":
    main()
