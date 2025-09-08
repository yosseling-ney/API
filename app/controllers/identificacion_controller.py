from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

# Crear segmento identificación
def crear_identificacion(usuario_actual):
    try:
        data = request.get_json()

        campos = [
            'identificacion_prenatal_id', 'nombres', 'apellidos', 'cedula',
            'fecha_nacimiento', 'edad', 'etnia', 'alfabeta', 'nivel_estudios',
            'anio_estudios', 'estado_civil', 'vive_sola', 'domicilio',
            'telefono', 'localidad', 'establecimiento_salud', 'lugar_parto'
        ]
        for campo in campos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        fecha = datetime.strptime(data['fecha_nacimiento'], "%Y-%m-%d")

        segmento = {
            "identificacion_prenatal_id": ObjectId(data['identificacion_prenatal_id']),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            "nombres": data['nombres'],
            "apellidos": data['apellidos'],
            "cedula": data['cedula'],
            "fecha_nacimiento": fecha,
            "edad": int(data['edad']),
            "etnia": data['etnia'],
            "alfabeta": bool(data['alfabeta']),
            "nivel_estudios": data['nivel_estudios'],
            "anio_estudios": int(data['anio_estudios']),
            "estado_civil": data['estado_civil'],
            "vive_sola": bool(data['vive_sola']),
            "domicilio": data['domicilio'],
            "telefono": data['telefono'],
            "localidad": data['localidad'],
            "establecimiento_salud": data['establecimiento_salud'],
            "lugar_parto": data['lugar_parto']
        }

        resultado = mongo.db.identificacion.insert_one(segmento)
        return jsonify({"mensaje": "Segmento guardado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al guardar", "detalle": str(e)}), 400


# Obtener segmento por ID de identificación prenatal
def obtener_identificacion_por_prenatal(id_prenatal):
    try:
        doc = mongo.db.identificacion.find_one({"identificacion_prenatal_id": ObjectId(id_prenatal)})
        if not doc:
            return jsonify({"mensaje": "No se encontró el segmento"}), 404

        doc['_id'] = str(doc['_id'])
        doc['usuario_id'] = str(doc['usuario_id'])
        doc['identificacion_prenatal_id'] = str(doc['identificacion_prenatal_id'])
        doc['fecha_nacimiento'] = doc['fecha_nacimiento'].strftime('%Y-%m-%d')
        return jsonify(doc), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener segmento", "detalle": str(e)}), 400


# Actualizar segmento
def actualizar_identificacion(id_prenatal):
    try:
        data = request.get_json()
        if 'fecha_nacimiento' in data:
            data['fecha_nacimiento'] = datetime.strptime(data['fecha_nacimiento'], "%Y-%m-%d")

        mongo.db.identificacion.update_one(
            {"identificacion_prenatal_id": ObjectId(id_prenatal)},
            {"$set": data}
        )
        return jsonify({"mensaje": "Segmento actualizado"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


# Eliminar segmento
def eliminar_identificacion(id_prenatal):
    try:
        resultado = mongo.db.identificacion.delete_one({"identificacion_prenatal_id": ObjectId(id_prenatal)})
        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "Segmento no encontrado"}), 404
        return jsonify({"mensaje": "Segmento eliminado"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
