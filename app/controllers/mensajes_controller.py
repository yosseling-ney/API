from flask import Blueprint, request, jsonify
from app.services import service_mensajes as svc
from app.services import service_paciente as svc_pac
from datetime import datetime, timezone
from app.utils.jwt_manager import verificar_token

bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")


def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code


def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


def _usuario_actual_from_request():
    auth_header = request.headers.get("Authorization", "") or ""
    token = auth_header.split(" ")[-1].strip() if auth_header else ""
    if not token:
        return None
    datos = verificar_token(token)
    return datos if datos and datos.get("usuario_id") else None


def _resolver_paciente_id_por_hint(*, paciente_id=None, tipo_identificacion=None, numero_identificacion=None,
                                   codigo_expediente=None, nombre=None, apellido=None, q=None):
    """Devuelve (paciente_id_str | None, error_message | None, http_code | None).
    Reglas:
    - Si paciente_id viene, se usa tal cual.
    - Si viene tipo+numero, busca por identificación.
    - Si viene codigo_expediente, busca por código.
    - Si viene nombre+apellido, hace búsqueda por q y exige match único.
    - Si viene q, idem.
    """
    if paciente_id:
        return paciente_id, None, None

    # Por identificación
    if tipo_identificacion and numero_identificacion:
        res, code = svc_pac.buscar_paciente_por_identificacion(tipo_identificacion, numero_identificacion)
        if code == 200 and res.get("ok"):
            return res["data"]["id"], None, None
        return None, res.get("error") or "Paciente no encontrado", 404 if code == 404 else 422

    # Por código de expediente
    if codigo_expediente:
        try:
            res, code = svc_pac.buscar_paciente_por_codigo_expediente(codigo_expediente)
        except Exception as e:
            return None, str(e), 400
        if code == 200 and res.get("ok"):
            return res["data"]["id"], None, None
        return None, res.get("error") or "Paciente no encontrado", 404 if code == 404 else 422

    # Por nombre y apellido -> usar listar_pacientes(q) y exigir match único
    consulta = None
    if nombre and apellido:
        consulta = f"{nombre} {apellido}"
    elif q:
        consulta = q

    if consulta:
        try:
            lr, lc = svc_pac.listar_pacientes(q=consulta, page=1, per_page=5, solo_activos=True)
        except Exception as e:
            return None, str(e), 400
        if lc == 200 and lr.get("ok"):
            items = (lr["data"] or {}).get("items", [])
            if len(items) == 1:
                return items[0]["id"], None, None
            if len(items) == 0:
                return None, "Paciente no encontrado", 404
            return None, "Ambiguo: coinciden varios pacientes", 409
        return None, lr.get("error") or "Error al buscar paciente", lc

    return None, None, None


@bp.get("/")
def list_mensajes():
    paciente_id = request.args.get("paciente_id")
    try:
        print(f"[mensajes] paciente_id raw={repr(paciente_id)}")
        if paciente_id:
            parsed = svc._oid(paciente_id)
            print(f"[mensajes] paciente_id parsed={parsed}")
    except Exception:
        pass
    # Hints opcionales para filtrar por paciente sin conocer el ID
    tipo_identificacion = request.args.get("tipo_identificacion")
    numero_identificacion = request.args.get("numero_identificacion")
    # Aceptar alias 'expediente' además de 'codigo_expediente'
    codigo_expediente = request.args.get("codigo_expediente") or request.args.get("expediente")
    nombre = request.args.get("nombre")
    apellido = request.args.get("apellido")
    q = request.args.get("q")

    if not paciente_id and any([tipo_identificacion and numero_identificacion, codigo_expediente, (nombre and apellido), q]):
        pid, err, err_code = _resolver_paciente_id_por_hint(
            paciente_id=None,
            tipo_identificacion=tipo_identificacion,
            numero_identificacion=numero_identificacion,
            codigo_expediente=codigo_expediente,
            nombre=nombre,
            apellido=apellido,
            q=q,
        )
        if err:
            return jsonify({"ok": False, "data": None, "error": err}), err_code
        paciente_id = pid
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 20)
    res, code = svc.listar_mensajes(paciente_id=paciente_id, page=page, per_page=per_page)
    if code == 200 and res.get("ok") and res.get("data"):
        try:
            now = datetime.now(timezone.utc)
            for it in res["data"].get("items", []):
                created_str = it.get("created_at")
                if created_str:
                    try:
                        created_dt = datetime.fromisoformat(created_str)
                        delta = now - created_dt
                        seconds = int(delta.total_seconds())
                        if seconds < 60:
                            it["time"] = "Hace unos segundos"
                        elif seconds < 3600:
                            mins = seconds // 60
                            it["time"] = f"Hace {mins} minuto{'s' if mins!=1 else ''}"
                        elif seconds < 86400:
                            hrs = seconds // 3600
                            it["time"] = f"Hace {hrs} hora{'s' if hrs!=1 else ''}"
                        else:
                            dias = seconds // 86400
                            it["time"] = f"Hace {dias} dias"
                    except Exception:
                        pass
        except Exception:
            pass
    return jsonify(res), code


@bp.post("/")
def crear_mensaje():
    body = request.get_json() or {}
    usuario_actual = _usuario_actual_from_request()
    if usuario_actual:
        body["created_by"] = usuario_actual.get("usuario_id")
    # Resolver paciente por hints si no vino paciente_id
    if not body.get("paciente_id"):
        exp_hint = body.get("codigo_expediente") or body.get("expediente")
        pid, err, err_code = _resolver_paciente_id_por_hint(
            paciente_id=None,
            tipo_identificacion=body.get("tipo_identificacion"),
            numero_identificacion=body.get("numero_identificacion"),
            codigo_expediente=exp_hint,
            nombre=body.get("nombre"),
            apellido=body.get("apellido"),
            q=body.get("q"),
        )
        if err:
            return jsonify({"ok": False, "data": None, "error": err}), err_code
        if pid:
            body["paciente_id"] = pid
    res, code = svc.crear_mensaje(body)
    return jsonify(res), code


@bp.put("/<mensaje_id>/read")
@bp.patch("/<mensaje_id>/read")
def marcar_leido(mensaje_id):
    res, code = svc.marcar_leido(mensaje_id)
    return jsonify(res), code


@bp.delete("/<mensaje_id>")
def eliminar_mensaje(mensaje_id):
    hard_param = (request.args.get("hard") or "").strip().lower()
    hard = hard_param in ("1", "true", "t", "yes", "y")
    res, code = svc.eliminar_mensaje(mensaje_id, hard=hard)
    return jsonify(res), code


@bp.put("/<mensaje_id>")
@bp.patch("/<mensaje_id>")
def actualizar_mensaje(mensaje_id):
    body = request.get_json() or {}
    res, code = svc.actualizar_mensaje(mensaje_id, body)
    return jsonify(res), code
