from flask import Blueprint, request, jsonify
from bson import ObjectId
from app import mongo
from app.db import start_session_if_possible
from app.utils.jwt_manager import verificar_token
from app.services import service_paciente, service_historial

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

    required_blocks = ["datos_generales"]
    faltan = [k for k in required_blocks if k not in body]
    if faltan:
        res, code = _fail(f"Faltan bloques: {', '.join(faltan)}", 422)
        return jsonify(res), code

    datos_generales = body["datos_generales"]
    hist_data = body.get("historial")

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
