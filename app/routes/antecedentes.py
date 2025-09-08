from flask import Blueprint
from app.controllers import antecedentes_controller
from app.utils.jwt_manager import token_required

antecedentes_bp = Blueprint("antecedentes_bp", __name__)

# Crear antecedentes (protegido con token)
@antecedentes_bp.route('/antecedentes', methods=["POST"])
@token_required
def crear(usuario_actual):
    return antecedentes_controller.crear_antecedentes(usuario_actual)

# Obtener antecedentes por identificacion_id
@antecedentes_bp.route('/antecedentes/<identificacion_id>', methods=["GET"])
def obtener(identificacion_id):
    return antecedentes_controller.obtener_antecedentes_por_paciente(identificacion_id)

# Actualizar antecedentes por identificacion_id
@antecedentes_bp.route('/antecedentes/<identificacion_id>', methods=["PUT"])
def actualizar(identificacion_id):
    return antecedentes_controller.actualizar_antecedentes(identificacion_id)

# Eliminar antecedentes por identificacion_id
@antecedentes_bp.route('/antecedentes/<identificacion_id>', methods=["DELETE"])
def eliminar(identificacion_id):
    return antecedentes_controller.eliminar_antecedentes(identificacion_id)
