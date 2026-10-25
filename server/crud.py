"""Rutas CRUD genéricas (listar, ver, crear, editar, eliminar) sobre una tabla.

Los nombres de tabla y columna vienen de las definiciones del código, nunca
del usuario; todos los valores van como parámetros (?) de SQLite.
"""
import sqlite3

import db
from router import ID, ApiError, clean


def integrity_error(exc, conflict_msg):
    text = str(exc)
    if "NOT NULL" in text or "CHECK" in text:
        return ApiError(400, "Faltan datos obligatorios o hay un valor no permitido.")
    return ApiError(409, conflict_msg)


def register_crud(router, base, table, fields, order_by="id DESC",
                  conflict_msg="Ya existe un registro con esos datos.", transform=None):
    """transform(values, existing) ajusta/valida los valores ya limpios;
    existing es la fila actual en una edición o None al crear."""
    item_path = base + "/" + ID
    transform = transform or (lambda values, existing: values)

    def fetch(item_id):
        row = db.query_one("SELECT * FROM {} WHERE id = ?".format(table), (item_id,))
        if not row:
            raise ApiError(404, "No encontrado.")
        return row

    @router.get(base)
    def list_items(req):
        return 200, db.query("SELECT * FROM {} ORDER BY {}".format(table, order_by))

    @router.get(item_path)
    def get_item(req):
        return 200, fetch(int(req.params["id"]))

    @router.post(base)
    def create_item(req):
        values = transform(clean(req.body, fields), None)
        # Los campos vacíos se omiten para que apliquen los DEFAULT de la tabla.
        values = {k: v for k, v in values.items() if v is not None}
        values["created_at"] = db.now_str()
        cols = list(values)
        try:
            new_id, _ = db.execute(
                "INSERT INTO {} ({}) VALUES ({})".format(table, ", ".join(cols), ", ".join("?" * len(cols))),
                [values[c] for c in cols],
            )
        except sqlite3.IntegrityError as exc:
            raise integrity_error(exc, conflict_msg)
        return 201, fetch(new_id)

    @router.patch(item_path)
    def update_item(req):
        item_id = int(req.params["id"])
        existing = fetch(item_id)
        values = transform(clean(req.body, fields, partial=True), existing)
        # Un texto borrado se guarda vacío (las columnas de texto no admiten NULL).
        text_fields = {f.name for f in fields if f.kind == "str"}
        values = {k: ("" if v is None and k in text_fields else v) for k, v in values.items()}
        try:
            db.execute(
                "UPDATE {} SET {} WHERE id = ?".format(table, ", ".join("{} = ?".format(c) for c in values)),
                list(values.values()) + [item_id],
            )
        except sqlite3.IntegrityError as exc:
            raise integrity_error(exc, conflict_msg)
        return 200, fetch(item_id)

    @router.delete(item_path)
    def delete_item(req):
        _, count = db.execute("DELETE FROM {} WHERE id = ?".format(table), (int(req.params["id"]),))
        if not count:
            raise ApiError(404, "No encontrado.")
        return 200, {"ok": True}

    return fetch
