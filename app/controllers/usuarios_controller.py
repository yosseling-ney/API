from flask import request, jsonify, g
from bson import ObjectId
from app import mongo
from app.models.usuario_model import serializar_usuario
from app.utils.helpers import encriptar_password, verificar_password
from app.utils.jwt_manager import generar_token, token_required


@token_required
def obtener_usuarios():
    usuarios = mongo.db.usuarios.find()
    resultado = [serializar_usuario(usuario) for usuario in usuarios]
    return jsonify(resultado)


def _is_admin():
    ua = getattr(g, 'usuario_actual', None) or {}
    rol = str(ua.get('rol', '')).strip().upper()
    return rol in ("ADMIN", "ADMINISTRADOR", "ADMINISTRATOR", "SUPER_ADMIN", "SUPERADMIN")


@token_required
def crear_usuario():
    # Requiere ADMIN
    if not _is_admin():
        return jsonify({"error": "No autorizado"}), 403
    data = request.get_json()
    nuevo_usuario = {
        "nombre": data['nombre'],
        "apellido": data['apellido'],
        "correo": data['correo'],
        "telefono": data.get('telefono'),
        "username": data['username'],
        "password": encriptar_password(data['password']),
        "rol": data['rol']
    }
    resultado = mongo.db.usuarios.insert_one(nuevo_usuario)
    return jsonify({"mensaje": "Usuario creado exitosamente", "id": str(resultado.inserted_id)}), 201


@token_required
def obtener_usuario_por_id(id):
    try:
        usuario = mongo.db.usuarios.find_one({"_id": ObjectId(id)})
        if usuario:
            return jsonify(serializar_usuario(usuario))
        return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception:
        return jsonify({"error": "ID no válido"}), 400


@token_required
def eliminar_usuario(id):
    # Requiere ADMIN
    if not _is_admin():
        return jsonify({"error": "No autorizado"}), 403
    try:
        resultado = mongo.db.usuarios.delete_one({"_id": ObjectId(id)})
        if resultado.deleted_count == 1:
            return jsonify({"mensaje": "Usuario eliminado correctamente"})
        return jsonify({"error": "Usuario no encontrado"}), 404
    except Exception:
        return jsonify({"error": "ID no válido"}), 400


def autentificar_usuarios():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username y password son requeridos"}), 400

    usuario = mongo.db.usuarios.find_one({"username": username})
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    if verificar_password(password, usuario['password']):
        token = generar_token(str(usuario['_id']), usuario['rol'])
        return jsonify({
            "mensaje": "Autenticación exitosa",
            "token": token,
            "usuario": {
                "id": str(usuario['_id']),
                "nombre": usuario['nombre'],
                "rol": usuario['rol']
            }
        }), 200
    else:
        return jsonify({"error": "Contraseña incorrecta"}), 401


@token_required
def actualizar_usuario(id):
    # Permitir si es ADMIN o si edita su propio perfil
    usuario_actual = getattr(g, 'usuario_actual', None) or {}
    es_admin = _is_admin()
    es_mismo_usuario = usuario_actual.get('usuario_id') == id
    if not (es_admin or es_mismo_usuario):
        return jsonify({"error": "No autorizado"}), 403
    try:
        data = request.get_json() or {}
        campos_a_actualizar = {}

        # Solo actualizamos los campos que vienen en el request
        if "nombre" in data:
            campos_a_actualizar["nombre"] = data["nombre"]
        if "apellido" in data:
            campos_a_actualizar["apellido"] = data["apellido"]
        if "correo" in data:
            correo = data["correo"]
            existe = mongo.db.usuarios.find_one({
                "correo": correo,
                "_id": {"$ne": ObjectId(id)}
            })
            if existe:
                return jsonify({"error": "El correo ya está en uso"}), 409
            campos_a_actualizar["correo"] = correo
        if "telefono" in data:
            campos_a_actualizar["telefono"] = data["telefono"]
        if "username" in data:
            username = data["username"]
            existe = mongo.db.usuarios.find_one({
                "username": username,
                "_id": {"$ne": ObjectId(id)}
            })
            if existe:
                return jsonify({"error": "El nombre de usuario ya está en uso"}), 409
            campos_a_actualizar["username"] = username
        if "password" in data and data["password"]:
            campos_a_actualizar["password"] = encriptar_password(data["password"])
        if "rol" in data:
            # Solo un ADMIN puede cambiar el rol
            if not es_admin:
                return jsonify({"error": "No autorizado para cambiar rol"}), 403
            campos_a_actualizar["rol"] = data["rol"]

        if not campos_a_actualizar:
            return jsonify({"error": "No se enviaron campos válidos para actualizar"}), 400

        resultado = mongo.db.usuarios.update_one(
            {"_id": ObjectId(id)},
            {"$set": campos_a_actualizar}
        )

        if resultado.matched_count == 0:
            return jsonify({"error": "Usuario no encontrado"}), 404

        usuario = mongo.db.usuarios.find_one({"_id": ObjectId(id)})
        return jsonify({
            "mensaje": "Usuario actualizado correctamente",
            "usuario": serializar_usuario(usuario) if usuario else None
        }), 200

    except Exception:
        return jsonify({"error": "ID no válido"}), 400
