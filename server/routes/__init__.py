"""Un módulo por recurso; cada uno expone su propio `router`."""
from routes import (appointments, auth_routes, campaigns, clients, dashboard, discount_codes,
                    expenses, inventory, services, staff)

ROUTERS = [m.router for m in (auth_routes, services, staff, appointments, clients, inventory,
                              expenses, campaigns, discount_codes, dashboard)]
