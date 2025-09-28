from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ---------------- Enums / límites del schema ----------------
_VAC_RUBEOLA = {"previa", "embarazo", "no", "no_sabe"}
_GRUPO_SANG = {"A", "B", "AB", "O"}
_RH = {"+", "-"}
_VIH_RES = {"+", "-", "s/d", "n/c"}
_SIFILIS = {"+", "-", "s/d"}

# rangos
_PESO_MIN, _PESO_MAX = 0.0, 300.0        # kg
_TALLA_MIN, _TALLA_MAX = 0.5, 2.5        # m
_HEMO_MIN, _HEMO_MAX = 0.0, 30.0         # g/dL
_GLU_MIN = 0.0                           # mg/dL

_REQUIRED_FIELDS = [
    # de la colec: (quitamos _id y dejamos identificacion_id opcional por orquestador)
    "peso_anterior",
    "talla",
    "fum",
    "fpp",
    "eg_confiable",
    "fumadora_activa",
    "fumadora_pasiva",
    "drogas",
    "alcohol",
    "violencia",
    "vacuna_rubeola",
    "vacuna_antitetanica",
    "examen_mamas",
    "examen_odonto",
    "cervix_normal",
    "grupo_sanguineo",
    "rh",
    "inmunizada",
    "gammaglobulina",
    "toxoplasmosis_igg",
    "toxoplasmosis_igm",
    "hierro_acido_folico",
    "hemoglobina",
    "vih_solicitado",
    "vih_resultado",
    "tratamiento_vih",
    "sifilis",
    "sifilis_tratamiento",
    "pareja_tratada",
    "chagas",
    "malaria",
    "bacteriuria",
    "glucemia1",
    "glucemia2",
    "estreptococo",
    "plan_parto",
    "consejeria_lactancia",
]


# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _as_bool(v, field):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise ValueError(f"{field} debe ser booleano")

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

def _as_date_ymd(s, field):
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string con formato YYYY-MM-DD")
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field} debe tener formato YYYY-MM-DD")

