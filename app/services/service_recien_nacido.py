from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ---------------- Enums del schema ----------------
_TIPO_NAC = {"vivo", "muerto_anteparto", "muerto_parto"}
_SEXO = {"Femenino", "Masculino", "No definido"}
_EG_METODO = {"FUM", "Ecografía precoz", "Examen físico"}
_PESO_EG = {"Adecuado", "Pequeño", "Grande"}
_SI_NO = {"si", "no"}
_REANIM = {"estimulación", "aspiración", "mascara", "oxigeno", "masaje", "tubo"}
_FALLECE_SALA = {"si", "no"}
_REFERIDO = {"aloj_conjunto", "neonatologia", "otro_hosp"}
_ATENDIO = {"medico", "obstetrica", "enfermera", "auxiliar", "estudiante", "empirica", "otro"}
_DEFECTO_TIPO = {"mayor", "menor", "ninguna"}
_VIH_EXP = {"si", "no", "s/d"}
_VIH_TTO = {"si", "no", "s/d", "n/c"}
_TAMIZAJE_RES = {"positivo", "negativo", "no_se_hizo"}

# ---------------- Rangos numéricos ----------------
_MIN0 = 0.0


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

def _as_float_ge0(v, field):
    try:
        x = float(v)
    except Exception:
        raise ValueError(f"{field} debe ser numérico")
    if x < 0:
        raise ValueError(f"{field} no puede ser negativo")
    return x

