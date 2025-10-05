from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Utilidades / Enums ----------------
_SI_NO_NC = {"si", "no", "n/c"}
_ESTADO = {"viva", "fallece"}

_REQUIRED_TOP_LEVEL = [
    "antirrubeola_post_parto",
    "gamma_globulina_antiD",
    "egreso_materno",
    "dias_completos_desde_parto",
    "responsable",
]

# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _norm_enum(v, opts, field):
    if isinstance(v, str) and v.strip().lower() in opts:
        return v.strip().lower()
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(opts))}")

def _as_int(v, field):
    try:
        iv = int(v)
        return iv
    except Exception:
        raise ValueError(f"{field} debe ser entero")

def _as_nonneg_int(v, field):
    iv = _as_int(v, field)
    if iv < 0:
        raise ValueError(f"{field} debe ser >= 0")
    return iv

def _parse_dt_flexible(s, field):
    """
    Acepta:
      - DD/MM/YYYY HH:MM
      - DD/MM/YYYY
      - YYYY-MM-DDTHH:MM
      - YYYY-MM-DD
    Si viene solo fecha, se asume 00:00.
    """
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string")
    s = s.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                dt = dt.replace(hour=0, minute=0)
            return dt
        except ValueError:
            continue
    raise ValueError(f"{field} con formato inválido")

