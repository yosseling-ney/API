# app/routes/__init__.py
from app.controllers.paciente_controller import bp as pacientes_bp
from app.routes.usuarios import usuarios_bp

def register_routes(app):
    app.register_blueprint(pacientes_bp)
    # Registrar rutas
    app.register_blueprint(usuarios_bp)
