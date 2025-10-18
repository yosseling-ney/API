from flask import request, jsonify
from bson import ObjectId
from app import mongo
from app.models.usuario_model import serializar_usuario
from app.utils.helpers import encriptar_password, verificar_password
from app.utils.jwt_manager import generar_token, token_required
from app.utils.helpers import verificar_password

@token_required
def obtener_usuarios(usuario_actual):
    usuarios = mongo.db.usuarios.find()
    resultado = [serializar_usuario(usuario) for usuario in usuarios]
    return jsonify(resultado)

def crear_usuario():
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

def obtener_usuario_por_id(id):
    try:
        usuario = mongo.db.usuarios.find_one({"_id": ObjectId(id)})
        if usuario:
            return jsonify(serializar_usuario(usuario))
        return jsonify({"error": "Usuario no encontrado"}), 404
    except:
        return jsonify({"error": "ID no válido"}), 400

def eliminar_usuario(id):
    try:
        resultado = mongo.db.usuarios.delete_one({"_id": ObjectId(id)})
        if resultado.deleted_count == 1:
            return jsonify({"mensaje": "Usuario eliminado correctamente"})
        return jsonify({"error": "Usuario no encontrado"}), 404
    except:
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
    

def actualizar_usuario(id):
    try:
        data = request.get_json()
        campos_a_actualizar = {}

        # Solo actualizamos los campos que vienen en el request
        if "nombre" in data:
            campos_a_actualizar["nombre"] = data["nombre"]
        if "apellido" in data:
            campos_a_actualizar["apellido"] = data["apellido"]
        if "correo" in data:
            campos_a_actualizar["correo"] = data["correo"]
        if "telefono" in data:
            campos_a_actualizar["telefono"] = data["telefono"]
        if "username" in data:
            campos_a_actualizar["username"] = data["username"]
        if "password" in data and data["password"]:
            campos_a_actualizar["password"] = encriptar_password(data["password"])
        if "rol" in data:
            campos_a_actualizar["rol"] = data["rol"]

        if not campos_a_actualizar:
            return jsonify({"error": "No se enviaron campos válidos para actualizar"}), 400

        resultado = mongo.db.usuarios.update_one(
            {"_id": ObjectId(id)},
            {"$set": campos_a_actualizar}
        )

        if resultado.matched_count == 0:
            return jsonify({"error": "Usuario no encontrado"}), 404

        return jsonify({"mensaje": "Usuario actualizado correctamente"}), 200

    except:
        return jsonify({"error": "ID no válido"}), 400

