# app/routes/__init__.py
from app.controllers.paciente_controller import bp as pacientes_bp
from app.controllers.historial_controller import bp as historiales_bp
from .settings import bp as settings_bp
from .mensajes import bp as mensajes_bp
from app.routes.usuarios import usuarios_bp

# Registrar rutas
def register_routes(app):
    app.register_blueprint(pacientes_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(historiales_bp)  
    app.register_blueprint(settings_bp)
    app.register_blueprint(mensajes_bp)
