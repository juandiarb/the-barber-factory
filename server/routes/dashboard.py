"""GET /api/dashboard: resumen del día, la semana y el mes en curso."""
from datetime import timedelta

import business
import db
from router import Router

router = Router()


@router.get(r"/api/dashboard")
def summary(req):
    now = business.now()
    today = now.date()
    week_end = today + timedelta(days=6)
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    active = "status NOT IN ('cancelada', 'no_asistio')"

    def scalar(sql, params=()):
        row = db.query_one(sql, params)
        return list(row.values())[0] or 0

    return 200, {
        "today": today.isoformat(),
        "month": month_start.strftime("%Y-%m"),
        "appointments_today": scalar(
            "SELECT COUNT(*) FROM appointments WHERE date = ? AND " + active, (today.isoformat(),)),
        "appointments_week": scalar(
            "SELECT COUNT(*) FROM appointments WHERE date >= ? AND date <= ? AND " + active,
            (today.isoformat(), week_end.isoformat())),
        # Ingresos estimados del mes: citas no canceladas con precio conocido.
        "revenue_month_estimated": scalar(
            "SELECT SUM(COALESCE(price, 0)) FROM appointments WHERE date >= ? AND date < ? AND " + active,
            (month_start.isoformat(), next_month.isoformat())),
        "revenue_month_completed": scalar(
            "SELECT SUM(COALESCE(price, 0)) FROM appointments WHERE status = 'completada' AND date >= ? AND date < ?",
            (month_start.isoformat(), next_month.isoformat())),
        "appointments_without_price": scalar(
            "SELECT COUNT(*) FROM appointments WHERE price IS NULL AND date >= ? AND date < ? AND " + active,
            (month_start.isoformat(), next_month.isoformat())),
        "expenses_month": scalar(
            "SELECT SUM(amount) FROM expenses WHERE date >= ? AND date < ?",
            (month_start.isoformat(), next_month.isoformat())),
        "new_clients_30d": scalar(
            "SELECT COUNT(*) FROM clients WHERE created_at >= ?",
            ((today - timedelta(days=30)).isoformat(),)),
        "clients": scalar("SELECT COUNT(*) FROM clients"),
        "top_services": db.query(
            "SELECT service AS name, COUNT(*) AS total FROM appointments WHERE date >= ? AND " + active +
            " GROUP BY service ORDER BY total DESC LIMIT 5", ((today - timedelta(days=90)).isoformat(),)),
        "low_stock": db.query(
            "SELECT id, name, quantity, unit, min_stock FROM inventory WHERE quantity <= min_stock ORDER BY name"),
        "next_appointments": db.query(
            "SELECT a.id, a.name, a.phone, a.service, a.sede, a.date, a.time, a.status, s.name AS staff_name, "
            "s.color AS staff_color FROM appointments a LEFT JOIN staff s ON s.id = a.staff_id "
            "WHERE (a.date > ? OR (a.date = ? AND a.time >= ?)) AND a.status IN ('pendiente', 'confirmada')"
            " ORDER BY a.date, a.time LIMIT 8",
            (today.isoformat(), today.isoformat(), now.strftime("%H:%M"))),
    }
