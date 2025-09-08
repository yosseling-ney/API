from flask import Blueprint
from app.controllers import patologias_controller
from app.utils.jwt_manager import token_required

patologias_bp = Blueprint("patologias_bp", __name__)

@patologias_bp.route("/patologias", methods=["POST"])
@token_required
def crear(usuario_actual):
    return patologias_controller.crear_patologia(usuario_actual)

@patologias_bp.route("/patologias/<patologia_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, patologia_id):
    return patologias_controller.obtener_patologia(usuario_actual, patologia_id)


@patologias_bp.route("/patologias/<patologia_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, patologia_id):
    return patologias_controller.actualizar_patologia(usuario_actual, patologia_id)


@patologias_bp.route("/patologias/<patologia_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, patologia_id):
    return patologias_controller.eliminar_patologia(usuario_actual, patologia_id)
