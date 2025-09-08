from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

def crear_egreso_materno(usuario_actual):
    try:
        data = request.get_json()

        # Validar campos obligatorios principales
        campos_requeridos = [
            "identificacion_id", "antirrubeola_post_parto", "gamma_globulina_antiD",
            "egreso_materno", "dias_completos_desde_parto", "responsable"
        ]
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        egreso_materno = data["egreso_materno"]

        # Validar campos requeridos dentro de egreso_materno
        if "estado" not in egreso_materno or "fecha" not in egreso_materno:
            return jsonify({"error": "Campos 'estado' y 'fecha' son requeridos en egreso_materno"}), 400

        # Validar formato de fecha dd/mm/yyyy
        try:
            egreso_materno["fecha"] = datetime.strptime(egreso_materno["fecha"], "%d/%m/%Y")
        except ValueError:
            return jsonify({"error": "La fecha debe tener formato DD/MM/YYYY"}), 400

        # Validaciones condicionales
        if egreso_materno.get("traslado", False):
            if "lugar_traslado" not in egreso_materno or not egreso_materno["lugar_traslado"].strip():
                return jsonify({"error": "Si 'traslado' es true, 'lugar_traslado' es obligatorio"}), 400

        if egreso_materno["estado"] == "fallece":
            if "edad_en_dias_fallecimiento" not in egreso_materno:
                return jsonify({"error": "Debe indicar 'edad_en_dias_fallecimiento' si estado es 'fallece'"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "antirrubeola_post_parto": data["antirrubeola_post_parto"],
            "gamma_globulina_antiD": data["gamma_globulina_antiD"],
            "egreso_materno": egreso_materno,
            "dias_completos_desde_parto": int(data["dias_completos_desde_parto"]),
            "responsable": data["responsable"]
        }

        resultado = mongo.db.egreso_materno.insert_one(documento)
        return jsonify({"mensaje": "Segmento egreso materno registrado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar egreso materno", "detalle": str(e)}), 400


def obtener_egreso_materno(usuario_actual, egreso_id):
    try:
        datos = mongo.db.egreso_materno.find_one({"_id": ObjectId(egreso_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        # Convertir ObjectId a string
        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])

        # Convertir fecha a dd/mm/yyyy
        if "egreso_materno" in datos and "fecha" in datos["egreso_materno"]:
            if isinstance(datos["egreso_materno"]["fecha"], datetime):
                datos["egreso_materno"]["fecha"] = datos["egreso_materno"]["fecha"].strftime("%d/%m/%Y")

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener datos", "detalle": str(e)}), 400


def actualizar_egreso_materno(usuario_actual, egreso_id):
    try:
        data = request.get_json()

        if "identificacion_id" in data:
            data["identificacion_id"] = ObjectId(data["identificacion_id"])

        if "egreso_materno" in data and "fecha" in data["egreso_materno"]:
            try:
                data["egreso_materno"]["fecha"] = datetime.strptime(data["egreso_materno"]["fecha"], "%d/%m/%Y")
            except ValueError:
                return jsonify({"error": "La fecha debe tener formato DD/MM/YYYY"}), 400

        resultado = mongo.db.egreso_materno.update_one(
            {"_id": ObjectId(egreso_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento egreso materno actualizado"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


def eliminar_egreso_materno(usuario_actual, egreso_id):
    try:
        resultado = mongo.db.egreso_materno.delete_one({"_id": ObjectId(egreso_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento egreso materno eliminado"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
