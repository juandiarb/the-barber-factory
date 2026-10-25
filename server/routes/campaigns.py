"""Campañas de marketing (CRUD protegido)."""
from crud import register_crud
from router import ApiError, Field, Router

router = Router()

STATUSES = ["borrador", "activa", "finalizada"]

FIELDS = [
    Field("name", "Nombre", required=True, max_len=100),
    Field("channel", "Canal", max_len=40),
    Field("message", "Mensaje de WhatsApp", max_len=1000),
    Field("starts_on", "Inicio", "date"),
    Field("ends_on", "Fin", "date"),
    Field("status", "Estado", "choice", choices=STATUSES),
]


def check_dates(values, existing):
    start = values.get("starts_on", (existing or {}).get("starts_on"))
    end = values.get("ends_on", (existing or {}).get("ends_on"))
    if start and end and end < start:
        raise ApiError(400, "La fecha de fin no puede ser anterior al inicio.")
    return values


register_crud(router, r"/api/campaigns", "campaigns", FIELDS, order_by="id DESC", transform=check_dates)
