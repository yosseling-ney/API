from datetime import datetime
from bson import ObjectId
from flask import current_app
from app import mongo

# ==== Imports (opcionales) de otros services ====
# Se intentan cargar para el GET agregado; si no existen, se ignoran sin romper.
try:
    from app.services import service_antencedentes as svc_ant
except Exception:
    svc_ant = None

try:
    from app.services import service_identificacion as svc_ident
except Exception:
    svc_ident = None

try:
    from app.services import service_gestacion_actual as svc_ga
except Exception:
    svc_ga = None

try:
    from app.services import service_parto_aborto as svc_pa
except Exception:
    svc_pa = None

try:
    from app.services import service_patologias as svc_pat
except Exception:
    svc_pat = None

try:
    from app.services import service_puerperio as svc_puer
except Exception:
    svc_puer = None

try:
    from app.services import service_recien_nacido as svc_rn
except Exception:
    svc_rn = None

try:
    from app.services import service_egreso_neonatal as svc_en
except Exception:
    svc_en = None

try:
    from app.services import service_egreso_materno as svc_em
except Exception:
    svc_em = None

try:
    from app.services import service_anticoncepcion as svc_antico
except Exception:
    svc_antico = None


# ==== Helpers de respuesta ====
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ==== Utils ====
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _validar_numero_gesta(v):
    try:
        i = int(v)
        if i < 1:
            raise ValueError
        return i
    except Exception:
        raise ValueError("numero_gesta debe ser entero >= 1")

def _ensure_indexes_historiales():
    """
    Índices recomendados para historiales:
    - Único: (paciente_id, numero_gesta)
    - Búsqueda por paciente_id
    - Búsqueda por cada referencia
    - (Opcional) compuesto por created_at + numero_gesta para listados
    """
    try:
        mongo.db.historiales.create_index(
            [("paciente_id", 1), ("numero_gesta", 1)],
            unique=True,
            name="uq_paciente_gesta"
        )
    except Exception:
        pass
    try:
        mongo.db.historiales.create_index("paciente_id", name="ix_paciente")
    except Exception:
        pass
    for ref_field in [
        "identificacion_id", "antecedentes_id", "gestacion_actual_id",
        "parto_aborto_id", "patologias_id", "recien_nacido_id",
        "puerperio_id", "egreso_neonatal_id", "egreso_materno_id",
        "anticoncepcion_id"
    ]:
        try:
            mongo.db.historiales.create_index(ref_field, name=f"ix_{ref_field}")
        except Exception:
            pass
    try:
        mongo.db.historiales.create_index(
            [("created_at", -1), ("numero_gesta", -1)],
            name="ix_created_gesta"
        )
    except Exception:
        pass

def _serialize_historial(doc: dict):
    def _sid(x):  # stringify id
        return str(x) if isinstance(x, ObjectId) else (x if isinstance(x, str) else None)

    return {
        "id": str(doc["_id"]),
        "paciente_id": _sid(doc.get("paciente_id")),
        "numero_gesta": doc.get("numero_gesta"),
        "identificacion_id": _sid(doc.get("identificacion_id")),
        "antecedentes_id": _sid(doc.get("antecedentes_id")),
        "gestacion_actual_id": _sid(doc.get("gestacion_actual_id")),
        "parto_aborto_id": _sid(doc.get("parto_aborto_id")),
        "patologias_id": _sid(doc.get("patologias_id")),
        "recien_nacido_id": _sid(doc.get("recien_nacido_id")),
        "puerperio_id": _sid(doc.get("puerperio_id")),
        "egreso_neonatal_id": _sid(doc.get("egreso_neonatal_id")),
        "egreso_materno_id": _sid(doc.get("egreso_materno_id")),
        "anticoncepcion_id": _sid(doc.get("anticoncepcion_id")),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "activo": doc.get("activo", True),
    }


