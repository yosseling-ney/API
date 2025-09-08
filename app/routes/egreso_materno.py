from flask import Blueprint
from app.controllers import egreso_materno_controller
from app.utils.jwt_manager import token_required

egreso_materno_bp = Blueprint("egreso_materno_bp", __name__)

# Crear egreso materno
@egreso_materno_bp.route("/egreso_materno", methods=["POST"])
@token_required
def crear(usuario_actual):
    return egreso_materno_controller.crear_egreso_materno(usuario_actual)

# Obtener por ID
@egreso_materno_bp.route("/egreso_materno/<egreso_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, egreso_id):
    return egreso_materno_controller.obtener_egreso_materno(usuario_actual, egreso_id)

# Actualizar
@egreso_materno_bp.route("/egreso_materno/<egreso_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, egreso_id):
    return egreso_materno_controller.actualizar_egreso_materno(usuario_actual, egreso_id)

# Eliminar
@egreso_materno_bp.route("/egreso_materno/<egreso_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, egreso_id):
    return egreso_materno_controller.eliminar_egreso_materno(usuario_actual, egreso_id)
