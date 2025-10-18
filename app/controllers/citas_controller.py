from flask import request
from datetime import datetime
from dateutil.parser import isoparse

from services.service_citas import crear_cita, listar_hoy, listar_proximas
from utils.helpers import today_range_utc, next_days_range_utc

def get_hoy():
    limit = int(request.args.get("limit", 100))
    start_utc, end_utc = today_range_utc()
    return listar_hoy(start_utc, end_utc, limit), 200

def get_proximas():
    days = int(request.args.get("days", 7))
    limit = int(request.args.get("limit", 200))
    start_utc, end_utc = next_days_range_utc(days)
    return listar_proximas(start_utc, end_utc, limit), 200

def post_crear():
    payload = request.get_json(force=True) or {}
    paciente_id = payload.get("paciente_id")
    start_at = payload.get("start_at")
    end_at = payload.get("end_at")

    if not paciente_id or not start_at:
        return {"message": "paciente_id y start_at son requeridos"}, 400

    try:
        start_dt = isoparse(start_at)
        end_dt = isoparse(end_at) if end_at else None
        item = crear_cita(
            paciente_id=paciente_id,
            start_at=start_dt,
            end_at=end_dt,
            title=payload.get("title"),
            description=payload.get("description"),
            provider=payload.get("provider"),
            location=payload.get("location"),
        )
        return item, 201
    except ValueError as ve:
        return {"message": str(ve)}, 400
    except Exception as e:
        return {"message": "No se pudo crear la cita"}, 500
