from flask import Blueprint
from app.controllers.identificaciones_prenatales_controller import (
    crear_identificacion_prenatal,
    obtener_identificacion_prenatal,
    obtener_todas_identificaciones,
    eliminar_identificacion_prenatal
)

identificaciones_bp = Blueprint('identificaciones_bp', __name__)

# Ruta para crear identificación prenatal
identificaciones_bp.route('/identificaciones-prenatales', methods=['POST'])(crear_identificacion_prenatal)

# Ruta para obtener una identificación específica
identificaciones_bp.route('/identificaciones-prenatales/<string:id>', methods=['GET'])(obtener_identificacion_prenatal)

# Ruta para listar todas las identificaciones
identificaciones_bp.route('/identificaciones-prenatales', methods=['GET'])(obtener_todas_identificaciones)

# Ruta para eliminar una identificación
identificaciones_bp.route('/identificaciones-prenatales/<string:id>', methods=['DELETE'])(eliminar_identificacion_prenatal)
