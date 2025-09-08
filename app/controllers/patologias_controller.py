from flask import request, jsonify
from bson import ObjectId
from app import mongo

def crear_patologia(usuario_actual):
    try:
        data = request.get_json()

        # Campos requeridos principales
        campos_requeridos = ["identificacion_id", "enfermedades", "resumen", "hemorragia", "tdp"]
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "enfermedades": data["enfermedades"],
            "resumen": data["resumen"],
            "hemorragia": data["hemorragia"],
            "tdp": data["tdp"]
        }

        resultado = mongo.db.patologias.insert_one(documento)
        return jsonify({"mensaje": "Patología registrada", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar la patología", "detalle": str(e)}), 400


def obtener_patologia(usuario_actual, patologia_id):
    try:
        datos = mongo.db.patologias.find_one({"_id": ObjectId(patologia_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener la patología", "detalle": str(e)}), 400



def actualizar_patologia(usuario_actual, patologia_id):
    try:
        data = request.get_json()

        # Evitar que usuario_id se modifique
        if "usuario_id" in data:
            del data["usuario_id"]

        # Convertir identificacion_id a ObjectId si se envía
        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])

        resultado = mongo.db.patologias.update_one(
            {"_id": ObjectId(patologia_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró la patología"}), 404

        return jsonify({"mensaje": "Patología actualizada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar la patología", "detalle": str(e)}), 400



def eliminar_patologia(usuario_actual, patologia_id):
    try:
        resultado = mongo.db.patologias.delete_one({"_id": ObjectId(patologia_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró la patología"}), 404

        return jsonify({"mensaje": "Patología eliminada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar la patología", "detalle": str(e)}), 400

