# === app/services/gestacion_actual.py  (FINAL) ===
from datetime import datetime
from bson import ObjectId
from app import mongo

def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

_VAC_RUBEOLA = {"previa", "embarazo", "no", "no_sabe"}
_GRUPO_SANG  = {"A", "B", "AB", "O"}
_RH          = {"+", "-"}
_VIH_RES     = {"+", "-", "s/d", "n/c"}
_SIFILIS     = {"+", "-", "s/d"}
_SIFILIS_TREP= {"+", "-", "s/d", "n/c"}

# nuevos enums
_EG_POR      = {"fum_<20s", "eco_<20s", "nc"}
_TRI_NSI     = {"normal", "anormal", "no_se_hizo"}     # cervix/pap/colpo/bacteriuria
_TRI_SIG     = {"+", "-", "no_se_hizo"}                 # chagas/malaria/estrepto
_TARV_ENUM   = {"si", "no", "nc"}
_SINO_NC     = {"si", "no", "nc"}
_SI_NO_SD_NC = {"si", "no", "s/d", "nc"}
_PRESENTACION = {"cef", "pelv", "transv", "nc"}
_PROTEINURIA = {"+", "-", "nc"}

# rangos
_PESO_MIN, _PESO_MAX   = 0.0, 300.0
_TALLA_MIN, _TALLA_MAX = 0.5, 2.5
_HEMO_MIN, _HEMO_MAX   = 0.0, 30.0
_GLU_MIN               = 0.0

_REQUIRED_FIELDS = [
    # básicos
    "peso_anterior","talla","fum","fpp","eg_confiable",
    # estilos de vida global
    "fumadora_activa","fumadora_pasiva","drogas","alcohol","violencia",
    # vacunas / exámenes
    "vacuna_rubeola","vacuna_antitetanica","examen_mamas","examen_odonto","cervix_normal",
    # grupo/rh
    "grupo_sanguineo","rh","inmunizada",
    # laboratorios principales
    "hemoglobina","anemia",
    # glucemias y cortes por edad gestacional
    "glucemia1","glucemia_ayunas_ge_92_lt24",
    "glucemia2","glucemia_ayunas_ge_92_ge24",
    # bacteriuria/estreptococo (solicitudes)
    "bacteriuria","estreptococo",
    # resultados obligatorios
    "chagas_res","malaria_res",
    # VIH por corte gestacional
    "vih_solicitada_lt20","vih_resultado_lt20","tarv_emb_lt20",
    "vih_solicitada_ge20","vih_resultado_ge20","tarv_emb_ge20",
    # Sífilis por corte gestacional
    "sifilis_no_trep_lt20","sifilis_trep_lt20","sifilis_tratamiento_lt20","pareja_tratada_lt20",
    "sifilis_no_trep_ge20","sifilis_trep_ge20","sifilis_tratamiento_ge20","pareja_tratada_ge20",
    # consejería
    "preparacion_parto","consejeria_lactancia_materna",
]

def _to_oid(v, field):
    try: return ObjectId(v)
    except Exception: raise ValueError(f"{field} no es un ObjectId válido")

def _as_bool(v, field):
    if isinstance(v, bool): return v
    if isinstance(v, (int,float)) and v in (0,1): return bool(v)
    if isinstance(v, str) and v.lower() in ("true","false"): return v.lower()=="true"
    raise ValueError(f"{field} debe ser booleano")

def _as_int_in_range(v, field, lo=None, hi=None):
    try: x=int(v)
    except Exception: raise ValueError(f"{field} debe ser entero")
    if (lo is not None and x<lo) or (hi is not None and x>hi):
        raise ValueError(f"{field} fuera de rango permitido [{lo}, {hi}]")
    return x

def _as_float(v, field):
    try: return float(v)
    except Exception: raise ValueError(f"{field} debe ser numérico")

def _as_float_in_range(v, field, lo=None, hi=None):
    x=_as_float(v, field)
    if (lo is not None and x<lo) or (hi is not None and x>hi):
        raise ValueError(f"{field} fuera de rango permitido [{lo}, {hi}]")
    return x

def _as_date_ymd(s, field):
    if not isinstance(s, str): raise ValueError(f"{field} debe ser string con formato YYYY-MM-DD")
    try: return datetime.strptime(s.strip(), "%Y-%m-%d")
    except Exception: raise ValueError(f"{field} debe tener formato YYYY-MM-DD")

def _norm_enum(v, opts, field):
    if isinstance(v, str) and v.strip() in opts: return v.strip()
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(opts))}")

# compat: aceptar booleanos y mapear a enums
def _norm_sino_nc_legacy(v, field):
    if isinstance(v, bool): return "si" if v else "no"
    return _norm_enum(v, _SINO_NC, field)

def _norm_tarv_legacy(v, field):
    if isinstance(v, bool): return "si" if v else "no"
    return _norm_enum(v, _TARV_ENUM, field)

