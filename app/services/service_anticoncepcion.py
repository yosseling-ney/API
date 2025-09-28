# app/services/service_anticoncepcion.py

from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ---------------- Enums / límites del schema ----------------
_CONSEJERIA = {"si", "no"}
_METODO = {
    "diu_post_evento",
    "diu",
    "barrera",
    "hormonal",
    "ligadura_tubaria",
    "natural",
    "otro",
    "ninguno",
}

_REQUIRED_FIELDS = ["consejeria", "metodo_elegido"]  # paciente_id viene en la firma


# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _norm_enum(v, opts, field):
    if isinstance(v, str) and (vv := v.strip()) in opts:
        return vv
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(opts))}")

def _require_fields(payload: dict):
    faltan = [f for f in _REQUIRED_FIELDS if f not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "consejeria": doc.get("consejeria"),
        "metodo_elegido": doc.get("metodo_elegido"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------- Services ----------------
def crear_anticoncepcion(
    paciente_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea el documento de 'anticoncepción' orquestado por paciente_id.
    Requiere en payload: consejeria ('si'|'no'), metodo_elegido (enum).
    Opcionales en payload: identificacion_id.
    Opcional en usuario_actual: usuario_id.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not paciente_id:
            return _fail("paciente_id es requerido", 422)

        _require_fields(payload)

        doc = {
            "paciente_id": _to_oid(paciente_id, "paciente_id"),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
               if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            "consejeria": _norm_enum(payload["consejeria"], _CONSEJERIA, "consejeria"),
            "metodo_elegido": _norm_enum(payload["metodo_elegido"], _METODO, "metodo_elegido"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = (mongo.db.anticoncepcion.insert_one(doc, session=session)
               if session else mongo.db.anticoncepcion.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar anticoncepción: {str(e)}", 400)


def obtener_anticoncepcion_por_id(ac_id: str):
    try:
        oid = _to_oid(ac_id, "ac_id")
        doc = mongo.db.anticoncepcion.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def get_anticoncepcion_by_id_paciente(paciente_id: str):
    """Devuelve el registro más reciente por paciente_id."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.anticoncepcion.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró anticoncepción para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def obtener_anticoncepcion_por_identificacion(identificacion_id: str):
    """Alternativa: obtener por identificacion_id (más reciente)."""
    try:
        oid = _to_oid(identificacion_id, "identificacion_id")
        doc = mongo.db.anticoncepcion.find_one({"identificacion_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró anticoncepción para esta identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def actualizar_anticoncepcion_por_id(ac_id: str, payload: dict, session=None):
    """
    Actualiza por _id. Re-normaliza enums si vienen.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(ac_id, "ac_id")
        upd = dict(payload)

        # ids opcionales
        if "identificacion_id" in upd and upd["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(upd["identificacion_id"], "identificacion_id")
        if "paciente_id" in upd and upd["paciente_id"]:
            upd["paciente_id"] = _to_oid(upd["paciente_id"], "paciente_id")
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # enums
        if "consejeria" in upd and upd["consejeria"] is not None:
            upd["consejeria"] = _norm_enum(upd["consejeria"], _CONSEJERIA, "consejeria")
        if "metodo_elegido" in upd and upd["metodo_elegido"] is not None:
            upd["metodo_elegido"] = _norm_enum(upd["metodo_elegido"], _METODO, "metodo_elegido")

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.anticoncepcion.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Anticoncepción actualizada"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)


def eliminar_anticoncepcion_por_id(ac_id: str, session=None):
    try:
        oid = _to_oid(ac_id, "ac_id")
        res = mongo.db.anticoncepcion.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Anticoncepción eliminada"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
