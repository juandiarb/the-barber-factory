"""Pinta index.html, intranet.html y terminos.html reemplazando {{marcadores}}
con los datos de negocio.json (todo escapado). Las listas (servicios, galería,
reseñas...) se pintan en el servidor como respaldo y el navegador las mejora a
partir del JSON incrustado en la página."""
import html
import json
import os
import re
from urllib.parse import quote

import business
import db

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def _script_json(obj):
    """JSON seguro para incrustar dentro de <script>."""
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _abs(base, path):
    if not path:
        return None
    return path if path.startswith("http") else "{}/{}".format(base, path.lstrip("/"))


def money(value):
    """48000 -> "$ 48.000"."""
    return "$ {:,}".format(int(value)).replace(",", ".")


def duration_text(minutes):
    """70 -> "1 h 10 min"."""
    h, m = divmod(int(minutes), 60)
    if h and m:
        return "{} h {} min".format(h, m)
    return "{} h".format(h) if h else "{} min".format(m)


def _services():
    """Servicios activos de la base (los administra la intranet)."""
    try:
        return db.query("SELECT id, name, description, price, price_from, duration, categories, image "
                        "FROM services WHERE active = 1 ORDER BY sort_order, id")
    except Exception:  # noqa: BLE001 — sin base, usa negocio.json
        photos = business.DATA.get("fotos_servicio", {})
        return [{"id": None, "name": s["nombre"], "description": s.get("descripcion", ""), "price": s.get("precio"),
                 "price_from": 1 if s.get("precio_desde") else 0, "duration": s["duracion"],
                 "categories": ", ".join(s.get("categorias", [])), "image": photos.get(s.get("foto"))}
                for s in business.DATA.get("servicios", [])]


def _opening_hours(blocks):
    return [{"@type": "OpeningHoursSpecification", "dayOfWeek": [DAY_NAMES[i] for i in b["dias"]],
             "opens": b["abre"], "closes": b["cierra"]} for b in blocks or [] if not b.get("cerrado")]


def _jsonld(base, services):
    d = business.DATA
    redes = d.get("redes") or {}
    data = {
        "@context": "https://schema.org",
        "@type": "HairSalon",
        "name": d["nombre"],
        "description": d.get("meta_descripcion"),
        "url": d.get("sitio_url") or base + "/",
        "telephone": d.get("telefono"),
        "address": {"@type": "PostalAddress", "streetAddress": d.get("direccion"),
                    "addressLocality": d.get("ciudad"), "addressRegion": d.get("region"),
                    "addressCountry": d.get("pais")},
        "openingHoursSpecification": _opening_hours(d.get("horario")),
        "sameAs": [u for u in redes.values() if u],
        "hasMap": "https://www.google.com/maps/search/?api=1&query={}".format(
            quote(d.get("mapa_busqueda") or business.full_address())),
    }
    if d.get("barrio"):
        data["address"]["streetAddress"] = "{}, {}".format(d["direccion"], d["barrio"])
    if d.get("codigo_postal"):
        data["address"]["postalCode"] = d["codigo_postal"]
    geo = d.get("geo") or {}
    if geo.get("lat") is not None:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": geo["lat"], "longitude": geo["lng"]}
    rating = d.get("calificacion") or {}
    if rating.get("valor") and rating.get("total"):
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating["valor"],
                                   "reviewCount": rating["total"], "bestRating": 5}
    if d.get("correo"):
        data["email"] = d["correo"]
    if d.get("imagen_og"):
        data["image"] = _abs(base, d["imagen_og"])
    prices = [s["price"] for s in services if s.get("price")]
    if prices:
        data["priceRange"] = "{} - {} {}".format(money(min(prices)), money(max(prices)), d.get("moneda", ""))
    elif d.get("rango_precios"):
        data["priceRange"] = d["rango_precios"]
    sedes = d.get("sedes") or []
    if len(sedes) > 1:
        data["department"] = [{"@type": "HairSalon", "name": "{} · {}".format(d["nombre"], s["nombre"]),
                               "address": s.get("direccion"),
                               "openingHoursSpecification": _opening_hours(s.get("horario"))} for s in sedes]
    elif sedes and sedes[0].get("horario"):
        data["openingHoursSpecification"] = _opening_hours(sedes[0]["horario"])
    return _script_json(data)


