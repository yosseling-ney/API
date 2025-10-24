from flask import Blueprint, request, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import re

from app import mongo
from app.services.medicos_service import validar_payload_medico, serializar_medico

medicos_bp = Blueprint("medicos_bp", __name__, url_prefix="/medicos")

FOLIO_PREFIX = "MED-"
FOLIO_PATTERN = re.compile(r"^MED-\d{4,}$")  # MED-0001, MED-0123, MED-10000


def oid(value):
    return ObjectId(value) if value and ObjectId.is_valid(value) else None


def generar_siguiente_folio():
    """
    Genera el siguiente folio secuencial con prefijo MED- y 4+ dígitos.
    Usa una agregación para extraer la parte numérica del folio actual más alto.
    """
    pipeline = [
        {"$match": {"folio": {"$regex": r"^MED-\d{4,}$"}}},
        # Extraemos el match con $regexFind en un campo temporal
        {"$addFields": {"_folio_match": {"$regexFind": {"input": "$folio", "regex": r"\d+"}}}},
        # Convertimos el match a entero; si es nulo, usamos 0
        {
            "$addFields": {
                "_folio_num": {
                    "$toInt": {"$ifNull": ["$_folio_match.match", 0]}
                }
            }
        },
        {"$sort": {"_folio_num": -1}},
        {"$limit": 1},
        {"$project": {"_folio_num": 1}}
    ]

    docs = list(mongo.db.medicos.aggregate(pipeline))
    last_num = docs[0]["_folio_num"] if docs else 0
    next_num = last_num + 1
    # zfill(4) garantiza al menos 4 dígitos
    return f"{FOLIO_PREFIX}{str(next_num).zfill(4)}"


@medicos_bp.post("/")
def crear_medico():
    """POST /medicos/ - Crear médico"""
    data = request.get_json(silent=True) or {}

    # Validamos payload (folio puede venir o no; si no viene lo generamos)
    ok, errors, cleaned = validar_payload_medico(data, "crear")
    if not ok:
        return jsonify({"message": "Validación fallida", "errors": errors}), 422

    # Asegurar folio: si no vino, generar; si vino, validar formato y normalizar
    folio_in = (data.get("folio") or "").strip().upper()
    if folio_in:
        if not FOLIO_PATTERN.match(folio_in):
            return jsonify({"message": "Validación fallida", "errors": {"folio": "Formato inválido. Use MED-0001"}}), 422
        cleaned["folio"] = folio_in
    else:
        cleaned["folio"] = generar_siguiente_folio()

    now = datetime.now(timezone.utc)
    cleaned["created_at"] = now
    cleaned["updated_at"] = now
    cleaned["created_by"] = None
    cleaned["updated_by"] = None

    try:
        res = mongo.db.medicos.insert_one(cleaned)
        doc = mongo.db.medicos.find_one({"_id": res.inserted_id})
        return jsonify({"message": "Médico creado", "data": serializar_medico(doc)}), 201
    except Exception as e:
        msg = str(e)
        if "dup key" in msg and "folio" in msg:
            return jsonify({"message": "El folio ya existe"}), 409
        if "dup key" in msg and "cedula" in msg:
            return jsonify({"message": "La cédula ya existe"}), 409
        if "dup key" in msg and "correo" in msg:
            return jsonify({"message": "El correo ya existe"}), 409
        return jsonify({"message": "Error al crear médico", "error": msg}), 500


