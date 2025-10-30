from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional

from bson import ObjectId

from app import mongo


def _utc_now_naive() -> datetime:
    return datetime.utcnow()


def _to_utc_naive(dt: datetime) -> datetime:
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_iso_utc(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        val = s.strip()
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        dt = datetime.fromisoformat(val)
        return _to_utc_naive(dt if dt.tzinfo else dt)
    except Exception:
        return None


def _month_range_utc(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = _to_utc_naive(now or datetime.utcnow())
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # inicio del próximo mes
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(microseconds=1)
    return start, end


def _count_pacientes_activos() -> int:
    filt = {
        "$and": [
            {"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]},
            {"activo": True},
        ]
    }
    try:
        return int(mongo.db.paciente.count_documents(filt))
    except Exception:
        return 0


def _citas_porcentaje_cumplidas(start_dt: datetime, end_dt: datetime) -> Tuple[int, int, int]:
    """
    Retorna (porcentaje_cumplidas, total_completed, total_programadas)
    porcentaje es redondeado a entero.
    """
    try:
        completed = int(
            mongo.db.citas.count_documents(
                {"status": "completed", "start_at": {"$gte": start_dt, "$lte": end_dt}}
            )
        )
    except Exception:
        completed = 0
    try:
        scheduled = int(
            mongo.db.citas.count_documents(
                {"status": "scheduled", "start_at": {"$gte": start_dt, "$lte": end_dt}}
            )
        )
    except Exception:
        scheduled = 0
    denom = max(1, completed + scheduled)
    porcentaje = round(100 * completed / denom)
    return porcentaje, completed, scheduled


def _get_last_apn(doc: dict, *, up_to: Optional[datetime] = None, start_from: Optional[datetime] = None) -> dict | None:
    apn = doc.get("apn") or []
    if not isinstance(apn, list) or not apn:
        return None
    # Filtrar por rango si se pasa. APN.fecha puede ser datetime o 'YYYY-MM-DD'
    def _to_date(x) -> Optional[datetime]:
        f = x.get("fecha")
        if f is None:
            return None
        if isinstance(f, datetime):
            return _to_utc_naive(f)
        if isinstance(f, str):
            try:
                return datetime.strptime(f, "%Y-%m-%d")
            except Exception:
                return None
        return None

    filtered: list[tuple[datetime, dict]] = []
    for it in apn:
        dt = _to_date(it)
        if not isinstance(dt, datetime):
            continue
        if up_to is not None and dt > up_to:
            continue
        # Nota: no filtramos por start_from al buscar el último APN para reglas de control
        filtered.append((dt, it))

    if not filtered:
        return None
    filtered.sort(key=lambda t: t[0])
    return filtered[-1][1]


def _clasificar_riesgo_por_ga(doc: dict, *, start_dt: datetime, end_dt: datetime) -> str:
    """
    Devuelve "alto" | "medio" | "ninguno" segun reglas clínicas:
    - Hipertensión: PA >= 140/90 (alto)
    - Diabetes gestacional: glucosa > 140 mg/dL (alto)
    - Anemia: Hb < 11 g/dL (medio)
    - IMC < 18.5 o > 30 (medio)
    - >30 días sin control APN (medio; si nunca tuvo control, cuenta como medio)
    """
    try:
        # 1) Hipertensión por último control APN
        # Para HTA y control, usar el último APN <= end_dt (aunque sea previo a start_dt)
        apn = _get_last_apn(doc, up_to=end_dt) or {}
        pa_sis = apn.get("pa_sis")
        pa_dia = apn.get("pa_dia")
        if isinstance(pa_sis, (int, float)) and isinstance(pa_dia, (int, float)):
            if pa_sis >= 140 or pa_dia >= 90:
                return "alto"

        # 2) Diabetes gestacional
        glu1 = doc.get("glucemia1")
        glu2 = doc.get("glucemia2")
        try:
            g1 = float(glu1) if glu1 is not None else None
        except Exception:
            g1 = None
        try:
            g2 = float(glu2) if glu2 is not None else None
        except Exception:
            g2 = None
        gmax = max([x for x in (g1, g2) if isinstance(x, (int, float))], default=None)
        if gmax is not None and gmax > 140:
            return "alto"

        # 3) Anemia
        hb = doc.get("hemoglobina")
        try:
            hbv = float(hb) if hb is not None else None
        except Exception:
            hbv = None
        if hbv is not None and hbv < 11:
            return "medio"

        # 4) IMC
        imc = doc.get("imc")
        try:
            imcv = float(imc) if imc is not None else None
        except Exception:
            imcv = None
        if imcv is not None and (imcv < 18.5 or imcv > 30):
            return "medio"

        # 5) Falta de control > 30 días
        # Base temporal: fecha 'end_dt'
        base = end_dt.date()
        fecha_s = apn.get("fecha") if isinstance(apn, dict) else None
        if not fecha_s:
            # Sin controles previos al 'to' => sin control
            return "medio"
        try:
            if isinstance(fecha_s, datetime):
                fec = _to_utc_naive(fecha_s).date()
            else:
                fec = datetime.strptime(str(fecha_s), "%Y-%m-%d").date()
        except Exception:
            return "medio"
        if (base - fec).days > 30:
            return "medio"

        return "ninguno"
    except Exception:
        # Cualquier error al clasificar: no castigar al paciente
        return "ninguno"


def _clasificar_por_paciente_ids(paciente_ids: list[ObjectId], *, start_dt: datetime, end_dt: datetime) -> Dict[str, int]:
    """
    Recorre pacientes (activos) y devuelve conteo por nivel: {alto, medio, ninguno}
    Usa el documento de gestacion_actual más reciente por paciente.
    """
    niveles = {"alto": 0, "medio": 0, "ninguno": 0}
    if not paciente_ids:
        return niveles

    for pid in paciente_ids:
        try:
            ga = mongo.db.gestacion_actual.find_one(
                {"paciente_id": pid}, sort=[("created_at", -1), ("_id", -1)]
            )
            if not ga:
                # Sin datos clínicos => no alertar
                niveles["ninguno"] += 1
                continue
            nivel = _clasificar_riesgo_por_ga(ga, start_dt=start_dt, end_dt=end_dt)
            niveles[nivel] = niveles.get(nivel, 0) + 1
        except Exception:
            niveles["ninguno"] += 1

    return niveles


def generar_resumen_panel(start_iso: Optional[str] = None, end_iso: Optional[str] = None) -> Dict[str, Any]:
    """
    Agrega métricas para el panel de reportes.
    Estructura de salida compatible con el frontend.
    """
    # Rango de fechas (UTC). Si no vienen, mes actual
    start_dt = _parse_iso_utc(start_iso)
    end_dt = _parse_iso_utc(end_iso)
    if start_dt is None or end_dt is None:
        start_dt, end_dt = _month_range_utc(_utc_now_naive())

    # 1) Pacientes activos (activo=True cuando exista el campo, y no eliminados)
    activos_total = _count_pacientes_activos()

    # 2) Citas cumplidas (% sobre programadas + cumplidas)
    citas_pct, _, _ = _citas_porcentaje_cumplidas(start_dt, end_dt)

    # 3) Clasificación de riesgo por reglas clínicas
    try:
        # Filtro base de pacientes activos según requerimiento
        filtro_activos = {
            "$and": [
                {"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]},
                {"activo": True},
            ]
        }
        cursor = mongo.db.paciente.find(filtro_activos, {"_id": 1})
        activos_ids = [d["_id"] for d in cursor]
    except Exception:
        activos_ids = []

    niveles = _clasificar_por_paciente_ids(activos_ids, start_dt=start_dt, end_dt=end_dt)
    total_eval = len(activos_ids)
    if total_eval == 0:
        # Evitar mostrar 100% alertas cuando no hay pacientes evaluados
        altas_pct = medias_pct = alertas_pct = 0
    else:
        altas_pct = round(100 * niveles.get("alto", 0) / total_eval)
        medias_pct = round(100 * niveles.get("medio", 0) / total_eval)
        # el resto como "alertas" (bajo/ninguno)
        alertas_pct = max(0, 100 - altas_pct - medias_pct)

    # 4) Conteo de "alertas en seguimiento": alto o medio
    alertas_en_seguimiento = int(niveles.get("alto", 0) + niveles.get("medio", 0))

    return {
        "cards": {
            "pacientes_activos": {"value": int(activos_total), "suffix": "gestantes"},
            "citas_cumplidas": {"value": int(citas_pct), "suffix": "%", "precision": 0},
            "alertas_generadas": {"value": int(alertas_en_seguimiento), "suffix": "en seguimiento"},
        },
        "indicadores": {
            "altas": {"percent": int(altas_pct)},
            "medias": {"percent": int(medias_pct)},
            "alertas": {"percent": int(alertas_pct)},
        },
    }


# Alias público esperado por el caller
def build_dashboard(start_iso: Optional[str] = None, end_iso: Optional[str] = None) -> Dict[str, Any]:
    return generar_resumen_panel(start_iso=start_iso, end_iso=end_iso)