def _head_extra(base):
    d = business.DATA
    tags = []
    url = d.get("sitio_url") or os.environ.get("SITE_URL")
    if url:
        tags.append('<link rel="canonical" href="{0}">'.format(_esc(url)))
    tags.append('<meta property="og:url" content="{0}">'.format(_esc((url or base).rstrip("/") + "/")))
    if d.get("imagen_og"):
        img = _esc(_abs(base, d["imagen_og"]))
        tags.append('<meta property="og:image" content="{0}">\n  <meta property="og:image:width" content="1200">'
                    '\n  <meta property="og:image:height" content="630">\n  <meta name="twitter:image" content="{0}">'
                    .format(img))
    return "\n  ".join(tags)


def _long_date(iso):
    """"2026-10-25" -> "25 de octubre de 2026"."""
    if not iso:
        return ""
    y, m, day = (int(x) for x in iso.split("-"))
    return "{} de {} de {}".format(day, MONTHS[m - 1], y)


PENDING = '<span class="pendiente">en actualización</span>'


def _legal_facts():
    """Ficha del responsable para /terminos. Lo que falte se marca "en actualización"."""
    d = business.DATA
    legal = d.get("legal") or {}
    sedes = "; ".join("{}: {}".format(s["nombre"], s["direccion"]) for s in d.get("sedes") or [])
    rows = [
        ("Nombre comercial", _esc(d["nombre"])),
        ("Razón social", _esc(legal["razon_social"]) if legal.get("razon_social") else PENDING),
        ("NIT", _esc(legal["nit"]) if legal.get("nit") else PENDING),
        ("Domicilio", _esc(business.full_address())),
        ("Sedes", _esc(sedes) if sedes else None),
        ("Teléfono / WhatsApp", _esc(d.get("telefono")) if d.get("telefono") else None),
        ("Correo", _esc(d["correo"]) if d.get("correo") else PENDING),
    ]
    return "".join("<div><dt>{}</dt><dd>{}</dd></div>".format(_esc(k), v) for k, v in rows if v)


def _legal_channels():
    """Canales de atención (PQR y datos personales) como <li>."""
    d = business.DATA
    items = []
    wa = business.whatsapp_url("Hola, tengo una solicitud sobre mis datos o un servicio de {}.".format(d["nombre"]))
    if wa:
        items.append('WhatsApp {}: <a href="{}" target="_blank" rel="noopener">escríbenos aquí</a>'.format(
            _esc(d.get("telefono") or ""), _esc(wa)))
    elif d.get("telefono"):
        items.append("Teléfono: {}".format(_esc(d["telefono"])))
    if d.get("correo"):
        items.append('Correo: <a href="mailto:{0}">{0}</a>'.format(_esc(d["correo"])))
    else:
        items.append("Correo electrónico: {}".format(PENDING))
    items.append("En persona, en {}.".format(_esc(business.full_address())))
    return "".join("<li>{}</li>".format(i) for i in items)


# ------------------------------------------------- bloques pintados en servidor

def _services_html(services):
    d = business.DATA
    show_duration = d.get("duraciones_confirmadas", True)
    out = []
    for s in services:
        if s.get("price") is None:
            price = '<span class="svc-price svc-price--ask">{}</span>'.format(_esc(d.get("precio_nulo_texto") or "Consultar"))
        else:
            price = '<span class="svc-price">{}{}</span>'.format("Desde " if s.get("price_from") else "", money(s["price"]))
        dur = '<span class="svc-dur">{}</span>'.format(duration_text(s["duration"])) if show_duration else ""
        out.append('<li class="svc" data-cats="{cats}"><button type="button" class="svc-btn" data-service-id="{id}" '
                   'data-service-name="{name}"><span class="svc-name">{name}</span><span class="svc-desc">{desc}</span>'
                   '<span class="svc-meta">{price}{dur}</span></button></li>'.format(
                       cats=_esc(s.get("categories")), id=_esc(s.get("id") or ""), name=_esc(s["name"]),
                       desc=_esc(s.get("description")), price=price, dur=dur))
    return "".join(out)


