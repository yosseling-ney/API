from flask import Blueprint, request
from app.controllers.usuarios_controller import (
    obtener_usuarios,
    crear_usuario,
    obtener_usuario_por_id,
    eliminar_usuario,
    autentificar_usuarios
)

usuarios_bp = Blueprint('usuarios_bp', __name__)

usuarios_bp.route('/usuarios', methods=['GET'])(obtener_usuarios)
usuarios_bp.route('/usuarios', methods=['POST'])(crear_usuario)
usuarios_bp.route('/usuarios/<id>', methods=['GET'])(obtener_usuario_por_id)
usuarios_bp.route('/usuarios/<id>', methods=['DELETE'])(eliminar_usuario)
usuarios_bp.route('/login', methods=['POST'])(autentificar_usuarios)