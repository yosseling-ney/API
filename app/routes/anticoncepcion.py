from flask import Blueprint
from app.controllers import anticoncepcion_controller
from app.utils.jwt_manager import token_required

anticoncepcion_bp = Blueprint("anticoncepcion_bp", __name__)

@anticoncepcion_bp.route("/anticoncepcion", methods=["POST"])
@token_required
def crear(usuario_actual):
    return anticoncepcion_controller.crear_anticoncepcion(usuario_actual)

@anticoncepcion_bp.route("/anticoncepcion/<anticoncepcion_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, anticoncepcion_id):
    return anticoncepcion_controller.obtener_anticoncepcion(usuario_actual, anticoncepcion_id)

@anticoncepcion_bp.route("/anticoncepcion/<anticoncepcion_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, anticoncepcion_id):
    return anticoncepcion_controller.actualizar_anticoncepcion(usuario_actual, anticoncepcion_id)

@anticoncepcion_bp.route("/anticoncepcion/<anticoncepcion_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, anticoncepcion_id):
    return anticoncepcion_controller.eliminar_anticoncepcion(usuario_actual, anticoncepcion_id)
