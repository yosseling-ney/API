from flask import Blueprint
from app.controllers import recien_nacido_controller
from app.utils.jwt_manager import token_required

recien_nacido_bp = Blueprint("recien_nacido_bp", __name__)

@recien_nacido_bp.route("/recien_nacido", methods=["POST"])
@token_required
def crear(usuario_actual):
    return recien_nacido_controller.crear_recien_nacido(usuario_actual)

@recien_nacido_bp.route("/recien_nacido/<recien_nacido_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, recien_nacido_id):
    return recien_nacido_controller.obtener_recien_nacido(usuario_actual, recien_nacido_id)

@recien_nacido_bp.route("/recien_nacido/<recien_nacido_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, recien_nacido_id):
    return recien_nacido_controller.actualizar_recien_nacido(usuario_actual, recien_nacido_id)

@recien_nacido_bp.route("/recien_nacido/<recien_nacido_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, recien_nacido_id):
    return recien_nacido_controller.eliminar_recien_nacido(usuario_actual, recien_nacido_id)