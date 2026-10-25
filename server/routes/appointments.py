"""Citas: reserva pública, disponibilidad y gestión protegida."""
import threading
import time
from datetime import date, timedelta

import business
import calendar_sync
import db
from router import DATE_RE, ID, ApiError, Field, Router
from routes.staff import works_at

router = Router()

STATUSES = db.STATUSES
MAX_DAYS_AHEAD = 120

FIELDS = [
    Field("name", "Nombre", required=True, max_len=80),
    Field("phone", "Teléfono", "phone", required=True, max_len=20),
    Field("date", "Fecha", "date", required=True),
    Field("time", "Hora", "time", required=True),
    Field("notes", "Notas", max_len=300),
]

APPT_SELECT = ("SELECT a.*, s.name AS staff_name, s.color AS staff_color FROM appointments a "
               "LEFT JOIN staff s ON s.id = a.staff_id")

# ------------------------------------------------------- límite anti-spam
# Reservas web: máximo 6 por IP y 3 por teléfono en una hora.
_recent = {}
_lock = threading.Lock()
LIMITS = {"ip": 6, "phone": 3}
WINDOW = 3600


def _rate_check(kind, key):
    with _lock:
        stamps = [t for t in _recent.get((kind, key), []) if t > time.time() - WINDOW]
        _recent[(kind, key)] = stamps
        if len(stamps) >= LIMITS[kind]:
            raise ApiError(429, "Recibimos varias reservas seguidas desde aquí. "
                                "Espera un rato o escríbenos por WhatsApp.")


def _rate_register(ip, phone):
    with _lock:
        for key in (("ip", ip), ("phone", phone)):
            _recent.setdefault(key, []).append(time.time())


# ------------------------------------------------------------- utilidades

def _find_service(body):
    """Acepta service_id o, como respaldo, el nombre exacto del servicio."""
    service_id = body.get("service_id")
    if service_id not in (None, ""):
        try:
            service_id = int(service_id)
        except (TypeError, ValueError):
            raise ApiError(400, "Servicio no válido.")
        service = db.query_one("SELECT * FROM services WHERE id = ? AND active = 1", (service_id,))
    elif isinstance(body.get("service"), str) and body["service"].strip():
        service = db.query_one("SELECT * FROM services WHERE name = ? COLLATE NOCASE AND active = 1",
                               (body["service"].strip()[:100],))
    else:
        raise ApiError(400, "Servicio es obligatorio.")
    if not service:
        raise ApiError(400, "El servicio elegido no existe o no está disponible.")
    return service


def _find_sede(value):
    if value not in (None, "") and not isinstance(value, str):
        raise ApiError(400, "Sede no válida.")
    if len(business.sedes()) > 1 and not value:
        raise ApiError(400, "Elige la sede.")
    sede = business.find_sede((value or "").strip()[:80])
    if business.sedes() and not sede:
        raise ApiError(400, "La sede elegida no existe.")
    return sede


def _find_staff(value, sede):
    if value in (None, "", 0, "0"):
        return None
    try:
        staff_id = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "Profesional no válido.")
    staff = db.query_one("SELECT * FROM staff WHERE id = ? AND active = 1", (staff_id,))
    if not staff:
        raise ApiError(400, "El profesional elegido no está disponible.")
    if sede and not works_at(staff, sede["nombre"]):
        raise ApiError(400, "{} no atiende en la sede {}.".format(staff["name"], sede["nombre"]))
    return staff


def _check_when(day, hour, sede, duration, enforce_hours):
    now = business.now()
    when = date.fromisoformat(day)
    if when < now.date() or (when == now.date() and hour <= now.strftime("%H:%M")):
        raise ApiError(400, "La fecha y hora no pueden estar en el pasado.")
    if not enforce_hours:
        return
    if when > now.date() + timedelta(days=MAX_DAYS_AHEAD):
        raise ApiError(400, "Solo se puede reservar hasta {} días adelante.".format(MAX_DAYS_AHEAD))
    hours = business.hours_for(when.weekday(), sede)
    if not hours:
        raise ApiError(400, "Ese día estamos cerrados. Elige otra fecha.")
    if hour not in business.slots_for(when, sede, duration):
        raise ApiError(400, "Esa hora no está disponible. Ese día atendemos de {} a {} y el servicio "
                            "debe terminar antes del cierre.".format(*hours))


def _taken(conn_or_none, day, sede_name, staff_id):
    """Horas ocupadas (citas no canceladas) en una fecha, sede y profesional."""
    sql = "SELECT DISTINCT time FROM appointments WHERE date = ? AND status != 'cancelada'"
    params = [day]
    if sede_name:
        sql += " AND (sede = ? OR sede IS NULL)"
        params.append(sede_name)
    if staff_id:
        sql += " AND staff_id = ?"
        params.append(staff_id)
    if conn_or_none is None:
        return {r["time"] for r in db.query(sql, params)}
    return {r["time"] for r in conn_or_none.execute(sql, params).fetchall()}


# ------------------------------------------------------------ disponibilidad

