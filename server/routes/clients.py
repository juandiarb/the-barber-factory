"""Clientes: CRUD protegido + historial GET /api/clients/{id}/appointments."""
import business
import db
from crud import register_crud
from router import ID, ApiError, Field, Router

router = Router()

FIELDS = [
    Field("name", "Nombre", required=True, max_len=80),
    Field("phone", "Teléfono", "phone", required=True, max_len=20),
    Field("email", "Correo", "email", max_len=120),
    Field("notes", "Notas", max_len=500),
]


def normalize(values, existing):
    if values.get("phone"):
        values["phone"] = business.normalize_phone(values["phone"])
    values["updated_at"] = db.now_str()
    return values


@router.get(r"/api/clients/" + ID + r"/appointments")
def history(req):
    client = db.query_one("SELECT id, phone FROM clients WHERE id = ?", (int(req.params["id"]),))
    if not client:
        raise ApiError(404, "Cliente no encontrado.")
    return 200, db.query(
        "SELECT a.*, s.name AS staff_name, s.color AS staff_color FROM appointments a "
        "LEFT JOIN staff s ON s.id = a.staff_id "
        "WHERE a.client_id = ? OR a.phone = ? ORDER BY a.date DESC, a.time DESC",
        (client["id"], client["phone"]))


register_crud(router, r"/api/clients", "clients", FIELDS, order_by="name COLLATE NOCASE",
              conflict_msg="Ya existe un cliente con ese teléfono.", transform=normalize)
