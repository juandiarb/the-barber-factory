# The Barber Factory · sitio, reservas e intranet

Sitio de una página para **The Barber Factory** (barbería exclusiva para hombres en El Peñón, Cali), con reserva de citas en línea, intranet para el equipo y página de términos y política de datos.

Sin frameworks, sin dependencias y sin paso de build: HTML, CSS y JavaScript vanilla en el navegador, y Python 3 con la librería estándar más SQLite en el servidor.

## Arrancar en local

```bash
python3 server/app.py
```

Abre <http://localhost:8895> (sitio), <http://localhost:8895/intranet> (intranet) y <http://localhost:8895/terminos>.

- El puerto sale de `PORT` (por defecto **8895**, para no chocar con los otros proyectos de la carpeta). Escucha en `0.0.0.0`.
- La base se crea sola en `server/data.db` (o donde diga `DB_PATH`) y se siembra con los servicios y el equipo de `negocio.json`.
- **Usuario de la intranet: `admin` / `admin`, en local y también en Render (así lo pidió el negocio para la demo). Es una clave pública: cualquiera que entre a `/intranet` puede adivinarla y ver nombres y teléfonos de clientes. Antes de usarla con clientes reales, define `ADMIN_PASSWORD` en Render → Environment.**

## Cambiar de negocio

Toda la información del negocio vive en **`negocio.json`** y las fotos en **`images/`**. La lógica no tiene ningún dato escrito. Para hacer otra barbería:

1. Cambia `negocio.json` (nombre, dirección, horarios por sede, servicios, equipo, reseñas, redes, `_fuentes`, `_pendientes`).
2. Reemplaza las fotos de `images/` y la imagen `images/og.jpg` (1200×630).
3. Borra `server/data.db` para que se vuelva a sembrar.

Reglas del archivo:

- Lo que no se sepa va como `null` y el sitio oculta ese bloque.
- `precio: null` muestra «Precio en barbería» (texto en `precio_nulo_texto`).
- `duraciones_confirmadas: false` oculta las duraciones en el sitio, pero se siguen usando para calcular las horas libres.
- Los días van de 0 = lunes a 6 = domingo. **Cada sede tiene su propio `horario`** y la reserva usa el de la sede elegida.
- Servicios y profesionales solo **siembran** la base la primera vez. Después se administran desde la intranet.
- Todas las fechas y horas se calculan en `zona_horaria` (America/Bogota), nunca en la del servidor.

## Estructura

```
negocio.json          única fuente de los datos del negocio
index.html            sitio público (plantilla con {{marcadores}})
intranet.html         intranet (noindex, nofollow)
terminos.html         términos y política de datos (plantilla)
robots.txt            bloquea /intranet y /api (el sitemap se sirve en /sitemap.xml)
css/ js/ images/      estáticos (las únicas carpetas que se sirven)
server/
  app.py              servidor HTTP, estáticos con lista blanca y protección contra path traversal, API
  db.py               esquema SQLite, migraciones idempotentes, siembra desde negocio.json
  auth.py             PBKDF2-HMAC-SHA256 (200.000 iteraciones), tokens HMAC de 12 h, límite de intentos
  router.py           router por método con expresiones regulares y validación de campos
  crud.py             rutas CRUD genéricas
  pages.py            pinta las plantillas (todo escapado), JSON-LD, sitemap
  business.py         carga negocio.json, horarios por sede y horas disponibles
  calendar_sync.py    Google Calendar opcional (urllib + OAuth2)
  authorize_calendar.py  autorización única de Google (flujo loopback)
  routes/             un archivo por recurso
render.yaml           despliegue en Render
```

## Diseño

La identidad sale del local real (fotos del perfil de Google Maps y del letrero):

