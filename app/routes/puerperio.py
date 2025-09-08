from flask import Blueprint
from app.controllers import puerperio_controller
from app.utils.jwt_manager import token_required

puerperio_bp = Blueprint("puerperio_bp", __name__)

@puerperio_bp.route("/puerperio", methods=["POST"])
@token_required
def crear(usuario_actual):
    return puerperio_controller.crear_puerperio(usuario_actual)

@puerperio_bp.route("/puerperio/<puerperio_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, puerperio_id):
    return puerperio_controller.obtener_puerperio(usuario_actual, puerperio_id)

@puerperio_bp.route("/puerperio/<puerperio_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, puerperio_id):
    return puerperio_controller.actualizar_puerperio(usuario_actual, puerperio_id)

@puerperio_bp.route("/puerperio/<puerperio_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, puerperio_id):
    return puerperio_controller.eliminar_puerperio(usuario_actual, puerperio_id)
