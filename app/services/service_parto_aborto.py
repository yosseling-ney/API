from datetime import datetime
from bson import ObjectId
from app import mongo

# ================== helpers de respuesta ==================
def _ok(data, code=200):   return {"ok": True,  "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ================== enums del schema ==================
_TIPO_EVENTO = {"Parto", "Aborto"}
_SI_NO = {"Si", "No"}
_LUGAR_PARTO = {"Institucional", "Domiciliar", "Otro"}
_CORTICOIDES_ESTADO = {"Completo", "Incompleto", "Ninguna", "N/C"}
_INICIO_PARTO = {"Espontáneo", "Inducido", "Cesárea Electiva"}
_EDAD_GEST_METODO = {"FUM", "USG", "Ambos"}
_PRESENTACION = {"Cefálica", "Pélvica", "Transversa"}
_ACOMPANANTE = {
    "Pareja","Familiar","Partera","Brigadista","Amigo/a",
    "Personal Salud","Otro","Ninguno"
}
_NACIMIENTO = {"Vivo","Muerte Anteparto","Muerte Intraparto","Muerto Ignora momento"}
_TERMINACION = {"Espontánea","Cesárea","Fórceps","Vacuum","Otra"}
_POSICION = {"Sentada","Acostada","Cuclillas"}
_EPI = {"Si", "No"}
_LIGADURA = {"Precoz","Tardía"}

# ================== utilidades ==================
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _as_int(v, field, lo=None, hi=None):
    try:
        x = int(v)
    except Exception:
        raise ValueError(f"{field} debe ser entero")
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError(f"{field} fuera de rango [{lo}, {hi}]")
    return x

def _as_bool(v, field):
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v in _SI_NO:
        return v == "Si"
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    raise ValueError(f"{field} debe ser booleano o 'Si'/'No'")

def _norm_enum(v, allowed, field):
    if isinstance(v, str) and v in allowed:
        return v
    raise ValueError(f"{field} inválido. Use uno de: {', '.join(sorted(allowed))}")

def _as_datetime_iso(s, field, fmt="%Y-%m-%dT%H:%M"):
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string con formato {fmt}")
    try:
        return datetime.strptime(s, fmt)
    except Exception:
        raise ValueError(f"{field} debe tener formato {fmt}")

def _as_date_ymd(s, field):
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string 'YYYY-MM-DD'")
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field} debe tener formato YYYY-MM-DD")