# ==== Services: HISTORIALES ====
def crear_historial(payload: dict, session=None):
    """
    Crea un historial clínico en 'historiales'.
    Requeridos: paciente_id (ObjectId), numero_gesta (int >= 1)
    Opcionales: referencias *_id (ObjectId)
    Regla: (paciente_id, numero_gesta) es único.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        _ensure_indexes_historiales()

        paciente_oid = _to_oid(payload.get("paciente_id"), "paciente_id")
        numero_gesta = _validar_numero_gesta(payload.get("numero_gesta"))

        doc = {
            "paciente_id": paciente_oid,
            "numero_gesta": numero_gesta,
            "activo": True,
            "created_at": payload.get("created_at") or datetime.utcnow(),
            "updated_at": payload.get("updated_at") or datetime.utcnow(),
        }

        # Referencias opcionales
        for ref_field in [
            "identificacion_id", "antecedentes_id", "gestacion_actual_id",
            "parto_aborto_id", "patologias_id", "recien_nacido_id",
            "puerperio_id", "egreso_neonatal_id", "egreso_materno_id",
            "anticoncepcion_id"
        ]:
            if payload.get(ref_field) is not None:
                doc[ref_field] = _to_oid(payload[ref_field], ref_field)

        try:
            current_app.logger.info(f"[historiales] Insert doc: {doc}")
        except Exception:
            pass

        res = (mongo.db.historiales.insert_one(doc, session=session)
               if session else mongo.db.historiales.insert_one(doc))
        return _ok({"id": str(res.inserted_id)}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        msg = str(e)
        try:
            current_app.logger.exception("Error al crear historial")
        except Exception:
            pass
        if "duplicate key" in msg.lower():
            return _fail("Duplicado: ya existe un historial con ese (paciente_id, numero_gesta)", 409)
        return _fail(f"Error al crear historial: {msg}", 400)


def actualizar_historial_por_id(historial_id: str, payload: dict, session=None):
    """
    Actualiza un historial:
    - Puede cambiar numero_gesta (manteniendo unicidad con paciente_id)
    - Puede set/unset referencias *_id (unset real con $unset si viene None)
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(historial_id, "historial_id")
        doc_actual = mongo.db.historiales.find_one({"_id": oid})
        if not doc_actual:
            return _fail("Historial no encontrado", 404)

        sets, unsets = {}, {}

        # numero_gesta
        if "numero_gesta" in payload and payload["numero_gesta"] is not None:
            sets["numero_gesta"] = _validar_numero_gesta(payload["numero_gesta"])

        # referencias
        for ref_field in [
            "identificacion_id", "antecedentes_id", "gestacion_actual_id",
            "parto_aborto_id", "patologias_id", "recien_nacido_id",
            "puerperio_id", "egreso_neonatal_id", "egreso_materno_id",
            "anticoncepcion_id"
        ]:
            if ref_field in payload:
                val = payload.get(ref_field)
                if val is None:
                    unsets[ref_field] = ""
                else:
                    sets[ref_field] = _to_oid(val, ref_field)

        # activo (soft delete)
        if "activo" in payload and payload["activo"] is not None:
            sets["activo"] = bool(payload["activo"])

        if not sets and not unsets:
            return _ok({"mensaje": "Nada para actualizar"}, 200)

        # Verificar unicidad si cambió numero_gesta
        if "numero_gesta" in sets and sets["numero_gesta"] != doc_actual.get("numero_gesta"):
            existe = mongo.db.historiales.find_one({
                "paciente_id": doc_actual["paciente_id"],
                "numero_gesta": sets["numero_gesta"],
                "_id": {"$ne": oid}
            })
            if existe:
                return _fail("Duplicado: (paciente_id, numero_gesta) ya existe", 409)

        sets["updated_at"] = datetime.utcnow()
        update_doc = {}
        if sets:   update_doc["$set"] = sets
        if unsets: update_doc["$unset"] = unsets

        res = mongo.db.historiales.update_one({"_id": oid}, update_doc, session=session)
        if res.matched_count == 0:
            return _fail("Historial no encontrado", 404)
        return _ok({"mensaje": "Historial actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al actualizar historial", 400)


def eliminar_historial_por_id(historial_id: str, hard: bool = False, session=None):
    """
    Elimina un historial.
    - hard=True: borrado físico
    - hard=False: soft delete (marca activo=False)
    """
    try:
        oid = _to_oid(historial_id, "historial_id")
        if hard:
            res = mongo.db.historiales.delete_one({"_id": oid}, session=session)
            if res.deleted_count == 0:
                return _fail("Historial no encontrado", 404)
            return _ok({"mensaje": "Historial eliminado definitivamente"}, 200)
        else:
            res = mongo.db.historiales.update_one(
                {"_id": oid},
                {"$set": {"activo": False, "updated_at": datetime.utcnow()}},
                session=session
            )
            if res.matched_count == 0:
                return _fail("Historial no encontrado", 404)
            return _ok({"mensaje": "Historial desactivado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar historial", 400)


def listar_historiales(paciente_id: str | None = None, page: int = 1, per_page: int = 20):
    """
    Listado simple. Si se pasa paciente_id, filtra por ese paciente.
    Orden: created_at desc, numero_gesta desc.
    """
    try:
        page = max(int(page or 1), 1)
        per_page = max(min(int(per_page or 20), 100), 1)

        filtro = {}
        if paciente_id:
            filtro["paciente_id"] = _to_oid(paciente_id, "paciente_id")

        total = mongo.db.historiales.count_documents(filtro)
        cursor = (
            mongo.db.historiales.find(filtro)
            .sort([("created_at", -1), ("numero_gesta", -1)])
            .skip((page - 1) * per_page)
            .limit(per_page)
        )
        items = [_serialize_historial(d) for d in cursor]
        return _ok({"items": items, "page": page, "per_page": per_page, "total": total}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al listar historiales", 400)


# ==== Helpers de vinculación de segmentos ====
def vincular_segmento(historial_id: str, campo_ref: str, doc_id: str, session=None):
    """Setea una referencia *_id dentro del historial."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        did = _to_oid(doc_id, "doc_id")
        res = mongo.db.historiales.update_one(
            {"_id": oid},
            {"$set": {campo_ref: did, "updated_at": datetime.utcnow()}},
            session=session
        )
        if res.matched_count == 0:
            return _fail("Historial no encontrado", 404)
        return _ok({"mensaje": f"{campo_ref} vinculado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al vincular segmento", 400)

def desvincular_segmento(historial_id: str, campo_ref: str, session=None):
    """Elimina una referencia *_id del historial (unset real)."""
    try:
        oid = _to_oid(historial_id, "historial_id")
        res = mongo.db.historiales.update_one(
            {"_id": oid},
            {"$unset": {campo_ref: ""}, "$set": {"updated_at": datetime.utcnow()}},
            session=session
        )
        if res.matched_count == 0:
            return _fail("Historial no encontrado", 404)
        return _ok({"mensaje": f"{campo_ref} desvinculado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al desvincular segmento", 400)


# ==== GET agregado priorizando historial_id ====
def _segmento(doc_hist, historial_id_str, ref_id_field, svc,
              by_hist_fn=(), by_refid_fns=(), by_paciente_fns=()):
    """
    Orden de resolución:
      1) por historial_id (si el service lo soporta)
      2) por ref_id guardado en el historial
      3) fallback por paciente_id (compat/migración)
    """
    if not svc:
        return None

    # 1) por historial_id
    for fn_name in by_hist_fn:
        if hasattr(svc, fn_name):
            try:
                res = getattr(svc, fn_name)(historial_id_str)
                if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                    return res[0]["data"]
                if isinstance(res, dict) and res.get("ok"):
                    return res["data"]
            except Exception:
                pass

    # 2) por ref_id guardado
    ref_val = doc_hist.get(ref_id_field)
    if ref_val:
        ref_str = str(ref_val)
        for fn_name in by_refid_fns:
            if hasattr(svc, fn_name):
                try:
                    res = getattr(svc, fn_name)(ref_str)
                    if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                        return res[0]["data"]
                    if isinstance(res, dict) and res.get("ok"):
                        return res["data"]
                except Exception:
                    pass

    # 3) por paciente_id
    pid = str(doc_hist["paciente_id"])
    for fn_name in by_paciente_fns:
        if hasattr(svc, fn_name):
            try:
                res = getattr(svc, fn_name)(pid)
                if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                    return res[0]["data"]
                if isinstance(res, dict) and res.get("ok"):
                    return res["data"]
            except Exception:
                pass
    return None


def obtener_historial(historial_id: str):
    """
    GET agregado del historial:
    - Retorna el historial base.
    - Enriquecer con segmentos priorizando obtener_*_por_historial(historial_id);
      si no, por *_id del historial; y por último por paciente_id.
    """
    try:
        oid = _to_oid(historial_id, "historial_id")
        doc = mongo.db.historiales.find_one({"_id": oid})
        if not doc:
            return _fail("Historial no encontrado", 404)

        out = _serialize_historial(doc)
        hid = str(doc["_id"])

        # Identificaciones del paciente (opcional, solo si el service lo expone)
        out["episodios"] = None
        if svc_ident and hasattr(svc_ident, "listar_identificaciones_por_paciente"):
            try:
                eps = svc_ident.listar_identificaciones_por_paciente(str(doc["paciente_id"]))
                if isinstance(eps, tuple) and isinstance(eps[0], dict) and eps[0].get("ok"):
                    out["episodios"] = eps[0]["data"]
                elif isinstance(eps, dict) and eps.get("ok"):
                    out["episodios"] = eps["data"]
            except Exception:
                pass

        # Segmentos
        out["antecedentes"] = _segmento(
            doc, hid, "antecedentes_id", svc_ant,
            by_hist_fn=("obtener_antecedentes_por_historial",),
            by_refid_fns=("obtener_antecedentes_por_id",),
            by_paciente_fns=("get_antecedentes_by_id_paciente",)
        )

        out["gestacion_actual"] = _segmento(
            doc, hid, "gestacion_actual_id", svc_ga,
            by_hist_fn=("obtener_gestacion_actual_por_historial",),
            by_refid_fns=("obtener_gestacion_actual_por_id",),
            by_paciente_fns=("get_gestacion_actual_by_id_paciente",)
        )

        out["parto_aborto"] = _segmento(
            doc, hid, "parto_aborto_id", svc_pa,
            by_hist_fn=("obtener_parto_aborto_por_historial",),
            by_refid_fns=("obtener_parto_aborto_por_id",),
            by_paciente_fns=("get_parto_aborto_by_id_paciente",)
        )

        out["patologias"] = _segmento(
            doc, hid, "patologias_id", svc_pat,
            by_hist_fn=("obtener_patologias_por_historial",),
            by_refid_fns=("obtener_patologias_por_id",),
            by_paciente_fns=("get_patologias_by_id_paciente",)
        )

        out["puerperio"] = _segmento(
            doc, hid, "puerperio_id", svc_puer,
            by_hist_fn=("obtener_puerperio_por_historial",),
            by_refid_fns=("obtener_puerperio_por_id",),
            by_paciente_fns=("get_puerperio_by_id_paciente",)
        )

        out["recien_nacido"] = _segmento(
            doc, hid, "recien_nacido_id", svc_rn,
            by_hist_fn=("obtener_recien_nacido_por_historial",),
            by_refid_fns=("obtener_recien_nacido_por_id",),
            by_paciente_fns=("get_recien_nacido_by_id_paciente",)
        )

        out["egreso_neonatal"] = _segmento(
            doc, hid, "egreso_neonatal_id", svc_en,
            by_hist_fn=("obtener_egreso_neonatal_por_historial",),
            by_refid_fns=("obtener_egreso_neonatal_por_id",),
            by_paciente_fns=("get_egreso_neonatal_by_id_paciente",)
        )

        out["egreso_materno"] = _segmento(
            doc, hid, "egreso_materno_id", svc_em,
            by_hist_fn=("obtener_egreso_materno_por_historial",),
            by_refid_fns=("obtener_egreso_materno_por_id",),
            by_paciente_fns=("get_egreso_materno_by_id_paciente",)
        )

        out["anticoncepcion"] = _segmento(
            doc, hid, "anticoncepcion_id", svc_antico,
            by_hist_fn=("obtener_anticoncepcion_por_historial",),
            by_refid_fns=("obtener_anticoncepcion_por_id",),
            by_paciente_fns=("get_anticoncepcion_by_id_paciente",)
        )

        return _ok(out, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener historial", 400)

def obtener_historial_por_paciente_y_numero_gesta(paciente_id: str, numero_gesta: int):
    """
    Busca un historial por paciente_id y numero_gesta.
    - paciente_id: ObjectId (string)
    - numero_gesta: entero >= 1
    Retorna el documento si existe, con sus referencias serializadas.
    """
    try:
        pid = _to_oid(paciente_id, "paciente_id")
        num_gesta = _validar_numero_gesta(numero_gesta)

        doc = mongo.db.historiales.find_one({
            "paciente_id": pid,
            "numero_gesta": num_gesta
        })

        if not doc:
            return _fail("No se encontró historial para ese paciente y número de gesta", 404)

        return _ok(_serialize_historial(doc), 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail(f"Error al obtener historial: {str(e)}", 400)

