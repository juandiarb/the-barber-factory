"""Google Calendar opcional, solo con la librería estándar (urllib + OAuth2).

Si faltan las variables de entorno o el token, no hace nada. Cualquier fallo se
registra en consola y nunca afecta la reserva: todo corre en un hilo aparte.

Variables (ver .env.example):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET   credenciales OAuth (app de escritorio)
  GOOGLE_REFRESH_TOKEN                      opcional; si no, se lee de google_token.json
  GOOGLE_CALENDAR_ID                        calendario del negocio (p. ej. "primary")
El calendario de cada profesional se configura en la intranet (Personal > ID de
Google Calendar) y debe estar compartido con la cuenta que autorizó.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import business

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_token.json")
TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{}/events"

_cache = {"token": None, "expires": 0}
_lock = threading.Lock()


def _refresh_token():
    token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()
    if token:
        return token
    try:
        with open(TOKEN_FILE, encoding="utf-8") as fh:
            return json.load(fh).get("refresh_token")
    except (OSError, ValueError):
        return None


def is_configured():
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET") and _refresh_token())


def _access_token():
    with _lock:
        if _cache["token"] and _cache["expires"] > time.time() + 60:
            return _cache["token"]
        body = urllib.parse.urlencode({
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": _refresh_token(),
            "grant_type": "refresh_token",
        }).encode()
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=10) as resp:
            data = json.load(resp)
        _cache["token"] = data["access_token"]
        _cache["expires"] = time.time() + int(data.get("expires_in", 3600))
        return _cache["token"]


def _create_event(calendar_id, event):
    req = urllib.request.Request(
        EVENTS_URL.format(urllib.parse.quote(calendar_id, safe="")),
        data=json.dumps(event).encode(),
        headers={"Authorization": "Bearer " + _access_token(), "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp).get("id")


def _event_for(appt):
    start = datetime.strptime(appt["date"] + " " + appt["time"], "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=int(appt.get("duration") or 30))
    tz = business.DATA.get("zona_horaria", "UTC")
    lines = ["Cliente: " + appt["name"], "Teléfono: " + appt["phone"]]
    if appt.get("barber"):
        lines.append("Profesional: " + appt["barber"])
    if appt.get("notes"):
        lines.append("Notas: " + appt["notes"])
    lines.append("Reserva #{} ({})".format(appt["id"], appt.get("source", "web")))
    return {
        "summary": "{} · {}".format(appt["service"], appt["name"]),
        "description": "\n".join(lines),
        "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:00"), "timeZone": tz},
        "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:00"), "timeZone": tz},
    }


def _sync(appt, staff_calendar_id):
    calendars = []
    business_cal = os.environ.get("GOOGLE_CALENDAR_ID", "").strip()
    if business_cal:
        calendars.append(business_cal)
    if staff_calendar_id and staff_calendar_id not in calendars:
        calendars.append(staff_calendar_id)
    event = _event_for(appt)
    for cal in calendars:
        try:
            _create_event(cal, event)
            print("[calendar] Cita #{} agregada a {}".format(appt["id"], cal), flush=True)
        except urllib.error.HTTPError as exc:
            print("[calendar] Error {} al crear evento en {}: {}".format(
                exc.code, cal, exc.read()[:300].decode("utf-8", "replace")), flush=True)
        except Exception as exc:  # noqa: BLE001 — nunca debe romper la reserva
            print("[calendar] No se pudo crear el evento en {}: {}".format(cal, exc), flush=True)


def sync_appointment(appt, staff_calendar_id=None):
    """Crea los eventos en segundo plano. Silencioso si no está configurado."""
    try:
        if not is_configured():
            return
        threading.Thread(target=_sync, args=(dict(appt), staff_calendar_id), daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        print("[calendar] Omitido: {}".format(exc), flush=True)
