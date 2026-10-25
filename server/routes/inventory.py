"""Inventario de insumos (CRUD protegido)."""
from crud import register_crud
from router import Field, Router

router = Router()

FIELDS = [
    Field("name", "Producto", required=True, max_len=100),
    Field("quantity", "Cantidad", "number", required=True, minimum=0, maximum=1_000_000),
    Field("unit", "Unidad", max_len=30),
    Field("min_stock", "Stock mínimo", "number", minimum=0, maximum=1_000_000),
    Field("notes", "Notas", max_len=300),
]

register_crud(router, r"/api/inventory", "inventory", FIELDS, order_by="name COLLATE NOCASE")