@medicos_bp.get("/")
def listar_medicos():
    """
    GET /medicos/ - Listar médicos (con paginación, filtros y orden)
    Query params:
      q: texto (busca por folio, nombre, cédula, especialidad, correo, teléfono)
      estado: activo|inactivo
      especialidad: enum de especialidades
      sexo: femenino|masculino|otro|no_especificado
      page: int (1..)
      limit: int (1..200)
      sort: updated_at|-updated_at|nombre_completo|-nombre_completo|fecha_nacimiento|-fecha_nacimiento|folio|-folio
    """
    q = (request.args.get("q") or "").strip()
    estado = request.args.get("estado")
    especialidad = request.args.get("especialidad")
    sexo = request.args.get("sexo")
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(max(int(request.args.get("limit", 20)), 1), 200)
    sort = request.args.get("sort", "-updated_at")

    filtro = {}
    if estado in ("activo", "inactivo"):
        filtro["estado"] = estado
    if especialidad:
        filtro["especialidad"] = especialidad
    if sexo in ("femenino", "masculino", "otro", "no_especificado"):
        filtro["sexo"] = sexo

    if q:
        filtro["$or"] = [
            {"folio": {"$regex": q, "$options": "i"}},
            {"nombre_completo": {"$regex": q, "$options": "i"}},
            {"cedula": {"$regex": q, "$options": "i"}},
            {"especialidad": {"$regex": q, "$options": "i"}},
            {"subespecialidad": {"$regex": q, "$options": "i"}},
            {"correo": {"$regex": q, "$options": "i"}},
            {"telefono": {"$regex": q, "$options": "i"}},
        ]

    sort_map = {
        "updated_at": ("updated_at", 1),
        "-updated_at": ("updated_at", -1),
        "nombre_completo": ("nombre_completo", 1),
        "-nombre_completo": ("nombre_completo", -1),
        "fecha_nacimiento": ("fecha_nacimiento", 1),
        "-fecha_nacimiento": ("fecha_nacimiento", -1),
        "folio": ("folio", 1),
        "-folio": ("folio", -1),
    }
    sort_field, sort_dir = sort_map.get(sort, ("updated_at", -1))

    col = mongo.db.medicos
    total = col.count_documents(filtro)
    docs = (
        col.find(filtro)
        .sort(sort_field, sort_dir)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    data = [serializar_medico(d) for d in docs]

    return jsonify({
        "data": data,
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": page * limit < total
    }), 200


@medicos_bp.get("/<id>")
def obtener_medico(id):
    """GET /medicos/{id} - Obtener médico por ID"""
    doc = mongo.db.medicos.find_one({"_id": oid(id)})
    if not doc:
        return jsonify({"message": "Médico no encontrado"}), 404
    return jsonify({"data": serializar_medico(doc)}), 200


@medicos_bp.put("/<id>")
@medicos_bp.patch("/<id>")
def actualizar_medico(id):
    """PUT/PATCH /medicos/{id} - Actualizar médico"""
    data = request.get_json(silent=True) or {}
    ok, errors, cleaned = validar_payload_medico(data, "actualizar")
    if not ok:
        return jsonify({"message": "Validación fallida", "errors": errors}), 422

    # Si viene folio en actualización, validar patrón y normalizar
    if "folio" in data:
        folio_in = (data.get("folio") or "").strip().upper()
        if not FOLIO_PATTERN.match(folio_in):
            return jsonify({"message": "Validación fallida", "errors": {"folio": "Formato inválido. Use MED-0001"}}), 422
        cleaned["folio"] = folio_in

    cleaned["updated_at"] = datetime.now(timezone.utc)
    cleaned["updated_by"] = None

    try:
        result = mongo.db.medicos.find_one_and_update(
            {"_id": oid(id)},
            {"$set": cleaned},
            return_document=True  # type: ignore
        )
        if not result:
            return jsonify({"message": "Médico no encontrado"}), 404
        return jsonify({"message": "Médico actualizado", "data": serializar_medico(result)}), 200
    except Exception as e:
        msg = str(e)
        if "dup key" in msg and "folio" in msg:
            return jsonify({"message": "El folio ya existe"}), 409
        if "dup key" in msg and "cedula" in msg:
            return jsonify({"message": "La cédula ya existe"}), 409
        if "dup key" in msg and "correo" in msg:
            return jsonify({"message": "El correo ya existe"}), 409
        return jsonify({"message": "Error al actualizar médico", "error": msg}), 500


@medicos_bp.delete("/<id>")
def eliminar_medico(id):
    """
    DELETE /medicos/{id} - Borrado lógico (estado: inactivo)
    Si quieres borrado físico: usa delete_one en lugar del update.
    """
    now = datetime.now(timezone.utc)
    result = mongo.db.medicos.find_one_and_update(
        {"_id": oid(id)},
        {"$set": {"estado": "inactivo", "updated_at": now}},
        return_document=True  # type: ignore
    )
    if not result:
        return jsonify({"message": "Médico no encontrado"}), 404
    return jsonify({"message": "Médico inactivado", "data": serializar_medico(result)}), 200
