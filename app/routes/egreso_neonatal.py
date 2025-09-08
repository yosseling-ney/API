from flask import Blueprint
from app.controllers import egreso_neonatal_controller
from app.utils.jwt_manager import token_required

egreso_neonatal_bp = Blueprint("egreso_neonatal_bp", __name__)

@egreso_neonatal_bp.route("/egreso_neonatal", methods=["POST"])
@token_required
def crear(usuario_actual):
    return egreso_neonatal_controller.crear_egreso_neonatal(usuario_actual)

@egreso_neonatal_bp.route("/egreso_neonatal/<egreso_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, egreso_id):
    return egreso_neonatal_controller.obtener_egreso_neonatal(usuario_actual, egreso_id)

@egreso_neonatal_bp.route("/egreso_neonatal/<egreso_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, egreso_id):
    return egreso_neonatal_controller.actualizar_egreso_neonatal(usuario_actual, egreso_id)

@egreso_neonatal_bp.route("/egreso_neonatal/<egreso_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, egreso_id):
    return egreso_neonatal_controller.eliminar_egreso_neonatal(usuario_actual, egreso_id)
