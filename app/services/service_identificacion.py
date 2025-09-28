from datetime import datetime
from bson import ObjectId
from app import mongo

# ================== Helpers de respuesta ==================
def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code

def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


# ================== Enums del schema ==================
_ETNIA = {"blanca", "indigena", "mestiza", "negra", "otros"}
_NIVEL = {"ninguno", "primaria", "secundaria", "universitaria"}
_ESTADO_CIVIL = {"soltera", "casada", "union_estable", "divorciada", "viuda", "otro"}

# Campos requeridos del payload (paciente_id y usuario_id vienen por firma/usuario_actual)
_REQUIRED = [
    "nombres", "apellidos", "cedula",
    "fecha_nacimiento", "edad", "etnia", "alfabeta",
    "nivel_estudios", "anio_estudios", "estado_civil", "vive_sola",
    "domicilio", "telefono", "localidad",
    "establecimiento_salud", "lugar_parto",
]


# ================== Utilidades ==================
def _to_oid(val, field):
    try:
        return ObjectId(val)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _as_int(val, field, min_v=None, max_v=None):
    try:
        iv = int(val)
    except Exception:
        raise ValueError(f"{field} debe ser entero")
    if (min_v is not None and iv < min_v) or (max_v is not None and iv > max_v):
        raise ValueError(f"{field} fuera de rango")
    return iv

def _as_bool(val, field):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and val in (0, 1):
        return bool(val)
    if isinstance(val, str) and val.lower() in ("true", "false"):
        return val.lower() == "true"
    raise ValueError(f"{field} debe ser booleano")

def _as_date_ymd(s, field):
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string (YYYY-MM-DD)")
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field} debe tener formato YYYY-MM-DD")

def _norm_enum(s, allowed, field):
    if isinstance(s, str) and s.strip() in allowed:
        return s.strip()
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(allowed))}")

