from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Constantes / Enums ----------------
_INVOL_UTER = {"cont", "flac", "otra"}
_SI_NO_NC   = {"si", "no", "n_c"}

_TEMP_MIN, _TEMP_MAX = 30.0, 45.0   # °C
_SIS_MIN, _SIS_MAX   = 50, 250      # mmHg
_DIA_MIN, _DIA_MAX   = 30, 150      # mmHg
_PUL_MIN, _PUL_MAX   = 30, 220      # lpm

# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _ensure_indexes():
    try:
        mongo.db.puerperio.create_index("historial_id", name="ix_puer_historial")
    except Exception:
        pass
    # compat
    try:
        mongo.db.puerperio.create_index("paciente_id", name="ix_puer_paciente")
    except Exception:
        pass

def _require(payload: dict, fields: list[str], where: str = ""):
    faltan = [f for f in fields if f not in payload]
    if faltan:
        pref = f"{where}: " if where else ""
        raise ValueError(pref + "Campos requeridos faltantes: " + ", ".join(faltan))

def _norm_enum(v, opts: set[str], field: str):
    if isinstance(v, str) and v.strip() in opts:
        return v.strip()
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(opts))}")

def _as_float(v, field):
    try:
        return float(v)
    except Exception:
        raise ValueError(f"{field} debe ser numérico")

def _as_float_in_range(v, field, lo=None, hi=None):
    x = _as_float(v, field)
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError(f"{field} fuera de rango permitido [{lo}, {hi}]")
    return x

def _as_int_in_range(v, field, lo=None, hi=None):
    try:
        x = int(v)
    except Exception:
        raise ValueError(f"{field} debe ser entero")
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError(f"{field} fuera de rango permitido [{lo}, {hi}]")
    return x

