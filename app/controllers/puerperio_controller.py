from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

# --- Función auxiliar para convertir fechas ---
def convertir_fechas_puerperio(puerperio_inmediato):
    """
    Convierte el campo dia_hora de string ISO a datetime para cumplir con bsonType: date.
    """
    convertido = []
    for item in puerperio_inmediato:
        nuevo_item = item.copy()
        if isinstance(nuevo_item.get("dia_hora"), str):
            try:
                # Convertir ISO 8601 con zona horaria Z
                nuevo_item["dia_hora"] = datetime.fromisoformat(
                    nuevo_item["dia_hora"].replace("Z", "+00:00")
                )
            except ValueError:
                raise ValueError(f"Formato de fecha inválido en dia_hora: {nuevo_item.get('dia_hora')}")
        convertido.append(nuevo_item)
    return convertido


# Crear registro de puerperio
def crear_puerperio(usuario_actual):
    try:
        data = request.get_json()

        campos_requeridos = [
            "identificacion_id", "puerperio_inmediato",
            "antirrubeola_postparto", "gammaglobulina_anti_d"
        ]
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        # Conversión de fechas
        puerperio_inmediato_convertido = convertir_fechas_puerperio(data["puerperio_inmediato"])

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "puerperio_inmediato": puerperio_inmediato_convertido,
            "antirrubeola_postparto": data["antirrubeola_postparto"],
            "gammaglobulina_anti_d": data["gammaglobulina_anti_d"]
        }

        resultado = mongo.db.puerperio.insert_one(documento)
        return jsonify({"mensaje": "Puerperio registrado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar", "detalle": str(e)}), 400


# Obtener por ID de puerperio
def obtener_puerperio(usuario_actual, puerperio_id):
    try:
        datos = mongo.db.puerperio.find_one({"_id": ObjectId(puerperio_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        # Convertir ObjectId a string
        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener los datos", "detalle": str(e)}), 400


# Actualizar registro
def actualizar_puerperio(usuario_actual, puerperio_id):
    try:
        data = request.get_json()

        # Si viene identificacion_id, convertirlo
        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])

        # Si viene puerperio_inmediato, convertir fechas
        if "puerperio_inmediato" in data:
            data["puerperio_inmediato"] = convertir_fechas_puerperio(data["puerperio_inmediato"])

        resultado = mongo.db.puerperio.update_one(
            {"_id": ObjectId(puerperio_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Puerperio actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


# Eliminar registro
def eliminar_puerperio(usuario_actual, puerperio_id):
    try:
        resultado = mongo.db.puerperperio.delete_one({"_id": ObjectId(puerperio_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Puerperio eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
