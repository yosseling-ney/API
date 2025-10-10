from flask import Blueprint, request, jsonify
from bson import ObjectId
from app import mongo
from app.db import start_session_if_possible
from app.utils.jwt_manager import verificar_token
from app.services import (
    service_historial,
    service_identificacion,
    service_antencedentes,
    service_gestacion_actual,
    service_parto_aborto,
    service_patologias,
    service_recien_nacido,
    service_puerperio,
    service_egreso_neonatal,
    service_egreso_materno,
    service_anticoncepcion,
    service_paciente,
)

bp = Blueprint("historiales", __name__, url_prefix="/historiales")

def _ok(data, code=200):   return {"ok": True,  "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

def _usuario_actual_from_request():
    auth_header = request.headers.get("Authorization", "") or ""
    token = auth_header.split(" ")[-1].strip() if auth_header else ""
    if not token:
        return None
    datos = verificar_token(token)
    return datos if datos and datos.get("usuario_id") else None


@bp.post("/create")
def crear_historial():
    """
    Orquesta la creación de: historial (requerido) + secciones HCP (opcionales).
    Si algún paso falla dentro de la transacción, se revierte.
    """
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    body = request.get_json() or {}

    # Solo exigimos el bloque base de historial; el resto es opcional.
    if "datos" not in body:
        res, code = _fail("Falta bloque: datos (historial)", 422)
        return jsonify(res), code

    def _resolve_numero_gesta(paciente_id_value, session=None):
        try:
            oid = ObjectId(paciente_id_value)
        except Exception:
            raise ValueError("datos.paciente_id debe ser un ObjectId válido")
        kwargs = {"sort": [("numero_gesta", -1)]}
        if session:
            kwargs["session"] = session
        doc = mongo.db.historiales.find_one({"paciente_id": oid}, **kwargs)
        if not doc:
            return 1
        ultimo = doc.get("numero_gesta") or 0
        try:
            ultimo = int(ultimo)
        except Exception:
            ultimo = 0
        return ultimo + 1

    historial_id = None
    paciente_id = None
    resumen = {"secciones_creadas": {}}
    session_used = False

    try:
        with start_session_if_possible() as s:
            session_used = bool(s)
            try:
                if s:
                    s.start_transaction()

                # 1) Crear historial 
                hist_payload = dict(body["datos"] or {})
                paciente_id = hist_payload.get("paciente_id")
                if not paciente_id:
                    raise RuntimeError("datos.paciente_id es requerido")

                numero_gesta = hist_payload.get("numero_gesta")
                if numero_gesta in (None, "", 0):
                    numero_gesta = _resolve_numero_gesta(paciente_id, session=s)
                hist_payload["numero_gesta"] = numero_gesta

                his_res, his_code = service_historial.crear_historial(hist_payload, session=s)
                if his_code not in (200, 201) or not his_res.get("ok"):
                    raise RuntimeError(his_res.get("error") or "Error creando historial")

                historial_id = his_res["data"].get("id")
                resumen["historial_id"] = historial_id
                resumen["paciente_id"] = paciente_id

                upd_res, upd_code = service_paciente.actualizar_paciente_por_id(
                    paciente_id, {"historial_id": historial_id}, session=s
                )
                if upd_code not in (200, 201) or not upd_res.get("ok"):
                    raise RuntimeError(upd_res.get("error") or "Error actualizando paciente")

                # Helper para crear secciones opcionales (inyectando historial_id)
                def _crear(nombre_bloque, servicio, nombre_fn):
                    if nombre_bloque not in body:
                        return
                    payload = dict(body[nombre_bloque] or {})
                    if not hasattr(servicio, nombre_fn):
                        raise RuntimeError(f"{nombre_bloque}: función '{nombre_fn}' no encontrada")
                    func = getattr(servicio, nombre_fn)
                    res, code = func(historial_id, payload, session=s, usuario_actual=usuario_actual)
                    if code not in (200, 201) or not res.get("ok"):
                        raise RuntimeError(res.get("error") or f"Error creando {nombre_bloque}")
                    resumen["secciones_creadas"][f"{nombre_bloque}_id"] = res["data"].get("id")

                    # Vincular campo *_id en el documento de historial
                    ref_field = f"{nombre_bloque}_id"
                    vinc_res, vinc_code = service_historial.vincular_segmento(
                        historial_id, ref_field, res["data"].get("id"), session=s
                    )
                    if vinc_code not in (200, 201) or not vinc_res.get("ok"):
                        raise RuntimeError(vinc_res.get("error") or f"Error vinculando {ref_field}")

                # 2) Crear secciones si vienen
                _crear("identificacion",  service_identificacion,   "crear_identificacion")
                _crear("antecedentes",    service_antencedentes,    "crear_antecedentes")
                _crear("gestacion_actual",service_gestacion_actual, "crear_gestacion_actual")
                _crear("parto_aborto",    service_parto_aborto,     "crear_parto_aborto")
                _crear("patologias",      service_patologias,       "crear_patologias")
                _crear("recien_nacido",   service_recien_nacido,    "crear_recien_nacido")
                _crear("puerperio",       service_puerperio,        "crear_puerperio")
                _crear("egreso_neonatal", service_egreso_neonatal,  "crear_egreso_neonatal")
                _crear("egreso_materno",  service_egreso_materno,   "crear_egreso_materno")
                _crear("anticoncepcion",  service_anticoncepcion,   "crear_anticoncepcion")

                if s:
                    s.commit_transaction()

            except Exception:
                if s:
                    s.abort_transaction()
                raise

    except Exception as e:
        # Si alcanzamos a crear historial, intentamos limpiarlo
        if historial_id:
            try:
                service_historial.eliminar_historial_por_id(historial_id, hard=True)
            except Exception:
                pass
        if paciente_id and historial_id and not session_used:
            try:
                service_paciente.actualizar_paciente_por_id(paciente_id, {"historial_id": None})
            except Exception:
                pass
        res, code = _fail(f"Transacción revertida: {str(e)}", 500)
        return jsonify(res), code

    res, code = _ok(resumen, 201)
    return jsonify(res), code


@bp.get("/<historial_id>")
def obtener_historial(historial_id):
    """
    Devuelve el agregado del historial + secciones HCP por historial_id.
    """
    hist_res, hist_code = service_historial.obtener_historial(historial_id)
    if hist_code not in (200, 201) or not hist_res.get("ok"):
        return jsonify(hist_res), hist_code

    agregado = {"historial": hist_res["data"]}

    # Helper para obtener secciones por historial (usa el primer método disponible)
    def _obtener(servicio, candidatos):
        for fn in candidatos:
            if hasattr(servicio, fn):
                try:
                    r, c = getattr(servicio, fn)(historial_id)
                    if c in (200, 201) and r.get("ok"):
                        return r["data"]
                except Exception:
                    pass
        return None

    agregado["identificacion"]  = _obtener(service_identificacion,  ("obtener_identificacion_por_historial",  "get_identificacion_by_historial_id"))
    agregado["antecedentes"]    = _obtener(service_antencedentes,   ("obtener_antecedentes_por_historial",    "get_antecedentes_by_historial_id"))
    agregado["gestacion_actual"]= _obtener(service_gestacion_actual,("obtener_gestacion_actual_por_historial","get_gestacion_actual_by_historial_id"))
    agregado["parto_aborto"]    = _obtener(service_parto_aborto,    ("obtener_parto_aborto_por_historial",    "get_parto_aborto_by_historial_id"))
    agregado["patologias"]      = _obtener(service_patologias,      ("obtener_patologias_por_historial",      "get_patologias_by_historial_id"))
    agregado["recien_nacido"]   = _obtener(service_recien_nacido,   ("obtener_recien_nacido_por_historial",   "get_recien_nacido_by_historial_id"))
    agregado["puerperio"]       = _obtener(service_puerperio,       ("obtener_puerperio_por_historial",       "get_puerperio_by_historial_id"))
    agregado["egreso_neonatal"] = _obtener(service_egreso_neonatal, ("obtener_egreso_neonatal_por_historial", "get_egreso_neonatal_by_historial_id"))
    agregado["egreso_materno"]  = _obtener(service_egreso_materno,  ("obtener_egreso_materno_por_historial",  "get_egreso_materno_by_historial_id"))
    agregado["anticoncepcion"]  = _obtener(service_anticoncepcion,  ("obtener_anticoncepcion_por_historial",  "get_anticoncepcion_by_historial_id"))

    res, code = _ok(agregado, 200)
    return jsonify(res), code


@bp.get("/por-paciente/<paciente_id>")
def obtener_historial_por_paciente(paciente_id):
    """
    Devuelve el agregado del historial más reciente para un paciente dado.
    Si no existe historial previo, responde 404.
    """
    # Buscar el historial más reciente del paciente
    hist_list_res, hist_list_code = service_historial.listar_historiales(
        paciente_id=paciente_id, page=1, per_page=1
    )
    if hist_list_code not in (200, 201) or not hist_list_res.get("ok"):
        return jsonify(hist_list_res), hist_list_code

    items = (hist_list_res["data"] or {}).get("items", [])
    if not items:
        res, code = _fail("Historial no encontrado para paciente", 404)
        return jsonify(res), code

    historial_id = items[0].get("id")

    # Reutilizar la lógica de agregado por historial_id
    hist_res, hist_code = service_historial.obtener_historial(historial_id)
    if hist_code not in (200, 201) or not hist_res.get("ok"):
        return jsonify(hist_res), hist_code

    agregado = {"historial": hist_res["data"]}

    def _obtener(servicio, candidatos):
        for fn in candidatos:
            if hasattr(servicio, fn):
                try:
                    r, c = getattr(servicio, fn)(historial_id)
                    if c in (200, 201) and r.get("ok"):
                        return r["data"]
                except Exception:
                    pass
        return None

    agregado["identificacion"]  = _obtener(service_identificacion,  ("obtener_identificacion_por_historial",  "get_identificacion_by_historial_id"))
    agregado["antecedentes"]    = _obtener(service_antencedentes,   ("obtener_antecedentes_por_historial",    "get_antecedentes_by_historial_id"))
    agregado["gestacion_actual"]= _obtener(service_gestacion_actual,("obtener_gestacion_actual_por_historial","get_gestacion_actual_by_historial_id"))
    agregado["parto_aborto"]    = _obtener(service_parto_aborto,    ("obtener_parto_aborto_por_historial",    "get_parto_aborto_by_historial_id"))
    agregado["patologias"]      = _obtener(service_patologias,      ("obtener_patologias_por_historial",      "get_patologias_by_historial_id"))
    agregado["recien_nacido"]   = _obtener(service_recien_nacido,   ("obtener_recien_nacido_por_historial",   "get_recien_nacido_by_historial_id"))
    agregado["puerperio"]       = _obtener(service_puerperio,       ("obtener_puerperio_por_historial",       "get_puerperio_by_historial_id"))
    agregado["egreso_neonatal"] = _obtener(service_egreso_neonatal, ("obtener_egreso_neonatal_por_historial", "get_egreso_neonatal_by_historial_id"))
    agregado["egreso_materno"]  = _obtener(service_egreso_materno,  ("obtener_egreso_materno_por_historial",  "get_egreso_materno_by_historial_id"))
    agregado["anticoncepcion"]  = _obtener(service_anticoncepcion,  ("obtener_anticoncepcion_por_historial",  "get_anticoncepcion_by_historial_id"))

    res, code = _ok(agregado, 200)
    return jsonify(res), code
