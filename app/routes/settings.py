from flask import Blueprint
from app.controllers import settings_controller as ctrl

bp = Blueprint("settings", __name__, url_prefix="/settings")

bp.add_url_rule("/",      view_func=ctrl.upsert,  methods=["POST"])
bp.add_url_rule("/",      view_func=ctrl.list_,   methods=["GET"])
bp.add_url_rule("/<key>", view_func=ctrl.get_one, methods=["GET"])
bp.add_url_rule("/<key>", view_func=ctrl.delete_one, methods=["DELETE"])
