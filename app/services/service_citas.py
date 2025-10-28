from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from bson import ObjectId
from flask import current_app
from app import mongo


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


def _parse_iso(s: str, field: str) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser un string ISO 8601")
    ss = s.strip()
    if ss.endswith("Z"):
        ss = ss[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ss)
    except Exception:
        raise ValueError(f"{field} no es un ISO 8601 válido")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize(doc: dict) -> dict:
    return {
        "_id": str(doc.get("_id")),
        "paciente_id": str(doc.get("paciente_id")) if isinstance(doc.get("paciente_id"), ObjectId) else (doc.get("paciente_id") or None),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "provider": doc.get("provider"),
        "status": doc.get("status"),
        "start_at": (doc.get("start_at").isoformat().replace("+00:00", "Z") if isinstance(doc.get("start_at"), datetime) else doc.get("start_at")),
        "end_at": (doc.get("end_at").isoformat().replace("+00:00", "Z") if isinstance(doc.get("end_at"), datetime) else doc.get("end_at")),
        "created_at": (doc.get("created_at").isoformat().replace("+00:00", "Z") if isinstance(doc.get("created_at"), datetime) else doc.get("created_at")),
        "updated_at": (doc.get("updated_at").isoformat().replace("+00:00", "Z") if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at")),
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
        # status opcional (default scheduled)
        st_in = payload.get("status")
        status_val = "scheduled"
        if st_in is not None:
            st = str(st_in).strip().lower()
            if st not in _STATUS_ENUM:
                return _fail("status inválido", 422)
            status_val = st

        now = datetime.now(timezone.utc)
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

        ins = mongo.db.citas.insert_one(doc)
        return _ok({"id": str(ins.inserted_id)}, 201)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("No se pudo crear la cita", 500)


def listar_hoy(start_utc: datetime, end_utc: datetime, limit: int = 100):
    try:
        _ensure_indexes()
        cur = (
            mongo.db.citas
            .find({"start_at": {"$gte": start_utc, "$lte": end_utc}})
            .sort("start_at", 1)
            .limit(int(limit) if limit else 100)
        )
        items = [_serialize(d) for d in cur]
        total = mongo.db.citas.count_documents({"start_at": {"$gte": start_utc, "$lte": end_utc}})
        return _ok({"items": items, "total": total}, 200)
    except Exception:
        return _fail("Error al listar citas de hoy", 500)


def listar_proximas(start_utc: datetime, end_utc: datetime, limit: int = 200):
    try:
        _ensure_indexes()
        query = {"start_at": {"$gte": start_utc, "$lte": end_utc}}
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


_STATUS_ENUM = {"scheduled", "completed", "cancelled"}


def actualizar_cita(cita_id: str, payload: dict):
    try:
        if not cita_id:
            return _fail("id es requerido", 422)
        oid = _oid(cita_id)
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        # Permitir campos editables desde la UI
        allowed = {"status", "title", "description", "provider", "location", "start_at", "end_at"}
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

        if not upd:
            return _fail("Nada para actualizar", 422)

        upd["updated_at"] = datetime.now(timezone.utc)
        res = mongo.db.citas.update_one({"_id": oid}, {"$set": upd})
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
        res = mongo.db.citas.update_one({"_id": oid}, {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}})
        return _ok({"deleted": res.modified_count}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("No se pudo eliminar la cita", 500)
