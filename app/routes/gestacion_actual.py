from flask import Blueprint
from app.controllers import gestacion_actual_controller
from app.utils.jwt_manager import token_required

gestacion_bp = Blueprint("gestacion_actual", __name__)  

# Crear segmento de gestación actual
@gestacion_bp.route("/gestacion_actual", methods=["POST"])
@token_required
def crear(usuario_actual):
    return gestacion_actual_controller.crear_gestacion_actual(usuario_actual)

# Obtener segmento de gestación actual por identificacion_id
@gestacion_bp.route("/gestacion_actual/<identificacion_id>", methods=["GET"])
@token_required
def obtener(usuario_actual, identificacion_id):
    return gestacion_actual_controller.obtener_gestacion_actual(usuario_actual, identificacion_id)

# Actualizar segmento de gestación actual por identificacion_id
@gestacion_bp.route("/gestacion_actual/<identificacion_id>", methods=["PUT"])
@token_required
def actualizar(usuario_actual, identificacion_id):
    return gestacion_actual_controller.actualizar_gestacion_actual(usuario_actual, identificacion_id)

# Eliminar segmento de gestación actual por identificacion_id
@gestacion_bp.route("/gestacion_actual/<identificacion_id>", methods=["DELETE"])
@token_required
def eliminar(usuario_actual, identificacion_id):
    return gestacion_actual_controller.eliminar_gestacion_actual(usuario_actual, identificacion_id)
