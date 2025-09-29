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

    return app
