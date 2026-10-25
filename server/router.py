"""Router por método con expresiones regulares, errores de API y validación."""
import re
from datetime import date


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Request:
    def __init__(self, method, path, query, body, client_ip):
        self.method = method
        self.path = path
        self.query = query      # dict de listas (parse_qs)
        self.body = body        # dict (JSON) o {}
        self.client_ip = client_ip
        self.params = {}
        self.user = None

    def arg(self, name, default=None):
        values = self.query.get(name)
        return values[0] if values else default


class Router:
    METHODS = ("GET", "POST", "PATCH", "DELETE")

    def __init__(self):
        self.routes = {m: [] for m in self.METHODS}

    def _register(self, method, pattern, public):
        def decorator(handler):
            self.routes[method].append((re.compile("^" + pattern + "$"), handler, public))
            return handler
        return decorator

    def get(self, pattern, public=False):
        return self._register("GET", pattern, public)

    def post(self, pattern, public=False):
        return self._register("POST", pattern, public)

    def patch(self, pattern, public=False):
        return self._register("PATCH", pattern, public)

    def delete(self, pattern, public=False):
        return self._register("DELETE", pattern, public)

    def match(self, method, path):
        for regex, handler, public in self.routes.get(method, []):
            m = regex.match(path)
            if m:
                return handler, m.groupdict(), public
        return None

    def knows(self, path):
        return any(regex.match(path) for routes in self.routes.values() for regex, _, _ in routes)


ID = r"(?P<id>\d+)"

# ---------------------------------------------------------------- validación

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")
URL_RE = re.compile(r"^(https://[^\s\"'<>]+|/?images/[\w./-]+)$")


class Field:
    """kind: str, int, number, bool, date, time, color, email, phone, url, choice."""

    def __init__(self, name, label, kind="str", required=False, max_len=200,
                 choices=None, minimum=None, maximum=None):
        self.name, self.label, self.kind = name, label, kind
        self.required, self.max_len, self.choices = required, max_len, choices
        self.minimum, self.maximum = minimum, maximum

    def clean(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if self.required:
                raise ApiError(400, "{} es obligatorio.".format(self.label))
            return None
        kind = self.kind
        if kind == "bool":
            if isinstance(value, bool):
                return 1 if value else 0
            if value in (0, 1, "0", "1", "true", "false"):
                return 1 if value in (1, "1", "true") else 0
            raise ApiError(400, "{} debe ser sí o no.".format(self.label))
        if kind in ("int", "number"):
            if isinstance(value, bool):
                raise ApiError(400, "{} debe ser un número.".format(self.label))
            try:
                num = int(value) if kind == "int" else float(value)
                if kind == "int" and isinstance(value, float) and value != int(value):
                    raise ValueError
            except (TypeError, ValueError):
                raise ApiError(400, "{} debe ser un número{}.".format(self.label, " entero" if kind == "int" else ""))
            if self.minimum is not None and num < self.minimum:
                raise ApiError(400, "{} debe ser al menos {}.".format(self.label, self.minimum))
            if self.maximum is not None and num > self.maximum:
                raise ApiError(400, "{} debe ser como máximo {}.".format(self.label, self.maximum))
            return num
        if not isinstance(value, str):
            raise ApiError(400, "{} debe ser texto.".format(self.label))
        value = value.strip()
        if len(value) > self.max_len:
            raise ApiError(400, "{} admite máximo {} caracteres.".format(self.label, self.max_len))
        if kind == "date":
            if not DATE_RE.match(value):
                raise ApiError(400, "{} debe tener el formato AAAA-MM-DD.".format(self.label))
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ApiError(400, "{} no es una fecha válida.".format(self.label))
        elif kind == "time" and not TIME_RE.match(value):
            raise ApiError(400, "{} debe tener el formato HH:MM.".format(self.label))
        elif kind == "color" and not COLOR_RE.match(value):
            raise ApiError(400, "{} debe ser un color como #1a2b3c.".format(self.label))
        elif kind == "email" and not EMAIL_RE.match(value):
            raise ApiError(400, "{} no es un correo válido.".format(self.label))
        elif kind == "phone" and not PHONE_RE.match(value):
            raise ApiError(400, "{} no es un teléfono válido.".format(self.label))
        elif kind == "url" and not URL_RE.match(value):
            raise ApiError(400, "{} debe ser una URL https:// o una ruta images/....".format(self.label))
        elif kind == "choice" and value not in self.choices:
            raise ApiError(400, "{} debe ser uno de: {}.".format(self.label, ", ".join(self.choices)))
        return value


def clean(data, fields, partial=False):
    """Valida un cuerpo JSON contra la lista de campos. En modo parcial
    (PATCH) solo valida los campos presentes."""
    if not isinstance(data, dict):
        raise ApiError(400, "El cuerpo debe ser un objeto JSON.")
    out = {}
    for field in fields:
        if partial and field.name not in data:
            continue
        value = field.clean(data.get(field.name))
        if value is None and field.kind == "bool" and partial:
            value = 0
        out[field.name] = value
    if partial and not out:
        raise ApiError(400, "No hay campos para actualizar.")
    return out
