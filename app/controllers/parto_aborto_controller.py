from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

def crear_parto_aborto(usuario_actual):
    try:
        data = request.get_json()

        campos_requeridos = [
            "identificacion_id", "tipo_evento", "fecha_ingreso", "carne_perinatal",
            "consultas_prenatales", "lugar_parto", "hospitalizacion_embarazo", "corticoides_antenatales",
            "inicio_parto", "ruptura_membrana", "edad_gestacional_parto", "presentacion",
            "tamano_fetal_acorde", "acompanante", "acompanamiento_solicitado_usuaria",
            "nacimiento", "fecha_hora_nacimiento", "nacimiento_multiple", "orden_nacimiento",
            "terminacion_parto", "posicion_parto", "episiotomia", "desgarros",
            "oxitocicos_pre", "oxitocicos_post", "placenta_expulsada", "ligadura_cordon",
            "medicacion_recibida", 
            "indicacion_principal_induccion_operacion",
            "induccion", "operacion", "partograma_usado"
        ]

        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        if not data["partograma_usado"]:
            if "partograma_detalle" not in data:
                return jsonify({"error": "Campo requerido: partograma_detalle"}), 400

        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "tipo_evento": data["tipo_evento"],
            "fecha_ingreso": datetime.strptime(data["fecha_ingreso"], "%Y-%m-%d"),
            "carne_perinatal": data["carne_perinatal"],
            "consultas_prenatales": int(data["consultas_prenatales"]),
            "lugar_parto": data["lugar_parto"],
            "hospitalizacion_embarazo": data["hospitalizacion_embarazo"],
            "corticoides_antenatales": data["corticoides_antenatales"],
            "inicio_parto": data["inicio_parto"],
            "ruptura_membrana": data["ruptura_membrana"],
            "edad_gestacional_parto": data["edad_gestacional_parto"],
            "presentacion": data["presentacion"],
            "tamano_fetal_acorde": data["tamano_fetal_acorde"],
            "acompanante": data["acompanante"],
            "acompanamiento_solicitado_usuaria": data["acompanamiento_solicitado_usuaria"],
            "nacimiento": data["nacimiento"],
            "fecha_hora_nacimiento": datetime.strptime(data["fecha_hora_nacimiento"], "%Y-%m-%dT%H:%M"),
            "nacimiento_multiple": data["nacimiento_multiple"],
            "orden_nacimiento": int(data["orden_nacimiento"]),
            "terminacion_parto": data["terminacion_parto"],
            "posicion_parto": data["posicion_parto"],
            "episiotomia": data["episiotomia"],
            "desgarros": data["desgarros"],
            "oxitocicos_pre": data["oxitocicos_pre"],
            "oxitocicos_post": data["oxitocicos_post"],
            "placenta_expulsada": data["placenta_expulsada"],
            "ligadura_cordon": data["ligadura_cordon"],
            "medicacion_recibida": data["medicacion_recibida"],
            "indicacion_principal_induccion_operacion": data["indicacion_principal_induccion_operacion"],
            "induccion": data["induccion"],
            "operacion": data["operacion"],
            "partograma_usado": data["partograma_usado"]
        }

        if not data["partograma_usado"]:
            documento["partograma_detalle"] = data["partograma_detalle"]

        resultado = mongo.db.parto_aborto.insert_one(documento)
        return jsonify({"mensaje": "Segmento registrado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al registrar", "detalle": str(e)}), 400


def obtener_parto_aborto(usuario_actual, identificacion_id):
    try:
        datos = mongo.db.parto_aborto.find_one({"identificacion_id": ObjectId(identificacion_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])
        datos["fecha_ingreso"] = datos["fecha_ingreso"].strftime("%Y-%m-%d")
        datos["fecha_hora_nacimiento"] = datos["fecha_hora_nacimiento"].strftime("%Y-%m-%dT%H:%M")

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener los datos", "detalle": str(e)}), 400


def actualizar_parto_aborto(usuario_actual, identificacion_id):
    try:
        data = request.get_json()

        if "fecha_ingreso" in data:
            data["fecha_ingreso"] = datetime.strptime(data["fecha_ingreso"], "%Y-%m-%d")
        if "fecha_hora_nacimiento" in data:
            data["fecha_hora_nacimiento"] = datetime.strptime(data["fecha_hora_nacimiento"], "%Y-%m-%dT%H:%M")
        if "orden_nacimiento" in data:
            data["orden_nacimiento"] = int(data["orden_nacimiento"])
        if "consultas_prenatales" in data:
            data["consultas_prenatales"] = int(data["consultas_prenatales"])

        resultado = mongo.db.parto_aborto.update_one(
            {"identificacion_id": ObjectId(identificacion_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


def eliminar_parto_aborto(usuario_actual, identificacion_id):
    try:
        resultado = mongo.db.parto_aborto.delete_one({"identificacion_id": ObjectId(identificacion_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el documento"}), 404

        return jsonify({"mensaje": "Segmento eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
