# app/routes/parto_aborto.py

from flask import Blueprint
from app.controllers import parto_aborto_controller
from app.utils.jwt_manager import token_required

parto_aborto_bp = Blueprint("parto_aborto_bp", __name__)

# Crear segmento Parto o Aborto
@parto_aborto_bp.route("/parto_aborto", methods=["POST"])
@token_required
def crear(usuario_actual):
    return parto_aborto_controller.crear_parto_aborto(usuario_actual)

# Obtener segmento Parto o Aborto por identificacion_id
@parto_aborto_bp.route("/parto_aborto/<identificacion_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, identificacion_id):
    return parto_aborto_controller.obtener_parto_aborto(usuario_actual, identificacion_id)

# Actualizar segmento Parto o Aborto por identificacion_id
@parto_aborto_bp.route("/parto_aborto/<identificacion_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, identificacion_id):
    return parto_aborto_controller.actualizar_parto_aborto(usuario_actual, identificacion_id)

# Eliminar segmento Parto o Aborto por identificacion_id
@parto_aborto_bp.route("/parto_aborto/<identificacion_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, identificacion_id):
    return parto_aborto_controller.eliminar_parto_aborto(usuario_actual, identificacion_id)