def _norm_tri_nsi_legacy_from_bool(v, field):
    if isinstance(v, bool): return "anormal" if v else "normal"
    return _norm_enum(v, _TRI_NSI, field)

def _norm_tri_sig_legacy_from_bool(v, field):
    if isinstance(v, bool): return "+" if v else "-"
    return _norm_enum(v, _TRI_SIG, field)

def _norm_si_no_sd_nc(v, field):
    return _norm_enum(v, _SI_NO_SD_NC, field)

def _as_optional_str(v):
    if v is None: return None
    if isinstance(v, str): return v
    return str(v)

def _as_float_in_range_or_none(v, field, lo=None, hi=None):
    if v is None: return None
    return _as_float_in_range(v, field, lo, hi)

def _as_int_in_range_or_none(v, field, lo=None, hi=None):
    if v is None: return None
    return _as_int_in_range(v, field, lo, hi)

def _as_date_ymd_or_none(s, field):
    if not s: return None
    return _as_date_ymd(s, field)

def _norm_apn_item(raw: dict, idx: int):
    if not isinstance(raw, dict):
        raise ValueError(f"apn[{idx}] debe ser un objeto")
    item = {}
    # requeridos por item
    item["fecha"] = _as_date_ymd(raw.get("fecha"), f"apn[{idx}].fecha")
    item["eg_semanas"] = _as_int_in_range(raw.get("eg_semanas"), f"apn[{idx}].eg_semanas", 0, 45)
    item["peso_kg"] = _as_float_in_range(raw.get("peso_kg"), f"apn[{idx}].peso_kg", _PESO_MIN, _PESO_MAX)
    item["pa_sis"] = _as_int_in_range(raw.get("pa_sis"), f"apn[{idx}].pa_sis", 60, 250)
    item["pa_dia"] = _as_int_in_range(raw.get("pa_dia"), f"apn[{idx}].pa_dia", 30, 150)
    # opcionales
    if raw.get("altura_uterina_cm") is not None:
        item["altura_uterina_cm"] = _as_float_in_range(raw.get("altura_uterina_cm"), f"apn[{idx}].altura_uterina_cm", 0, 60)
    if raw.get("presentacion") is not None:
        item["presentacion"] = _norm_enum(raw.get("presentacion"), _PRESENTACION, f"apn[{idx}].presentacion")
    if raw.get("fcf_lpm") is not None:
        item["fcf_lpm"] = _as_int_in_range(raw.get("fcf_lpm"), f"apn[{idx}].fcf_lpm", 0, 250)
    if raw.get("mov_fetales") is not None:
        item["mov_fetales"] = _norm_sino_nc_legacy(raw.get("mov_fetales"), f"apn[{idx}].mov_fetales")
    if raw.get("proteinuria") is not None:
        item["proteinuria"] = _norm_enum(raw.get("proteinuria"), _PROTEINURIA, f"apn[{idx}].proteinuria")
    if raw.get("nota") is not None:
        item["nota"] = _as_optional_str(raw.get("nota"))
    if raw.get("iniciales") is not None:
        item["iniciales"] = _as_optional_str(raw.get("iniciales"))
    if raw.get("proxima_cita") is not None:
        item["proxima_cita"] = _as_date_ymd_or_none(raw.get("proxima_cita"), f"apn[{idx}].proxima_cita")
    return item

def _norm_apn_list(lst):
    if lst is None:
        return None
    if not isinstance(lst, list):
        raise ValueError("apn debe ser una lista")
    if len(lst) == 0:
        return []
    return [_norm_apn_item(x, i) for i, x in enumerate(lst)]

def _require_fields(payload: dict):
    faltan=[f for f in _REQUIRED_FIELDS if f not in payload]
    if faltan: raise ValueError("Campos requeridos faltantes: "+", ".join(faltan))

def _ensure_indexes():
    try: mongo.db.gestacion_actual.create_index("historial_id", name="ix_ga_historial_id")
    except Exception: pass
    try: mongo.db.gestacion_actual.create_index("paciente_id", name="ix_ga_paciente_id")
    except Exception: pass

