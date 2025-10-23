from datetime import datetime 
from dateutil.relativedelta import relativedelta 
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Enums / límites ----------------
_DIABETES_TIPO = {"ninguna", "tipo I", "tipo II", "gestacional"}
_SI_NO = {"si", "no"}
_FRACASO_METODO = {"no_usaba", "barrera", "diu", "hormonal", "emergencia", "natural"}

#  enum de tiempo desde el último embarazo
_TIEMPO_INTERVALOS = {"< 1 año", "1 a < 2 años", "2 a < 5 años", ">= 5 años"}

#  enum de peso del RN del último embarazo (según tu JSON Schema)
_PESO_ULTIMO_PREVIO_ENUM = {
    "menor a 2500g",
    "entre 2500g y 4000g",
    "mayor a 4000g",
    "no aplica/sin dato",
}

_REQUIRED_FIELDS = [
    "antecedentes_familiares",
    "antecedentes_personales",
    "gesta_previa",
    "partos",
    "cesareas",
    "vaginales",
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
    if isinstance(v, str):
        vv = v.strip()
        if vv in opts:
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

#  helper para clasificar el intervalo desde FFUE a fecha de referencia
def _clasificar_tiempo_desde_ultimo_embarazo(ffue: datetime, ref: datetime | None = None) -> str:
    """
    Devuelve uno de: < 1 año | 1 a < 2 años | 2 a < 5 años | >= 5 años
    ref por defecto: ahora (UTC). Si luego tienes la FUR del embarazo actual, puedes cambiar 'ref'.
    """
    if not ref:
        ref = datetime.utcnow()
    if ffue > ref:
        # Si llega una fecha en el futuro por error, normalizamos a '< 1 año'
        return "< 1 año"
    delta = relativedelta(ref, ffue)
    meses = delta.years * 12 + delta.months
    if meses < 12:
        return "< 1 año"
    if 12 <= meses < 24:
        return "1 a < 2 años"
    if 24 <= meses < 60:
        return "2 a < 5 años"
    return ">= 5 años"

# mapping de etiquetas legacy del front a enum del schema
def _map_peso_client_to_schema(v: str | None) -> str | None:
    if v is None:
        return None
    vv = str(v).strip()
    mapping = {
        "< 2500g": "menor a 2500g",
        "normal/n/c": "entre 2500g y 4000g",
        "> 4000g": "mayor a 4000g",
        "no_aplica": "no aplica/sin dato",
    }
    # Si ya viene en formato schema, respétalo
    if vv in _PESO_ULTIMO_PREVIO_ENUM:
        return vv
    return mapping.get(vv)

# Compatibilidad: mapeo de claves "legacy" del payload a las actuales
def _compat_map_legacy(payload: dict, for_update: bool = False) -> dict:
    """
    Mapea posibles nombres de campos legacy a los usados por el servicio.
    Es conservador: si no encuentra sinónimos, devuelve el payload tal cual.

    Ejemplos mapeados:
      - fecha_ultimo_embarazo, ffue -> fecha_fin_ultimo_embarazo
      - fracaso_metodo -> fracaso_metodo_anticonceptivo
      - tiempo_ultimo_embarazo -> tiempo_desde_ultimo_embarazo
      - familiares/personales -> antecedentes_familiares/antecedentes_personales
      - gemelares -> antecedente_gemelares (dentro de antecedentes_personales)
      - booleano en embarazo_planeado True/False -> "si"/"no"
    """
    if not isinstance(payload, dict):
        return payload

    out = dict(payload)

    # ---- Raíz: sinónimos de campos
    if "fecha_fin_ultimo_embarazo" not in out:
        for k in ("fecha_ultimo_embarazo", "ffue", "fecha_fin_ult_embarazo"):
            if k in out and out[k]:
                out["fecha_fin_ultimo_embarazo"] = out.pop(k)
                break

    if "fracaso_metodo_anticonceptivo" not in out and "fracaso_metodo" in out:
        out["fracaso_metodo_anticonceptivo"] = out.pop("fracaso_metodo")

    if "tiempo_desde_ultimo_embarazo" not in out and "tiempo_ultimo_embarazo" in out:
        out["tiempo_desde_ultimo_embarazo"] = out.pop("tiempo_ultimo_embarazo")

    # En algunos payloads antiguos venían como "familiares"/"personales"
    if "antecedentes_familiares" not in out and isinstance(out.get("familiares"), dict):
        out["antecedentes_familiares"] = out.pop("familiares")
    if "antecedentes_personales" not in out and isinstance(out.get("personales"), dict):
        out["antecedentes_personales"] = out.pop("personales")

    # Normalizar embarazo_planeado si vino como booleano
    if "embarazo_planeado" in out and isinstance(out["embarazo_planeado"], bool):
        out["embarazo_planeado"] = "si" if out["embarazo_planeado"] else "no"

    # Ids alternativos
    if "paciente_id" not in out and out.get("paciente"):
        out["paciente_id"] = out.pop("paciente")
    if "identificacion_id" not in out and out.get("identificacion"):
        out["identificacion_id"] = out.pop("identificacion")
    if "usuario_id" not in out and out.get("usuario"):
        out["usuario_id"] = out.pop("usuario")

    # ---- Subdocumento: antecedentes_personales
    ap = out.get("antecedentes_personales")
    if isinstance(ap, dict):
        if "antecedente_gemelares" not in ap and "gemelares" in ap:
            ap["antecedente_gemelares"] = ap.pop("gemelares")
        # Aceptar sinónimo tipo_diabetes -> diabetes_tipo
        if "diabetes_tipo" not in ap and ap.get("tipo_diabetes"):
            ap["diabetes_tipo"] = ap.pop("tipo_diabetes")
        # Aceptar peso_ultimo_previo legacy como ya manejado por _map_peso_client_to_schema más adelante
        # No transformamos aquí valores; solo dejamos el campo si vino con otro nombre
        if "peso_ultimo_previo" not in ap and ap.get("peso_rn_ultimo_embarazo") is not None:
            ap["peso_ultimo_previo"] = ap.pop("peso_rn_ultimo_embarazo")

    # Para crear, si faltan bloques, inicializar diccionarios vacíos
    if not for_update:
        out.setdefault("antecedentes_familiares", {})
        out.setdefault("antecedentes_personales", {})

    return out

# Validación de Coherencia Obstétrica 
def _validate_obstetric_coherence(data: dict):
    gesta_previa = data.get("gesta_previa", -1)
    partos    = int(data.get("partos", 0) or 0)
    cesareas  = int(data.get("cesareas", 0) or 0)
    vaginales = int(data.get("vaginales", 0) or 0)
    abortos   = int(data.get("abortos", 0) or 0)
    ectopico  = int(data.get("embarazo_ectopico", 0) or 0)

    if gesta_previa == 0:
        campos_a_cero = [
            "partos", "cesareas", "vaginales", "abortos",
            "nacidos_vivos", "nacidos_muertos", "embarazo_ectopico",
            "hijos_vivos", "muertos_primera_semana", "muertos_despues_semana"
        ]
        for campo in campos_a_cero:
            valor = data.get(campo)
            if valor is not None and int(valor) != 0:
                raise ValueError(
                    f"Inconsistencia de datos: Si 'gesta_previa' es 0, '{campo}' debe ser 0."
                )

    if partos != cesareas + vaginales:
        raise ValueError("Inconsistencia de datos: 'partos' debe ser igual a 'vaginales + cesareas'.")
    if cesareas > partos:
        raise ValueError("Inconsistencia de datos: 'cesareas' no puede superar 'partos'.")
    if vaginales > partos:
        raise ValueError("Inconsistencia de datos: 'vaginales' no puede superar 'partos'.")

    if gesta_previa > 0:
        total_eventos = partos + abortos + ectopico
        if total_eventos > gesta_previa:
            raise ValueError(
                "Inconsistencia de datos: La suma de Partos, Abortos y Embarazos Ectópicos no puede superar la 'gesta_previa'."
            )

# ======================================================================
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
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "antecedentes_familiares": doc.get("antecedentes_familiares"),
        "antecedentes_personales": doc.get("antecedentes_personales"),
        "gesta_previa": doc.get("gesta_previa"),
        "partos": doc.get("partos"),
        "cesareas": doc.get("cesareas"),
        "vaginales": doc.get("vaginales"),
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
        # NUEVO:
        "tiempo_desde_ultimo_embarazo": doc.get("tiempo_desde_ultimo_embarazo"),
        "embarazo_planeado": doc.get("embarazo_planeado"),
        "fracaso_metodo_anticonceptivo": doc.get("fracaso_metodo_anticonceptivo"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ---------------- Normalizadores de subdocumentos ----------------
_FAM_REQ = {"tbc", "diabetes", "hipertension", "preeclampsia", "eclampsia", "otra_condicion_medica_grave"}
_FAM_OPT = {"observaciones"}

_PER_REQ = {
    "tbc", "diabetes", "hipertension", "preeclampsia", "eclampsia",
    "otra_condicion_medica_grave", "violencia", "vih", "cirugia_genito_urinaria",
    "infertilidad", "cardiopatia", "nefropatia"
}
#  agregar peso_ultimo_previo como opcional
_PER_OPT = {"antecedente_gemelares", "observaciones", "diabetes_tipo", "peso_ultimo_previo"}

#  defaults para completar faltantes al CREAR
_FAM_DEFAULTS = {k: False for k in _FAM_REQ}
_PER_DEFAULTS = {k: False for k in _PER_REQ}

def _norm_str(v, field):
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(f"{field} debe ser string")
    return v.strip()

#  normalizador RELAJADO para crear (completa faltantes con False)
def _norm_antecedentes_familiares(obj: dict) -> dict:
    if not isinstance(obj, dict):
        # si no mandan objeto, inicializamos a todos False
        obj = {}
    out = dict(_FAM_DEFAULTS)  # completa todo a False
    # pisa con lo que venga en el payload (validando tipos si vienen)
    for k in _FAM_REQ:
        if k in obj and obj[k] is not None:
            out[k] = _as_bool(obj[k], f"antecedentes_familiares.{k}")
    if "observaciones" in obj and obj["observaciones"] is not None:
        out["observaciones"] = _norm_str(obj["observaciones"], "antecedentes_familiares.observaciones")
    return out

#  normalizador RELAJADO para crear (completa faltantes con False)
def _norm_antecedentes_personales(obj: dict) -> dict:
    if not isinstance(obj, dict):
        obj = {}
    out = dict(_PER_DEFAULTS)
    for k in _PER_REQ:
        if k in obj and obj[k] is not None:
            out[k] = _as_bool(obj[k], f"antecedentes_personales.{k}")

    # opcionales
    if "antecedente_gemelares" in obj and obj["antecedente_gemelares"] is not None:
        out["antecedente_gemelares"] = _as_bool(obj["antecedente_gemelares"], "antecedentes_personales.antecedente_gemelares")
    if "observaciones" in obj and obj["observaciones"] is not None:
        out["observaciones"] = _norm_str(obj["observaciones"], "antecedentes_personales.observaciones")

    # peso_ultimo_previo (acepta legacy y enum)
    if "peso_ultimo_previo" in obj and obj["peso_ultimo_previo"] is not None:
        p = _norm_str(obj["peso_ultimo_previo"], "antecedentes_personales.peso_ultimo_previo")
        mapped = _map_peso_client_to_schema(p)
        if mapped is None or mapped not in _PESO_ULTIMO_PREVIO_ENUM:
            raise ValueError("antecedentes_personales.peso_ultimo_previo inválido")
        out["peso_ultimo_previo"] = mapped

    # diabetes_tipo
    diab = out.get("diabetes", False)
    if "diabetes_tipo" in obj and obj["diabetes_tipo"] is not None:
        dt = _norm_str(obj["diabetes_tipo"], "antecedentes_personales.diabetes_tipo")
        if dt not in _DIABETES_TIPO:
            raise ValueError("antecedentes_personales.diabetes_tipo inválido")
        out["diabetes_tipo"] = dt
    else:
        # si no mandan diabetes_tipo:
        out["diabetes_tipo"] = "ninguna" if not diab else "ninguna"  # por defecto
        if diab:
            # si diabetes es True y no vino tipo, exige tipo explícito
            raise ValueError("Si antecedentes_personales.diabetes es true, debe indicar diabetes_tipo")

    return out

# --- Estos dos siguen siendo 'partial' para UPDATE (ya existían) ---
def _norm_antecedentes_familiares_partial(obj: dict) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("antecedentes_familiares debe ser objeto")
    extras = set(obj.keys()) - (_FAM_REQ | _FAM_OPT)
    if extras:
        raise ValueError("antecedentes_familiares: campos no permitidos: " + ", ".join(sorted(extras)))
    out = {}
    for k in (set(obj.keys()) & _FAM_REQ):
        out[k] = _as_bool(obj[k], f"antecedentes_familiares.{k}")
    if "observaciones" in obj and obj["observaciones"] is not None:
        out["observaciones"] = _norm_str(obj["observaciones"], "antecedentes_familiares.observaciones")
    return out

def _norm_antecedentes_personales_partial(obj: dict) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("antecedentes_personales debe ser objeto")
    extras = set(obj.keys()) - (_PER_REQ | _PER_OPT)
    if extras:
        raise ValueError("antecedentes_personales: campos no permitidos: " + ", ".join(sorted(extras)))
    out = {}
    for k in (set(obj.keys()) & _PER_REQ):
        out[k] = _as_bool(obj[k], f"antecedentes_personales.{k}")
    if "antecedente_gemelares" in obj and obj["antecedente_gemelares"] is not None:
        out["antecedente_gemelares"] = _as_bool(obj["antecedente_gemelares"], "antecedentes_personales.antecedente_gemelares")
    if "observaciones" in obj and obj["observaciones"] is not None:
        out["observaciones"] = _norm_str(obj["observaciones"], "antecedentes_personales.observaciones")

    # permitir actualización parcial de peso_ultimo_previo (acepta legacy y enum)
    if "peso_ultimo_previo" in obj and obj["peso_ultimo_previo"] is not None:
        p = _norm_str(obj["peso_ultimo_previo"], "antecedentes_personales.peso_ultimo_previo")
        mapped = _map_peso_client_to_schema(p)
        if mapped is None or mapped not in _PESO_ULTIMO_PREVIO_ENUM:
            raise ValueError("antecedentes_personales.peso_ultimo_previo inválido")
        out["peso_ultimo_previo"] = mapped

    if "diabetes_tipo" in obj and obj["diabetes_tipo"] is not None:
        dt = _norm_str(obj["diabetes_tipo"], "antecedentes_personales.diabetes_tipo")
        if dt not in _DIABETES_TIPO:
            raise ValueError("antecedentes_personales.diabetes_tipo inválido")
        out["diabetes_tipo"] = dt
    return out

# ---------------- Services ----------------
def crear_antecedentes(
    historial_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        payload = _compat_map_legacy(payload, for_update=False)
        _require_fields(payload)
        _ensure_indexes()

        historial_oid = _to_oid(historial_id, "historial_id")
        if not mongo.db.historiales.find_one({"_id": historial_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        fecha_ffue = _parse_date(payload["fecha_fin_ultimo_embarazo"], "fecha_fin_ultimo_embarazo")

        # Si envían el tiempo categorizado, lo validamos; si no, lo calculamos.
        if "tiempo_desde_ultimo_embarazo" in payload and payload["tiempo_desde_ultimo_embarazo"] is not None:
            tiempo_cat = _norm_enum(
                payload["tiempo_desde_ultimo_embarazo"], _TIEMPO_INTERVALOS, "tiempo_desde_ultimo_embarazo"
            )
        else:
            tiempo_cat = _clasificar_tiempo_desde_ultimo_embarazo(fecha_ffue)

        normalized_data = {
            "historial_id": historial_oid,
            **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")}
               if payload.get("paciente_id") else {}),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
               if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            # RELAJADO: completa faltantes con False
            "antecedentes_familiares": _norm_antecedentes_familiares(payload.get("antecedentes_familiares", {})),
            "antecedentes_personales": _norm_antecedentes_personales(payload.get("antecedentes_personales", {})),
            "gesta_previa": _as_nonneg_int(payload["gesta_previa"], "gesta_previa"),
            "partos": _as_nonneg_int(payload["partos"], "partos"),
            "cesareas": _as_nonneg_int(payload["cesareas"], "cesareas"),
            "vaginales": _as_nonneg_int(payload["vaginales"], "vaginales"),
            "abortos": _as_nonneg_int(payload["abortos"], "abortos"),
            "nacidos_vivos": _as_nonneg_int(payload["nacidos_vivos"], "nacidos_vivos"),
            "nacidos_muertos": _as_nonneg_int(payload["nacidos_muertos"], "nacidos_muertos"),
            "embarazo_ectopico": _as_nonneg_int(payload["embarazo_ectopico"], "embarazo_ectopico"),
            "hijos_vivos": _as_nonneg_int(payload["hijos_vivos"], "hijos_vivos"),
            "muertos_primera_semana": _as_nonneg_int(payload["muertos_primera_semana"], "muertos_primera_semana"),
            "muertos_despues_semana": _as_nonneg_int(payload["muertos_despues_semana"], "muertos_despues_semana"),
            "fecha_fin_ultimo_embarazo": fecha_ffue,
            "tiempo_desde_ultimo_embarazo": tiempo_cat,  # NUEVO
            "embarazo_planeado": _norm_enum(payload["embarazo_planeado"], _SI_NO, "embarazo_planeado"),
            "fracaso_metodo_anticonceptivo": _norm_enum(
                payload["fracaso_metodo_anticonceptivo"], _FRACASO_METODO, "fracaso_metodo_anticonceptivo"
            ),
        }

        _validate_obstetric_coherence(normalized_data)

        doc = {
            **normalized_data,
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
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(ant_id, "ant_id")
        payload = _compat_map_legacy(payload, for_update=True)
        upd = dict(payload)

        # Ids / FK
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

        # Enums
        if "diabetes_tipo" in upd and upd["diabetes_tipo"] is not None:
            upd["diabetes_tipo"] = _norm_enum(upd["diabetes_tipo"], _DIABETES_TIPO, "diabetes_tipo")
        if "embarazo_planeado" in upd and upd["embarazo_planeado"] is not None:
            upd["embarazo_planeado"] = _norm_enum(upd["embarazo_planeado"], _SI_NO, "embarazo_planeado")
        if "fracaso_metodo_anticonceptivo" in upd and upd["fracaso_metodo_anticonceptivo"] is not None:
            upd["fracaso_metodo_anticonceptivo"] = _norm_enum(
                upd["fracaso_metodo_anticonceptivo"], _FRACASO_METODO, "fracaso_metodo_anticonceptivo"
            )

        # NUEVO: permitir establecer/forzar tiempo_desde_ultimo_embarazo
        fecha_en_update = None
        if "fecha_fin_ultimo_embarazo" in upd and upd["fecha_fin_ultimo_embarazo"]:
            fecha_en_update = _parse_date(upd["fecha_fin_ultimo_embarazo"], "fecha_fin_ultimo_embarazo")
            upd["fecha_fin_ultimo_embarazo"] = fecha_en_update

        if "tiempo_desde_ultimo_embarazo" in upd and upd["tiempo_desde_ultimo_embarazo"] is not None:
            # Permito el valor especial "__auto__" para forzar recálculo sin enviar enum
            if isinstance(upd["tiempo_desde_ultimo_embarazo"], str) and upd["tiempo_desde_ultimo_embarazo"].strip() == "__auto__":
                # si mandan "__auto__", calculo usando la fecha nueva (si vino) o la ya almacenada
                current_doc_res = obtener_antecedentes_por_id(ant_id)
                if not current_doc_res[0]["ok"]:
                    return current_doc_res
                current_doc = current_doc_res[0]["data"]
                base_fecha = fecha_en_update or (
                    datetime.strptime(current_doc["fecha_fin_ultimo_embarazo"], "%Y-%m-%d")
                    if current_doc.get("fecha_fin_ultimo_embarazo") else None
                )
                if not base_fecha:
                    return _fail("No se puede autocalcular tiempo_desde_ultimo_embarazo sin fecha_fin_ultimo_embarazo", 422)
                upd["tiempo_desde_ultimo_embarazo"] = _clasificar_tiempo_desde_ultimo_embarazo(base_fecha)
            else:
                upd["tiempo_desde_ultimo_embarazo"] = _norm_enum(
                    upd["tiempo_desde_ultimo_embarazo"], _TIEMPO_INTERVALOS, "tiempo_desde_ultimo_embarazo"
                )
        elif fecha_en_update is not None:
            # Si actualizaron la fecha pero no mandaron el tiempo, NO lo tocamos automáticamente
            # (evitamos cambios silenciosos). Si lo quieres automático siempre, descomenta:
            # upd["tiempo_desde_ultimo_embarazo"] = _clasificar_tiempo_desde_ultimo_embarazo(fecha_en_update)
            pass

        # Subdocumentos (parciales en update)
        if "antecedentes_familiares" in upd and upd["antecedentes_familiares"] is not None:
            upd["antecedentes_familiares"] = _norm_antecedentes_familiares_partial(upd["antecedentes_familiares"])
        if "antecedentes_personales" in upd and upd["antecedentes_personales"] is not None:
            upd["antecedentes_personales"] = _norm_antecedentes_personales_partial(upd["antecedentes_personales"])

        # Ints
        for k in (
            "gesta_previa", "partos", "cesareas", "vaginales", "abortos",
            "nacidos_vivos", "nacidos_muertos", "embarazo_ectopico",
            "hijos_vivos", "muertos_primera_semana", "muertos_despues_semana"
        ):
            if k in upd and upd[k] is not None:
                upd[k] = _as_nonneg_int(upd[k], k)

        # Validación de coherencia sobre el merge
        current_doc_res = obtener_antecedentes_por_id(ant_id)
        if not current_doc_res[0]["ok"]:
            return current_doc_res
        current_doc = current_doc_res[0]["data"]
        merged = dict(current_doc)
        merged.update({
            # homogeneizamos claves a como las usa la validación
            **{k: v for k, v in upd.items()}
        })
        # Adaptar fecha serializada -> datetime para validar si fuera necesario
        if isinstance(merged.get("fecha_fin_ultimo_embarazo"), str):
            try:
                merged["fecha_fin_ultimo_embarazo"] = datetime.strptime(merged["fecha_fin_ultimo_embarazo"], "%Y-%m-%d")
            except Exception:
                pass

        _validate_obstetric_coherence(merged)

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
