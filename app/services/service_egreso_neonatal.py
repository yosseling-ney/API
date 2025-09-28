from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code

def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


# ---------------- Constantes / Utilidades ----------------
_ESTADO_ENUM = {"vivo", "traslado", "fallece"}
_SI_NO_ENUM = {"si", "no"}
_ALIMENTO_ENUM = {"lact_exclusiva", "lact_no_exclusiva", "leche_artificial"}

_REQUIRED_FIELDS = [
    # del orquestador: paciente_id es requerido en la FIRMA, no en el payload
    "estado",
    "fecha_hora_evento",
    "codigo_traslado",            # si estado == traslado, debe venir no-vacío
    "fallece_durante_traslado",   # si estado == traslado, enum si/no
    "edad_egreso_dias",
    "id_rn",
    "alimento_alta",
    "boca_arriba",
    "bcg_aplicada",
    "peso_egreso",
    "nombre_rn",
    "responsable",
]

def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _norm_enum(value, enum_set, field):
    if isinstance(value, str):
        v = value.strip().lower()
        if v in enum_set:
            return v
    raise ValueError(f"{field} inválido; use uno de: {', '.join(sorted(enum_set))}")

def _as_nonneg_int(v, field):
    try:
        iv = int(v)
        if iv < 0:
            raise ValueError
        return iv
    except Exception:
        raise ValueError(f"{field} debe ser entero >= 0")

def _as_nonneg_float(v, field):
    try:
        fv = float(v)
        if fv < 0:
            raise ValueError
        return fv
    except Exception:
        raise ValueError(f"{field} debe ser numérico >= 0")

