from flask import Flask, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import os

mongo = PyMongo()

def create_app():
    load_dotenv()

    app = Flask(__name__)
    CORS(app)

    # Aceptar rutas con y sin slash final globalmente
    app.url_map.strict_slashes = False

    # Config
    app.config["MONGO_URI"] = os.getenv("MONGO_URI") or "mongodb://localhost:27017/sigepren_db"

    # Inicializar Mongo
    mongo.init_app(app)

    # Registrar rutas (blueprints)
    try:
        from app.routes import register_routes
        register_routes(app)
    except Exception as e:
        # Si aún no tienes el paquete routes, no tires la app.
        print(f"[routes] aviso: {e}")

    # Salud
    @app.get("/")
    def home():
        return jsonify({"mensaje": "API funcionando"}), 200

    # Salud bajo /api para verificar prefijo
    @app.get("/api/health")
    def api_health():
        return jsonify({"ok": True}), 200

    # Listado de rutas para depuracin
    @app.get("/api/_routes")
    def list_routes():
        rules = sorted([str(r) for r in app.url_map.iter_rules()])
        return jsonify({"routes": rules}), 200

    return app
