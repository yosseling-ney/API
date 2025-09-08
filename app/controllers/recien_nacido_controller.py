from flask import request, jsonify
from bson import ObjectId
from app import mongo

def crear_recien_nacido(usuario_actual):
    try:
        data = request.get_json()

        # Validar campos principales requeridos
        campos_requeridos = [
            "identificacion_id", "tipo_nacimiento", "sexo", "peso_nacer",
            "perimetro_cefalico", "longitud", "edad_gestacional",
            "peso_edad_gestacional", "cuidados_inmediatos", "apgar",
            "reanimacion", "fallece_sala_parto", "referido", "atendio",
            "defectos_congenitos", "enfermedades", "vih_rn",
            "tamizaje_neonatal", "meconio"
        ]

        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "tipo_nacimiento": data["tipo_nacimiento"],
            "sexo": data["sexo"],
            "peso_nacer": float(data["peso_nacer"]),
            "perimetro_cefalico": float(data["perimetro_cefalico"]),
            "longitud": float(data["longitud"]),
            "edad_gestacional": data["edad_gestacional"],  # objeto
            "peso_edad_gestacional": data["peso_edad_gestacional"],
            "cuidados_inmediatos": data["cuidados_inmediatos"],  # objeto
            "apgar": data["apgar"],  # objeto
            "reanimacion": data["reanimacion"],  # array
            "fallece_sala_parto": data["fallece_sala_parto"],
            "referido": data["referido"],
            "atendio": data["atendio"],  # objeto
            "defectos_congenitos": data["defectos_congenitos"],  # objeto
            "enfermedades": data["enfermedades"],  # objeto
            "vih_rn": data["vih_rn"],  # objeto
            "tamizaje_neonatal": data["tamizaje_neonatal"],  # objeto
            "meconio": data["meconio"]
        }

        resultado = mongo.db.recien_nacidos.insert_one(documento)
        return jsonify({"mensaje": "Segmento registrado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar", "detalle": str(e)}), 400


def obtener_recien_nacido(usuario_actual, recien_nacido_id):
    try:
        datos = mongo.db.recien_nacidos.find_one({"_id": ObjectId(recien_nacido_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener los datos", "detalle": str(e)}), 400


def actualizar_recien_nacido(usuario_actual, recien_nacido_id):
    try:
        data = request.get_json()

        # Si viene identificacion_id, convertirlo a ObjectId
        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])

        resultado = mongo.db.recien_nacidos.update_one(
            {"_id": ObjectId(recien_nacido_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


def eliminar_recien_nacido(usuario_actual, recien_nacido_id):
    try:
        resultado = mongo.db.recien_nacidos.delete_one({"_id": ObjectId(recien_nacido_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
