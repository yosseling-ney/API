from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Enums / límites ----------------
_DIABETES_TIPO = {"ninguna", "tipo I", "tipo II", "gestacional"}
_SI_NO = {"si", "no"}
_FRACASO_METODO = {"no_usaba", "barrera", "diu", "hormonal", "emergencia", "natural"}

_REQUIRED_FIELDS = [
    # ahora el FK principal es historial_id (se exige en la firma de crear)
    "antecedentes_familiares",
    "antecedentes_personales",
    "diabetes_tipo",
    "violencia",
    "gesta_previa",
    "partos",
    "cesareas",
    "abortos",
    "nacidos_vivos",
    "nacidos_muertos",
    "embarazo_ectopico",
    "hijos_vivos",
    "muertos_primera_semana",
    "muertos_despues_semana",
    "fecha_fin_ultimo_embarazo",
    "embarazo_planeado",
    "fracaso_metodo_anticonceptivo",
]

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

def _as_nonneg_int(v, field):
    try:
        iv = int(v)
        if iv < 0:
            raise ValueError
        return iv
    except Exception:
        raise ValueError(f"{field} debe ser entero >= 0")

def _as_bool(v, field):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise ValueError(f"{field} debe ser booleano")

def _parse_date(s, field):
    """
    Acepta 'YYYY-MM-DD' o 'DD/MM/YYYY'. Si solo viene 'YYYY-MM', asume día 01.
    """
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string")
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m":
                dt = dt.replace(day=1)
            return dt
        except ValueError:
            continue
    raise ValueError(f"{field} debe tener formato 'YYYY-MM-DD', 'DD/MM/YYYY' o 'YYYY-MM'")

