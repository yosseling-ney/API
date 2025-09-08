from flask import Blueprint
from app.controllers import identificacion_controller
from app.utils.jwt_manager import token_required

identificacion_bp = Blueprint('identificacion_bp', __name__)

@identificacion_bp.route('/identificacion', methods=["POST"])
@token_required
def crear(usuario_actual):
    return identificacion_controller.crear_identificacion(usuario_actual)

@identificacion_bp.route('/identificacion/<id_prenatal>', methods=["GET"])
def obtener(id_prenatal):
    return identificacion_controller.obtener_identificacion_por_prenatal(id_prenatal)

@identificacion_bp.route('/identificacion/<id_prenatal>', methods=["PUT"])
def actualizar(id_prenatal):
    return identificacion_controller.actualizar_identificacion(id_prenatal)

@identificacion_bp.route('/identificacion/<id_prenatal>', methods=["DELETE"])
def eliminar(id_prenatal):
    return identificacion_controller.eliminar_identificacion(id_prenatal)
