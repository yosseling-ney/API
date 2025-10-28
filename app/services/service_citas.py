from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from bson import ObjectId
from flask import current_app
from app import mongo
from app.db import start_session_if_possible


# Duración por defecto de una cita cuando no se envía `end_at`
_DEFAULT_SLOT_MINUTES = 30


# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code


def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


# ---------------- Utils ----------------
def _oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError("id no es un ObjectId válido")


def _utc_naive(dt: datetime) -> datetime:
    """Convierte un datetime a UTC naive (tzinfo=None)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_iso(s: str, field: str) -> datetime:
    if isinstance(s, datetime):
        return _utc_naive(s if s.tzinfo else s)
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser un string ISO 8601")
    ss = s.strip()
    if ss.endswith("Z"):
        ss = ss[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ss)
    except Exception:
        raise ValueError(f"{field} no es un ISO 8601 válido")
    # devolver UTC naive
    return _utc_naive(dt if dt.tzinfo else dt)


def _iso_z(dt: datetime | None) -> str | None:
    if not isinstance(dt, datetime):
        return None
    # asumimos que lo almacenado es UTC naive
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize(doc: dict) -> dict:
    return {
        "_id": str(doc.get("_id")),
        "paciente_id": str(doc.get("paciente_id")) if isinstance(doc.get("paciente_id"), ObjectId) else (doc.get("paciente_id") or None),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "provider": doc.get("provider"),
        "status": doc.get("status"),
        "start_at": _iso_z(doc.get("start_at")),
        "end_at": _iso_z(doc.get("end_at")),
        "created_at": _iso_z(doc.get("created_at")),
        "updated_at": _iso_z(doc.get("updated_at")),
    }


def _ensure_indexes():
    try:
        mongo.db.citas.create_index([("start_at", 1)], name="ix_citas_start_at")
    except Exception:
        pass
    try:
        mongo.db.citas.create_index([("paciente_id", 1)], name="ix_citas_paciente")
    except Exception:
        pass
    try:
        mongo.db.citas.create_index([("status", 1)], name="ix_citas_status")
    except Exception:
        pass


# ---------------- Services ----------------
def crear_cita(payload: dict):
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        _ensure_indexes()

        paciente_id = payload.get("paciente_id")
        if not paciente_id:
            return _fail("paciente_id es requerido", 422)

        try:
            pac_oid = _oid(paciente_id)
        except ValueError as ve:
            return _fail(str(ve), 422)

        # validar que el paciente exista (FK suave)
        pac = mongo.db.paciente.find_one({"_id": pac_oid})
        if not pac:
            return _fail("paciente no existe", 404)

        start_dt = _parse_iso(payload.get("start_at"), "start_at")
        end_dt = _parse_iso(payload.get("end_at"), "end_at") if payload.get("end_at") else None
        if end_dt is None:
            end_dt = start_dt + timedelta(minutes=_DEFAULT_SLOT_MINUTES)
        # status opcional (default scheduled)
        st_in = payload.get("status")
        status_val = "scheduled"
        if st_in is not None:
            st = str(st_in).strip().lower()
            if st not in _STATUS_ENUM:
                return _fail("status inválido", 422)
            status_val = st

        now = datetime.utcnow()
        doc = {
            "paciente_id": pac_oid,
            "title": payload.get("title") or None,
            "description": payload.get("description") or None,
            "provider": payload.get("provider") or None,
            "status": status_val,
            "start_at": start_dt,
            "end_at": end_dt,
            "created_at": now,
            "updated_at": now,
        }
        # Conflictos: mismo doctor con solape de intervalos mientras esté programada
        if doc.get("provider") and doc.get("status") == "scheduled":
            prov = doc["provider"]
            new_start, new_end = start_dt, end_dt
            # Buscar posibles solapadas: start < new_end AND end > new_start
            candidates = mongo.db.citas.find({
                "provider": prov,
                "status": "scheduled",
                "start_at": {"$lt": new_end},
                "$or": [
                    {"end_at": {"$gt": new_start}},
                    {"end_at": None},
                ],
            }).limit(1)
            for c in candidates:
                c_start = c.get("start_at")
                c_end = c.get("end_at") or (c_start + timedelta(minutes=_DEFAULT_SLOT_MINUTES) if isinstance(c_start, datetime) else None)
                if isinstance(c_start, datetime) and isinstance(c_end, datetime):
                    if c_start < new_end and c_end > new_start:
                        return _fail("Conflicto: el doctor ya tiene una cita en ese intervalo", 409)

        # Insert con sesión si es posible (mejor para carreras + índice único como red)
        with start_session_if_possible() as s:
            ins = mongo.db.citas.insert_one(doc, session=s if s else None)
        return _ok({"id": str(ins.inserted_id)}, 201)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("No se pudo crear la cita", 500)


def _to_naive(dt: datetime | None) -> datetime | None:
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def listar_hoy(start_utc: datetime, end_utc: datetime, limit: int = 100):
    try:
        _ensure_indexes()
        start_utc = _to_naive(start_utc) or start_utc
        end_utc = _to_naive(end_utc) or end_utc
        cur = (
            mongo.db.citas
            .find({
                "start_at": {"$gte": start_utc, "$lte": end_utc},
                "status": "scheduled",
            })
            .sort("start_at", 1)
            .limit(int(limit) if limit else 100)
        )
        items = [_serialize(d) for d in cur]
        total = mongo.db.citas.count_documents({
            "start_at": {"$gte": start_utc, "$lte": end_utc},
            "status": "scheduled",
        })
        return _ok({"items": items, "total": total}, 200)
    except Exception:
        return _fail("Error al listar citas de hoy", 500)


def listar_proximas(start_utc: datetime, end_utc: datetime, limit: int = 200):
    try:
        _ensure_indexes()
        start_utc = _to_naive(start_utc) or start_utc
        end_utc = _to_naive(end_utc) or end_utc
        query = {"start_at": {"$gte": start_utc, "$lte": end_utc}, "status": "scheduled"}
        cur = (
            mongo.db.citas
            .find(query)
            .sort("start_at", 1)
            .limit(int(limit) if limit else 200)
        )
        items = [_serialize(d) for d in cur]
        total = mongo.db.citas.count_documents(query)
        return _ok({"items": items, "total": total}, 200)
    except Exception:
        return _fail("Error al listar próximas citas", 500)


def listar_activas(limit: int = 200, start_utc: datetime | None = None, end_utc: datetime | None = None):
    try:
        _ensure_indexes()
        query: dict = {"status": "scheduled"}
        start_utc = _to_naive(start_utc) or start_utc
        end_utc = _to_naive(end_utc) or end_utc
        if start_utc is not None or end_utc is not None:
            rng = {}
            if start_utc is not None:
                rng["$gte"] = start_utc
            if end_utc is not None:
                rng["$lte"] = end_utc
            if rng:
                query["start_at"] = rng
        cur = (
            mongo.db.citas
            .find(query)
            .sort("start_at", 1)
            .limit(int(limit) if limit else 200)
        )
        items = [_serialize(d) for d in cur]
        total = mongo.db.citas.count_documents(query)
        return _ok({"items": items, "total": total}, 200)
    except Exception:
        return _fail("Error al listar citas activas", 500)


def listar_historicas(desde_utc: datetime | None = None, hasta_utc: datetime | None = None, limit: int = 200):
    try:
        _ensure_indexes()
        query: dict = {"status": {"$in": ["completed", "cancelled"]}}
        desde_utc = _to_naive(desde_utc) or desde_utc
        hasta_utc = _to_naive(hasta_utc) or hasta_utc
        if desde_utc is not None or hasta_utc is not None:
            rng = {}
            if desde_utc is not None:
                rng["$gte"] = desde_utc
            if hasta_utc is not None:
                rng["$lte"] = hasta_utc
            if rng:
                query["start_at"] = rng
        cur = (
            mongo.db.citas
            .find(query)
            .sort("start_at", -1)
            .limit(int(limit) if limit else 200)
        )
        items = [_serialize(d) for d in cur]
        total = mongo.db.citas.count_documents(query)
        return _ok({"items": items, "total": total}, 200)
    except Exception:
        return _fail("Error al listar citas históricas", 500)


_STATUS_ENUM = {"scheduled", "completed", "cancelled"}


def actualizar_cita(cita_id: str, payload: dict):
    try:
        if not cita_id:
            return _fail("id es requerido", 422)
        oid = _oid(cita_id)
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        # Permitir campos editables desde la UI
        allowed = {"status", "title", "description", "provider", "location", "start_at", "end_at", "if_unmodified_since"}
        unknown = set(payload.keys()) - allowed
        if unknown:
            return _fail("Propiedades no permitidas en PATCH: " + ", ".join(sorted(unknown)), 422)

        upd = {}
        # status (opcional)
        if "status" in payload:
            st_raw = payload.get("status")
            if st_raw is not None:
                st = str(st_raw).strip().lower()
                if st not in _STATUS_ENUM:
                    return _fail("status inválido", 422)
                upd["status"] = st

        # textos (opcionales)
        if "title" in payload:
            upd["title"] = payload.get("title") or None
        if "description" in payload:
            upd["description"] = payload.get("description") or None
        if "provider" in payload:
            upd["provider"] = payload.get("provider") or None
        if "location" in payload:
            upd["location"] = payload.get("location") or None

        # fechas (opcionales, ISO8601)
        if "start_at" in payload:
            val = payload.get("start_at")
            if val is None:
                upd["start_at"] = None
            else:
                upd["start_at"] = _parse_iso(val, "start_at")
        if "end_at" in payload:
            val = payload.get("end_at")
            if val is None:
                upd["end_at"] = None
            else:
                upd["end_at"] = _parse_iso(val, "end_at")

        if not upd and "if_unmodified_since" not in payload:
            return _fail("Nada para actualizar", 422)

        # Antes de actualizar, comprobar conflictos si sigue programada y se cambia provider/start/end
        # Traer la cita actual para conocer valores por defecto
        current = mongo.db.citas.find_one({"_id": oid})
        if not current:
            return _fail("cita no existe", 404)

        next_status = upd.get("status", current.get("status"))
        next_provider = upd.get("provider", current.get("provider"))
        next_start = upd.get("start_at", current.get("start_at"))
        # Determinar end efectivo: payload.end_at, si no; el existente; si no; start + default
        if "end_at" in upd:
            next_end = upd.get("end_at")
        else:
            cur_end = current.get("end_at")
            next_end = cur_end if isinstance(cur_end, datetime) else (
                (next_start + timedelta(minutes=_DEFAULT_SLOT_MINUTES)) if isinstance(next_start, datetime) else None
            )

        if next_provider and next_status == "scheduled" and isinstance(next_start, datetime) and isinstance(next_end, datetime):
            # Buscar solape con otras citas activas del mismo doctor
            candidates = mongo.db.citas.find({
                "_id": {"$ne": oid},
                "provider": next_provider,
                "status": "scheduled",
                "start_at": {"$lt": next_end},
                "$or": [
                    {"end_at": {"$gt": next_start}},
                    {"end_at": None},
                ],
            }).limit(1)
            for c in candidates:
                c_start = c.get("start_at")
                c_end = c.get("end_at") or (c_start + timedelta(minutes=_DEFAULT_SLOT_MINUTES) if isinstance(c_start, datetime) else None)
                if isinstance(c_start, datetime) and isinstance(c_end, datetime):
                    if c_start < next_end and c_end > next_start:
                        return _fail("Conflicto: el doctor ya tiene una cita en ese intervalo", 409)

        # Trazabilidad: si se cambia a "cancelled" y antes no lo estaba, registrar marca temporal
        if ("status" in upd) and (upd.get("status") == "cancelled") and (current.get("status") != "cancelled"):
            upd["cancelled_at"] = datetime.utcnow()

        # Soporte de bloqueo optimista opcional
        cond_ts = None
        if "if_unmodified_since" in payload and payload.get("if_unmodified_since"):
            try:
                cond_ts = _parse_iso(payload.get("if_unmodified_since"), "if_unmodified_since")
            except ValueError:
                return _fail("if_unmodified_since no es ISO válido", 422)

        upd["updated_at"] = datetime.utcnow()
        f = {"_id": oid}
        if cond_ts is not None:
            # cond_ts viene parseado a UTC naive
            f["updated_at"] = cond_ts
        with start_session_if_possible() as s:
            res = mongo.db.citas.update_one(f, {"$set": upd}, session=s if s else None)
        if cond_ts is not None and res.modified_count == 0:
            return _fail("conflicto de edición: el recurso cambió", 409)
        return _ok({"updated": res.modified_count}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("No se pudo actualizar la cita", 500)


def eliminar_cita(cita_id: str, hard: bool = True):
    try:
        oid = _oid(cita_id)
        if hard:
            res = mongo.db.citas.delete_one({"_id": oid})
            return _ok({"deleted": res.deleted_count}, 200)
        # Soft-delete: marcar status como cancelled
        res = mongo.db.citas.update_one({"_id": oid}, {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}})
        return _ok({"deleted": res.modified_count}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("No se pudo eliminar la cita", 500)
