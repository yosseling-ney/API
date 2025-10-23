# app/services/service_egreso_neonatal.py
from datetime import datetime
from bson import ObjectId
from app import mongo

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Constantes / Utilidades ----------------
_ESTADO_ENUM   = {"vivo", "traslado", "fallece"}
_SI_NO_ENUM    = {"si", "no"}
_ALIMENTO_ENUM = {"lact_exclusiva", "lact_no_exclusiva", "leche_artificial"}

# Campos siempre requeridos en el payload (los condicionales se validan aparte)
_REQUIRED_CORE = [
    "estado",
    "fecha_hora_evento",
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
    Acepta:
      - 'YYYY-MM-DD HH:MM'
      - 'DD/MM/YYYY HH:MM'
      - 'YYYY-MM-DD' o 'DD/MM/YYYY' (asume 00:00)
      - 'YYYY-MM-DD HH:MM:SS'
      - ISO: 'YYYY-MM-DDTHH:MM' o 'YYYY-MM-DDTHH:MM:SS'
    """
    if not isinstance(dt_str, str):
        raise ValueError(f"{field} debe ser string")
    s = dt_str.strip()
    formatos = (
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in formatos:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                dt = dt.replace(hour=0, minute=0)
            return dt
        except ValueError:
            continue
    raise ValueError(f"{field} debe tener formato 'YYYY-MM-DD HH:MM' (o equivalentes aceptados)")

def _require_core(payload: dict):
    faltan = [f for f in _REQUIRED_CORE if f not in payload]
    if faltan:
        raise ValueError("Campos requeridos faltantes: " + ", ".join(faltan))

def _ensure_indexes():
    try:
        mongo.db.egreso_neonatal.create_index("historial_id", name="ix_en_historial_id")
    except Exception:
        pass
    try:
        mongo.db.egreso_neonatal.create_index("paciente_id", name="ix_en_paciente_id")
    except Exception:
        pass

def _serialize(doc: dict):
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc["historial_id"]) if doc.get("historial_id") else None,
        "paciente_id": str(doc["paciente_id"]) if doc.get("paciente_id") else None,  # apoyo/migración
        "identificacion_id": str(doc["identificacion_id"]) if doc.get("identificacion_id") else None,
        "usuario_id": str(doc["usuario_id"]) if doc.get("usuario_id") else None,

        "estado": doc.get("estado"),  # 'vivo' | 'traslado' | 'fallece'
        "fecha_hora_evento": doc["fecha_hora_evento"].strftime("%Y-%m-%d %H:%M") if doc.get("fecha_hora_evento") else None,

        # Traslado
        "codigo_traslado": doc.get("codigo_traslado"),
        "fallece_durante_traslado": doc.get("fallece_durante_traslado"),  # 'si' | 'no' | None

        # Fallece fuera de lugar de nacimiento
        "fallece_fuera_lugar_nacimiento": doc.get("fallece_fuera_lugar_nacimiento"),  # 'si'|'no'|None
        "codigo_establecimiento_fallecimiento": doc.get("codigo_establecimiento_fallecimiento"),

        "edad_egreso_dias": doc.get("edad_egreso_dias"),
        "id_rn": doc.get("id_rn"),
        "alimento_alta": doc.get("alimento_alta"),
        "boca_arriba": doc.get("boca_arriba"),
        "bcg_aplicada": doc.get("bcg_aplicada"),
        "peso_egreso": doc.get("peso_egreso"),
        "nombre_rn": doc.get("nombre_rn"),
        "responsable": doc.get("responsable"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

# ---------------- Services ----------------
def crear_egreso_neonatal(
    historial_id: str,
    payload: dict,
    session=None,
    usuario_actual: dict | None = None
):
    """
    Crea egreso RN ORIENTADO A HISTORIAL.
    - Si estado = 'traslado' => obligatorio: codigo_traslado (no vacío) y fallece_durante_traslado ('si'|'no').
    - Si estado = 'fallece'  => si fallece_fuera_lugar_nacimiento = 'si' => obligatorio codigo_establecimiento_fallecimiento.
    - En 'vivo' se anulan campos de traslado/fallecimiento.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)
        if not historial_id:
            return _fail("historial_id es requerido", 422)

        _require_core(payload)
        _ensure_indexes()

        # validar FK principal
        h_oid = _to_oid(historial_id, "historial_id")
        if not mongo.db.historiales.find_one({"_id": h_oid}):
            return _fail("historial_id no encontrado en historiales", 404)

        estado = _norm_enum(payload["estado"], _ESTADO_ENUM, "estado")
        fecha_dt = _parse_dt(payload["fecha_hora_evento"], "fecha_hora_evento")
        edad_dias = _as_nonneg_int(payload["edad_egreso_dias"], "edad_egreso_dias")
        peso = _as_nonneg_float(payload["peso_egreso"], "peso_egreso")

        alimento = _norm_enum(payload["alimento_alta"], _ALIMENTO_ENUM, "alimento_alta")
        boca_arriba = _norm_enum(payload["boca_arriba"], _SI_NO_ENUM, "boca_arriba")
        bcg = _norm_enum(payload["bcg_aplicada"], _SI_NO_ENUM, "bcg_aplicada")

        # --- Campos de traslado / fallecimiento
        codigo_traslado = (payload.get("codigo_traslado") or "").strip()
        fallece_valor = payload.get("fallece_durante_traslado")
        fallece_durante_traslado = None

        fallece_fuera_lugar_nacimiento_val = payload.get("fallece_fuera_lugar_nacimiento")
        fallece_fuera_lugar_nacimiento = None
        codigo_estab_fallecimiento = (payload.get("codigo_establecimiento_fallecimiento") or "").strip()

        # Validaciones condicionales por estado
        if estado == "traslado":
            if not codigo_traslado:
                return _fail("Si estado = 'traslado', 'codigo_traslado' es obligatorio", 422)
            if fallece_valor is None:
                return _fail("Si estado = 'traslado', 'fallece_durante_traslado' es obligatorio ('si'|'no')", 422)
            fallece_durante_traslado = _norm_enum(fallece_valor, _SI_NO_ENUM, "fallece_durante_traslado")
            # En traslado no aplica info de fallecimiento fuera del lugar de nacimiento
            fallece_fuera_lugar_nacimiento = None
            codigo_estab_fallecimiento = None

        elif estado == "fallece":
            # En fallece, traslado no aplica
            codigo_traslado = None
            fallece_durante_traslado = None
            # Validar “fuera del lugar de nacimiento”
            if fallece_fuera_lugar_nacimiento_val is not None:
                fallece_fuera_lugar_nacimiento = _norm_enum(
                    fallece_fuera_lugar_nacimiento_val, _SI_NO_ENUM, "fallece_fuera_lugar_nacimiento"
                )
                if fallece_fuera_lugar_nacimiento == "si" and not codigo_estab_fallecimiento:
                    return _fail(
                        "Si 'fallece_fuera_lugar_nacimiento' = 'si', 'codigo_establecimiento_fallecimiento' es obligatorio",
                        422
                    )
            else:
                # si no se envía, queda None (no marcado)
                fallece_fuera_lugar_nacimiento = None
                codigo_estab_fallecimiento = None

        else:  # estado == "vivo"
            # En vivo no aplica traslado ni fallecimiento
            codigo_traslado = None
            fallece_durante_traslado = None
            fallece_fuera_lugar_nacimiento = None
            codigo_estab_fallecimiento = None

        doc = {
            "historial_id": h_oid,
            **({"paciente_id": _to_oid(payload["paciente_id"], "paciente_id")} if payload.get("paciente_id") else {}),
            **({"identificacion_id": _to_oid(payload["identificacion_id"], "identificacion_id")} if payload.get("identificacion_id") else {}),
            **({"usuario_id": _to_oid(usuario_actual["usuario_id"], "usuario_id")}
               if usuario_actual and usuario_actual.get("usuario_id") else {}),
            "estado": estado,
            "fecha_hora_evento": fecha_dt,
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

        # set condicionales
        if codigo_traslado is not None:
            doc["codigo_traslado"] = codigo_traslado
        if fallece_durante_traslado is not None:
            doc["fallece_durante_traslado"] = fallece_durante_traslado
        if fallece_fuera_lugar_nacimiento is not None:
            doc["fallece_fuera_lugar_nacimiento"] = fallece_fuera_lugar_nacimiento
        if codigo_estab_fallecimiento:
            doc["codigo_establecimiento_fallecimiento"] = codigo_estab_fallecimiento

        res = (mongo.db.egreso_neonatal.insert_one(doc, session=session)
               if session else mongo.db.egreso_neonatal.insert_one(doc))
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
    except Exception:
        return _fail("Error al obtener datos", 400)

def obtener_egreso_neonatal_por_historial(historial_id: str):
    """Devuelve el registro más reciente por historial_id."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.egreso_neonatal.find_one({"historial_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró egreso neonatal para este historial", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener datos", 400)

# ---- Soporte/migración (opcional)
def get_egreso_neonatal_by_id_paciente(paciente_id: str):
    """Más reciente por paciente_id (soporte legado)."""
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.egreso_neonatal.find_one({"paciente_id": oid}, sort=[("created_at", -1)])
        if not doc:
            return _fail("No se encontró egreso neonatal para este paciente", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener datos", 400)

def actualizar_egreso_neonatal_por_id(egreso_id: str, payload: dict, session=None):
    """
    Actualiza por _id. Permite cambiar historial_id (validando existencia).
    Re-normaliza enums y fecha si vienen y aplica coherencias de traslado/fallece,
    incluso cuando 'estado' NO viene en el payload (usa el estado efectivo).
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(egreso_id, "egreso_id")
        current = mongo.db.egreso_neonatal.find_one({"_id": oid})
        if not current:
            return _fail("No se encontró el documento", 404)

        update = dict(payload)

        # FK principal
        if "historial_id" in update and update["historial_id"] is not None:
            h_oid = _to_oid(update["historial_id"], "historial_id")
            if not mongo.db.historiales.find_one({"_id": h_oid}):
                return _fail("historial_id no encontrado en historiales", 404)
            update["historial_id"] = h_oid

        # Auxiliares
        if "identificacion_id" in update and update["identificacion_id"]:
            update["identificacion_id"] = _to_oid(update["identificacion_id"], "identificacion_id")
        if "paciente_id" in update and update["paciente_id"]:
            update["paciente_id"] = _to_oid(update["paciente_id"], "paciente_id")
        if "usuario_id" in update and update["usuario_id"]:
            update["usuario_id"] = _to_oid(update["usuario_id"], "usuario_id")

        # Campos con normalización
        if "estado" in update and update["estado"] is not None:
            update["estado"] = _norm_enum(update["estado"], _ESTADO_ENUM, "estado")

        if "fecha_hora_evento" in update and update["fecha_hora_evento"]:
            update["fecha_hora_evento"] = _parse_dt(update["fecha_hora_evento"], "fecha_hora_evento")

        if "codigo_traslado" in update and update["codigo_traslado"] is not None:
            update["codigo_traslado"] = str(update["codigo_traslado"]).strip()

        if "fallece_durante_traslado" in update and update["fallece_durante_traslado"] is not None:
            update["fallece_durante_traslado"] = _norm_enum(update["fallece_durante_traslado"], _SI_NO_ENUM, "fallece_durante_traslado")

        if "fallece_fuera_lugar_nacimiento" in update and update["fallece_fuera_lugar_nacimiento"] is not None:
            update["fallece_fuera_lugar_nacimiento"] = _norm_enum(update["fallece_fuera_lugar_nacimiento"], _SI_NO_ENUM, "fallece_fuera_lugar_nacimiento")

        if "codigo_establecimiento_fallecimiento" in update and update["codigo_establecimiento_fallecimiento"] is not None:
            update["codigo_establecimiento_fallecimiento"] = str(update["codigo_establecimiento_fallecimiento"]).strip()

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

        # -------- Coherencia usando estado efectivo --------
        estado_efectivo = update.get("estado") or current.get("estado")

        if estado_efectivo == "traslado":
            if "codigo_traslado" in update and update["codigo_traslado"] == "":
                return _fail("Si estado = 'traslado', 'codigo_traslado' no puede ser vacío", 422)

            # Si se tocan campos de traslado, asegurar tener fallece_durante_traslado (nuevo o actual)
            if ("codigo_traslado" in update or "fallece_durante_traslado" in update):
                if update.get("fallece_durante_traslado") is None and current.get("fallece_durante_traslado") is None:
                    return _fail("Si estado = 'traslado', 'fallece_durante_traslado' es obligatorio ('si'|'no')", 422)

            # En traslado no aplica fallece fuera del lugar
            update["fallece_fuera_lugar_nacimiento"] = None
            update["codigo_establecimiento_fallecimiento"] = None

        elif estado_efectivo == "fallece":
            # En fallece, traslado no aplica
            update["codigo_traslado"] = None
            update["fallece_durante_traslado"] = None

            # Si (nuevo o actual) marca fuera del lugar = 'si', debe haber código (nuevo o actual)
            ff_new = update.get("fallece_fuera_lugar_nacimiento")
            ff_eff = ff_new if ff_new is not None else current.get("fallece_fuera_lugar_nacimiento")
            if ff_eff == "si":
                cod_final = update.get("codigo_establecimiento_fallecimiento", current.get("codigo_establecimiento_fallecimiento"))
                if not cod_final:
                    return _fail(
                        "Si 'fallece_fuera_lugar_nacimiento' = 'si', 'codigo_establecimiento_fallecimiento' es obligatorio",
                        422
                    )

        else:  # vivo
            update["codigo_traslado"] = None
            update["fallece_durante_traslado"] = None
            update["fallece_fuera_lugar_nacimiento"] = None
            update["codigo_establecimiento_fallecimiento"] = None

        update["updated_at"] = datetime.utcnow()

        res = mongo.db.egreso_neonatal.update_one({"_id": oid}, {"$set": update}, session=session)
        if res.matched_count == 0:
            return _fail("No se encontró el documento", 404)
        return _ok({"mensaje": "Egreso neonatal actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
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
    except Exception:
        return _fail("Error al eliminar", 400)

def eliminar_egreso_neonatal_por_historial_id(historial_id: str, session=None):
    try:
        oid = _to_oid(historial_id, "historial_id")
        res = mongo.db.egreso_neonatal.delete_many({"historial_id": oid}, session=session)
        if res.deleted_count == 0:
            return _fail("No se encontraron documentos para este historial", 404)
        return _ok({"mensaje": f"Se eliminaron {res.deleted_count} egresos neonatales"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar", 400)
