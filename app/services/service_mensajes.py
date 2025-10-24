from datetime import datetime, timezone
from typing import Optional, Tuple, Any, Dict

from bson import ObjectId
from app import mongo


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(val: Optional[str]) -> Optional[ObjectId]:
    """Convierte a ObjectId tolerando espacios, mayúsculas y separadores.

    - trim
    - intento directo
    - si falla, elimina cualquier carácter no hex y reintenta
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return ObjectId(s)
    except Exception:
        pass
    # Intento con solo hex (elimina separadores invisibles o erróneos)
    import re as _re
    s2 = _re.sub(r"[^0-9a-fA-F]", "", s)
    if len(s2) == 24:
        try:
            return ObjectId(s2)
        except Exception:
            return None
    return None


def _serialize(doc: dict | None) -> Optional[dict]:
    if not doc:
        return None
    out = dict(doc)
    for k in ("_id", "paciente_id", "created_by"):
        if out.get(k):
            out[k] = str(out[k])
    if isinstance(out.get("created_at"), datetime):
        out["created_at"] = out["created_at"].isoformat()
    if isinstance(out.get("scheduled_at"), datetime):
        out["scheduled_at"] = out["scheduled_at"].isoformat()
    if isinstance(out.get("sent_at"), datetime):
        out["sent_at"] = out["sent_at"].isoformat()
    return out


def crear_mensaje(data: Dict[str, Any], *, session=None) -> Tuple[dict, int]:
    """Crea un mensaje simple asociado a un paciente.

    Requeridos: paciente_id (str), description (str)
    Opcionales: title (str), type (str: 'message'|'reminder'), scheduled_at (ISO8601)
    """
    paciente_oid = _oid((data.get("paciente_id") or "").strip())
    description = (data.get("description") or "").strip()
    title = (data.get("title") or "").strip() or None
    tipo = (data.get("type") or "message").strip() or "message"

    if not paciente_oid:
        return {"ok": False, "data": None, "error": "paciente_id invalido"}, 422
    if not description:
        return {"ok": False, "data": None, "error": "description es requerido"}, 422

    scheduled_at = data.get("scheduled_at")
    if isinstance(scheduled_at, str) and scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at)
        except Exception:
            return {"ok": False, "data": None, "error": "scheduled_at debe ser ISO8601"}, 422
    else:
        scheduled_at = None

    doc = {
        "paciente_id": paciente_oid,
        "title": title,
        "description": description,
        "type": tipo,
        "created_at": _now(),
        "created_by": _oid((data.get("created_by") or "").strip()),
        "read": False,
        "scheduled_at": scheduled_at,
        "sent_at": None,
    }

    if scheduled_at is None and tipo == "message":
        doc["sent_at"] = doc["created_at"]

    if session:
        res = mongo.db.mensajes.insert_one(doc, session=session)
    else:
        res = mongo.db.mensajes.insert_one(doc)

    return {"ok": True, "data": {"id": str(res.inserted_id)} , "error": None}, 201


def listar_mensajes(*, paciente_id: Optional[str] = None, page: int = 1, per_page: int = 20) -> Tuple[dict, int]:
    page = max(1, int(page or 1))
    per_page = max(1, min(100, int(per_page or 20)))
    q: Dict[str, Any] = {"deleted": {"$ne": True}}
    if paciente_id:
        oid = _oid(paciente_id)
        if not oid:
            return {"ok": False, "data": None, "error": "paciente_id invalido"}, 422
        q["paciente_id"] = oid

    cursor = mongo.db.mensajes.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
    items = [
        _serialize(doc) for doc in cursor
    ]
    total = mongo.db.mensajes.count_documents(q)
    data = {"items": items, "page": page, "per_page": per_page, "total": total}
    return {"ok": True, "data": data, "error": None}, 200


def marcar_leido(mensaje_id: str, *, session=None) -> Tuple[dict, int]:
    oid = _oid(mensaje_id)
    if not oid:
        return {"ok": False, "data": None, "error": "id invalido"}, 422
    upd = {"$set": {"read": True}}
    if session:
        res = mongo.db.mensajes.update_one({"_id": oid}, upd, session=session)
    else:
        res = mongo.db.mensajes.update_one({"_id": oid}, upd)
    if res.matched_count == 0:
        return {"ok": False, "data": None, "error": "no_encontrado"}, 404
    return {"ok": True, "data": {"updated": 1}, "error": None}, 200


def actualizar_mensaje(mensaje_id: str, data: Dict[str, Any], *, session=None) -> Tuple[dict, int]:
    oid = _oid(mensaje_id)
    if not oid:
        return {"ok": False, "data": None, "error": "id invalido"}, 422
    if not isinstance(data, dict):
        return {"ok": False, "data": None, "error": "JSON invalido"}, 400

    upd: Dict[str, Any] = {}

    if "title" in data:
        t = data.get("title")
        if t is not None:
            if not isinstance(t, str):
                return {"ok": False, "data": None, "error": "title debe ser string"}, 422
            t = t.strip()
        upd["title"] = t or None

    if "description" in data:
        d = data.get("description")
        if not isinstance(d, str) or not d.strip():
            return {"ok": False, "data": None, "error": "description debe ser string no vacio"}, 422
        upd["description"] = d.strip()

    if "type" in data:
        tp = (data.get("type") or "").strip()
        if tp not in ("message", "reminder"):
            return {"ok": False, "data": None, "error": "type debe ser 'message' o 'reminder'"}, 422
        upd["type"] = tp

    if "scheduled_at" in data:
        sa = data.get("scheduled_at")
        if sa in (None, ""):
            upd["scheduled_at"] = None
        elif isinstance(sa, str):
            try:
                upd["scheduled_at"] = datetime.fromisoformat(sa)
            except Exception:
                return {"ok": False, "data": None, "error": "scheduled_at debe ser ISO8601"}, 422
        elif isinstance(sa, datetime):
            upd["scheduled_at"] = sa
        else:
            return {"ok": False, "data": None, "error": "scheduled_at invalido"}, 422

    if "read" in data:
        r = data.get("read")
        if not isinstance(r, bool):
            return {"ok": False, "data": None, "error": "read debe ser booleano"}, 422
        upd["read"] = r

    if not upd:
        return {"ok": True, "data": {"updated": 0, "mensaje": "Nada para actualizar"}, "error": None}, 200

    if session:
        res = mongo.db.mensajes.update_one({"_id": oid}, {"$set": upd}, session=session)
    else:
        res = mongo.db.mensajes.update_one({"_id": oid}, {"$set": upd})
    if res.matched_count == 0:
        return {"ok": False, "data": None, "error": "no_encontrado"}, 404
    return {"ok": True, "data": {"updated": 1}, "error": None}, 200

def eliminar_mensaje(mensaje_id: str, *, hard: bool = False, session=None) -> Tuple[dict, int]:
    oid = _oid(mensaje_id)
    if not oid:
        return {"ok": False, "data": None, "error": "id invalido"}, 422
    if hard:
        if session:
            res = mongo.db.mensajes.delete_one({"_id": oid}, session=session)
        else:
            res = mongo.db.mensajes.delete_one({"_id": oid})
        if res.deleted_count == 0:
            return {"ok": False, "data": None, "error": "no_encontrado"}, 404
        return {"ok": True, "data": {"deleted": 1}, "error": None}, 200
    else:
        upd = {"$set": {"deleted": True, "deleted_at": _now()}}
        if session:
            res = mongo.db.mensajes.update_one({"_id": oid}, upd, session=session)
        else:
            res = mongo.db.mensajes.update_one({"_id": oid}, upd)
        if res.matched_count == 0:
            return {"ok": False, "data": None, "error": "no_encontrado"}, 404
        return {"ok": True, "data": {"deleted": 1}, "error": None}, 200
