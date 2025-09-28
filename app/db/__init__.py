# app/db/__init__.py
from flask import current_app
from contextlib import contextmanager

# Alias al cliente Mongo que inicializas en app/__init__.py
from app import mongo

@contextmanager
def start_session_if_possible():
    """
    Intenta abrir una sesión de MongoDB para transacciones.
    Si tu Mongo no es réplica, devuelve None (y el código sigue funcionando).
    """
    client = mongo.cx  # el MongoClient que Flask guarda en mongo
    session = None
    try:
        session = client.start_session()
        session.start_transaction()
    except Exception:
        session = None  # si no hay soporte de transacciones, sigue sin error
    try:
        yield session
    finally:
        if session:
            session.end_session()
