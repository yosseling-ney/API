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

    app.config["MONGO_URI"] = os.getenv("MONGO_URI")
    mongo.init_app(app)

    @app.route('/')
    def home():
        return jsonify({"mensaje": "API  funcionando "}), 200

    # Registrar rutas
    from app.routes.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp)

    # rutas de identificaciones prenatales 
    from app.routes.identificaciones_prenatales import identificaciones_bp
    app.register_blueprint(identificaciones_bp)

    # Rutas del segmento de identificación de historia clínica
    from app.routes.identificacion import identificacion_bp
    app.register_blueprint(identificacion_bp)

    # rutas de antecedentes
    from app.routes.antecedentes import antecedentes_bp
    app.register_blueprint(antecedentes_bp)

    #rutas del segmento gestacion_actual
    from app.routes.gestacion_actual import gestacion_bp
    app.register_blueprint(gestacion_bp)

    #rutas del segmento parto o aborto
    from app.routes.parto_aborto import parto_aborto_bp
    app.register_blueprint(parto_aborto_bp)

    #ruta del segmento de patalogias
    from app.routes.patologias import patologias_bp
    app.register_blueprint(patologias_bp)

    #ruta del segmento de recien nacid@s
    from app.routes.recien_nacido import recien_nacido_bp
    app.register_blueprint(recien_nacido_bp)

    #ruta del segmento puerperio
    from app.routes.puerperio import puerperio_bp
    app.register_blueprint(puerperio_bp)

    #ruta del segmento 8 Egreso del Recién Nacido/a 
    from app.routes.egreso_neonatal import egreso_neonatal_bp
    app.register_blueprint(egreso_neonatal_bp)

    #ruta del segemento egreso materno 
    from app.routes.egreso_materno import egreso_materno_bp
    app.register_blueprint(egreso_materno_bp)

    #ruta del segmento de anticoncepcion
    from app.routes.anticoncepcion import anticoncepcion_bp
    app.register_blueprint(anticoncepcion_bp)

    return app