def _serialize(doc: dict):
    # serializar APN (si existe)
    apn_ser = []
    try:
        for item in (doc.get("apn") or []):
            apn_ser.append({
                **({"fecha": item.get("fecha").strftime("%Y-%m-%d")} if isinstance(item.get("fecha"), datetime) else ({"fecha": item.get("fecha")} if item.get("fecha") else {})),
                **{k: v for k, v in item.items() if k not in ("fecha", "proxima_cita")},
                **({"proxima_cita": item.get("proxima_cita").strftime("%Y-%m-%d")} if isinstance(item.get("proxima_cita"), datetime) else ({"proxima_cita": item.get("proxima_cita")} if item.get("proxima_cita") else {})),
            })
    except Exception:
        apn_ser = []
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        # básicos
        "peso_anterior": doc.get("peso_anterior"),
        "talla": doc.get("talla"),
        "imc": doc.get("imc"),
        "fum": doc["fum"].strftime("%Y-%m-%d") if doc.get("fum") else None,
        "fpp": doc["fpp"].strftime("%Y-%m-%d") if doc.get("fpp") else None,
        "eg_confiable": doc.get("eg_confiable"),
        "eg_confiable_por": doc.get("eg_confiable_por"),
        # estilos de vida (global)
        "fumadora_activa": doc.get("fumadora_activa"),
        "fumadora_pasiva": doc.get("fumadora_pasiva"),
        "drogas": doc.get("drogas"),
        "alcohol": doc.get("alcohol"),
        "violencia": doc.get("violencia"),
        # estilos de vida por trimestre
        "fuma_act_t1": doc.get("fuma_act_t1"), "fuma_act_t2": doc.get("fuma_act_t2"), "fuma_act_t3": doc.get("fuma_act_t3"),
        "fuma_pas_t1": doc.get("fuma_pas_t1"), "fuma_pas_t2": doc.get("fuma_pas_t2"), "fuma_pas_t3": doc.get("fuma_pas_t3"),
        "drogas_t1": doc.get("drogas_t1"), "drogas_t2": doc.get("drogas_t2"), "drogas_t3": doc.get("drogas_t3"),
        "alcohol_t1": doc.get("alcohol_t1"), "alcohol_t2": doc.get("alcohol_t2"), "alcohol_t3": doc.get("alcohol_t3"),
        "violencia_t1": doc.get("violencia_t1"), "violencia_t2": doc.get("violencia_t2"), "violencia_t3": doc.get("violencia_t3"),
        # vacunas / exámenes
        "vacuna_rubeola": doc.get("vacuna_rubeola"),
        "vacuna_antitetanica": doc.get("vacuna_antitetanica"),
        "antitetanica_dosis": doc.get("antitetanica_dosis"),
        "antitetanica_mes_gestacion": doc.get("antitetanica_mes_gestacion"),
        "examen_mamas": doc.get("examen_mamas"),
        "examen_odonto": doc.get("examen_odonto"),
        "cervix_normal": doc.get("cervix_normal"),
        "cervix_inspeccion": doc.get("cervix_inspeccion"),
        "pap": doc.get("pap"),
        "colposcopia": doc.get("colposcopia"),
        "grupo_sanguineo": doc.get("grupo_sanguineo"),
        "rh": doc.get("rh"),
        "inmunizada": doc.get("inmunizada"),
        "gammaglobulina": doc.get("gammaglobulina"),
        "gammaglobulina_estado": doc.get("gammaglobulina_estado"),
        # toxoplasmosis (nuevo)
        "toxoplasmosis_igg": doc.get("toxoplasmosis_igg"),  # legacy
        "toxoplasmosis_igm": doc.get("toxoplasmosis_igm"),  # legacy
        "toxoplasmosis_igg_lt20": doc.get("toxoplasmosis_igg_lt20"),
        "toxoplasmosis_igg_ge20": doc.get("toxoplasmosis_igg_ge20"),
        "toxoplasmosis_igm_primera": doc.get("toxoplasmosis_igm_primera"),
        "hb_lt20": doc.get("hb_lt20"),
        "hb_ge20": doc.get("hb_ge20"),
        "hierro_acido_folico": doc.get("hierro_acido_folico"),  # legacy
        "hemoglobina": doc.get("hemoglobina"),
        "anemia": doc.get("anemia"),
        "hierro_indicado": doc.get("hierro_indicado"),
        "acido_folico_indicado": doc.get("acido_folico_indicado"),
        # VIH (nuevo)
        "vih_solicitado": doc.get("vih_solicitado"),  # legacy
        "vih_resultado": doc.get("vih_resultado"),    # legacy
        "tratamiento_vih": doc.get("tratamiento_vih"),# legacy
        "tarv": doc.get("tarv"),                      # legacy
        "vih_solicitada_lt20": doc.get("vih_solicitada_lt20"),
        "vih_resultado_lt20": doc.get("vih_resultado_lt20"),
        "tarv_emb_lt20": doc.get("tarv_emb_lt20"),
        "vih_solicitada_ge20": doc.get("vih_solicitada_ge20"),
        "vih_resultado_ge20": doc.get("vih_resultado_ge20"),
        "tarv_emb_ge20": doc.get("tarv_emb_ge20"),
        "sifilis": doc.get("sifilis"),  # legacy global
        "sifilis_no_trep_lt20": doc.get("sifilis_no_trep_lt20"),
        "sifilis_no_trep_ge20": doc.get("sifilis_no_trep_ge20"),
        "sifilis_trep_lt20": doc.get("sifilis_trep_lt20"),
        "sifilis_trep_ge20": doc.get("sifilis_trep_ge20"),
        "sifilis_tratamiento": doc.get("sifilis_tratamiento"),  # legacy global
        "pareja_tratada": doc.get("pareja_tratada"),            # legacy global
        "sifilis_tratamiento_lt20": doc.get("sifilis_tratamiento_lt20"),
        "pareja_tratada_lt20": doc.get("pareja_tratada_lt20"),
        "sifilis_tratamiento_ge20": doc.get("sifilis_tratamiento_ge20"),
        "pareja_tratada_ge20": doc.get("pareja_tratada_ge20"),
        "chagas": doc.get("chagas"),   # legacy solicitud
        "malaria": doc.get("malaria"), # legacy solicitud
        "bacteriuria": doc.get("bacteriuria"),
        "chagas_res": doc.get("chagas_res"),
        "malaria_res": doc.get("malaria_res"),
        "bacteriuria_res": doc.get("bacteriuria_res"),
        "estreptococo": doc.get("estreptococo"),
        "estreptococo_res": doc.get("estreptococo_res"),
        "glucemia1": doc.get("glucemia1"),
        "glucemia2": doc.get("glucemia2"),
        "glucemia_ayunas_ge_92_lt24": doc.get("glucemia_ayunas_ge_92_lt24"),
        "glucemia_ayunas_ge_92_ge24": doc.get("glucemia_ayunas_ge_92_ge24"),
        "plan_parto": doc.get("plan_parto"),                    # legacy
        "consejeria_lactancia": doc.get("consejeria_lactancia"),# legacy
        "preparacion_parto": doc.get("preparacion_parto"),
        "consejeria_lactancia_materna": doc.get("consejeria_lactancia_materna"),
        # lista APN
        "apn": apn_ser,
        "nota_control": doc.get("nota_control"),
        "iniciales_personal": doc.get("iniciales_personal"),
        "proxima_cita": doc["proxima_cita"].strftime("%Y-%m-%d") if doc.get("proxima_cita") else None,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

