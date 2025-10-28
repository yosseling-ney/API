from flask import Blueprint
from app.controllers.citas_controller import (
    get_hoy,
    get_proximas,
    get_activas,
    get_historicas,
    post_crear,
    patch_actualizar,
    delete_eliminar,
)

# Nota: si deseas proteger con JWT, importa y aplica decoradores aquí.

bp = Blueprint("citas", __name__, url_prefix="/citas")

bp.add_url_rule("/hoy", view_func=get_hoy, methods=["GET"])
bp.add_url_rule("/proximas", view_func=get_proximas, methods=["GET"])
bp.add_url_rule("/activas", view_func=get_activas, methods=["GET"])
bp.add_url_rule("/historicas", view_func=get_historicas, methods=["GET"])
bp.add_url_rule("/", view_func=post_crear, methods=["POST"])
bp.add_url_rule("/<cita_id>", view_func=patch_actualizar, methods=["PATCH"])
bp.add_url_rule("/<cita_id>", view_func=delete_eliminar, methods=["DELETE"])
