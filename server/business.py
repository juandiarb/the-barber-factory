"""Datos del negocio. Única fuente: negocio.json en la raíz del proyecto.

Para usar este sistema con otro negocio, edita negocio.json; no hace falta tocar
la lógica.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "negocio.json")

with open(CONFIG_PATH, encoding="utf-8") as fh:
    DATA = json.load(fh)


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(DATA.get("zona_horaria") or "UTC")
    except Exception:
        # Sin base de datos de zonas horarias: usa el desfase fijo del archivo.
        offset = DATA.get("utc_offset") or "+00:00"
        sign = -1 if offset.startswith("-") else 1
        hh, mm = offset[1:].split(":")
        return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


TZ = _tz()


def now():
    """Fecha y hora actuales en la zona horaria del negocio."""
    return datetime.now(TZ)


def today_iso():
    return now().date().isoformat()


def full_address():
    parts = [DATA.get("direccion"), DATA.get("barrio"), DATA.get("ciudad")]
    return ", ".join(p for p in parts if p)


def whatsapp_url(message=""):
    number = DATA.get("whatsapp")
    if not number:
        return None
    url = "https://wa.me/" + number
    return url + "?text=" + quote(message) if message else url


def normalize_phone(phone):
    """Deja solo dígitos y antepone el indicativo del país a números locales,
    para que '311 529 3383' y '+57 311-529-3383' sean el mismo cliente."""
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    prefix = DATA.get("indicativo_pais") or ""
    if prefix and len(digits) == 10 and not digits.startswith(prefix):
        digits = prefix + digits
    return digits


# ------------------------------------------------------------------ sedes

def sedes():
    return DATA.get("sedes") or []


def sede_names():
    return [s["nombre"] for s in sedes()]


def find_sede(name):
    """La sede por nombre; sin nombre (o una sola sede) devuelve la principal."""
    all_sedes = sedes()
    if not all_sedes:
        return None
    if name:
        for s in all_sedes:
            if s["nombre"] == name:
                return s
        return None
    return next((s for s in all_sedes if s.get("principal")), all_sedes[0])


def hours_for(weekday, sede=None):
    """(abre, cierra) en 'HH:MM' para un día (0 = lunes) en una sede, o None
    si ese día cierra. Cada sede tiene su propio horario; si no lo trae, usa el
    horario general."""
    blocks = (sede or {}).get("horario") or DATA.get("horario", [])
    for block in blocks:
        if weekday in block.get("dias", []):
            if block.get("cerrado"):
                return None
            return block["abre"], block["cierra"]
    return None


def to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def from_minutes(total):
    return "{:02d}:{:02d}".format(total // 60, total % 60)


def slots_for(day, sede=None, duration=None):
    """Horas de inicio posibles un día: cada intervalo_citas_min dentro del
    horario, dejando tiempo para terminar el servicio antes del cierre."""
    hours = hours_for(day.weekday(), sede)
    if not hours:
        return []
    step = int(DATA.get("intervalo_citas_min") or 30)
    duration = int(duration or step)
    start, end = to_minutes(hours[0]), to_minutes(hours[1])
    return [from_minutes(t) for t in range(start, end - duration + 1, step)]


def public_data():
    """Lo que el navegador necesita para pintar el sitio (sin notas internas)."""
    data = {k: v for k, v in DATA.items() if not k.startswith("_")}
    data["direccion_completa"] = full_address()
    data["whatsapp_url"] = whatsapp_url(DATA.get("reserva_whatsapp_mensaje", ""))
    data["whatsapp_promos_url"] = whatsapp_url(DATA.get("promo_whatsapp_mensaje", ""))
    data["hoy"] = today_iso()
    data["ahora"] = now().strftime("%H:%M")
    return data
