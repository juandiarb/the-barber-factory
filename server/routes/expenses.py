"""Gastos (CRUD protegido)."""
from crud import register_crud
from router import Field, Router

router = Router()

FIELDS = [
    Field("description", "Descripción", required=True, max_len=120),
    Field("category", "Categoría", max_len=60),
    Field("amount", "Monto", "int", required=True, minimum=0, maximum=1_000_000_000),
    Field("date", "Fecha", "date", required=True),
    Field("notes", "Notas", max_len=300),
]

register_crud(router, r"/api/expenses", "expenses", FIELDS, order_by="date DESC, id DESC")