def crear_gestacion_actual(historial_id: str, payload: dict, session=None, usuario_actual: dict|None=None):
    try:
        if not isinstance(payload, dict): return _fail("JSON inválido", 400)
        if not historial_id: return _fail("historial_id es requerido", 422)
        _require_fields(payload); _ensure_indexes()

        h_oid=_to_oid(historial_id,"historial_id")
        if not mongo.db.historiales.find_one({"_id": h_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        peso = _as_float_in_range(payload["peso_anterior"], "peso_anterior", _PESO_MIN, _PESO_MAX)
        talla= _as_float_in_range(payload["talla"], "talla", _TALLA_MIN, _TALLA_MAX)
        imc  = round(peso/(talla*talla), 2)

        doc = {
            "historial_id": h_oid,
            **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")} if payload.get("paciente_id") else {}),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")} if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            # básicos
            "peso_anterior": peso,
            "talla": talla,
            "imc": imc,
            "fum": _as_date_ymd(payload["fum"], "fum"),
            "fpp": _as_date_ymd(payload["fpp"], "fpp"),
            "eg_confiable": _as_bool(payload["eg_confiable"], "eg_confiable"),
            "eg_confiable_por": _norm_enum(payload.get("eg_confiable_por"), _EG_POR, "eg_confiable_por") if payload.get("eg_confiable_por") else None,
            # estilos de vida (global)
            "fumadora_activa": _as_bool(payload["fumadora_activa"], "fumadora_activa"),
            "fumadora_pasiva": _as_bool(payload["fumadora_pasiva"], "fumadora_pasiva"),
            "drogas": _as_bool(payload["drogas"], "drogas"),
            "alcohol": _as_bool(payload["alcohol"], "alcohol"),
            "violencia": _as_bool(payload["violencia"], "violencia"),
            # por trimestre (si se envían)
            **{k: _norm_sino_nc_legacy(payload[k], k) for k in [
                "fuma_act_t1","fuma_act_t2","fuma_act_t3",
                "fuma_pas_t1","fuma_pas_t2","fuma_pas_t3",
                "drogas_t1","drogas_t2","drogas_t3",
                "alcohol_t1","alcohol_t2","alcohol_t3",
                "violencia_t1","violencia_t2","violencia_t3",
            ] if k in payload and payload[k] is not None},
            # vacunas / exámenes
            "vacuna_rubeola": _norm_enum(payload["vacuna_rubeola"], _VAC_RUBEOLA, "vacuna_rubeola"),
            "vacuna_antitetanica": _as_bool(payload["vacuna_antitetanica"], "vacuna_antitetanica"),
            "antitetanica_dosis": _as_int_in_range(payload.get("antitetanica_dosis"), "antitetanica_dosis", 0, 6) if payload.get("antitetanica_dosis") is not None else None,
            "antitetanica_mes_gestacion": _as_int_in_range(payload.get("antitetanica_mes_gestacion"), "antitetanica_mes_gestacion", 0, 45) if payload.get("antitetanica_mes_gestacion") is not None else None,
            "examen_mamas": _as_bool(payload["examen_mamas"], "examen_mamas"),
            "examen_odonto": _as_bool(payload["examen_odonto"], "examen_odonto"),
            "cervix_normal": _as_bool(payload["cervix_normal"], "cervix_normal"),
            "cervix_inspeccion": _norm_tri_nsi_legacy_from_bool(payload.get("cervix_inspeccion"), "cervix_inspeccion") if "cervix_inspeccion" in payload else None,
            "pap": _norm_tri_nsi_legacy_from_bool(payload.get("pap"), "pap") if "pap" in payload else None,
            "colposcopia": _norm_tri_nsi_legacy_from_bool(payload.get("colposcopia"), "colposcopia") if "colposcopia" in payload else None,
            "grupo_sanguineo": _norm_enum(payload["grupo_sanguineo"], _GRUPO_SANG, "grupo_sanguineo"),
            "rh": _norm_enum(payload["rh"], _RH, "rh"),
            "inmunizada": _as_bool(payload["inmunizada"], "inmunizada"),
            **({"gammaglobulina": _as_bool(payload["gammaglobulina"], "gammaglobulina")} if payload.get("gammaglobulina") is not None else {}),
            "gammaglobulina_estado": _norm_sino_nc_legacy(payload.get("gammaglobulina_estado"), "gammaglobulina_estado") if payload.get("gammaglobulina_estado") is not None else None,
            # toxoplasmosis (nuevo); compat: aceptar legacy igg/igm si llegan
            **({"toxoplasmosis_igg": _as_bool(payload["toxoplasmosis_igg"], "toxoplasmosis_igg")} if payload.get("toxoplasmosis_igg") is not None else {}),
            **({"toxoplasmosis_igm": _as_bool(payload["toxoplasmosis_igm"], "toxoplasmosis_igm")} if payload.get("toxoplasmosis_igm") is not None else {}),
            "toxoplasmosis_igg_lt20": _norm_tri_sig_legacy_from_bool(payload.get("toxoplasmosis_igg_lt20"), "toxoplasmosis_igg_lt20") if "toxoplasmosis_igg_lt20" in payload else None,
            "toxoplasmosis_igg_ge20": _norm_tri_sig_legacy_from_bool(payload.get("toxoplasmosis_igg_ge20"), "toxoplasmosis_igg_ge20") if "toxoplasmosis_igg_ge20" in payload else None,
            "toxoplasmosis_igm_primera": _norm_tri_sig_legacy_from_bool(payload.get("toxoplasmosis_igm_primera"), "toxoplasmosis_igm_primera") if "toxoplasmosis_igm_primera" in payload else None,
            "hb_lt20": _as_float_in_range(payload["hb_lt20"], "hb_lt20", _HEMO_MIN, _HEMO_MAX) if payload.get("hb_lt20") is not None else None,
            "hb_ge20": _as_float_in_range(payload["hb_ge20"], "hb_ge20", _HEMO_MIN, _HEMO_MAX) if payload.get("hb_ge20") is not None else None,
            **({"hierro_acido_folico": _as_bool(payload["hierro_acido_folico"], "hierro_acido_folico")} if payload.get("hierro_acido_folico") is not None else {}),
            "hierro_indicado": _as_bool(payload["hierro_indicado"], "hierro_indicado"),
            "acido_folico_indicado": _as_bool(payload["acido_folico_indicado"], "acido_folico_indicado"),
            "hemoglobina": _as_float_in_range(payload["hemoglobina"], "hemoglobina", _HEMO_MIN, _HEMO_MAX),
            "anemia": _as_bool(payload["anemia"], "anemia"),
            # VIH compat legacy
            **({"vih_solicitado": _as_bool(payload["vih_solicitado"], "vih_solicitado")} if payload.get("vih_solicitado") is not None else {}),
            **({"vih_resultado": _norm_enum(payload["vih_resultado"], _VIH_RES, "vih_resultado")} if payload.get("vih_resultado") is not None else {}),
            **({"tratamiento_vih": _as_bool(payload["tratamiento_vih"], "tratamiento_vih")} if payload.get("tratamiento_vih") is not None else {}),
            **({"tarv": _norm_tarv_legacy(payload.get("tarv"), "tarv")} if payload.get("tarv") is not None else {}),
            # VIH nueva estructura
            "vih_solicitada_lt20": _norm_sino_nc_legacy(payload.get("vih_solicitada_lt20"), "vih_solicitada_lt20") if payload.get("vih_solicitada_lt20") is not None else None,
            "vih_resultado_lt20": _norm_enum(payload.get("vih_resultado_lt20"), _VIH_RES, "vih_resultado_lt20") if payload.get("vih_resultado_lt20") is not None else None,
            "tarv_emb_lt20": _norm_sino_nc_legacy(payload.get("tarv_emb_lt20"), "tarv_emb_lt20") if payload.get("tarv_emb_lt20") is not None else None,
            "vih_solicitada_ge20": _norm_sino_nc_legacy(payload.get("vih_solicitada_ge20"), "vih_solicitada_ge20") if payload.get("vih_solicitada_ge20") is not None else None,
            "vih_resultado_ge20": _norm_enum(payload.get("vih_resultado_ge20"), _VIH_RES, "vih_resultado_ge20") if payload.get("vih_resultado_ge20") is not None else None,
            "tarv_emb_ge20": _norm_sino_nc_legacy(payload.get("tarv_emb_ge20"), "tarv_emb_ge20") if payload.get("tarv_emb_ge20") is not None else None,
            **({"sifilis": _norm_enum(payload["sifilis"], _SIFILIS, "sifilis")} if payload.get("sifilis") is not None else {}),
            "sifilis_no_trep_lt20": _norm_enum(payload.get("sifilis_no_trep_lt20"), _SIFILIS, "sifilis_no_trep_lt20") if payload.get("sifilis_no_trep_lt20") else None,
            "sifilis_no_trep_ge20": _norm_enum(payload.get("sifilis_no_trep_ge20"), _SIFILIS, "sifilis_no_trep_ge20") if payload.get("sifilis_no_trep_ge20") else None,
            "sifilis_trep_lt20": _norm_enum(payload.get("sifilis_trep_lt20"), _SIFILIS_TREP, "sifilis_trep_lt20") if payload.get("sifilis_trep_lt20") else None,
            "sifilis_trep_ge20": _norm_enum(payload.get("sifilis_trep_ge20"), _SIFILIS_TREP, "sifilis_trep_ge20") if payload.get("sifilis_trep_ge20") else None,
            # sífilis (nueva estructura) + compat
            **({"sifilis_tratamiento": _as_bool(payload["sifilis_tratamiento"], "sifilis_tratamiento")} if payload.get("sifilis_tratamiento") is not None else {}),
            **({"pareja_tratada": _as_bool(payload["pareja_tratada"], "pareja_tratada")} if payload.get("pareja_tratada") is not None else {}),
            "sifilis_tratamiento_lt20": _norm_si_no_sd_nc(payload.get("sifilis_tratamiento_lt20"), "sifilis_tratamiento_lt20") if payload.get("sifilis_tratamiento_lt20") is not None else None,
            "pareja_tratada_lt20": _norm_si_no_sd_nc(payload.get("pareja_tratada_lt20"), "pareja_tratada_lt20") if payload.get("pareja_tratada_lt20") is not None else None,
            "sifilis_tratamiento_ge20": _norm_si_no_sd_nc(payload.get("sifilis_tratamiento_ge20"), "sifilis_tratamiento_ge20") if payload.get("sifilis_tratamiento_ge20") is not None else None,
            "pareja_tratada_ge20": _norm_si_no_sd_nc(payload.get("pareja_tratada_ge20"), "pareja_tratada_ge20") if payload.get("pareja_tratada_ge20") is not None else None,
            **({"chagas": _as_bool(payload["chagas"], "chagas")} if payload.get("chagas") is not None else {}),
            **({"malaria": _as_bool(payload["malaria"], "malaria")} if payload.get("malaria") is not None else {}),
            "bacteriuria": _as_bool(payload["bacteriuria"], "bacteriuria"),
            "chagas_res": _norm_tri_sig_legacy_from_bool(payload.get("chagas_res"), "chagas_res") if "chagas_res" in payload else None,
            "malaria_res": _norm_tri_sig_legacy_from_bool(payload.get("malaria_res"), "malaria_res") if "malaria_res" in payload else None,
            "bacteriuria_res": _norm_tri_nsi_legacy_from_bool(payload.get("bacteriuria_res"), "bacteriuria_res") if "bacteriuria_res" in payload else None,
            "estreptococo": _as_bool(payload["estreptococo"], "estreptococo"),
            "estreptococo_res": _norm_tri_sig_legacy_from_bool(payload.get("estreptococo_res"), "estreptococo_res") if "estreptococo_res" in payload else None,
            "glucemia1": _as_float_in_range(payload["glucemia1"], "glucemia1", _GLU_MIN, None),
            "glucemia2": _as_float_in_range(payload["glucemia2"], "glucemia2", _GLU_MIN, None),
            "glucemia_ayunas_ge_92_lt24": _as_bool(payload["glucemia_ayunas_ge_92_lt24"], "glucemia_ayunas_ge_92_lt24"),
            "glucemia_ayunas_ge_92_ge24": _as_bool(payload["glucemia_ayunas_ge_92_ge24"], "glucemia_ayunas_ge_92_ge24"),
            # consejería nueva + compat legacy
            "preparacion_parto": _as_bool(payload["preparacion_parto"], "preparacion_parto"),
            "consejeria_lactancia_materna": _as_bool(payload["consejeria_lactancia_materna"], "consejeria_lactancia_materna"),
            "nota_control": payload.get("nota_control"),
            "iniciales_personal": payload.get("iniciales_personal"),
            # lista APN si llega
            **({"apn": _norm_apn_list(payload.get("apn"))} if "apn" in payload else {}),
            # compat legacy
            **({"plan_parto": _as_bool(payload["plan_parto"], "plan_parto")} if payload.get("plan_parto") is not None else {}),
            **({"consejeria_lactancia": _as_bool(payload["consejeria_lactancia"], "consejeria_lactancia")} if payload.get("consejeria_lactancia") is not None else {}),
            "proxima_cita": _as_date_ymd(payload["proxima_cita"], "proxima_cita") if payload.get("proxima_cita") else None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = mongo.db.gestacion_actual.insert_one(doc, session=session) if session else mongo.db.gestacion_actual.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve: return _fail(str(ve), 422)
    except Exception as e:  return _fail(f"Error al guardar gestación actual: {str(e)}", 400)

def obtener_gestacion_actual_por_id(ga_id: str):
    try:
        oid=_to_oid(ga_id,"ga_id")
        doc=mongo.db.gestacion_actual.find_one({"_id": oid})
        if not doc: return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al obtener", 400)

def obtener_gestacion_actual_por_historial(historial_id: str):
    try:
        oid=_to_oid(historial_id,"historial_id")
        doc=mongo.db.gestacion_actual.find_one({"historial_id": oid}, sort=[("created_at",-1)])
        if not doc: return _fail("No se encontró gestación actual para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al obtener", 400)

def get_gestacion_actual_by_id_paciente(paciente_id: str):
    try:
        oid=_to_oid(paciente_id,"paciente_id")
        doc=mongo.db.gestacion_actual.find_one({"paciente_id": oid}, sort=[("created_at",-1)])
        if not doc: return _fail("No se encontró gestación actual para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al obtener", 400)

def obtener_gestacion_actual_por_identificacion(identificacion_id: str):
    try:
        oid=_to_oid(identificacion_id,"identificacion_id")
        doc=mongo.db.gestacion_actual.find_one({"identificacion_id": oid}, sort=[("created_at",-1)])
        if not doc: return _fail("No se encontró gestación actual para esta identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al obtener", 400)

def actualizar_gestacion_actual_por_id(ga_id: str, payload: dict, session=None):
    try:
        if not isinstance(payload, dict): return _fail("JSON inválido", 400)
        oid=_to_oid(ga_id,"ga_id"); upd=dict(payload)

        if "historial_id" in upd and upd["historial_id"] is not None:
            h_oid=_to_oid(upd["historial_id"],"historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            upd["historial_id"]=h_oid

        for k in ("identificacion_id","paciente_id","usuario_id"):
            if k in upd and upd[k]: upd[k]=_to_oid(upd[k], k)

        for f in ("fum","fpp","proxima_cita"):
            if f in upd and upd[f]: upd[f]=_as_date_ymd(upd[f], f)

        for f in ("peso_anterior","talla","hemoglobina"):
            if f in upd and upd[f] is not None:
                if f=="peso_anterior": upd[f]=_as_float_in_range(upd[f], f, _PESO_MIN,_PESO_MAX)
                elif f=="talla":      upd[f]=_as_float_in_range(upd[f], f, _TALLA_MIN,_TALLA_MAX)
                else:                 upd[f]=_as_float_in_range(upd[f], f, _HEMO_MIN,_HEMO_MAX)

        # recalcular IMC si cambió peso/talla
        if ("peso_anterior" in upd or "talla" in upd):
            doc=mongo.db.gestacion_actual.find_one({"_id": oid}, {"peso_anterior":1,"talla":1})
            peso = upd.get("peso_anterior", doc.get("peso_anterior"))
            talla= upd.get("talla", doc.get("talla"))
            if peso is not None and talla is not None:
                upd["imc"]=round(float(peso)/(float(talla)*float(talla)), 2)

        for f in ("hb_lt20","hb_ge20"):
            if f in upd and upd[f] is not None:
                upd[f]=_as_float_in_range(upd[f], f, _HEMO_MIN,_HEMO_MAX)
        for g in ("glucemia1","glucemia2"):
            if g in upd and upd[g] is not None:
                upd[g]=_as_float_in_range(upd[g], g, _GLU_MIN, None)
        for i in ("antitetanica_dosis","antitetanica_mes_gestacion"):
            if i in upd and upd[i] is not None:
                upd[i]=_as_int_in_range(upd[i], i, 0, 6 if i=="antitetanica_dosis" else 45)

        for b in ("eg_confiable","fumadora_activa","fumadora_pasiva","drogas","alcohol","violencia",
                  "vacuna_antitetanica","examen_mamas","examen_odonto","cervix_normal","inmunizada",
                  "gammaglobulina","toxoplasmosis_igg","toxoplasmosis_igm","hierro_acido_folico",
                  "vih_solicitado","tratamiento_vih","sifilis_tratamiento","pareja_tratada",
                  "chagas","malaria","bacteriuria","estreptococo","plan_parto","consejeria_lactancia"):
            if b in upd and upd[b] is not None: upd[b]=_as_bool(upd[b], b)

        if "vacuna_rubeola" in upd and upd["vacuna_rubeola"]:
            upd["vacuna_rubeola"]=_norm_enum(upd["vacuna_rubeola"], _VAC_RUBEOLA,"vacuna_rubeola")
        if "grupo_sanguineo" in upd and upd["grupo_sanguineo"]:
            upd["grupo_sanguineo"]=_norm_enum(upd["grupo_sanguineo"], _GRUPO_SANG,"grupo_sanguineo")
        if "rh" in upd and upd["rh"]:
            upd["rh"]=_norm_enum(upd["rh"], _RH,"rh")
        if "vih_resultado" in upd and upd["vih_resultado"]:
            upd["vih_resultado"]=_norm_enum(upd["vih_resultado"], _VIH_RES,"vih_resultado")
        if "sifilis" in upd and upd["sifilis"]:
            upd["sifilis"]=_norm_enum(upd["sifilis"], _SIFILIS,"sifilis")
        if "eg_confiable_por" in upd and upd["eg_confiable_por"]:
            upd["eg_confiable_por"]=_norm_enum(upd["eg_confiable_por"], _EG_POR,"eg_confiable_por")

        for tri in ("cervix_inspeccion","pap","colposcopia","bacteriuria_res"):
            if tri in upd and upd[tri] is not None:
                upd[tri]=_norm_tri_nsi_legacy_from_bool(upd[tri], tri)
        for tri in ("chagas_res","malaria_res","estreptococo_res"):
            if tri in upd and upd[tri] is not None:
                upd[tri]=_norm_tri_sig_legacy_from_bool(upd[tri], tri)

        if "tarv" in upd and upd["tarv"] is not None:
            upd["tarv"]=_norm_tarv_legacy(upd["tarv"], "tarv")
        if "gammaglobulina_estado" in upd and upd["gammaglobulina_estado"] is not None:
            upd["gammaglobulina_estado"]=_norm_sino_nc_legacy(upd["gammaglobulina_estado"], "gammaglobulina_estado")

        for k in [
            "fuma_act_t1","fuma_act_t2","fuma_act_t3","fuma_pas_t1","fuma_pas_t2","fuma_pas_t3",
            "drogas_t1","drogas_t2","drogas_t3","alcohol_t1","alcohol_t2","alcohol_t3",
            "violencia_t1","violencia_t2","violencia_t3"
        ]:
            if k in upd and upd[k] is not None:
                upd[k]=_norm_sino_nc_legacy(upd[k], k)

        for k in ("sifilis_no_trep_lt20","sifilis_no_trep_ge20"):
            if k in upd and upd[k]:
                upd[k]=_norm_enum(upd[k], _SIFILIS, k)
        for k in ("sifilis_trep_lt20","sifilis_trep_ge20"):
            if k in upd and upd[k]:
                upd[k]=_norm_enum(upd[k], _SIFILIS_TREP, k)

        upd["updated_at"]=datetime.utcnow()
        res=mongo.db.gestacion_actual.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count==0: return _fail("No se encontró el documento", 404)
        return _ok({"mensaje":"Gestación actual actualizada"}, 200)

    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al actualizar", 400)

def eliminar_gestacion_actual_por_id(ga_id: str, session=None):
    try:
        oid=_to_oid(ga_id,"ga_id")
        res=mongo.db.gestacion_actual.delete_one({"_id": oid}, session=session)
        if res.deleted_count==0: return _fail("No se encontró el documento", 404)
        return _ok({"mensaje":"Gestación actual eliminada"}, 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al eliminar", 400)

def eliminar_gestacion_actual_por_historial_id(historial_id: str, session=None):
    try:
        oid=_to_oid(historial_id,"historial_id")
        res=mongo.db.gestacion_actual.delete_many({"historial_id": oid}, session=session)
        if res.deleted_count==0: return _fail("No se encontraron documentos para este historial", 404)
        return _ok({"mensaje": f"Se eliminaron {res.deleted_count} registros de gestación actual"}, 200)
    except ValueError as ve: return _fail(str(ve), 422)
    except Exception: return _fail("Error al eliminar", 400)
