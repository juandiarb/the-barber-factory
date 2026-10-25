"""Catálogo de servicios: CRUD protegido + GET /api/services/public."""
import db
from crud import register_crud
from router import Field, Router

router = Router()

FIELDS = [
    Field("name", "Nombre", required=True, max_len=100),
    Field("description", "Descripción", max_len=500),
    # Vacío = precio sin publicar: el sitio muestra "Precio en barbería".
    Field("price", "Precio", "int", minimum=0, maximum=100_000_000),
    Field("price_from", "Precio 'desde'", "bool"),
    Field("duration", "Duración", "int", required=True, minimum=5, maximum=600),
    Field("categories", "Categorías", max_len=200),
    Field("image", "Foto", "url", max_len=500),
    Field("active", "Activo", "bool"),
    Field("sort_order", "Orden", "int", minimum=0, maximum=10_000),
]


def tidy(values, existing):
    if values.get("categories"):
        parts = [p.strip() for p in values["categories"].split(",")]
        values["categories"] = ", ".join(p for p in parts if p)
    return values


@router.get(r"/api/services/public", public=True)
def public_list(req):
    return 200, db.query(
        "SELECT id, name, description, price, price_from, duration, categories, image FROM services "
        "WHERE active = 1 ORDER BY sort_order, id")


register_crud(router, r"/api/services", "services", FIELDS, order_by="sort_order, id",
              conflict_msg="Ya existe un servicio con esos datos.", transform=tidy)