def _parse_dt(dt_str: str, field="fecha_hora_evento"):
    """
    Acepta "YYYY-MM-DD HH:MM" o "DD/MM/YYYY HH:MM".
    Si te llega solo fecha "YYYY-MM-DD" ó "DD/MM/YYYY", asume 00:00.
    """
    if not isinstance(dt_str, str):
        raise ValueError(f"{field} debe ser string")
    s = dt_str.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                dt = dt.replace(hour=0, minute=0)
            return dt
        except ValueError:
            continue
    raise ValueError(f"{field} debe tener formato 'YYYY-MM-DD HH:MM' o 'DD/MM/YYYY HH:MM'")

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
        "estado": doc.get("estado"),  # 'vivo' | 'traslado' | 'fallece'
        "fecha_hora_evento": doc["fecha_hora_evento"].strftime("%Y-%m-%d %H:%M") if doc.get("fecha_hora_evento") else None,
        "codigo_traslado": doc.get("codigo_traslado"),
        "fallece_durante_traslado": doc.get("fallece_durante_traslado"),  # 'si' | 'no'
        "edad_egreso_dias": doc.get("edad_egreso_dias"),
        "id_rn": doc.get("id_rn"),
        "alimento_alta": doc.get("alimento_alta"),        # enum alimento
        "boca_arriba": doc.get("boca_arriba"),            # 'si' | 'no'
        "bcg_aplicada": doc.get("bcg_aplicada"),          # 'si' | 'no'
        "peso_egreso": doc.get("peso_egreso"),
        "nombre_rn": doc.get("nombre_rn"),
        "responsable": doc.get("responsable"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------- Services ----------------
def crear_egreso_neonatal(
    paciente_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea egreso RN.
    Requiere en la firma: paciente_id.
    Requiere en payload: campos de _REQUIRED_FIELDS.
    Opcionales: identificacion_id. usuario_actual.usuario_id (recomendado para auditoría).
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        if not paciente_id:
            return _fail("paciente_id es requerido", 422)

        _require_fields(payload)

        estado = _norm_enum(payload["estado"], _ESTADO_ENUM, "estado")
        fecha_dt = _parse_dt(payload["fecha_hora_evento"], "fecha_hora_evento")
        edad_dias = _as_nonneg_int(payload["edad_egreso_dias"], "edad_egreso_dias")
        peso = _as_nonneg_float(payload["peso_egreso"], "peso_egreso")

        alimento = _norm_enum(payload["alimento_alta"], _ALIMENTO_ENUM, "alimento_alta")
        boca_arriba = _norm_enum(payload["boca_arriba"], _SI_NO_ENUM, "boca_arriba")
        bcg = _norm_enum(payload["bcg_aplicada"], _SI_NO_ENUM, "bcg_aplicada")

        # Validaciones condicionales por estado
        codigo_traslado = (payload.get("codigo_traslado") or "").strip()
        fallece_durante_traslado = _norm_enum(payload["fallece_durante_traslado"], _SI_NO_ENUM, "fallece_durante_traslado")

        if estado == "traslado":
            if not codigo_traslado:
                return _fail("Si estado = 'traslado', 'codigo_traslado' es obligatorio", 422)
        else:
            # si no es traslado, podemos limpiar estos campos
            if not codigo_traslado:
                codigo_traslado = None
            fallece_durante_traslado = None

        doc = {
            "paciente_id": _to_oid(paciente_id, "paciente_id"),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")}
               if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            "estado": estado,
            "fecha_hora_evento": fecha_dt,
            "codigo_traslado": codigo_traslado,
            "fallece_durante_traslado": fallece_durante_traslado,
            "edad_egreso_dias": edad_dias,
            "id_rn": str(payload["id_rn"]).strip(),
            "alimento_alta": alimento,
            "boca_arriba": boca_arriba,
            "bcg_aplicada": bcg,
            "peso_egreso": peso,
            "nombre_rn": str(payload["nombre_rn"]).strip(),
            "responsable": str(payload["responsable"]).strip(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        res = mongo.db.egreso_neonatal.insert_one(doc, session=session) if session else mongo.db.egreso_neonatal.insert_one(doc)
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al registrar egreso neonatal: {str(e)}", 400)


def obtener_egreso_neonatal_por_id(egreso_id: str):
    try:
        oid = _to_oid(egreso_id, "egreso_id")
        doc = mongo.db.egreso_neonatal.find_one({"_id": oid})
        if not doc:
            return _fail("No se encontraron datos", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener datos", 400)


def get_egreso_neonatal_by_id_paciente(paciente_id: str):
    """
    Devuelve el más reciente por paciente_id (por si existen varios).
    """
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.egreso_neonatal.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró egreso neonatal para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener datos", 400)


def obtener_egreso_neonatal_por_identificacion(identificacion_id: str):
    try:
        oid = _to_oid(identificacion_id, "identificacion_id")
        doc = mongo.db.egreso_neonatal.find_one({"identificacion_id": oid})
        if not doc:
            return _fail("No se encontró egreso neonatal para esta identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al obtener datos", 400)


def actualizar_egreso_neonatal_por_id(egreso_id: str, payload: dict, session=None):
    """
    Actualiza por _id. Re-normaliza enums y fecha si vienen.
    """
    try        :
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(egreso_id, "egreso_id")
        update = dict(payload)

        if "estado" in update and update["estado"] is not None:
            update["estado"] = _norm_enum(update["estado"], _ESTADO_ENUM, "estado")

        if "fecha_hora_evento" in update and update["fecha_hora_evento"]:
            update["fecha_hora_evento"] = _parse_dt(update["fecha_hora_evento"], "fecha_hora_evento")

        if "codigo_traslado" in update and update["codigo_traslado"] is not None:
            update["codigo_traslado"] = str(update["codigo_traslado"]).strip()

        if "fallece_durante_traslado" in update and update["fallece_durante_traslado"] is not None:
            update["fallece_durante_traslado"] = _norm_enum(update["fallece_durante_traslado"], _SI_NO_ENUM, "fallece_durante_traslado")

        if "edad_egreso_dias" in update and update["edad_egreso_dias"] is not None:
            update["edad_egreso_dias"] = _as_nonneg_int(update["edad_egreso_dias"], "edad_egreso_dias")

        if "peso_egreso" in update and update["peso_egreso"] is not None:
            update["peso_egreso"] = _as_nonneg_float(update["peso_egreso"], "peso_egreso")

        if "alimento_alta" in update and update["alimento_alta"] is not None:
            update["alimento_alta"] = _norm_enum(update["alimento_alta"], _ALIMENTO_ENUM, "alimento_alta")

        if "boca_arriba" in update and update["boca_arriba"] is not None:
            update["boca_arriba"] = _norm_enum(update["boca_arriba"], _SI_NO_ENUM, "boca_arriba")

        if "bcg_aplicada" in update and update["bcg_aplicada"] is not None:
            update["bcg_aplicada"] = _norm_enum(update["bcg_aplicada"], _SI_NO_ENUM, "bcg_aplicada")

        if "identificacion_id" in update and update["identificacion_id"]:
            update["identificacion_id"] = _to_oid(update["identificacion_id"], "identificacion_id")

        if "paciente_id" in update and update["paciente_id"]:
            update["paciente_id"] = _to_oid(update["paciente_id"], "paciente_id")

        if "usuario_id" in update and update["usuario_id"]:
            update["usuario_id"] = _to_oid(update["usuario_id"], "usuario_id")

        # coherencia condicional si estado no es traslado
        if update.get("estado") and update["estado"] != "traslado":
            if "codigo_traslado" in update and not update["codigo_traslado"]:
                update["codigo_traslado"] = None
            if "fallece_durante_traslado" in update:
                update["fallece_durante_traslado"] = None

        update["updated_at"] = datetime.utcnow()

        res = mongo.db.egreso_neonatal.update_one({"_id": oid}, {"$set": update}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Egreso neonatal actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al actualizar", 400)


def eliminar_egreso_neonatal_por_id(egreso_id: str, session=None):
    try:
        oid = _to_oid(egreso_id, "egreso_id")
        res = mongo.db.egreso_neonatal.delete_one({"_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Egreso neonatal eliminado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al eliminar", 400)
