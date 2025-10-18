from flask import Blueprint
from controllers.citas_controller import get_hoy, get_proximas, post_crear
# Si requieres auth: from utils.jwt_manager import login_required

citas_bp = Blueprint("citas", __name__)

@citas_bp.get("/hoy")
def r_hoy():
    return get_hoy()

@citas_bp.get("/proximas")
def r_proximas():
    return get_proximas()

@citas_bp.post("")
def r_crear():
    return post_crear()
