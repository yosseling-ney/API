from flask import request, jsonify
from bson import ObjectId
from app import mongo

# Crear registro de anticoncepción
def crear_anticoncepcion(usuario_actual):
    try:
        data = request.get_json()

        # Validar campos requeridos
        campos_requeridos = ["identificacion_id", "consejeria", "metodo_elegido"]
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "consejeria": data["consejeria"],
            "metodo_elegido": data["metodo_elegido"]
        }

        resultado = mongo.db.anticoncepcion.insert_one(documento)
        return jsonify({"mensaje": "Registro de anticoncepción creado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar anticoncepción", "detalle": str(e)}), 400


# Obtener un registro por ID
def obtener_anticoncepcion(usuario_actual, anticoncepcion_id):
    try:
        datos = mongo.db.anticoncepcion.find_one({"_id": ObjectId(anticoncepcion_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener anticoncepción", "detalle": str(e)}), 400


# Actualizar un registro por ID
def actualizar_anticoncepcion(usuario_actual, anticoncepcion_id):
    try:
        data = request.get_json()

        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])

        resultado = mongo.db.anticoncepcion.update_one(
            {"_id": ObjectId(anticoncepcion_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el registro"}), 404

        return jsonify({"mensaje": "Registro de anticoncepción actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar anticoncepción", "detalle": str(e)}), 400


# Eliminar un registro por ID
def eliminar_anticoncepcion(usuario_actual, anticoncepcion_id):
    try:
        resultado = mongo.db.anticoncepcion.delete_one({"_id": ObjectId(anticoncepcion_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el registro"}), 404

        return jsonify({"mensaje": "Registro de anticoncepción eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar anticoncepción", "detalle": str(e)}), 400
