from flask import Blueprint
from app.controllers.mensajes_controller import list_mensajes, crear_mensaje, marcar_leido, eliminar_mensaje, actualizar_mensaje

bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")

bp.add_url_rule("/", view_func=list_mensajes, methods=["GET"])
bp.add_url_rule("/", view_func=crear_mensaje, methods=["POST"])
bp.add_url_rule("/<mensaje_id>/read", view_func=marcar_leido, methods=["PUT", "PATCH"])
bp.add_url_rule("/<mensaje_id>", view_func=actualizar_mensaje, methods=["PUT", "PATCH"])
bp.add_url_rule("/<mensaje_id>", view_func=eliminar_mensaje, methods=["DELETE"])
