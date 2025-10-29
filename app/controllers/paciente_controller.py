from flask import Blueprint, request, jsonify
from bson import ObjectId
from app import mongo
from app.db import start_session_if_possible
from app.utils.jwt_manager import verificar_token
from app.services import service_paciente, service_historial
from pymongo import DESCENDING
from datetime import datetime
import math

bp = Blueprint("pacientes", __name__, url_prefix="/pacientes")

def _ok(data, code=200):   return {"ok": True,  "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

def _usuario_actual_from_request():
    auth_header = request.headers.get("Authorization", "") or ""
    token = auth_header.split(" ")[-1].strip() if auth_header else ""
    if not token:
        return None
    datos = verificar_token(token)
    return datos if datos and datos.get("usuario_id") else None


def _to_str_id(doc):
    if not isinstance(doc, dict):
        return doc
    d = dict(doc)
    if d.get("_id"):
        try:
            d["id"] = str(d.pop("_id"))
        except Exception:
            pass
    # Normalizar posibles referencias comunes
    for key in ("paciente_id", "historial_id", "usuario_crea_id", "usuario_actualiza_id"):
        if isinstance(d.get(key), ObjectId):
            d[key] = str(d[key])
    # Convertir fechas a ISO para JSON
    for key in ("created_at", "updated_at", "deleted_at"):
        val = d.get(key)
        if isinstance(val, datetime):
            d[key] = val.isoformat()
    # Campo derivado de compatibilidad
    if "activo" not in d:
        d["activo"] = d.get("deleted_at") in (None, "", 0)
    return d


@bp.get("/identificacion")
def buscar_por_identificacion():
    """Busca paciente por tipo/numero de identificación.
    Frontend espera 200 si existe o 404 si no existe/identificación inválida.
    """
    tipo = (request.args.get("tipo_identificacion") or "").strip()
    numero = (request.args.get("numero_identificacion") or "").strip()

    if not tipo or not numero:
        res, code = _fail("tipo_identificacion y numero_identificacion son requeridos", 422)
        return jsonify(res), code

    res, code = service_paciente.buscar_paciente_por_identificacion(tipo, numero)

    # El UI sólo reacciona a 200 (existe) o 404 (no existe).
    # Si el servicio valida como 422 (formato inválido), lo tratamos como no encontrado.
    if code == 422:
        return jsonify({"ok": False, "data": None, "error": "No existe paciente con esa identificacion"}), 404

    return jsonify(res), code


@bp.get("")
def listar_pacientes():
    """Lista pacientes con filtros de estado, búsqueda y paginación.
    Query params:
      - estado: activos | inactivos | todos (por defecto: activos)
      - q: término de búsqueda (nombres, apellidos, numero_identificacion)
      - page, per_page
    """
    estado = (request.args.get("estado") or "").strip().lower() or "activos"
    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 10))
    except Exception:
        per_page = 10
    per_page = min(max(1, per_page), 100)

    filt = {}
    if estado in ("activos", "activo", "true", "1"):
        filt["$or"] = [
            {"deleted_at": None},
            {"deleted_at": {"$exists": False}},
        ]
    elif estado in ("inactivos", "inactivo", "false", "0"):
        filt["deleted_at"] = {"$ne": None}
    # si es "todos", no filtramos por activo

    if q:
        rx = {"$regex": q, "$options": "i"}
        buscador = {"$or": [
            {"nombres": rx},
            {"apellidos": rx},
            {"nombre_completo": rx},
            {"numero_identificacion": rx},
        ]}
        filt = {"$and": [filt, buscador]} if filt else buscador

    try:
        total = mongo.db.paciente.count_documents(filt)
        cursor = (
            mongo.db.paciente
            .find(filt)
            .sort([("_id", DESCENDING)])
            .skip((page - 1) * per_page)
            .limit(per_page)
        )
        items = [_to_str_id(doc) for doc in cursor]
        data = {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": math.ceil(total / per_page) if per_page else 0,
        }
        res, code = _ok(data, 200)
        return jsonify(res), code
    except Exception as e:
        res, code = _fail(f"Error listando pacientes: {str(e)}", 500)
        return jsonify(res), code


