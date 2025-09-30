
from flask import Blueprint, request, jsonify
from app.db import start_session_if_possible  # tu helper de sesiones/tx
from app.services import (
    service_paciente,
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
)

bp = Blueprint("pacientes", __name__, url_prefix="/paciente")

def _ok(data, code=200):   return {"ok": True,  "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

def _usuario_actual_from_request():
    # Ajusta según tu autenticación (JWT / headers). Ejemplo simple:
    user_id = request.headers.get("X-User-Id")
    return {"usuario_id": user_id} if user_id else None


@bp.post("/create")
def crear_paciente():
    """
    Orquesta la creación de: paciente + todas las secciones HCP.
    Si algún paso falla, revierte (si hay transacción disponible).
    """
    usuario_actual = _usuario_actual_from_request()
    if not usuario_actual:
        res, code = _fail("usuario no autenticado", 401)
        return jsonify(res), code

    body = request.get_json() or {}
    # Bloques mínimos esperados en el payload:
    required_blocks = [
        "datos_generales",
        "identificacion",
        "antecedentes",
        "gestacion_actual",
        "parto_aborto",
        "patologias",
        "recien_nacido",
        "puerperio",
        "egreso_neonatal",
        "egreso_materno",
        "anticoncepcion",
    ]
    faltan = [k for k in required_blocks if k not in body]
    if faltan:
        res, code = _fail(f"Faltan bloques: {', '.join(faltan)}", 422)
        return jsonify(res), code

    with start_session_if_possible() as s:
        try:
            # 1) Paciente base
            pac_res, pac_code = service_paciente.crear_paciente(body["datos_generales"], session=s)
            if pac_code not in (200, 201) or not pac_res.get("ok"):
                if s: s.abort_transaction()
                return jsonify(pac_res), pac_code
            paciente_id = pac_res["data"]["id"]

            # 2) Identificación (inyectamos paciente_id)
            ident_payload = dict(body["identificacion"])
            ident_payload["paciente_id"] = paciente_id
            ident_res, ident_code = service_identificacion.crear_identificacion(
                usuario_actual, ident_payload, session=s
            )
            if ident_code not in (200, 201) or not ident_res.get("ok"):
                raise RuntimeError(ident_res.get("error") or "Error creando identificación")

            # 3) Antecedentes
            ant_res, ant_code = service_antencedentes.crear_antecedentes(
                paciente_id, body["antecedentes"], session=s
            )
            if ant_code not in (200, 201) or not ant_res.get("ok"):
                raise RuntimeError(ant_res.get("error") or "Error creando antecedentes")

            # 4) Gestación actual
            gest_res, gest_code = service_gestacion_actual.crear_gestacion_actual(
                paciente_id, body["gestacion_actual"], session=s
            )
            if gest_code not in (200, 201) or not gest_res.get("ok"):
                raise RuntimeError(gest_res.get("error") or "Error creando gestación actual")

            # 5) Parto/Aborto
            pa_res, pa_code = service_parto_aborto.crear_parto_aborto(
                paciente_id, body["parto_aborto"], session=s
            )
            if pa_code not in (200, 201) or not pa_res.get("ok"):
                raise RuntimeError(pa_res.get("error") or "Error creando parto/aborto")

            # 6) Patologías
            pat_res, pat_code = service_patologias.crear_patologias(
                paciente_id, body["patologias"], session=s
            )
            if pat_code not in (200, 201) or not pat_res.get("ok"):
                raise RuntimeError(pat_res.get("error") or "Error creando patologías")

            # 7) Recién nacido
            rn_res, rn_code = service_recien_nacido.crear_recien_nacido(
                paciente_id, body["recien_nacido"], session=s
            )
            if rn_code not in (200, 201) or not rn_res.get("ok"):
                raise RuntimeError(rn_res.get("error") or "Error creando recien_nacido")

            # 8) Puerperio
            puer_res, puer_code = service_puerperio.crear_puerperio(
                paciente_id, body["puerperio"], session=s
            )
            if puer_code not in (200, 201) or not puer_res.get("ok"):
                raise RuntimeError(puer_res.get("error") or "Error creando puerperio")

            # 9) Egreso neonatal (Egreso del Recién Nacido/a )
            eneon_res, eneon_code = service_egreso_neonatal.crear_egreso_neonatal(
                paciente_id, body["egreso_neonatal"], session=s
            )
            if eneon_code not in (200, 201) or not eneon_res.get("ok"):
                raise RuntimeError(eneon_res.get("error") or "Error creando egreso_neonatal")

            # 10) Egreso materno
            emat_res, emat_code = service_egreso_materno.crear_egreso_materno(
                paciente_id, body["egreso_materno"], session=s
            )
            if emat_code not in (200, 201) or not emat_res.get("ok"):
                raise RuntimeError(emat_res.get("error") or "Error creando egreso_materno")

            # 11) Anticoncepción
            anti_res, anti_code = service_anticoncepcion.crear_anticoncepcion(
                paciente_id, body["anticoncepcion"], session=s
            )
            if anti_code not in (200, 201) or not anti_res.get("ok"):
                raise RuntimeError(anti_res.get("error") or "Error creando anticoncepción")

            if s: s.commit_transaction()

            res, code = _ok({
                "paciente_id": paciente_id,
                "identificacion_id": ident_res["data"].get("id"),
                "antecedentes_id": ant_res["data"].get("id"),
                "gestacion_actual_id": gest_res["data"].get("id"),
                "parto_aborto_id": pa_res["data"].get("id"),
                "patologias_id": pat_res["data"].get("id"),
                "recien_nacido_id": rn_res["data"].get("id"),
                "puerperio_id": puer_res["data"].get("id"),
                "egreso_neonatal_id": eneon_res["data"].get("id"),
                "egreso_materno_id": emat_res["data"].get("id"),
                "anticoncepcion_id": anti_res["data"].get("id"),
            }, 201)
            return jsonify(res), code

        except Exception as e:
            if s: s.abort_transaction()
            res, code = _fail(f"Transacción revertida: {str(e)}", 500)
            return jsonify(res), code


@bp.get("/<paciente_id>")
def obtener_paciente(paciente_id):
    """
    Devuelve el agregado del paciente + todas las secciones HCP,
    usando exclusivamente SERVICES.
    """
    pac = service_paciente.obtener_paciente(paciente_id)
    if not pac.get("ok"):
        return jsonify(pac), 404

    ident, _ = service_identificacion.obtener_identificacion_por_paciente(paciente_id)
    ant, _   = service_antencedentes.get_antecedentes_by_id_paciente(paciente_id)
    gest, _  = service_gestacion_actual.get_gestacion_actual_by_id_paciente(paciente_id)
    pa, _    = service_parto_aborto.get_parto_aborto_by_id_paciente(paciente_id)
    pat, _   = service_patologias.get_patologias_by_id_paciente(paciente_id)
    rn, _    = service_recien_nacido.get_recien_nacido_by_id_paciente(paciente_id)
    puer, _  = service_puerperio.get_puerperio_by_id_paciente(paciente_id)
    eneon,_  = service_egreso_neonatal.get_egreso_neonatal_by_id_paciente(paciente_id)
    emat,_   = service_egreso_materno.get_egreso_materno_by_id_paciente(paciente_id)
    anti,_   = service_anticoncepcion.get_anticoncepcion_by_id_paciente(paciente_id)

    res, code = _ok({
        "paciente": pac["data"],
        "identificacion": ident["data"] if ident.get("ok") else None,
        "antecedentes":   ant["data"]   if ant.get("ok")   else None,
        "gestacion_actual": gest["data"] if gest.get("ok") else None,
        "parto_aborto":   pa["data"]    if pa.get("ok")    else None,
        "patologias":     pat["data"]   if pat.get("ok")   else None,
        "recien_nacido":  rn["data"]    if rn.get("ok")    else None,
        "puerperio":      puer["data"]  if puer.get("ok")  else None,
        "egreso_neonatal": eneon["data"] if eneon.get("ok") else None,
        "egreso_materno": emat["data"]  if emat.get("ok")  else None,
        "anticoncepcion": anti["data"]  if anti.get("ok")  else None,
    }, 200)
    return jsonify(res), code