def _require(payload, fields):
    faltan = [k for k in fields if k not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _ensure_indexes():
    try:
        mongo.db.parto_aborto.create_index("historial_id", name="ix_pa_historial")
    except Exception:
        pass
    try:
        mongo.db.parto_aborto.create_index("paciente_id", name="ix_pa_paciente")  # compat
    except Exception:
        pass

def _serialize(doc):
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,  # compat
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "tipo_evento": doc.get("tipo_evento"),
        "fecha_ingreso": doc["fecha_ingreso"].strftime("%Y-%m-%d") if doc.get("fecha_ingreso") else None,
        "carne_perinatal": doc.get("carne_perinatal"),
        "consultas_prenatales": doc.get("consultas_prenatales"),
        "lugar_parto": doc.get("lugar_parto"),
        "hospitalizacion_embarazo": doc.get("hospitalizacion_embarazo"),
        "corticoides_antenatales": doc.get("corticoides_antenatales"),
        "inicio_parto": doc.get("inicio_parto"),
        "ruptura_membrana": doc.get("ruptura_membrana"),
        "edad_gestacional_parto": doc.get("edad_gestacional_parto"),
        "presentacion": doc.get("presentacion"),
        "tamano_fetal_acorde": doc.get("tamano_fetal_acorde"),
        "acompanante": doc.get("acompanante"),
        "acompanamiento_solicitado_usuaria": doc.get("acompanamiento_solicitado_usuaria"),
        "nacimiento": doc.get("nacimiento"),
        "fecha_hora_nacimiento": doc["fecha_hora_nacimiento"].strftime("%Y-%m-%dT%H:%M") if doc.get("fecha_hora_nacimiento") else None,
        "nacimiento_multiple": doc.get("nacimiento_multiple"),
        "orden_nacimiento": doc.get("orden_nacimiento"),
        "terminacion_parto": doc.get("terminacion_parto"),
        "posicion_parto": doc.get("posicion_parto"),
        "episiotomia": doc.get("episiotomia"),
        "desgarros": doc.get("desgarros"),
        "oxitocicos_pre": doc.get("oxitocicos_pre"),
        "oxitocicos_post": doc.get("oxitocicos_post"),
        "placenta_expulsada": doc.get("placenta_expulsada"),
        "ligadura_cordon": doc.get("ligadura_cordon"),
        "medicacion_recibida": doc.get("medicacion_recibida"),
        "indicacion_principal_induccion_operacion": doc.get("indicacion_principal_induccion_operacion"),
        "induccion": doc.get("induccion"),
        "operacion": doc.get("operacion"),
        "partograma_usado": doc.get("partograma_usado"),
        "partograma_detalle": doc.get("partograma_detalle"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ================== construcción del documento ==================
_REQ_TOP = [
    "tipo_evento","fecha_ingreso","carne_perinatal","consultas_prenatales","lugar_parto",
    "hospitalizacion_embarazo","corticoides_antenatales","inicio_parto","ruptura_membrana",
    "edad_gestacional_parto","presentacion","tamano_fetal_acorde","acompanante",
    "acompanamiento_solicitado_usuaria","nacimiento","fecha_hora_nacimiento",
    "nacimiento_multiple","orden_nacimiento","terminacion_parto","posicion_parto","episiotomia",
    "desgarros","oxitocicos_pre","oxitocicos_post","placenta_expulsada","ligadura_cordon",
    "medicacion_recibida","indicacion_principal_induccion_operacion","induccion","operacion",
    "partograma_usado"
]

def _build_rpm(rpm: dict):
    _require(rpm, ["hubo"])
    dto = {"hubo": _norm_enum(rpm["hubo"], _SI_NO, "ruptura_membrana.hubo")}
    if dto["hubo"] == "Si":
        _require(rpm, ["fecha_inicio", "hora_inicio"])
        fi = rpm["fecha_inicio"]; hi = rpm["hora_inicio"]
        _require(fi, ["dia","mes","anio"]); _require(hi, ["hora","minuto"])
        dto.update({
            "fecha_inicio": {
                "dia": _as_int(fi["dia"], "ruptura_membrana.fecha_inicio.dia", 1, 31),
                "mes": _as_int(fi["mes"], "ruptura_membrana.fecha_inicio.mes", 1, 12),
                "anio": _as_int(fi["anio"], "ruptura_membrana.fecha_inicio.anio", 1900),
            },
            "hora_inicio": {
                "hora": _as_int(hi["hora"], "ruptura_membrana.hora_inicio.hora", 0, 23),
                "minuto": _as_int(hi["minuto"], "ruptura_membrana.hora_inicio.minuto", 0, 59),
            },
            "antes_37_semanas": _as_bool(rpm.get("antes_37_semanas", False), "ruptura_membrana.antes_37_semanas"),
            "duracion_ruptura_18h_omas": _as_bool(rpm.get("duracion_ruptura_18h_omas", False), "ruptura_membrana.duracion_ruptura_18h_omas"),
            "temperatura_mayor_38": _as_bool(rpm.get("temperatura_mayor_38", False), "ruptura_membrana.temperatura_mayor_38"),
        })
    return dto

def _build_medicacion(med: dict):
    def _opt(name):
        v = med.get(name, "No")
        return _norm_enum(v, _SI_NO, f"medicacion_recibida.{name}")
    return {
        "oxitocicos": _opt("oxitocicos"),
        "antibiotico": _opt("antibiotico"),
        "analgesia": _opt("analgesia"),
        "anestesia_local": _opt("anestesia_local"),
        "anestesia_general": _opt("anestesia_general"),
        "anestesia_regional": _opt("anestesia_regional"),
        "transfusion": _opt("transfusion"),
        "otros": str(med.get("otros", "")).strip() if med.get("otros") else "",
    }

def _build_partograma(items):
    if not items:
        return []
    out = []
    for i, it in enumerate(items):
        _require(it, ["hora","minuto","posicion_madre","pa","pulso","contracciones",
                      "dilatacion","altura_presentacion","variedad_posicion","meconio","fcf_dips"])
        out.append({
            "hora": _as_int(it["hora"], f"partograma_detalle[{i}].hora", 0, 23),
            "minuto": _as_int(it["minuto"], f"partograma_detalle[{i}].minuto", 0, 59),
            "posicion_madre": str(it["posicion_madre"]),
            "pa": str(it["pa"]),
            "pulso": _as_int(it["pulso"], f"partograma_detalle[{i}].pulso", 0),
            "contracciones": _as_int(it["contracciones"], f"partograma_detalle[{i}].contracciones", 0),
            "dilatacion": str(it["dilatacion"]),
            "altura_presentacion": str(it["altura_presentacion"]),
            "variedad_posicion": str(it["variedad_posicion"]),
            "meconio": _as_bool(it["meconio"], f"partograma_detalle[{i}].meconio"),
            "fcf_dips": _as_bool(it["fcf_dips"], f"partograma_detalle[{i}].fcf_dips"),
        })
    return out

def _build_doc(historial_id: str, payload: dict, usuario_actual: dict | None):
    _require(payload, _REQ_TOP)
    return {
        "historial_id": _to_oid(historial_id, "historial_id"),
        # compat (opcional): permitir guardar paciente_id si viene
        **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")}
           if payload.get("paciente_id") else {}),
        "usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id") if (usuario_actual and usuario_actual.get("usuario_id")) else None,
        "tipo_evento": _norm_enum(payload["tipo_evento"], _TIPO_EVENTO, "tipo_evento"),
        "fecha_ingreso": _as_date_ymd(payload["fecha_ingreso"], "fecha_ingreso"),
        "carne_perinatal": _norm_enum(payload["carne_perinatal"], _SI_NO, "carne_perinatal"),
        "consultas_prenatales": _as_int(payload["consultas_prenatales"], "consultas_prenatales", 0),
        "lugar_parto": _norm_enum(payload["lugar_parto"], _LUGAR_PARTO, "lugar_parto"),
        "hospitalizacion_embarazo": {
            "hubo": _norm_enum(payload["hospitalizacion_embarazo"]["hubo"], _SI_NO, "hospitalizacion_embarazo.hubo"),
            "dias": _as_int(payload["hospitalizacion_embarazo"]["dias"], "hospitalizacion_embarazo.dias", 0),
        },
        "corticoides_antenatales": {
            "estado": _norm_enum(payload["corticoides_antenatales"]["estado"], _CORTICOIDES_ESTADO, "corticoides_antenatales.estado"),
            "semana_inicio": _as_int(payload["corticoides_antenatales"]["semana_inicio"], "corticoides_antenatales.semana_inicio", 0),
        },
        "inicio_parto": _norm_enum(payload["inicio_parto"], _INICIO_PARTO, "inicio_parto"),
        "ruptura_membrana": _build_rpm(payload["ruptura_membrana"]),
        "edad_gestacional_parto": {
            "semanas": _as_int(payload["edad_gestacional_parto"]["semanas"], "edad_gestacional_parto.semanas", 0),
            "dias": _as_int(payload["edad_gestacional_parto"]["dias"], "edad_gestacional_parto.dias", 0, 6),
            "metodo": _norm_enum(payload["edad_gestacional_parto"]["metodo"], _EDAD_GEST_METODO, "edad_gestacional_parto.metodo"),
        },
        "presentacion": _norm_enum(payload["presentacion"], _PRESENTACION, "presentacion"),
        "tamano_fetal_acorde": _norm_enum(payload["tamano_fetal_acorde"], _SI_NO, "tamano_fetal_acorde"),
        "acompanante": _norm_enum(payload["acompanante"], _ACOMPANANTE, "acompanante"),
        "acompanamiento_solicitado_usuaria": _norm_enum(payload["acompanamiento_solicitado_usuaria"], _SI_NO, "acompanamiento_solicitado_usuaria"),
        "nacimiento": _norm_enum(payload["nacimiento"], _NACIMIENTO, "nacimiento"),
        "fecha_hora_nacimiento": _as_datetime_iso(payload["fecha_hora_nacimiento"], "fecha_hora_nacimiento"),
        "nacimiento_multiple": _norm_enum(payload["nacimiento_multiple"], _SI_NO, "nacimiento_multiple"),
        "orden_nacimiento": _as_int(payload["orden_nacimiento"], "orden_nacimiento", 0),
        "terminacion_parto": _norm_enum(payload["terminacion_parto"], _TERMINACION, "terminacion_parto"),
        "posicion_parto": _norm_enum(payload["posicion_parto"], _POSICION, "posicion_parto"),
        "episiotomia": _norm_enum(payload["episiotomia"], _EPI, "episiotomia"),
        "desgarros": {
            "hubo": _norm_enum(payload["desgarros"]["hubo"], _SI_NO, "desgarros.hubo"),
            **({"grado": _as_int(payload["desgarros"]["grado"], "desgarros.grado", 1, 4)} if payload["desgarros"]["hubo"] == "Si" else {"grado": None}),
        },
        "oxitocicos_pre": _norm_enum(payload["oxitocicos_pre"], _SI_NO, "oxitocicos_pre"),
        "oxitocicos_post": _norm_enum(payload["oxitocicos_post"], _SI_NO, "oxitocicos_post"),
        "placenta_expulsada": _norm_enum(payload["placenta_expulsada"], _SI_NO, "placenta_expulsada"),
        "ligadura_cordon": _norm_enum(payload["ligadura_cordon"], _LIGADURA, "ligadura_cordon"),
        "medicacion_recibida": _build_medicacion(payload.get("medicacion_recibida", {})),
        "indicacion_principal_induccion_operacion": str(payload["indicacion_principal_induccion_operacion"]).strip(),
        "induccion": [str(x) for x in payload.get("induccion", [])],
        "operacion": [str(x) for x in payload.get("operacion", [])],
        "partograma_usado": _as_bool(payload["partograma_usado"], "partograma_usado"),
        "partograma_detalle": _build_partograma(payload.get("partograma_detalle")),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

# ================== services ==================
def crear_parto_aborto(historial_id: str, payload: dict, session=None, usuario_actual: dict | None = None):
    """Crea registro de parto/aborto orquestado por historial_id (FK principal)."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        _ensure_indexes()

        # validar que exista el historial
        h_oid = _to_oid(historial_id, "historial_id")
        if not mongo.db.historiales.find_one({"_id": h_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        doc = _build_doc(historial_id, payload, usuario_actual)
        res = (mongo.db.parto_aborto.insert_one(doc, session=session)
               if session else mongo.db.parto_aborto.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar parto/aborto: {str(e)}", 400)

def obtener_parto_aborto_por_id(pa_id: str):
    try:
        oid = _to_oid(pa_id, "pa_id")
        doc = mongo.db.parto_aborto.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontró el registro", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener registro", 400)

def obtener_parto_aborto_por_historial(historial_id: str):
    """Devuelve el registro más reciente para el historial_id."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.parto_aborto.find_one({"historial_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró registro para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener registro", 400)

# ===== Compat (apoyo/migración): búsquedas por paciente_id =====
def get_parto_aborto_by_id_paciente(paciente_id: str):
    """Devuelve el registro más reciente para el paciente (compat)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.parto_aborto.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró registro para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener registro", 400)

def actualizar_parto_aborto_por_id(pa_id: str, payload: dict, session=None):
    """Actualiza por _id (re-normaliza campos presentes en payload). Permite mover de historial validando existencia."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(pa_id, "pa_id")
        upd = {}

        # FK principal: historial_id (si viene, validar)
        if "historial_id" in payload and payload["historial_id"] is not None:
            h_oid = _to_oid(payload["historial_id"], "historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            upd["historial_id"] = h_oid

        # compat: permitir mover a otro paciente si viene
        if "paciente_id" in payload and payload["paciente_id"]:
            upd["paciente_id"] = _to_oid(payload["paciente_id"], "paciente_id")
        if "usuario_id" in payload and payload["usuario_id"]:
            upd["usuario_id"] = _to_oid(payload["usuario_id"], "usuario_id")

        # enums simples
        for f, enum in [
            ("tipo_evento", _TIPO_EVENTO),
            ("carne_perinatal", _SI_NO),
            ("lugar_parto", _LUGAR_PARTO),
            ("inicio_parto", _INICIO_PARTO),
            ("presentacion", _PRESENTACION),
            ("tamano_fetal_acorde", _SI_NO),
            ("acompanante", _ACOMPANANTE),
            ("acompanamiento_solicitado_usuaria", _SI_NO),
            ("nacimiento", _NACIMIENTO),
            ("nacimiento_multiple", _SI_NO),
            ("terminacion_parto", _TERMINACION),
            ("posicion_parto", _POSICION),
            ("episiotomia", _EPI),
            ("ligadura_cordon", _LIGADURA),
        ]:
            if f in payload and payload[f] is not None:
                upd[f] = _norm_enum(payload[f], enum, f)

        # fechas / números
        if "fecha_ingreso" in payload and payload["fecha_ingreso"]:
            upd["fecha_ingreso"] = _as_date_ymd(payload["fecha_ingreso"], "fecha_ingreso")
        if "consultas_prenatales" in payload and payload["consultas_prenatales"] is not None:
            upd["consultas_prenatales"] = _as_int(payload["consultas_prenatales"], "consultas_prenatales", 0)
        if "fecha_hora_nacimiento" in payload and payload["fecha_hora_nacimiento"]:
            upd["fecha_hora_nacimiento"] = _as_datetime_iso(payload["fecha_hora_nacimiento"], "fecha_hora_nacimiento")
        if "orden_nacimiento" in payload and payload["orden_nacimiento"] is not None:
            upd["orden_nacimiento"] = _as_int(payload["orden_nacimiento"], "orden_nacimiento", 0)

        # objetos anidados
        if "hospitalizacion_embarazo" in payload and payload["hospitalizacion_embarazo"]:
            he = payload["hospitalizacion_embarazo"]
            upd["hospitalizacion_embarazo"] = {
                "hubo": _norm_enum(he["hubo"], _SI_NO, "hospitalizacion_embarazo.hubo"),
                "dias": _as_int(he["dias"], "hospitalizacion_embarazo.dias", 0),
            }

        if "corticoides_antenatales" in payload and payload["corticoides_antenatales"]:
            ca = payload["corticoides_antenatales"]
            upd["corticoides_antenatales"] = {
                "estado": _norm_enum(ca["estado"], _CORTICOIDES_ESTADO, "corticoides_antenatales.estado"),
                "semana_inicio": _as_int(ca["semana_inicio"], "corticoides_antenatales.semana_inicio", 0),
            }

        if "ruptura_membrana" in payload and payload["ruptura_membrana"]:
            upd["ruptura_membrana"] = _build_rpm(payload["ruptura_membrana"])

        if "edad_gestacional_parto" in payload and payload["edad_gestacional_parto"]:
            eg = payload["edad_gestacional_parto"]
            upd["edad_gestacional_parto"] = {
                "semanas": _as_int(eg["semanas"], "edad_gestacional_parto.semanas", 0),
                "dias": _as_int(eg["dias"], "edad_gestacional_parto.dias", 0, 6),
                "metodo": _norm_enum(eg["metodo"], _EDAD_GEST_METODO, "edad_gestacional_parto.metodo"),
            }

        if "desgarros" in payload and payload["desgarros"]:
            dg = payload["desgarros"]
            upd["desgarros"] = {
                "hubo": _norm_enum(dg["hubo"], _SI_NO, "desgarros.hubo"),
                **({"grado": _as_int(dg["grado"], "desgarros.grado", 1, 4)} if dg.get("hubo") == "Si" else {"grado": None})
            }

        if "medicacion_recibida" in payload and payload["medicacion_recibida"]:
            upd["medicacion_recibida"] = _build_medicacion(payload["medicacion_recibida"])

        if "induccion" in payload and payload["induccion"] is not None:
            upd["induccion"] = [str(x) for x in payload["induccion"]]
        if "operacion" in payload and payload["operacion"] is not None:
            upd["operacion"] = [str(x) for x in payload["operacion"]]

        if "partograma_usado" in payload and payload["partograma_usado"] is not None:
            upd["partograma_usado"] = _as_bool(payload["partograma_usado"], "partograma_usado")
        if "partograma_detalle" in payload:
            upd["partograma_detalle"] = _build_partograma(payload["partograma_detalle"])

        if "indicacion_principal_induccion_operacion" in payload and payload["indicacion_principal_induccion_operacion"] is not None:
            upd["indicacion_principal_induccion_operacion"] = str(payload["indicacion_principal_induccion_operacion"]).strip()

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.parto_aborto.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Registro actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar registro", 400)

def eliminar_parto_aborto_por_id(pa_id: str, session=None):
    try:
        oid = _to_oid(pa_id, "pa_id")
        res = mongo.db.parto_aborto.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Registro eliminado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar registro", 400)
