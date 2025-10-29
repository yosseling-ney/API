from flask import Blueprint
from app.controllers.backup_controller import download_backup

bp = Blueprint("backup", __name__, url_prefix="/backup")

bp.add_url_rule("/", view_func=download_backup, methods=["GET"])