def _as_int_ge0(v, field):
    try:
        x = int(v)
    except Exception:
        raise ValueError(f"{field} debe ser entero")
    if x < 0:
        raise ValueError(f"{field} no puede ser negativo")
    return x

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "tipo_nacimiento": doc.get("tipo_nacimiento"),
        "sexo": doc.get("sexo"),
        "peso_nacer": doc.get("peso_nacer"),
        "perimetro_cefalico": doc.get("perimetro_cefalico"),
        "longitud": doc.get("longitud"),
        "edad_gestacional": doc.get("edad_gestacional"),
        "peso_edad_gestacional": doc.get("peso_edad_gestacional"),
        "cuidados_inmediatos": doc.get("cuidados_inmediatos"),
        "apgar": doc.get("apgar"),
        "reanimacion": doc.get("reanimacion"),
        "fallece_sala_parto": doc.get("fallece_sala_parto"),
        "referido": doc.get("referido"),
        "atendio": doc.get("atendio"),
        "defectos_congenitos": doc.get("defectos_congenitos"),
        "enfermedades": doc.get("enfermedades"),
        "vih_rn": doc.get("vih_rn"),
        "tamizaje_neonatal": doc.get("tamizaje_neonatal"),
        "meconio": doc.get("meconio"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------- Builders ----------------
def _build_edad_gestacional(eg: dict) -> dict:
    _require(eg, ["semanas", "dias", "metodo", "estimada"], "edad_gestacional")
    return {
        "semanas": _as_int_ge0(eg["semanas"], "edad_gestacional.semanas"),
        "dias": _as_int_ge0(eg["dias"], "edad_gestacional.dias"),
        "metodo": _norm_enum(eg["metodo"], _EG_METODO, "edad_gestacional.metodo"),
        "estimada": bool(eg["estimada"]),
    }

def _build_cuidados(ci: dict) -> dict:
    _require(ci, ["vitamina_k", "profilaxis_ocular", "apego_precoz"], "cuidados_inmediatos")
    return {
        "vitamina_k": _norm_enum(ci["vitamina_k"], _SI_NO, "cuidados_inmediatos.vitamina_k"),
        "profilaxis_ocular": _norm_enum(ci["profilaxis_ocular"], _SI_NO, "cuidados_inmediatos.profilaxis_ocular"),
        "apego_precoz": _norm_enum(ci["apego_precoz"], _SI_NO, "cuidados_inmediatos.apego_precoz"),
    }

def _build_apgar(ap: dict) -> dict:
    _require(ap, ["min_1", "min_5"], "apgar")
    m1 = _as_int_ge0(ap["min_1"], "apgar.min_1")
    m5 = _as_int_ge0(ap["min_5"], "apgar.min_5")
    if not (0 <= m1 <= 10) or not (0 <= m5 <= 10):
        raise ValueError("apgar.min_1 y apgar.min_5 deben estar en [0,10]")
    return {"min_1": m1, "min_5": m5}

def _build_atendio(at: dict) -> dict:
    _require(at, ["parto", "neonato"], "atendio")
    return {
        "parto": _norm_enum(at["parto"], _ATENDIO, "atendio.parto"),
        "neonato": _norm_enum(at["neonato"], _ATENDIO, "atendio.neonato"),
    }

def _build_defectos(dc: dict) -> dict:
    _require(dc, ["presenta", "tipo_malformacion", "codigo", "detalle"], "defectos_congenitos")
    return {
        "presenta": _norm_enum(dc["presenta"], _SI_NO, "defectos_congenitos.presenta"),
        "tipo_malformacion": _norm_enum(dc["tipo_malformacion"], _DEFECTO_TIPO, "defectos_congenitos.tipo_malformacion"),
        "codigo": str(dc["codigo"]),
        "detalle": str(dc["detalle"]),
    }

def _build_enfermedades(enf: dict) -> dict:
    _require(enf, ["codigos", "ninguna", "uno_o_mas"], "enfermedades")
    if not isinstance(enf["codigos"], list):
        raise ValueError("enfermedades.codigos debe ser arreglo")
    if len(enf["codigos"]) > 3:
        raise ValueError("enfermedades.codigos admite máximo 3 códigos")
    return {
        "codigos": [str(x) for x in enf["codigos"]],
        "ninguna": bool(enf["ninguna"]),
        "uno_o_mas": bool(enf["uno_o_mas"]),
    }

def _build_vih_rn(vih: dict) -> dict:
    _require(vih, ["exposicion", "tratamiento"], "vih_rn")
    return {
        "exposicion": _norm_enum(vih["exposicion"], _VIH_EXP, "vih_rn.exposicion"),
        "tratamiento": _norm_enum(vih["tratamiento"], _VIH_TTO, "vih_rn.tratamiento"),
    }

def _build_tamizaje(tz: dict) -> dict:
    _require(tz, ["vdrl", "tsh", "hbpatia", "bilirrubina", "toxo_igm"], "tamizaje_neonatal")
    return {
        "vdrl": _norm_enum(tz["vdrl"], _TAMIZAJE_RES, "tamizaje_neonatal.vdrl"),
        "tsh": _norm_enum(tz["tsh"], _TAMIZAJE_RES, "tamizaje_neonatal.tsh"),
        "hbpatia": _norm_enum(tz["hbpatia"], _TAMIZAJE_RES, "tamizaje_neonatal.hbpatia"),
        "bilirrubina": _norm_enum(tz["bilirrubina"], _TAMIZAJE_RES, "tamizaje_neonatal.bilirrubina"),
        "toxo_igm": _norm_enum(tz["toxo_igm"], _TAMIZAJE_RES, "tamizaje_neonatal.toxo_igm"),
    }

def _build_doc(paciente_id: str, payload: dict, usuario_actual: dict | None):
    _require(payload, [
        "tipo_nacimiento","sexo","peso_nacer","perimetro_cefalico","longitud",
        "edad_gestacional","peso_edad_gestacional","cuidados_inmediatos","apgar",
        "reanimacion","fallece_sala_parto","referido","atendio","defectos_congenitos",
        "enfermedades","vih_rn","tamizaje_neonatal","meconio"
    ])

    # reanimación
    if not isinstance(payload["reanimacion"], list):
        raise ValueError("reanimacion debe ser arreglo")
    reanim = [_norm_enum(x, _REANIM, "reanimacion[]") for x in payload["reanimacion"]]

    return {
        "paciente_id": _to_oid(paciente_id, "paciente_id"),
        **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
           if payload.get("identificacion_id") else {}),
        **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
           if usuario_actual and usuario_actual.get("usuario_id") else {}),
        "tipo_nacimiento": _norm_enum(payload["tipo_nacimiento"], _TIPO_NAC, "tipo_nacimiento"),
        "sexo": _norm_enum(payload["sexo"], _SEXO, "sexo"),
        "peso_nacer": _as_float_ge0(payload["peso_nacer"], "peso_nacer"),
        "perimetro_cefalico": _as_float_ge0(payload["perimetro_cefalico"], "perimetro_cefalico"),
        "longitud": _as_float_ge0(payload["longitud"], "longitud"),
        "edad_gestacional": _build_edad_gestacional(payload["edad_gestacional"]),
        "peso_edad_gestacional": _norm_enum(payload["peso_edad_gestacional"], _PESO_EG, "peso_edad_gestacional"),
        "cuidados_inmediatos": _build_cuidados(payload["cuidados_inmediatos"]),
        "apgar": _build_apgar(payload["apgar"]),
        "reanimacion": reanim,
        "fallece_sala_parto": _norm_enum(payload["fallece_sala_parto"], _FALLECE_SALA, "fallece_sala_parto"),
        "referido": _norm_enum(payload["referido"], _REFERIDO, "referido"),
        "atendio": _build_atendio(payload["atendio"]),
        "defectos_congenitos": _build_defectos(payload["defectos_congenitos"]),
        "enfermedades": _build_enfermedades(payload["enfermedades"]),
        "vih_rn": _build_vih_rn(payload["vih_rn"]),
        "tamizaje_neonatal": _build_tamizaje(payload["tamizaje_neonatal"]),
        "meconio": _norm_enum(payload["meconio"], _SI_NO, "meconio"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ---------------- Services ----------------
def crear_recien_nacido(paciente_id: str, payload: dict, session=None, usuario_actual: dict | None = None):
    """Crea el documento de recién nacido (orquestado por paciente_id)."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not paciente_id:
            return _fail("paciente_id es requerido", 422)

        doc = _build_doc(paciente_id, payload, usuario_actual)
        res = (mongo.db.recien_nacido.insert_one(doc, session=session)
               if session else mongo.db.recien_nacido.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al guardar recién nacido: {str(e)}", 400)


def obtener_recien_nacido_por_id(rn_id: str):
    try:
        oid = _to_oid(rn_id, "rn_id")
        doc = mongo.db.recien_nacido.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def get_recien_nacido_by_id_paciente(paciente_id: str):
    """Devuelve el registro más reciente por paciente_id."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.recien_nacido.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró registro de recién nacido para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener", 400)


