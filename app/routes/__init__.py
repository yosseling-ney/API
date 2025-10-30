from app.controllers.paciente_controller import bp as pacientes_bp
from app.controllers.historial_controller import bp as historiales_bp
from app.controllers.medicos_controller import medicos_bp
from .settings import bp as settings_bp
from .mensajes import bp as mensajes_bp
from .citas import bp as citas_bp
from app.routes.usuarios import usuarios_bp
from .backup import bp as backup_bp
from .reportes import bp as reportes_bp

# Registrar rutas
def register_routes(app):
    # Montar todo bajo /api para unificar el prefijo, conservando el prefijo propio de cada BP
    def with_api(bp):
        return "/api" + (bp.url_prefix or "")

    app.register_blueprint(pacientes_bp,   url_prefix=with_api(pacientes_bp))
    app.register_blueprint(usuarios_bp,    url_prefix=with_api(usuarios_bp))
    app.register_blueprint(historiales_bp, url_prefix=with_api(historiales_bp))  
    app.register_blueprint(settings_bp,    url_prefix=with_api(settings_bp))
    app.register_blueprint(mensajes_bp,    url_prefix=with_api(mensajes_bp))
    app.register_blueprint(medicos_bp,     url_prefix=with_api(medicos_bp))
    app.register_blueprint(citas_bp,       url_prefix=with_api(citas_bp))
    app.register_blueprint(backup_bp,      url_prefix=with_api(backup_bp))
    app.register_blueprint(reportes_bp,    url_prefix=with_api(reportes_bp))
