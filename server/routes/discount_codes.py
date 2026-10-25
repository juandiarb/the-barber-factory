"""Códigos de descuento (CRUD protegido)."""
import re

from crud import register_crud
from router import ApiError, Field, Router

router = Router()

CODE_RE = re.compile(r"^[A-Z0-9_-]{3,30}$")

FIELDS = [
    Field("code", "Código", required=True, max_len=30),
    Field("description", "Descripción", max_len=200),
    Field("kind", "Tipo", "choice", required=True, choices=["porcentaje", "monto"]),
    Field("value", "Valor", "int", required=True, minimum=1, maximum=100_000_000),
    Field("starts_on", "Desde", "date"),
    Field("expires_on", "Vence", "date"),
    Field("max_uses", "Usos máximos", "int", minimum=1, maximum=1_000_000),
    Field("uses", "Usos", "int", minimum=0, maximum=1_000_000),
    Field("active", "Activo", "bool"),
]


def check(values, existing):
    if "code" in values:
        values["code"] = values["code"].upper()
        if not CODE_RE.match(values["code"]):
            raise ApiError(400, "El código admite de 3 a 30 letras, números, guion o guion bajo.")
    kind = values.get("kind") or (existing or {}).get("kind")
    value = values.get("value") or (existing or {}).get("value")
    if kind == "porcentaje" and value and value > 100:
        raise ApiError(400, "Un descuento porcentual no puede pasar de 100.")
    start = values.get("starts_on", (existing or {}).get("starts_on"))
    end = values.get("expires_on", (existing or {}).get("expires_on"))
    if start and end and end < start:
        raise ApiError(400, "La fecha de vencimiento no puede ser anterior al inicio.")
    return values


register_crud(router, r"/api/discount-codes", "discount_codes", FIELDS, order_by="id DESC",
              conflict_msg="Ya existe un código con ese nombre.", transform=check)