def actualizar_recien_nacido_por_id(rn_id: str, payload: dict, session=None):
    """Actualiza por _id. Valida/normaliza lo presente en payload."""
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(rn_id, "rn_id")
        upd = {}

        # Reasignaciones opcionales
        if "paciente_id" in payload and payload["paciente_id"]:
            upd["paciente_id"] = _to_oid(payload["paciente_id"], "paciente_id")
        if "identificacion_id" in payload and payload["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(payload["identificacion_id"], "identificacion_id")
        if "usuario_id" in payload and payload["usuario_id"]:
            upd["usuario_id"] = _to_oid(payload["usuario_id"], "usuario_id")

        # Campos simples/enums
        for f, enum in [
            ("tipo_nacimiento", _TIPO_NAC),
            ("sexo", _SEXO),
            ("peso_edad_gestacional", _PESO_EG),
            ("fallece_sala_parto", _FALLECE_SALA),
            ("referido", _REFERIDO),
            ("meconio", _SI_NO),
        ]:
            if f in payload and payload[f] is not None:
                upd[f] = _norm_enum(payload[f], enum, f)

        for f in ("peso_nacer", "perimetro_cefalico", "longitud"):
            if f in payload and payload[f] is not None:
                upd[f] = _as_float_ge0(payload[f], f)

        # Subdocumentos
        if "edad_gestacional" in payload and payload["edad_gestacional"] is not None:
            upd["edad_gestacional"] = _build_edad_gestacional(payload["edad_gestacional"])

        if "cuidados_inmediatos" in payload and payload["cuidados_inmediatos"] is not None:
            upd["cuidados_inmediatos"] = _build_cuidados(payload["cuidados_inmediatos"])

        if "apgar" in payload and payload["apgar"] is not None:
            upd["apgar"] = _build_apgar(payload["apgar"])

        if "reanimacion" in payload and payload["reanimacion"] is not None:
            if not isinstance(payload["reanimacion"], list):
                return _fail("reanimacion debe ser arreglo", 422)
            upd["reanimacion"] = [_norm_enum(x, _REANIM, "reanimacion[]") for x in payload["reanimacion"]]

        if "atendio" in payload and payload["atendio"] is not None:
            upd["atendio"] = _build_atendio(payload["atendio"])

        if "defectos_congenitos" in payload and payload["defectos_congenitos"] is not None:
            upd["defectos_congenitos"] = _build_defectos(payload["defectos_congenitos"])

        if "enfermedades" in payload and payload["enfermedades"] is not None:
            upd["enfermedades"] = _build_enfermedades(payload["enfermedades"])

        if "vih_rn" in payload and payload["vih_rn"] is not None:
            upd["vih_rn"] = _build_vih_rn(payload["vih_rn"])

        if "tamizaje_neonatal" in payload and payload["tamizaje_neonatal"] is not None:
            upd["tamizaje_neonatal"] = _build_tamizaje(payload["tamizaje_neonatal"])

        if not upd:
            return _fail("Nada para actualizar", 422)

        upd["updated_at"] = datetime.utcnow()
        res = mongo.db.recien_nacido.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Recién nacido actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)


def eliminar_recien_nacido_por_id(rn_id: str, session=None):
    try:
        oid = _to_oid(rn_id, "rn_id")
        res = mongo.db.recien_nacido.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Recién nacido eliminado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