@bp.post("/create")
def crear_paciente():
    """
    Orquesta la creacion de: paciente + primer historial.
    Si falla historial, revierte y borra el paciente creado.
    """
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    body = request.get_json() or {}

    # Aceptar dos formatos:
    # 1) { "datos_generales": { ... }, "historial": {...?} }
    # 2) payload plano con los campos del paciente (y opcionalmente "historial")
    if isinstance(body.get("datos_generales"), dict):
        datos_generales = body["datos_generales"]
        hist_data = body.get("historial")
    else:
        # fallback: tratar el body como datos_generales, excluyendo la clave 'historial'
        datos_generales = {k: v for k, v in body.items() if k != "historial"}
        hist_data = body.get("historial")
        if not datos_generales:
            res, code = _fail("Faltan bloques: datos_generales", 422)
            return jsonify(res), code

    resumen = {"paciente_id": None, "historial_id": None}
    paciente_id = None
    historial_id = None
    session_used = False

    def _resolve_numero_gesta(current_payload, paciente_id_str, session=None):
        supplied = current_payload.get("numero_gesta")
        if supplied not in (None, "", 0):
            return supplied
        try:
            oid = ObjectId(paciente_id_str)
        except Exception:
            return 1
        query = {"paciente_id": oid}
        if session:
            doc = mongo.db.historiales.find_one(query, sort=[("numero_gesta", -1)], session=session)
        else:
            doc = mongo.db.historiales.find_one(query, sort=[("numero_gesta", -1)])
        if not doc:
            return 1
        ultimo = doc.get("numero_gesta") or 0
        try:
            ultimo = int(ultimo)
        except Exception:
            ultimo = 0
        return ultimo + 1

    try:
        with start_session_if_possible() as s:
            session_used = bool(s)
            try:
                if s:
                    s.start_transaction()

                pac_res, pac_code = service_paciente.crear_paciente(datos_generales, session=s)
                if pac_code not in (200, 201) or not pac_res.get("ok"):
                    if s:
                        s.abort_transaction()
                    return jsonify(pac_res), pac_code

                paciente_id = pac_res["data"]["id"]
                resumen["paciente_id"] = paciente_id

                if hist_data is not None:
                    hist_payload = dict(hist_data or {})
                    hist_payload["paciente_id"] = paciente_id
                    hist_payload["numero_gesta"] = _resolve_numero_gesta(hist_payload, paciente_id, session=s)

                    his_res, his_code = service_historial.crear_historial(hist_payload, session=s)
                    if his_code not in (200, 201) or not his_res.get("ok"):
                        raise RuntimeError(his_res.get("error") or "Error creando historial")

                    historial_id = his_res["data"]["id"]
                    resumen["historial_id"] = historial_id

                    upd_res, upd_code = service_paciente.actualizar_paciente_por_id(
                        paciente_id,
                        {"historial_id": historial_id},
                        session=s,
                    )
                    if upd_code not in (200, 201) or not upd_res.get("ok"):
                        raise RuntimeError(upd_res.get("error") or "Error vinculando historial al paciente")

                if s:
                    s.commit_transaction()
            except Exception:
                if s:
                    s.abort_transaction()
                raise
    except Exception as e:
        if paciente_id and not session_used:
            try:
                if historial_id:
                    service_historial.eliminar_historial_por_id(historial_id, hard=True)
            except Exception:
                pass
            try:
                service_paciente.eliminar_paciente_por_id(paciente_id, hard=True)
            except Exception:
                pass
        res, code = _fail(f"Transaccion revertida: {str(e)}", 500)
        return jsonify(res), code

    res, code = _ok(resumen, 201)
    return jsonify(res), code

@bp.get("/<paciente_id>")
def obtener_paciente(paciente_id):
    """
    Devuelve el paciente + su historial más reciente (si existe).
    """
    pac_res, pac_code = service_paciente.obtener_paciente(paciente_id)
    if pac_code not in (200, 201) or not pac_res.get("ok"):
        return jsonify(pac_res), pac_code

    # Traer historial más reciente
    hist_list_res, hist_list_code = service_historial.listar_historiales(
        paciente_id=paciente_id, page=1, per_page=1
    )

    historial_mas_reciente = None
    if hist_list_code == 200 and hist_list_res.get("ok"):
        items = (hist_list_res["data"] or {}).get("items", [])
        historial_mas_reciente = items[0] if items else None

    res, code = _ok(
        {
            "paciente": pac_res["data"],
            "historial": historial_mas_reciente,
        },
        200,
    )
    return jsonify(res), code


