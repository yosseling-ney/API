from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

def crear_egreso_neonatal(usuario_actual):
    try:
        data = request.get_json()

        # Validar campos requeridos
        campos_requeridos = [
            "identificacion_id", "estado", "fecha_hora_evento",
            "codigo_traslado", "fallece_durante_traslado", "edad_egreso_dias",
            "id_rn", "alimento_alta", "boca_arriba", "bcg_aplicada",
            "peso_egreso", "nombre_rn", "responsable"
        ]
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "estado": data["estado"],
            "fecha_hora_evento": datetime.fromisoformat(data["fecha_hora_evento"]),
            "codigo_traslado": data["codigo_traslado"],
            "fallece_durante_traslado": data["fallece_durante_traslado"],
            "edad_egreso_dias": int(data["edad_egreso_dias"]),
            "id_rn": data["id_rn"],
            "alimento_alta": data["alimento_alta"],
            "boca_arriba": data["boca_arriba"],
            "bcg_aplicada": data["bcg_aplicada"],
            "peso_egreso": float(data["peso_egreso"]),
            "nombre_rn": data["nombre_rn"],
            "responsable": data["responsable"]
        }

        resultado = mongo.db.egreso_neonatal.insert_one(documento)
        return jsonify({"mensaje": "Egreso registrado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar el egreso", "detalle": str(e)}), 400


def obtener_egreso_neonatal(usuario_actual, egreso_id):
    try:
        datos = mongo.db.egreso_neonatal.find_one({"_id": ObjectId(egreso_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])
        return jsonify(datos), 200

    except Exception as e:
        return jsonify({"error": "Error al obtener el egreso", "detalle": str(e)}), 400


def actualizar_egreso_neonatal(usuario_actual, egreso_id):
    try:
        data = request.get_json()

        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])
        if "fecha_hora_evento" in data:
            data["fecha_hora_evento"] = datetime.fromisoformat(data["fecha_hora_evento"])

        resultado = mongo.db.egreso_neonatal.update_one(
            {"_id": ObjectId(egreso_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el egreso"}), 404

        return jsonify({"mensaje": "Egreso actualizado correctamente"}), 200

    except Exception as e:
        return jsonify({"error": "Error al actualizar el egreso", "detalle": str(e)}), 400


def eliminar_egreso_neonatal(usuario_actual, egreso_id):
    try:
        resultado = mongo.db.egreso_neonatal.delete_one({"_id": ObjectId(egreso_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el egreso"}), 404

        return jsonify({"mensaje": "Egreso eliminado correctamente"}), 200

    except Exception as e:
        return jsonify({"error": "Error al eliminar el egreso", "detalle": str(e)}), 400
