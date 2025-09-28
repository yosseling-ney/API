from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ---------------- Enums / validaciones del schema ----------------
_SI_NO_MIN = {"si", "no"}                                   # para la mayoría de flags string
_RES_SIF_VIH = {"positivo", "negativo", "n_r", "n_c"}       # TDP pruebas
_TARV = {"si", "no", "n_c"}
_HEM_TRIM = {"1_trim", "2_trim", "3_trim", "postparto", "infec_puerperal", "ninguno"}

# enfermedades (todas si/no en minúsculas)
_ENF_KEYS = [
    "hta_previa", "hta_inducida_embarazo", "preeclampsia", "eclampsia",
    "cardiopatia", "nefropatia", "diabetes", "infeccion_ovular",
    "infeccion_urinaria", "amenaza_parto_preter", "rciu",
    "rotura_premembranas", "anemia", "otra_cond_grave"
]


# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _require(payload: dict, fields: list[str], where: str = ""):
    faltan = [f for f in fields if f not in payload]
    if faltan:
        pref = f"{where}: " if where else ""
        raise ValueError(pref + "Campos requeridos faltantes: " + ", ".join(faltan))

def _norm_enum(v, opts: set[str], field: str):
    if isinstance(v, str) and v.strip() in opts:
        return v.strip()
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(opts))}")

def _as_bool(v, field: str):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise ValueError(f"{field} debe ser booleano")

def _serialize(doc: dict):
    """Convierte ObjectIds/fechas a string para respuesta."""
    out = {
        "id": str(doc["_id"]),
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "enfermedades": doc.get("enfermedades"),
        "resumen": doc.get("resumen"),
        "hemorragia": doc.get("hemorragia"),
        "tdp": doc.get("tdp"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    return out


# ---------------- Builders ----------------
def _build_enfermedades(enf: dict) -> dict:
    _require(enf, _ENF_KEYS, "enfermedades")
    dto = {}
    for k in _ENF_KEYS:
        dto[k] = _norm_enum(enf[k], _SI_NO_MIN, f"enfermedades.{k}")
    return dto

def _build_resumen(res: dict) -> dict:
    _require(res, ["ninguna", "uno_o_mas"], "resumen")
    return {
        "ninguna": _as_bool(res["ninguna"], "resumen.ninguna"),
        "uno_o_mas": _as_bool(res["uno_o_mas"], "resumen.uno_o_mas"),
    }

def _build_hemorragia(he: dict) -> dict:
    _require(he, ["hemorragia_ocurrio", "trimestre", "codigo"], "hemorragia")
    dto = {
        "hemorragia_ocurrio": _norm_enum(he["hemorragia_ocurrio"], _SI_NO_MIN, "hemorragia.hemorragia_ocurrio"),
        "trimestre": _norm_enum(he["trimestre"], _HEM_TRIM, "hemorragia.trimestre"),
    }
    cod = he.get("codigo", [])
    if not isinstance(cod, list):
        raise ValueError("hemorragia.codigo debe ser arreglo de strings (máx 3)")
    if len(cod) > 3:
        raise ValueError("hemorragia.codigo admite hasta 3 códigos")
    dto["codigo"] = [str(x) for x in cod]
    return dto

def _build_tdp(tdp: dict) -> dict:
    _require(tdp, ["prueba_sifilis", "prueba_vih", "tarv"], "tdp")
    return {
        "prueba_sifilis": _norm_enum(tdp["prueba_sifilis"], _RES_SIF_VIH, "tdp.prueba_sifilis"),
        "prueba_vih": _norm_enum(tdp["prueba_vih"], _RES_SIF_VIH, "tdp.prueba_vih"),
        "tarv": _norm_enum(tdp["tarv"], _TARV, "tdp.tarv"),
    }

def _build_doc(paciente_id: str, payload: dict, usuario_actual: dict | None):
    _require(payload, ["enfermedades", "resumen", "hemorragia", "tdp"])
    return {
        "paciente_id": _to_oid(paciente_id, "paciente_id"),
        # identificacion_id puede venir o no (lo dejamos opcional por orquestación)
        **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
           if payload.get("identificacion_id") else {}),
        "usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id") if (usuario_actual and usuario_actual.get("usuario_id")) else None,
        "enfermedades": _build_enfermedades(payload["enfermedades"]),
        "resumen": _build_resumen(payload["resumen"]),
        "hemorragia": _build_hemorragia(payload["hemorragia"]),
        "tdp": _build_tdp(payload["tdp"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ---------------- Services ----------------
def crear_patologias(paciente_id: str, payload: dict, session=None, usuario_actual: dict | None = None):
    """Crea el documento de patologías para un paciente (orquestado por paciente_id)."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not paciente_id:
            return _fail("paciente_id es requerido", 422)

        doc = _build_doc(paciente_id, payload, usuario_actual)
        res = mongo.db.patologias.insert_one(doc, session=session) if session else mongo.db.patologias.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar patologías: {str(e)}", 400)


def obtener_patologias_por_id(pat_id: str):
    try:
        oid = _to_oid(pat_id, "pat_id")
        doc = mongo.db.patologias.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def get_patologias_by_id_paciente(paciente_id: str):
    """Devuelve la más reciente por paciente_id (para el GET agregado/orquestador)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.patologias.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró registro de patologías para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def actualizar_patologias_por_id(pat_id: str, payload: dict, session=None):
    """Actualiza por _id. Re-valida y normaliza únicamente los campos presentes."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(pat_id, "pat_id")
        upd = {}

        # opcionalmente mover vínculos
        if "paciente_id" in payload and payload["paciente_id"]:
            upd["paciente_id"] = _to_oid(payload["paciente_id"], "paciente_id")
        if "identificacion_id" in payload and payload["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(payload["identificacion_id"], "identificacion_id")
        if "usuario_id" in payload and payload["usuario_id"]:
            upd["usuario_id"] = _to_oid(payload["usuario_id"], "usuario_id")

        # bloques anidados
        if "enfermedades" in payload and payload["enfermedades"]:
            upd["enfermedades"] = _build_enfermedades(payload["enfermedades"])

        if "resumen" in payload and payload["resumen"]:
            upd["resumen"] = _build_resumen(payload["resumen"])

        if "hemorragia" in payload and payload["hemorragia"]:
            upd["hemorragia"] = _build_hemorragia(payload["hemorragia"])

        if "tdp" in payload and payload["tdp"]:
            upd["tdp"] = _build_tdp(payload["tdp"])

        if not upd:
            return _fail("Nada para actualizar", 422)

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.patologias.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Patologías actualizadas"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)


def eliminar_patologias_por_id(pat_id: str, session=None):
    try:
        oid = _to_oid(pat_id, "pat_id")
        res = mongo.db.patologias.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Patologías eliminadas"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