def _norm_enum(v, opts, field):
    if isinstance(v, str) and v.strip() in opts:
        return v.strip()
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
        # básicos
        "peso_anterior": doc.get("peso_anterior"),
        "talla": doc.get("talla"),
        "fum": doc["fum"].strftime("%Y-%m-%d") if doc.get("fum") else None,
        "fpp": doc["fpp"].strftime("%Y-%m-%d") if doc.get("fpp") else None,
        "eg_confiable": doc.get("eg_confiable"),
        # estilos de vida
        "fumadora_activa": doc.get("fumadora_activa"),
        "fumadora_pasiva": doc.get("fumadora_pasiva"),
        "drogas": doc.get("drogas"),
        "alcohol": doc.get("alcohol"),
        "violencia": doc.get("violencia"),
        # vacunas / exámenes
        "vacuna_rubeola": doc.get("vacuna_rubeola"),
        "vacuna_antitetanica": doc.get("vacuna_antitetanica"),
        "examen_mamas": doc.get("examen_mamas"),
        "examen_odonto": doc.get("examen_odonto"),
        "cervix_normal": doc.get("cervix_normal"),
        "grupo_sanguineo": doc.get("grupo_sanguineo"),
        "rh": doc.get("rh"),
        "inmunizada": doc.get("inmunizada"),
        "gammaglobulina": doc.get("gammaglobulina"),
        "toxoplasmosis_igg": doc.get("toxoplasmosis_igg"),
        "toxoplasmosis_igm": doc.get("toxoplasmosis_igm"),
        "hierro_acido_folico": doc.get("hierro_acido_folico"),
        "hemoglobina": doc.get("hemoglobina"),
        "vih_solicitado": doc.get("vih_solicitado"),
        "vih_resultado": doc.get("vih_resultado"),
        "tratamiento_vih": doc.get("tratamiento_vih"),
        "sifilis": doc.get("sifilis"),
        "sifilis_tratamiento": doc.get("sifilis_tratamiento"),
        "pareja_tratada": doc.get("pareja_tratada"),
        "chagas": doc.get("chagas"),
        "malaria": doc.get("malaria"),
        "bacteriuria": doc.get("bacteriuria"),
        "glucemia1": doc.get("glucemia1"),
        "glucemia2": doc.get("glucemia2"),
        "estreptococo": doc.get("estreptococo"),
        "plan_parto": doc.get("plan_parto"),
        "consejeria_lactancia": doc.get("consejeria_lactancia"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------- Services ----------------
def crear_gestacion_actual(
    paciente_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea el documento de 'gestación actual'.
    Requiere: paciente_id (firma) + todos los campos en _REQUIRED_FIELDS.
    Opcional: identificacion_id, usuario_actual.usuario_id.
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
            # básicos
            "peso_anterior": _as_float_in_range(payload["peso_anterior"], "peso_anterior", _PESO_MIN, _PESO_MAX),
            "talla": _as_float_in_range(payload["talla"], "talla", _TALLA_MIN, _TALLA_MAX),
            "fum": _as_date_ymd(payload["fum"], "fum"),
            "fpp": _as_date_ymd(payload["fpp"], "fpp"),
            "eg_confiable": _as_bool(payload["eg_confiable"], "eg_confiable"),
            # estilos de vida
            "fumadora_activa": _as_bool(payload["fumadora_activa"], "fumadora_activa"),
            "fumadora_pasiva": _as_bool(payload["fumadora_pasiva"], "fumadora_pasiva"),
            "drogas": _as_bool(payload["drogas"], "drogas"),
            "alcohol": _as_bool(payload["alcohol"], "alcohol"),
            "violencia": _as_bool(payload["violencia"], "violencia"),
            # vacunas / exámenes
            "vacuna_rubeola": _norm_enum(payload["vacuna_rubeola"], _VAC_RUBEOLA, "vacuna_rubeola"),
            "vacuna_antitetanica": _as_bool(payload["vacuna_antitetanica"], "vacuna_antitetanica"),
            "examen_mamas": _as_bool(payload["examen_mamas"], "examen_mamas"),
            "examen_odonto": _as_bool(payload["examen_odonto"], "examen_odonto"),
            "cervix_normal": _as_bool(payload["cervix_normal"], "cervix_normal"),
            "grupo_sanguineo": _norm_enum(payload["grupo_sanguineo"], _GRUPO_SANG, "grupo_sanguineo"),
            "rh": _norm_enum(payload["rh"], _RH, "rh"),
            "inmunizada": _as_bool(payload["inmunizada"], "inmunizada"),
            "gammaglobulina": _as_bool(payload["gammaglobulina"], "gammaglobulina"),
            "toxoplasmosis_igg": _as_bool(payload["toxoplasmosis_igg"], "toxoplasmosis_igg"),
            "toxoplasmosis_igm": _as_bool(payload["toxoplasmosis_igm"], "toxoplasmosis_igm"),
            "hierro_acido_folico": _as_bool(payload["hierro_acido_folico"], "hierro_acido_folico"),
            "hemoglobina": _as_float_in_range(payload["hemoglobina"], "hemoglobina", _HEMO_MIN, _HEMO_MAX),
            "vih_solicitado": _as_bool(payload["vih_solicitado"], "vih_solicitado"),
            "vih_resultado": _norm_enum(payload["vih_resultado"], _VIH_RES, "vih_resultado"),
            "tratamiento_vih": _as_bool(payload["tratamiento_vih"], "tratamiento_vih"),
            "sifilis": _norm_enum(payload["sifilis"], _SIFILIS, "sifilis"),
            "sifilis_tratamiento": _as_bool(payload["sifilis_tratamiento"], "sifilis_tratamiento"),
            "pareja_tratada": _as_bool(payload["pareja_tratada"], "pareja_tratada"),
            "chagas": _as_bool(payload["chagas"], "chagas"),
            "malaria": _as_bool(payload["malaria"], "malaria"),
            "bacteriuria": _as_bool(payload["bacteriuria"], "bacteriuria"),
            "glucemia1": _as_float_in_range(payload["glucemia1"], "glucemia1", _GLU_MIN, None),
            "glucemia2": _as_float_in_range(payload["glucemia2"], "glucemia2", _GLU_MIN, None),
            "estreptococo": _as_bool(payload["estreptococo"], "estreptococo"),
            "plan_parto": _as_bool(payload["plan_parto"], "plan_parto"),
            "consejeria_lactancia": _as_bool(payload["consejeria_lactancia"], "consejeria_lactancia"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = mongo.db.gestacion_actual.insert_one(doc, session=session) if session else mongo.db.gestacion_actual.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar gestación actual: {str(e)}", 400)


def obtener_gestacion_actual_por_id(ga_id: str):
    try:
        oid = _to_oid(ga_id, "ga_id")
        doc = mongo.db.gestacion_actual.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener", 400)


def get_gestacion_actual_by_id_paciente(paciente_id: str):
    """Devuelve la más reciente por paciente_id (útil para el GET agregado)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.gestacion_actual.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró gestación actual para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener", 400)


def obtener_gestacion_actual_por_identificacion(identificacion_id: str):
    """Alternativa: por identificacion_id (devuelve la más reciente)."""
    try:
        oid = _to_oid(identificacion_id, "identificacion_id")
        doc = mongo.db.gestacion_actual.find_one({"identificacion_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró gestación actual para esta identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener", 400)


def actualizar_gestacion_actual_por_id(ga_id: str, payload: dict, session=None):
    """
    Actualiza por _id. Re-normaliza fechas, enums, rangos si vienen.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(ga_id, "ga_id")
        upd = dict(payload)

        # ids
        if "identificacion_id" in upd and upd["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(upd["identificacion_id"], "identificacion_id")
        if "paciente_id" in upd and upd["paciente_id"]:
            upd["paciente_id"] = _to_oid(upd["paciente_id"], "paciente_id")
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # fechas
        if "fum" in upd and upd["fum"]:
            upd["fum"] = _as_date_ymd(upd["fum"], "fum")
        if "fpp" in upd and upd["fpp"]:
            upd["fpp"] = _as_date_ymd(upd["fpp"], "fpp")

        # num/rangos
        if "peso_anterior" in upd and upd["peso_anterior"] is not None:
            upd["peso_anterior"] = _as_float_in_range(upd["peso_anterior"], "peso_anterior", _PESO_MIN, _PESO_MAX)
        if "talla" in upd and upd["talla"] is not None:
            upd["talla"] = _as_float_in_range(upd["talla"], "talla", _TALLA_MIN, _TALLA_MAX)
        if "hemoglobina" in upd and upd["hemoglobina"] is not None:
            upd["hemoglobina"] = _as_float_in_range(upd["hemoglobina"], "hemoglobina", _HEMO_MIN, _HEMO_MAX)
        for g_field in ("glucemia1", "glucemia2"):
            if g_field in upd and upd[g_field] is not None:
                upd[g_field] = _as_float_in_range(upd[g_field], g_field, _GLU_MIN, None)

        # bools
        for b in ("eg_confiable","fumadora_activa","fumadora_pasiva","drogas","alcohol","violencia",
                  "vacuna_antitetanica","examen_mamas","examen_odonto","cervix_normal","inmunizada",
                  "gammaglobulina","toxoplasmosis_igg","toxoplasmosis_igm","hierro_acido_folico",
                  "vih_solicitado","tratamiento_vih","sifilis_tratamiento","pareja_tratada",
                  "chagas","malaria","bacteriuria","estreptococo","plan_parto","consejeria_lactancia"):
            if b in upd and upd[b] is not None:
                upd[b] = _as_bool(upd[b], b)

        # enums
        if "vacuna_rubeola" in upd and upd["vacuna_rubeola"]:
            upd["vacuna_rubeola"] = _norm_enum(upd["vacuna_rubeola"], _VAC_RUBEOLA, "vacuna_rubeola")
        if "grupo_sanguineo" in upd and upd["grupo_sanguineo"]:
            upd["grupo_sanguineo"] = _norm_enum(upd["grupo_sanguineo"], _GRUPO_SANG, "grupo_sanguineo")
        if "rh" in upd and upd["rh"]:
            upd["rh"] = _norm_enum(upd["rh"], _RH, "rh")
        if "vih_resultado" in upd and upd["vih_resultado"]:
            upd["vih_resultado"] = _norm_enum(upd["vih_resultado"], _VIH_RES, "vih_resultado")
        if "sifilis" in upd and upd["sifilis"]:
            upd["sifilis"] = _norm_enum(upd["sifilis"], _SIFILIS, "sifilis")

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.gestacion_actual.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Gestación actual actualizada"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al actualizar", 400)


def eliminar_gestacion_actual_por_id(ga_id: str, session=None):
    try:
        oid = _to_oid(ga_id, "ga_id")
        res = mongo.db.gestacion_actual.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Gestación actual eliminada"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al eliminar", 400)
