from flask import Blueprint

from app.controllers.reportes_controller import (
    get_dashboard,
    get_dashboard_pdf,
    get_dashboard_excel,
    get_dashboard_json_download,
)


bp = Blueprint("reportes", __name__, url_prefix="/reportes")

bp.add_url_rule("/dashboard", view_func=get_dashboard, methods=["GET"])
bp.add_url_rule("/dashboard/pdf", view_func=get_dashboard_pdf, methods=["GET"])
bp.add_url_rule("/dashboard/excel", view_func=get_dashboard_excel, methods=["GET"])
bp.add_url_rule("/dashboard/json", view_func=get_dashboard_json_download, methods=["GET"])
