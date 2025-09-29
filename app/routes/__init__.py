# app/routes/__init__.py
from .pacientes import bp as pacientes_bp

def register_routes(app):
    app.register_blueprint(pacientes_bp)

# Registrar rutas
    from app.routes.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp)
