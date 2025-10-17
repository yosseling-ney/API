import jwt
from flask import request, jsonify, g
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv('JWT_SECRET_KEY')


def generar_token(usuario_id, rol):
    token = jwt.encode(
        {"usuario_id": usuario_id, "rol": rol},
        SECRET_KEY,
        algorithm="HS256"
    )
    return token


def verificar_token(token):
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[-1]

        if not token:
            return jsonify({'error': 'Token no proporcionado'}), 401

        datos = verificar_token(token)
        if not datos:
            return jsonify({'error': 'Token inválido'}), 401

        # Guardar el usuario actual en el contexto de la petición
        g.usuario_actual = datos

        # No alterar la firma de la función vista
        return f(*args, **kwargs)

    return decorated