@bp.patch("/<paciente_id>/activar")
def activar_paciente(paciente_id):
    """Activa un paciente (activo=True). Requiere autenticación."""
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    try:
        upd = {"$set": {"deleted_at": None}, "$unset": {"deleted_by": ""}}
        result = mongo.db.paciente.update_one({"_id": ObjectId(paciente_id)}, upd)
        if result.matched_count == 0:
            res, code = _fail("Paciente no encontrado", 404)
            return jsonify(res), code
        res, code = _ok({"id": paciente_id, "activo": True}, 200)
        return jsonify(res), code
    except Exception as e:
        res, code = _fail(f"Error activando paciente: {str(e)}", 500)
        return jsonify(res), code


@bp.patch("/<paciente_id>/desactivar")
def desactivar_paciente(paciente_id):
    """Desactiva un paciente (activo=False). Requiere autenticación."""
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    try:
        # Validar ObjectId del paciente
        try:
            oid = ObjectId(paciente_id)
        except Exception:
            res, code = _fail("paciente_id inválido", 422)
            return jsonify(res), code

        # deleted_by como ObjectId si es válido; si no, omitir
        deleted_by_val = None
        uid = usuario_actual.get("usuario_id")
        try:
            if uid is not None:
                deleted_by_val = ObjectId(str(uid))
        except Exception:
            deleted_by_val = None

        set_fields = {"deleted_at": datetime.utcnow()}
        if deleted_by_val is not None:
            set_fields["deleted_by"] = deleted_by_val

        upd = {"$set": set_fields}
        result = mongo.db.paciente.update_one({"_id": oid}, upd)
        if result.matched_count == 0:
            res, code = _fail("Paciente no encontrado", 404)
            return jsonify(res), code
        res, code = _ok({"id": paciente_id, "activo": False}, 200)
        return jsonify(res), code
    except Exception as e:
        res, code = _fail(f"Error desactivando paciente: {str(e)}", 500)
        return jsonify(res), code


@bp.put("/<paciente_id>")
@bp.patch("/<paciente_id>")
def actualizar_paciente(paciente_id):
    """
    Actualiza un paciente por id. Acepta actualizaciones parciales (PATCH) o completas (PUT).
    Requiere autenticación.
    """
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    body = request.get_json() or {}
    if not isinstance(body, dict):
        res, code = _fail("JSON inválido", 400)
        return jsonify(res), code

    res, code = service_paciente.actualizar_paciente_por_id(paciente_id, body)
    return jsonify(res), code


@bp.put("/update")
@bp.patch("/update")
def actualizar_paciente_legacy():
    """
    Ruta legacy para actualizaciones cuando no se usa el path con id.
    Espera `paciente_id` en body o query y el resto de campos a actualizar en el body.
    """
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    data = request.get_json() or {}
    if not isinstance(data, dict):
        res, code = _fail("JSON inválido", 400)
        return jsonify(res), code

    paciente_id = data.get("paciente_id") or request.args.get("paciente_id")
    if not paciente_id:
        res, code = _fail("paciente_id es requerido", 422)
        return jsonify(res), code

    # Si viene un objeto `payload`, úsalo; si no, usa el body sin paciente_id
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {
        k: v for k, v in data.items() if k != "paciente_id"
    }

    if not isinstance(payload, dict):
        res, code = _fail("payload inválido", 400)
        return jsonify(res), code

    res, code = service_paciente.actualizar_paciente_por_id(paciente_id, payload)
    return jsonify(res), code


@bp.get("/resumen")
def resumen_pacientes():
    """Devuelve totales de pacientes activos, inactivos y total. Requiere autenticación."""
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code


# Endpoint de migración removido a pedido: no exponer ruta de cambios masivos.

    try:
        activos = mongo.db.paciente.count_documents({"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]})
        inactivos = mongo.db.paciente.count_documents({"deleted_at": {"$ne": None}})
        total = mongo.db.paciente.count_documents({})
        res, code = _ok({
            "activos": activos,
            "inactivos": inactivos,
            "total": total,
        }, 200)
        return jsonify(res), code
    except Exception as e:
        res, code = _fail(f"Error obteniendo resumen: {str(e)}", 500)
        return jsonify(res), code