def _require(payload):
    faltan = [k for k in _REQUIRED if k not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "nombres": doc.get("nombres"),
        "apellidos": doc.get("apellidos"),
        "cedula": doc.get("cedula"),
        "fecha_nacimiento": doc["fecha_nacimiento"].strftime("%Y-%m-%d") if doc.get("fecha_nacimiento") else None,
        "edad": doc.get("edad"),
        "etnia": doc.get("etnia"),
        "alfabeta": doc.get("alfabeta"),
        "nivel_estudios": doc.get("nivel_estudios"),
        "anio_estudios": doc.get("anio_estudios"),
        "estado_civil": doc.get("estado_civil"),
        "vive_sola": doc.get("vive_sola"),
        "domicilio": doc.get("domicilio"),
        "telefono": doc.get("telefono"),
        "localidad": doc.get("localidad"),
        "establecimiento_salud": doc.get("establecimiento_salud"),
        "lugar_parto": doc.get("lugar_parto"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ================== Services (CRUD) ==================
def crear_identificacion(
    paciente_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea Identificación orquestada por paciente_id.
    Requiere: paciente_id (firma), usuario_actual.usuario_id y todos los campos en _REQUIRED.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not paciente_id:
            return _fail("paciente_id es requerido", 422)
        if not usuario_actual or not usuario_actual.get("usuario_id"):
            return _fail("usuario_actual.usuario_id es requerido", 422)

        _require(payload)

        doc = {
            "paciente_id": _to_oid(paciente_id, "paciente_id"),
            "usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id"),
            "nombres": str(payload["nombres"]).strip(),
            "apellidos": str(payload["apellidos"]).strip(),
            "cedula": str(payload["cedula"]).strip(),
            "fecha_nacimiento": _as_date_ymd(payload["fecha_nacimiento"], "fecha_nacimiento"),
            "edad": _as_int(payload["edad"], "edad", min_v=0),
            "etnia": _norm_enum(payload["etnia"], _ETNIA, "etnia"),
            "alfabeta": _as_bool(payload["alfabeta"], "alfabeta"),
            "nivel_estudios": _norm_enum(payload["nivel_estudios"], _NIVEL, "nivel_estudios"),
            "anio_estudios": _as_int(payload["anio_estudios"], "anio_estudios", min_v=0),
            "estado_civil": _norm_enum(payload["estado_civil"], _ESTADO_CIVIL, "estado_civil"),
            "vive_sola": _as_bool(payload["vive_sola"], "vive_sola"),
            "domicilio": str(payload["domicilio"]).strip(),
            "telefono": str(payload["telefono"]).strip(),
            "localidad": str(payload["localidad"]).strip(),
            "establecimiento_salud": str(payload["establecimiento_salud"]).strip(),
            "lugar_parto": str(payload["lugar_parto"]).strip(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = mongo.db.identificacion.insert_one(doc, session=session) if session else mongo.db.identificacion.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar identificación: {str(e)}", 400)


def obtener_identificacion_por_id(ident_id: str):
    """GET por _id del documento de identificación."""
    try:
        oid = _to_oid(ident_id, "ident_id")
        doc = mongo.db.identificacion.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontró la identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener identificación", 400)


def get_identificacion_by_id_paciente(paciente_id: str):
    """GET por paciente_id: devuelve la identificación más reciente del paciente."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.identificacion.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró identificación para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener identificación", 400)


# ======= Helpers por paciente_id (simetría con otros services) =======
def obtener_identificacion_por_paciente(paciente_id: str):
    """Alias legible de get_identificacion_by_id_paciente."""
    return get_identificacion_by_id_paciente(paciente_id)


def actualizar_identificacion_por_id(ident_id: str, payload: dict, session=None):
    """PUT/PATCH por _id. Normaliza tipos si vienen."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(ident_id, "ident_id")
        upd = dict(payload)

        # OIDs (soporta mover a otro paciente, no recomendado pero posible)
        if "paciente_id" in upd and upd["paciente_id"]:
            upd["paciente_id"] = _to_oid(upd["paciente_id"], "paciente_id")
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # fechas
        if "fecha_nacimiento" in upd and upd["fecha_nacimiento"]:
            upd["fecha_nacimiento"] = _as_date_ymd(upd["fecha_nacimiento"], "fecha_nacimiento")

        # ints/bools
        if "edad" in upd and upd["edad"] is not None:
            upd["edad"] = _as_int(upd["edad"], "edad", min_v=0)
        for b in ("alfabeta", "vive_sola"):
            if b in upd and upd[b] is not None:
                upd[b] = _as_bool(upd[b], b)

        # enums
        if "etnia" in upd and upd["etnia"]:
            upd["etnia"] = _norm_enum(upd["etnia"], _ETNIA, "etnia")
        if "nivel_estudios" in upd and upd["nivel_estudios"]:
            upd["nivel_estudios"] = _norm_enum(upd["nivel_estudios"], _NIVEL, "nivel_estudios")
        if "estado_civil" in upd and upd["estado_civil"]:
            upd["estado_civil"] = _norm_enum(upd["estado_civil"], _ESTADO_CIVIL, "estado_civil")

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.identificacion.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("Identificación no encontrada", 404)
        return _ok({"mensaje": "Identificación actualizada"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar identificación", 400)


def actualizar_identificacion_por_paciente(paciente_id: str, payload: dict, session=None):
    """PUT/PATCH por paciente_id (sin upsert)."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        filtro = {"paciente_id": _to_oid(paciente_id, "paciente_id")}
        upd = dict(payload)

        # ids (usuario que actualiza, opcional)
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # fechas
        if "fecha_nacimiento" in upd and upd["fecha_nacimiento"]:
            upd["fecha_nacimiento"] = _as_date_ymd(upd["fecha_nacimiento"], "fecha_nacimiento")

        # enteros / bools
        if "edad" in upd and upd["edad"] is not None:
            upd["edad"] = _as_int(upd["edad"], "edad", min_v=0)

        for b in ("alfabeta", "vive_sola"):
            if b in upd and upd[b] is not None:
                upd[b] = _as_bool(upd[b], b)

        # enums
        if "etnia" in upd and upd["etnia"]:
            upd["etnia"] = _norm_enum(upd["etnia"], _ETNIA, "etnia")
        if "nivel_estudios" in upd and upd["nivel_estudios"]:
            upd["nivel_estudios"] = _norm_enum(upd["nivel_estudios"], _NIVEL, "nivel_estudios")
        if "estado_civil" in upd and upd["estado_civil"]:
            upd["estado_civil"] = _norm_enum(upd["estado_civil"], _ESTADO_CIVIL, "estado_civil")

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.identificacion.update_one(filtro, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("Identificación no encontrada para este paciente", 404)
        return _ok({"mensaje": "Identificación actualizada"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar identificación", 400)


def eliminar_identificacion_por_id(ident_id: str, session=None):
    """DELETE por _id."""
    try:
        oid = _to_oid(ident_id, "ident_id")
        res = mongo.db.identificacion.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("Identificación no encontrada", 404)
        return _ok({"mensaje": "Identificación eliminada"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar identificación", 400)


def eliminar_identificacion_por_paciente(paciente_id: str, session=None):
    """DELETE por paciente_id."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        res = mongo.db.identificacion.delete_one({"paciente_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("Identificación no encontrada para este paciente", 404)
        return _ok({"mensaje": "Identificación eliminada"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar identificación", 400)
