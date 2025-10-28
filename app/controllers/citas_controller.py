from flask import request, jsonify
from datetime import datetime, time, timedelta, timezone

from app.services.service_citas import (
    crear_cita,
    listar_hoy,
    listar_proximas,
    listar_activas,
    listar_historicas,
    buscar_citas,
    actualizar_cita,
    eliminar_cita,
)
from app.utils.helpers import TZ


def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code


def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


def _range_today_system_tz():
    """Devuelve (start_utc, end_utc) del día actual en el sistema (TZ de helpers)."""
    now_local = datetime.now(TZ)
    start_local = datetime.combine(now_local.date(), time.min).replace(tzinfo=TZ)
    end_local = datetime.combine(now_local.date(), time.max).replace(tzinfo=TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _range_next_days_from_tomorrow_system_tz(days: int):
    """Desde el inicio de mañana local, hasta el fin del día (hoy+days) local."""
    days = int(days)
    now_local = datetime.now(TZ)
    tomorrow_date = (now_local + timedelta(days=1)).date()
    start_local = datetime.combine(tomorrow_date, time.min).replace(tzinfo=TZ)
    # fin del rango: fin de (hoy + days)
    end_date = (now_local + timedelta(days=days)).date()
    end_local = datetime.combine(end_date, time.max).replace(tzinfo=TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _range_from_tomorrow_paged_system_tz(page: int, per_days: int):
    """
    Paginación por ventanas de días desde mañana:
    - page >= 1, per_days (cap 90)
    - ventana: [mañana + (page-1)*per_days, (mañana + page*per_days - 1) endOfDay]
    """
    page = max(int(page), 1)
    per_days = max(min(int(per_days), 90), 1)
    now_local = datetime.now(TZ)
    base_date = (now_local + timedelta(days=1)).date()  # mañana
    start_date = base_date + timedelta(days=(page - 1) * per_days)
    end_date = base_date + timedelta(days=page * per_days - 1)
    start_local = datetime.combine(start_date, time.min).replace(tzinfo=TZ)
    end_local = datetime.combine(end_date, time.max).replace(tzinfo=TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def get_hoy():
    # “Fecha actual (en el sistema)” => usar TZ del sistema (helpers.TZ)
    try:
        limit = int(request.args.get("limit", 100))
    except Exception:
        return jsonify(_fail("limit inválido", 422)[0]), 422
    start_utc, end_utc = _range_today_system_tz()
    res, code = listar_hoy(start_utc, end_utc, limit)
    return jsonify(res), code


def get_proximas():
    # “A partir de mañana en adelante” => desde inicio de mañana local
    try:
        limit = int(request.args.get("limit", 200))
    except Exception:
        return jsonify(_fail("parámetros inválidos", 422)[0]), 422

    # Si viene paginación por días (page/per_days), se usa esa ventana con cap 90 días
    page_q = request.args.get("page")
    if page_q is not None:
        try:
            page = max(int(page_q), 1)
            per_days = int(request.args.get("per_days") or request.args.get("perDays") or 90)
        except Exception:
            return jsonify(_fail("page/per_days inválidos", 422)[0]), 422
        start_utc, end_utc = _range_from_tomorrow_paged_system_tz(page, per_days)
    else:
        # Default: 7 días; permitir hasta 30 días por razones de UX/rendimiento
        try:
            days = int(request.args.get("dias") or request.args.get("days", 7))
        except Exception:
            return jsonify(_fail("days/dias inválido", 422)[0]), 422
        days = max(min(days, 30), 1)
        start_utc, end_utc = _range_next_days_from_tomorrow_system_tz(days)
    res, code = listar_proximas(start_utc, end_utc, limit)
    return jsonify(res), code


def _parse_ymd_local_to_utc(s: str | None, *, end_of_day: bool = False):
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        t = time.max if end_of_day else time.min
        local_dt = datetime.combine(dt.date(), t).replace(tzinfo=TZ)
        return local_dt.astimezone(timezone.utc)
    except Exception:
        return None


def get_activas():
    try:
        limit = int(request.args.get("limit", 200))
    except Exception:
        return jsonify(_fail("limit inválido", 422)[0]), 422
    desde = _parse_ymd_local_to_utc(request.args.get("desde"))
    hasta = _parse_ymd_local_to_utc(request.args.get("hasta"), end_of_day=True)
    res, code = listar_activas(limit=limit, start_utc=desde, end_utc=hasta)
    return jsonify(res), code


def get_historicas():
    try:
        limit = int(request.args.get("limit", 200))
    except Exception:
        return jsonify(_fail("limit inválido", 422)[0]), 422
    desde = _parse_ymd_local_to_utc(request.args.get("desde"))
    hasta = _parse_ymd_local_to_utc(request.args.get("hasta"), end_of_day=True)
    res, code = listar_historicas(desde_utc=desde, hasta_utc=hasta, limit=limit)
    return jsonify(res), code


def get_search():
    # Parámetros: q (título/doctor), paciente (nombre), desde, hasta, page, per_page, status
    q = request.args.get("q")
    paciente = request.args.get("paciente")
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except Exception:
        return jsonify(_fail("page/per_page inválidos", 422)[0]), 422
    status = request.args.get("status")
    if status and status not in {"scheduled", "completed", "cancelled"}:
        status = None

    desde = _parse_ymd_local_to_utc(request.args.get("desde"))
    hasta = _parse_ymd_local_to_utc(request.args.get("hasta"), end_of_day=True)

    res, code = buscar_citas(
        q=q,
        paciente_nombre=paciente,
        desde_utc=desde,
        hasta_utc=hasta,
        page=page,
        per_page=per_page,
        status=status,
    )
    return jsonify(res), code


def post_crear():
    payload = request.get_json(silent=True) or {}
    # Dejar validación al servicio para mantener mensajes consistentes
    res, code = crear_cita(payload)
    return jsonify(res), code


def patch_actualizar(cita_id: str):
    payload = request.get_json(silent=True) or {}
    res, code = actualizar_cita(cita_id, payload)
    return jsonify(res), code


def delete_eliminar(cita_id: str):
    hard = request.args.get("hard")
    hard_flag = True if hard in ("1", "true", "True") else False
    res, code = eliminar_cita(cita_id, hard=hard_flag)
    return jsonify(res), code