@router.get(r"/api/availability", public=True)
def availability(req):
    day = req.arg("fecha", "")
    if not DATE_RE.match(day or ""):
        raise ApiError(400, "fecha debe tener el formato AAAA-MM-DD.")
    try:
        when = date.fromisoformat(day)
    except ValueError:
        raise ApiError(400, "fecha no es una fecha válida.")
    sede = _find_sede(req.arg("sede"))
    staff = _find_staff(req.arg("profesional"), sede)
    duration = None
    if req.arg("servicio"):
        try:
            row = db.query_one("SELECT duration FROM services WHERE id = ? AND active = 1", (int(req.arg("servicio")),))
            duration = row["duration"] if row else None
        except ValueError:
            raise ApiError(400, "servicio no válido.")
    now = business.now()
    hours = business.hours_for(when.weekday(), sede)
    result = {"fecha": day, "sede": sede["nombre"] if sede else None, "cerrado": hours is None,
              "abre": hours[0] if hours else None, "cierra": hours[1] if hours else None, "horas": []}
    if when < now.date() or when > now.date() + timedelta(days=MAX_DAYS_AHEAD):
        result["fuera_de_rango"] = True
        return 200, result
    taken = _taken(None, day, sede["nombre"] if sede else None, staff["id"] if staff else None)
    for slot in business.slots_for(when, sede, duration):
        if when == now.date() and slot <= now.strftime("%H:%M"):
            continue
        result["horas"].append({"hora": slot, "libre": slot not in taken})
    return 200, result


# ------------------------------------------------------------------ reservar

@router.post(r"/api/appointments", public=True)
def create(req):
    from_intranet = req.user is not None
    values = {field.name: field.clean(req.body.get(field.name)) for field in FIELDS}
    service = _find_service(req.body)
    sede = _find_sede(req.body.get("sede"))
    staff = _find_staff(req.body.get("staff_id"), sede)
    # Ley 1581 de 2012: la reserva web necesita autorización previa y expresa
    # para tratar los datos; se guarda la fecha como prueba (Decreto 1377 de 2013).
    accepted = req.body.get("accept_terms") is True
    if not from_intranet and not accepted:
        raise ApiError(400, "Para reservar debes aceptar los términos y la política de datos.")
    _check_when(values["date"], values["time"], sede, service["duration"], enforce_hours=not from_intranet)
    status = "pendiente"
    if from_intranet and req.body.get("status"):
        status = Field("status", "Estado", "choice", choices=STATUSES).clean(req.body.get("status"))
    phone = business.normalize_phone(values["phone"])
    if not from_intranet:
        _rate_check("ip", req.client_ip)
        _rate_check("phone", phone)
    created = db.now_str()
    sede_name = sede["nombre"] if sede else None

    with db.transaction(immediate=True) as conn:
        if values["time"] in _taken(conn, values["date"], sede_name, staff["id"] if staff else None):
            raise ApiError(409, "Ese horario ya está ocupado")

        client = conn.execute("SELECT id FROM clients WHERE phone = ?", (phone,)).fetchone()
        if client:
            client_id = client["id"]
            conn.execute("UPDATE clients SET name = ?, updated_at = ? WHERE id = ?", (values["name"], created, client_id))
        else:
            client_id = conn.execute(
                "INSERT INTO clients (name, phone, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (values["name"], phone, created, created)).lastrowid

        appt_id = conn.execute(
            "INSERT INTO appointments (name, phone, service, service_id, price, duration, sede, date, time, notes, "
            "barber, staff_id, client_id, status, source, created_at, terms_accepted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (values["name"], phone, service["name"], service["id"], service["price"], service["duration"],
             sede_name, values["date"], values["time"], values["notes"], staff["name"] if staff else None,
             staff["id"] if staff else None, client_id, status, "intranet" if from_intranet else "web", created,
             created if accepted else None),
        ).lastrowid

    if not from_intranet:
        _rate_register(req.client_ip, phone)
    appointment = db.query_one(APPT_SELECT + " WHERE a.id = ?", (appt_id,))
    calendar_sync.sync_appointment(appointment, staff.get("calendar_id") if staff else None)
    if from_intranet:
        return 201, appointment
    return 201, {k: appointment[k] for k in ("id", "service", "sede", "date", "time", "barber", "status")}


# ------------------------------------------------------------------ gestión

@router.get(r"/api/appointments")
def list_all(req):
    where, params = [], []
    status = req.arg("status")
    if status in STATUSES:
        where.append("a.status = ?")
        params.append(status)
    scope = req.arg("scope", "all")
    order = "a.date DESC, a.time DESC"
    if scope == "upcoming":
        where.append("a.date >= ?")
        params.append(business.today_iso())
        order = "a.date, a.time"
    elif scope == "past":
        where.append("a.date < ?")
        params.append(business.today_iso())
    sql = APPT_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    return 200, db.query(sql + " ORDER BY " + order + " LIMIT 500", params)


@router.patch(r"/api/appointments/" + ID)
def update(req):
    appt_id = int(req.params["id"])
    if not db.query_one("SELECT id FROM appointments WHERE id = ?", (appt_id,)):
        raise ApiError(404, "Cita no encontrada.")
    changes = {}
    if "status" in req.body:
        changes["status"] = Field("status", "Estado", "choice", required=True, choices=STATUSES).clean(req.body["status"])
    if "notes" in req.body:
        changes["notes"] = Field("notes", "Notas", max_len=300).clean(req.body["notes"])
    if not changes:
        raise ApiError(400, "No hay campos para actualizar.")
    db.execute("UPDATE appointments SET {} WHERE id = ?".format(", ".join(c + " = ?" for c in changes)),
               list(changes.values()) + [appt_id])
    return 200, db.query_one(APPT_SELECT + " WHERE a.id = ?", (appt_id,))


@router.delete(r"/api/appointments/" + ID)
def delete(req):
    _, count = db.execute("DELETE FROM appointments WHERE id = ?", (int(req.params["id"]),))
    if not count:
        raise ApiError(404, "Cita no encontrada.")
    return 200, {"ok": True}