def _require_fields(payload: dict):
    faltan = [f for f in _REQUIRED_TOP_LEVEL if f not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _ensure_indexes():
    try:
        mongo.db.egreso_materno.create_index("historial_id", name="ix_em_historial_id")
    except Exception:
        pass
    try:
        mongo.db.egreso_materno.create_index("paciente_id", name="ix_em_paciente_id")
    except Exception:
        pass

def _serialize(doc: dict):
    egreso = dict(doc.get("egreso_materno") or {})
    if isinstance(egreso.get("fecha"), datetime):
        egreso["fecha"] = egreso["fecha"].strftime("%d/%m/%Y %H:%M")
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,  # apoyo/migración
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,
        "antirrubeola_post_parto": doc.get("antirrubeola_post_parto"),
        "gamma_globulina_antiD": doc.get("gamma_globulina_antiD"),
        "egreso_materno": egreso,
        "dias_completos_desde_parto": doc.get("dias_completos_desde_parto"),
        "responsable": doc.get("responsable"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ---------------- Services ----------------
def crear_egreso_materno(
    historial_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea un documento en egreso_materno ORIENTADO A HISTORIAL.
    Requiere en firma: historial_id (FK principal).
    Requiere en payload: antirrubeola_post_parto, gamma_globulina_antiD,
    egreso_materno{estado, fecha, ...}, dias_completos_desde_parto, responsable.
    Opcionales: paciente_id, identificacion_id. usuario_actual.usuario_id para auditoría.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        _require_fields(payload)
        _ensure_indexes()

        # validar FK principal
        h_oid = _to_oid(historial_id, "historial_id")
        if not mongo.db.historiales.find_one({"_id": h_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        # enums top-level
        antirr = _norm_enum(payload["antirrubeola_post_parto"], _SI_NO_NC, "antirrubeola_post_parto")
        gammaD = _norm_enum(payload["gamma_globulina_antiD"], _SI_NO_NC, "gamma_globulina_antiD")

        # egreso_materno
        egreso = payload["egreso_materno"]
        if not isinstance(egreso, dict):
            return _fail("egreso_materno debe ser objeto", 422)
        if "estado" not in egreso or "fecha" not in egreso:
            return _fail("En egreso_materno faltan 'estado' y/o 'fecha'", 422)

        estado = _norm_enum(str(egreso["estado"]), _ESTADO, "egreso_materno.estado")
        fecha_dt = _parse_dt_flexible(egreso["fecha"], "egreso_materno.fecha")

        traslado_flag = bool(egreso.get("traslado", False))
        lugar_traslado = (egreso.get("lugar_traslado") or "").strip() if traslado_flag else None
        if traslado_flag and not lugar_traslado:
            return _fail("Si 'traslado' es true, 'lugar_traslado' es obligatorio", 422)

        fallece_tx = egreso.get("fallece_durante_o_en_traslado", None)
        if fallece_tx is not None:
            fallece_tx = bool(fallece_tx)

        edad_fall = egreso.get("edad_en_dias_fallecimiento", None)
        if estado == "fallece":
            if edad_fall is None:
                return _fail("Si estado='fallece', 'edad_en_dias_fallecimiento' es obligatorio", 422)
            edad_fall = _as_nonneg_int(edad_fall, "egreso_materno.edad_en_dias_fallecimiento")
        elif traslado_flag and fallece_tx:
            if edad_fall is None:
                return _fail("Si fallece durante/en traslado, 'edad_en_dias_fallecimiento' es obligatorio", 422)
            edad_fall = _as_nonneg_int(edad_fall, "egreso_materno.edad_en_dias_fallecimiento")
        else:
            edad_fall = None

        doc = {
            "historial_id": h_oid,
            **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")}
               if payload.get("paciente_id") else {}),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
               if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            "antirrubeola_post_parto": antirr,
            "gamma_globulina_antiD": gammaD,
            "egreso_materno": {
                "estado": estado,
                "fecha": fecha_dt,
                **({"traslado": True, "lugar_traslado": lugar_traslado} if traslado_flag else {"traslado": False}),
                **({"fallece_durante_o_en_traslado": fallece_tx} if fallece_tx is not None else {}),
                **({"edad_en_dias_fallecimiento": edad_fall} if edad_fall is not None else {}),
            },
            "dias_completos_desde_parto": _as_nonneg_int(payload["dias_completos_desde_parto"], "dias_completos_desde_parto"),
            "responsable": str(payload["responsable"]).strip(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = (mongo.db.egreso_materno.insert_one(doc, session=session)
               if session else mongo.db.egreso_materno.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al registrar egreso materno: {str(e)}", 400)

def obtener_egreso_materno_por_id(egreso_id: str):
    try:
        oid = _to_oid(egreso_id, "egreso_id")
        doc = mongo.db.egreso_materno.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener datos", 400)

def obtener_egreso_materno_por_historial(historial_id: str):
    """Devuelve el registro más reciente por historial_id."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.egreso_materno.find_one({"historial_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontraron datos de egreso materno para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener datos", 400)

# ---- Soporte/migración (opcional)
def get_egreso_materno_by_id_paciente(paciente_id: str):
    """Más reciente por paciente_id (soporte legado)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.egreso_materno.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontraron datos de egreso materno para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener datos", 400)

def actualizar_egreso_materno_por_id(egreso_id: str, payload: dict, session=None):
    """
    Actualiza por _id. Permite cambiar historial_id (validando existencia).
    Re-normaliza enums y fechas si vienen y valida coherencias.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(egreso_id, "egreso_id")
        upd = dict(payload)

        # FK principal
        if "historial_id" in upd and upd["historial_id"] is not None:
            h_oid = _to_oid(upd["historial_id"], "historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            upd["historial_id"] = h_oid

        # ids auxiliares
        if "identificacion_id" in upd and upd["identificacion_id"]:
            upd["identificacion_id"] = _to_oid(upd["identificacion_id"], "identificacion_id")
        if "paciente_id" in upd and upd["paciente_id"]:
            upd["paciente_id"] = _to_oid(upd["paciente_id"], "paciente_id")
        if "usuario_id" in upd and upd["usuario_id"]:
            upd["usuario_id"] = _to_oid(upd["usuario_id"], "usuario_id")

        # top-level enums/ints
        if "antirrubeola_post_parto" in upd and upd["antirrubeola_post_parto"] is not None:
            upd["antirrubeola_post_parto"] = _norm_enum(upd["antirrubeola_post_parto"], _SI_NO_NC, "antirrubeola_post_parto")

        if "gamma_globulina_antiD" in upd and upd["gamma_globulina_antiD"] is not None:
            upd["gamma_globulina_antiD"] = _norm_enum(upd["gamma_globulina_antiD"], _SI_NO_NC, "gamma_globulina_antiD")

        if "dias_completos_desde_parto" in upd and upd["dias_completos_desde_parto"] is not None:
            upd["dias_completos_desde_parto"] = _as_nonneg_int(upd["dias_completos_desde_parto"], "dias_completos_desde_parto")

        # egreso_materno
        if "egreso_materno" in upd and isinstance(upd["egreso_materno"], dict):
            em = dict(upd["egreso_materno"])

            if "estado" in em and em["estado"] is not None:
                em["estado"] = _norm_enum(str(em["estado"]), _ESTADO, "egreso_materno.estado")

            if "fecha" in em and em["fecha"]:
                em["fecha"] = _parse_dt_flexible(em["fecha"], "egreso_materno.fecha")

            # traslado & coherencias
            if "traslado" in em and em["traslado"] is not None:
                em["traslado"] = bool(em["traslado"])

            traslado_flag = em.get("traslado", None)
            if traslado_flag is True and not em.get("lugar_traslado"):
                return _fail("Si 'traslado' es true, 'lugar_traslado' es obligatorio", 422)

            if "fallece_durante_o_en_traslado" in em and em["fallece_durante_o_en_traslado"] is not None:
                em["fallece_durante_o_en_traslado"] = bool(em["fallece_durante_o_en_traslado"])

            if "edad_en_dias_fallecimiento" in em and em["edad_en_dias_fallecimiento"] is not None:
                em["edad_en_dias_fallecimiento"] = _as_nonneg_int(em["edad_en_dias_fallecimiento"], "egreso_materno.edad_en_dias_fallecimiento")

            # Reglas de coherencia
            estado = em.get("estado")
            if estado == "fallece" and em.get("edad_en_dias_fallecimiento") is None:
                return _fail("Si estado='fallece', 'edad_en_dias_fallecimiento' es obligatorio", 422)
            if traslado_flag is True and em.get("fallece_durante_o_en_traslado") is True and em.get("edad_en_dias_fallecimiento") is None:
                return _fail("Si fallece durante/en traslado, 'edad_en_dias_fallecimiento' es obligatorio", 422)

            upd["egreso_materno"] = em

        upd["updated_at"] = datetime.utcnow()

        res = mongo.db.egreso_materno.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Egreso materno actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar", 400)

def eliminar_egreso_materno_por_id(egreso_id: str, session=None):
    try:
        oid = _to_oid(egreso_id, "egreso_id")
        res = mongo.db.egreso_materno.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Egreso materno eliminado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)

def eliminar_egreso_materno_por_historial_id(historial_id: str, session=None):
    try:
        oid = _to_oid(historial_id, "historial_id")
        res = mongo.db.egreso_materno.delete_many({"historial_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontraron documentos para este historial", 404)
        return _ok({"mensaje": f"Se eliminaron {res.deleted_count} egresos maternos"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