def _service_options(services):
    return "".join('<option value="{}">{}</option>'.format(_esc(s.get("id") or s["name"]), _esc(s["name"]))
                   for s in services)


def context(base):
    d = business.DATA
    rating = d.get("calificacion") or {}
    redes = d.get("redes") or {}
    sedes = d.get("sedes") or []
    main = next((x for x in sedes if x.get("principal")), sedes[0] if sedes else {})
    map_query = main.get("mapa_busqueda") or d.get("mapa_busqueda") or business.full_address()
    phone_digits = "".join(c for c in d.get("telefono") or "" if c.isdigit() or c == "+")
    services = _services()
    name = d["nombre"]
    # "The Barber Factory" -> "The Barber" + "Factory" (la última palabra va en letra de neón).
    head, _, tail = name.rpartition(" ")
    raw = {
        "nombre": name,
        "nombre_1": head or name,
        "nombre_2": tail if head else "",
        "eyebrow": d.get("eyebrow"),
        "lema": d.get("lema"),
        "titular": d.get("titular"),
        "subtitulo": d.get("subtitulo"),
        "meta_descripcion": d.get("meta_descripcion"),
        "direccion_completa": business.full_address(),
        "telefono": d.get("telefono"),
        "telefono_href": "tel:" + phone_digits if phone_digits else "",
        "whatsapp_url": business.whatsapp_url(d.get("reserva_whatsapp_mensaje", "")),
        "instagram": redes.get("instagram"),
        "instagram_usuario": d.get("instagram_usuario"),
        "facebook": redes.get("facebook"),
        "horario_corto": d.get("horario_corto"),
        "rating_valor": str(rating.get("valor") or "").replace(".", ","),
        "rating_total": rating.get("total"),
        "rating_fuente": rating.get("fuente"),
        "hero_foto": d.get("hero_foto"),
        "mapa_url": "https://www.google.com/maps?q={}&output=embed".format(quote(map_query)),
        "mapa_link": "https://www.google.com/maps/search/?api=1&query={}".format(quote(map_query)),
        "anio": business.now().year,
        "ciudad": d.get("ciudad"),
        "terminos_fecha": _long_date((d.get("legal") or {}).get("terminos_actualizados")),
        "num_servicios": len(services),
    }
    for i, photo in enumerate((d.get("hero_fotos") or [])[:3], start=1):
        raw["hero_foto_{}".format(i)] = photo.get("src")
        raw["hero_foto_{}_alt".format(i)] = photo.get("alt")
        raw["hero_foto_{}_w".format(i)] = photo.get("w", "")
        raw["hero_foto_{}_h".format(i)] = photo.get("h", "")
    ctx = {k: _esc(v) for k, v in raw.items()}
    ctx["head_extra"] = _head_extra(base)
    ctx["jsonld"] = _jsonld(base, services)
    public = business.public_data()
    public["servicios_db"] = services
    ctx["business_json"] = _script_json(public)
    ctx["legal_facts"] = _legal_facts()
    ctx["legal_channels"] = _legal_channels()
    ctx["services_html"] = _services_html(services)
    ctx["service_options"] = _service_options(services)
    return ctx


def render(path, base="http://localhost"):
    with open(path, encoding="utf-8") as fh:
        template = fh.read()
    ctx = context(base)

    def sub(match):
        key = match.group(1)
        if key not in ctx:
            print("[pages] Marcador desconocido: {{{{{}}}}} en {}".format(key, os.path.basename(path)))
            return ""
        return ctx[key]

    return PLACEHOLDER.sub(sub, template)


def sitemap(base):
    today = business.today_iso()
    urls = "".join("<url><loc>{}{}</loc><lastmod>{}</lastmod></url>".format(_esc(base), p, today)
                   for p in ("/", "/terminos"))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{}</urlset>\n'.format(urls))
