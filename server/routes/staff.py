"""Personal: CRUD protegido + GET /api/staff/public (sin datos de contacto)."""
import business
import db
from crud import register_crud
from router import ApiError, Field, Router

router = Router()

FIELDS = [
    Field("name", "Nombre", required=True, max_len=80),
    Field("phone", "Teléfono", "phone", max_len=20),
    Field("email", "Correo", "email", max_len=120),
    Field("role", "Cargo", max_len=60),
    Field("color", "Color", "color", max_len=7),
    Field("sedes", "Sedes", max_len=300),
    Field("calendar_id", "ID de Google Calendar", max_len=200),
    Field("active", "Activo", "bool"),
]


def split_sedes(text):
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def check_sedes(values, existing):
    if values.get("sedes"):
        names = split_sedes(values["sedes"])
        unknown = [n for n in names if n not in business.sede_names()]
        if unknown:
            raise ApiError(400, "Sede desconocida: {}. Sedes: {}.".format(
                ", ".join(unknown), ", ".join(business.sede_names())))
        values["sedes"] = ", ".join(names)
    return values


def works_at(staff, sede_name):
    """Sin sedes asignadas = atiende en todas."""
    names = split_sedes(staff.get("sedes"))
    return not names or not sede_name or sede_name in names


@router.get(r"/api/staff/public", public=True)
def public_list(req):
    sede = req.arg("sede")
    rows = db.query("SELECT id, name, role, color, sedes FROM staff WHERE active = 1 ORDER BY name")
    return 200, [r for r in rows if works_at(r, sede)]


register_crud(router, r"/api/staff", "staff", FIELDS, order_by="active DESC, name", transform=check_sedes)