- **Paleta:** negro industrial del techo (`#121110`), amarillo de las capas y las banquetas (`#f2c230`), ladrillo de las paredes (`#b5532c`) y el crema cálido de los bombillos del letrero (`#f3eddf`). Los colores de éxito y error salen de la misma paleta: amarillo para el éxito y ladrillo claro para el error, siempre con ícono y texto.
- **Tipografías:**
  - *Rye*: las letras con espuelas del escudo de la fachada («THE … FACTORY»).
  - *Yellowtail*: el neón en cursiva de la palabra «Factory» en la barra.
  - *Saira Stencil One*: letras de plantilla de fábrica para rótulos, cifras y botones.
  - *Barlow*: texto corrido; es una grotesca industrial, inspirada en señalización vial.
- **Firma visual:**
  1. Franjas de precaución amarillo/negro (por lo de *Factory*), en la franja inclinada, los bordes de sección y la intro.
  2. Filas de bombillos tipo marquesina alrededor del nombre, como el letrero «BARBER» de la barra.
  3. Marcos con las esquinas recortadas, como el escudo de la fachada.

## API

Pública:

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/appointments` | Reservar (valida campos, horario de la sede, 120 días, términos; 409 si el horario está ocupado) |
| GET | `/api/services/public` | Servicios activos |
| GET | `/api/staff/public?sede=` | Profesionales activos (sin datos de contacto) |
| GET | `/api/availability?fecha=&sede=&profesional=&servicio=` | Horas del día con `libre: true/false` |
| POST | `/api/auth/login` | Login (5 intentos fallidos por IP cada 10 min) |

Protegida (`Authorization: Bearer <token>`): CRUD de `services`, `staff`, `clients`, `inventory`, `expenses`, `campaigns` y `discount-codes`; `GET/POST /api/appointments`, `PATCH` y `DELETE /api/appointments/{id}`; `GET /api/clients/{id}/appointments`; `GET /api/dashboard`; `GET /api/auth/me`.

Antispam: máximo 6 reservas web por IP y 3 por teléfono en una hora.

## Google Calendar (opcional)

Cada reserva puede crear un evento en el calendario del negocio y en el del profesional (si tiene ID en Intranet → Personal). Si falta la configuración, se omite en silencio, y un fallo de Google nunca rompe la reserva.

1. En <https://console.cloud.google.com> crea un proyecto, habilita **Google Calendar API** y crea credenciales OAuth de tipo **App de escritorio**. Agrega tu cuenta como usuario de prueba.
2. En tu terminal: `export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...` y luego `python3 server/authorize_calendar.py`.
3. Acepta con la cuenta dueña del calendario. El token queda en `server/google_token.json` (ignorado por git).
4. En Render define `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` (el valor del archivo) y `GOOGLE_CALENDAR_ID` (por ejemplo `primary`).

## Despliegue en Render

1. Sube el repositorio a GitHub.
2. En Render: **New → Blueprint** y elige el repositorio. `render.yaml` crea el servicio web gratis y genera `SESSION_SECRET`.
3. La intranet arranca con `admin` / `admin`. Para cambiar la clave, agrega `ADMIN_PASSWORD` en el panel de Render → el servicio → **Environment** y redespliega: se aplica en cada arranque.
4. Cuando tengas dominio, define `SITE_URL` (y `sitio_url` en `negocio.json`) para el canonical y el sitemap.

### Límites del plan gratis (importante)

- **El servicio se duerme** tras ~15 minutos sin visitas. La primera carga tarda de 30 a 60 segundos: abre el link antes de mostrárselo al cliente.
- **SQLite sin disco persistente se borra en cada reinicio o despliegue**: citas, clientes, inventario y cambios del catálogo. Para uso real hace falta un **disco persistente** de Render (de pago), montado por ejemplo en `/var/data`, con `DB_PATH=/var/data/data.db`, o una base gestionada.

## Seguridad

- Credenciales por variables de entorno (`ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET`), aplicadas en cada arranque.
- Consultas SQL con parámetros, todo dato escapado al pintar HTML y cabeceras `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` y CSP.
- Solo se sirven `css/`, `js/`, `images/` y las páginas declaradas; nunca `server/`, `.env`, `.git` ni la base.
- Ni secretos ni bases de datos entran al repositorio (`.gitignore`).