def _require_fields(payload: dict):
    faltan = [f for f in _REQUIRED_FIELDS if f not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _ensure_indexes():
    try:
        mongo.db.antecedentes.create_index("historial_id", name="ix_antecedentes_historial_id")
    except Exception:
        pass
    try:
        mongo.db.antecedentes.create_index("paciente_id", name="ix_antecedentes_paciente_id")
    except Exception:
        pass

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,  # apoyo/migración
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "antecedentes_familiares": doc.get("antecedentes_familiares"),
        "antecedentes_personales": doc.get("antecedentes_personales"),
        "diabetes_tipo": doc.get("diabetes_tipo"),
        "violencia": doc.get("violencia"),
        "gesta_previa": doc.get("gesta_previa"),
        "partos": doc.get("partos"),
        "cesareas": doc.get("cesareas"),
        "abortos": doc.get("abortos"),
        "nacidos_vivos": doc.get("nacidos_vivos"),
        "nacidos_muertos": doc.get("nacidos_muertos"),
        "embarazo_ectopico": doc.get("embarazo_ectopico"),
        "hijos_vivos": doc.get("hijos_vivos"),
        "muertos_primera_semana": doc.get("muertos_primera_semana"),
        "muertos_despues_semana": doc.get("muertos_despues_semana"),
        "fecha_fin_ultimo_embarazo": (
            doc["fecha_fin_ultimo_embarazo"].strftime("%Y-%m-%d")
            if doc.get("fecha_fin_ultimo_embarazo") else None
        ),
        "embarazo_planeado": doc.get("embarazo_planeado"),
        "fracaso_metodo_anticonceptivo": doc.get("fracaso_metodo_anticonceptivo"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ---------------- Services ----------------
def crear_antecedentes(
    historial_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea antecedentes ORIENTADO A HISTORIAL:
    - historial_id (OBLIGATORIO, FK principal)
    - paciente_id e identificacion_id: OPCIONALES (apoyo/migración)
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        _require_fields(payload)
        _ensure_indexes()

        historial_oid = _to_oid(historial_id, "historial_id")

        # Validación suave: el historial debe existir
        if not mongo.db.historiales.find_one({"_id": historial_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        doc = {
            "historial_id": historial_oid,
            **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")}
               if payload.get("paciente_id") else {}),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
               if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            "antecedentes_familiares": str(payload["antecedentes_familiares"]).strip(),
            "antecedentes_personales": str(payload["antecedentes_personales"]).strip(),
            "diabetes_tipo": _norm_enum(payload["diabetes_tipo"], _DIABETES_TIPO, "diabetes_tipo"),
            "violencia": _as_bool(payload["violencia"], "violencia"),
            "gesta_previa": _as_nonneg_int(payload["gesta_previa"], "gesta_previa"),
            "partos": _as_nonneg_int(payload["partos"], "partos"),
            "cesareas": _as_nonneg_int(payload["cesareas"], "cesareas"),
            "abortos": _as_nonneg_int(payload["abortos"], "abortos"),
            "nacidos_vivos": _as_nonneg_int(payload["nacidos_vivos"], "nacidos_vivos"),
            "nacidos_muertos": _as_nonneg_int(payload["nacidos_muertos"], "nacidos_muertos"),
            "embarazo_ectopico": _as_nonneg_int(payload["embarazo_ectopico"], "embarazo_ectopico"),
            "hijos_vivos": _as_nonneg_int(payload["hijos_vivos"], "hijos_vivos"),
            "muertos_primera_semana": _as_nonneg_int(payload["muertos_primera_semana"], "muertos_primera_semana"),
            "muertos_despues_semana": _as_nonneg_int(payload["muertos_despues_semana"], "muertos_despues_semana"),
            "fecha_fin_ultimo_embarazo": _parse_date(payload["fecha_fin_ultimo_embarazo"], "fecha_fin_ultimo_embarazo"),
            "embarazo_planeado": _norm_enum(payload["embarazo_planeado"], _SI_NO, "embarazo_planeado"),
            "fracaso_metodo_anticonceptivo": _norm_enum(
                payload["fracaso_metodo_anticonceptivo"], _FRACASO_METODO, "fracaso_metodo_anticonceptivo"
            ),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = (mongo.db.antecedentes.insert_one(doc, session=session)
               if session else mongo.db.antecedentes.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar antecedentes: {str(e)}", 400)

def obtener_antecedentes_por_id(ant_id: str):
    try:
        oid = _to_oid(ant_id, "ant_id")
        doc = mongo.db.antecedentes.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

def obtener_antecedentes_por_historial(historial_id: str):
    """Devuelve el registro más reciente por historial_id."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.antecedentes.find_one({"historial_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontraron antecedentes para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

# ---- Soporte/migración (opcional): aún se puede consultar por paciente_id
def get_antecedentes_by_id_paciente(paciente_id: str):
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.antecedentes.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontraron antecedentes para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

def obtener_antecedentes_por_identificacion(identificacion_id: str):
    """Alternativa: obtener por identificacion_id (más reciente)."""
    try:
        oid = _to_oid(identificacion_id, "identificacion_id")
        doc = mongo.db.antecedentes.find_one({"identificacion_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontraron antecedentes para esta identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)

def actualizar_antecedentes_por_id(ant_id: str, payload: dict, session=None):
    """Actualiza por _id. Permite cambiar historial_id (validando existencia) y normaliza enums/bools/ints/fecha."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(ant_id, "ant_id")
        upd = dict(payload)

        # ids opcionales / FK principal puede cambiarse
        if "historial_id" in upd and upd["historial_id"] is not None:
            h_oid = _to_oid(upd["historial_id"], "historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            upd["historial_id"] = h_oid

        if "identificacion_id" in upd and upd["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(upd["identificacion_id"], "identificacion_id")
        if "paciente_id" in upd and upd["paciente_id"]:
            upd["paciente_id"] = _to_oid(upd["paciente_id"], "paciente_id")
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # enums
        if "diabetes_tipo" in upd and upd["diabetes_tipo"] is not None:
            upd["diabetes_tipo"] = _norm_enum(upd["diabetes_tipo"], _DIABETES_TIPO, "diabetes_tipo")
        if "embarazo_planeado" in upd and upd["embarazo_planeado"] is not None:
            upd["embarazo_planeado"] = _norm_enum(upd["embarazo_planeado"], _SI_NO, "embarazo_planeado")
        if "fracaso_metodo_anticonceptivo" in upd and upd["fracaso_metodo_anticonceptivo"] is not None:
            upd["fracaso_metodo_anticonceptivo"] = _norm_enum(
                upd["fracaso_metodo_anticonceptivo"], _FRACASO_METODO, "fracaso_metodo_anticonceptivo"
            )

        # bools
        if "violencia" in upd and upd["violencia"] is not None:
            upd["violencia"] = _as_bool(upd["violencia"], "violencia")

        # ints
        for k in (
            "gesta_previa", "partos", "cesareas", "abortos",
            "nacidos_vivos", "nacidos_muertos", "embarazo_ectopico",
            "hijos_vivos", "muertos_primera_semana", "muertos_despues_semana"
        ):
            if k in upd and upd[k] is not None:
                upd[k] = _as_nonneg_int(upd[k], k)

        # fecha
        if "fecha_fin_ultimo_embarazo" in upd and upd["fecha_fin_ultimo_embarazo"]:
            upd["fecha_fin_ultimo_embarazo"] = _parse_date(upd["fecha_fin_ultimo_embarazo"], "fecha_fin_ultimo_embarazo")

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.antecedentes.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Antecedentes actualizados"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)

def eliminar_antecedentes_por_id(ant_id: str, session=None):
    try:
        oid = _to_oid(ant_id, "ant_id")
        res = mongo.db.antecedentes.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Antecedentes eliminados"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)

def eliminar_antecedentes_por_historial_id(historial_id: str, session=None):
    try:
        oid = _to_oid(historial_id, "historial_id")
        res = mongo.db.antecedentes.delete_many({"historial_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontraron documentos para este historial", 404)
        return _ok({"mensaje": f"Se eliminaron {res.deleted_count} antecedentes"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)

# soporte previo si aún lo usas en limpiezas antiguas
def eliminar_antecedentes_por_paciente_id(paciente_id: str, session=None):
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        res = mongo.db.antecedentes.delete_many({"paciente_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontraron documentos para este paciente", 404)
        return _ok({"mensaje": f"Se eliminaron {res.deleted_count} antecedentes"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