def _as_datetime(s, field):
    if isinstance(s, datetime):
        return s
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string con fecha/hora")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            pass
    raise ValueError(f"{field} debe tener formato 'YYYY-MM-DD HH:MM' (o ISO)")

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,  # compat
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "puerperio_inmediato": [
            {
                "dia_hora": (r["dia_hora"].isoformat() if isinstance(r.get("dia_hora"), datetime) else r.get("dia_hora")),
                "temperatura": r.get("temperatura"),
                "presion_arterial": r.get("presion_arterial"),
                "pulso": r.get("pulso"),
                "involucion_uterina": r.get("involucion_uterina"),
                "loquios": r.get("loquios"),
            } for r in (doc.get("puerperio_inmediato") or [])
        ],
        "antirrubeola_postparto": doc.get("antirrubeola_postparto"),
        "gammaglobulina_anti_d": doc.get("gammaglobulina_anti_d"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ---------------- Builders ----------------
def _build_registro_puerperio(r: dict) -> dict:
    _require(
        r,
        ["dia_hora", "temperatura", "presion_arterial", "pulso", "involucion_uterina", "loquios"],
        "puerperio_inmediato[]"
    )
    pa = r["presion_arterial"]
    if not isinstance(pa, dict):
        raise ValueError("presion_arterial debe ser objeto {sistolica, diastolica}")
    _require(pa, ["sistolica", "diastolica"], "presion_arterial")

    return {
        "dia_hora": _as_datetime(r["dia_hora"], "dia_hora"),
        "temperatura": _as_float_in_range(r["temperatura"], "temperatura", _TEMP_MIN, _TEMP_MAX),
        "presion_arterial": {
            "sistolica": _as_int_in_range(pa["sistolica"], "presion_arterial.sistolica", _SIS_MIN, _SIS_MAX),
            "diastolica": _as_int_in_range(pa["diastolica"], "presion_arterial.diastolica", _DIA_MIN, _DIA_MAX),
        },
        "pulso": _as_int_in_range(r["pulso"], "pulso", _PUL_MIN, _PUL_MAX),
        "involucion_uterina": _norm_enum(r["involucion_uterina"], _INVOL_UTER, "involucion_uterina"),
        "loquios": str(r["loquios"]),
    }

def _build_doc(historial_id: str, payload: dict, usuario_actual: dict | None):
    _require(payload, ["puerperio_inmediato", "antirrubeola_postparto", "gammaglobulina_anti_d"])
    if not isinstance(payload["puerperio_inmediato"], list):
        raise ValueError("puerperio_inmediato debe ser un arreglo de registros")

    return {
        "historial_id": _to_oid(historial_id, "historial_id"),
        # compat: permitir guardar paciente_id si viene
        **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")}
           if payload.get("paciente_id") else {}),
        **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
           if payload.get("identificacion_id") else {}),
        **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
           if usuario_actual and usuario_actual.get("usuario_id") else {}),
        "puerperio_inmediato": [_build_registro_puerperio(x) for x in payload["puerperio_inmediato"]],
        "antirrubeola_postparto": _norm_enum(payload["antirrubeola_postparto"], _SI_NO_NC, "antirrubeola_postparto"),
        "gammaglobulina_anti_d": _norm_enum(payload["gammaglobulina_anti_d"], _SI_NO_NC, "gammaglobulina_anti_d"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

# ---------------- Services ----------------
def crear_puerperio(historial_id: str, payload: dict, session=None, usuario_actual: dict | None = None):
    """Crea registro de puerperio inmediato (FK principal: historial_id)."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        _ensure_indexes()

        # validar existencia del historial
        h_oid = _to_oid(historial_id, "historial_id")
        if not mongo.db.historiales.find_one({"_id": h_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        doc = _build_doc(historial_id, payload, usuario_actual)
        res = mongo.db.puerperio.insert_one(doc, session=session) if session else mongo.db.puerperio.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar puerperio: {str(e)}", 400)

def obtener_puerperio_por_id(pue_id: str):
    try:
        oid = _to_oid(pue_id, "pue_id")
        doc = mongo.db.puerperio.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

def obtener_puerperio_por_historial(historial_id: str):
    """Devuelve el registro más reciente por historial_id."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.puerperio.find_one({"historial_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró puerperio para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

# -------- Compat por paciente_id (apoyo de migración) --------
def get_puerperio_by_id_paciente(paciente_id: str):
    """Devuelve el registro más reciente por paciente_id (compatibilidad)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.puerperio.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró puerperio para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

def actualizar_puerperio_por_id(pue_id: str, payload: dict, session=None):
    """Actualiza por _id. Normaliza y valida lo que venga. Soporta mover entre historiales validando existencia."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(pue_id, "pue_id")
        upd = {}

        # FK principal: historial_id (si viene, validar)
        if "historial_id" in payload and payload["historial_id"] is not None:
            h_oid = _to_oid(payload["historial_id"], "historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            upd["historial_id"] = h_oid

        # Re-vínculos opcionales (compat)
        if "paciente_id" in payload and payload["paciente_id"]:
            upd["paciente_id"] = _to_oid(payload["paciente_id"], "paciente_id")
        if "identificacion_id" in payload and payload["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(payload["identificacion_id"], "identificacion_id")
        if "usuario_id" in payload and payload["usuario_id"]:
            upd["usuario_id"] = _to_oid(payload["usuario_id"], "usuario_id")

        # Bloques
        if "puerperio_inmediato" in payload and payload["puerperio_inmediato"] is not None:
            if not isinstance(payload["puerperio_inmediato"], list):
                return _fail("puerperio_inmediato debe ser arreglo", 422)
            upd["puerperio_inmediato"] = [_build_registro_puerperio(x) for x in payload["puerperio_inmediato"]]

        for f, enum in [
            ("antirrubeola_postparto", _SI_NO_NC),
            ("gammaglobulina_anti_d", _SI_NO_NC),
        ]:
            if f in payload and payload[f] is not None:
                upd[f] = _norm_enum(payload[f], enum, f)

        if not upd:
            return _fail("Nada para actualizar", 422)

        upd["updated_at"] = datetime.utcnow()
        res = mongo.db.puerperio.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Puerperio actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)

def eliminar_puerperio_por_id(pue_id: str, session=None):
    try:
        oid = _to_oid(pue_id, "pue_id")
        res = mongo.db.puerperio.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Puerperio eliminado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
