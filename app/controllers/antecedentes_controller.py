from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo

# Crear antecedentes
def crear_antecedentes(usuario_actual):
    try:
        data = request.get_json()

        campos_obligatorios = [
            'identificacion_id', 'antecedentes_familiares', 'antecedentes_personales', 'diabetes_tipo',
            'violencia', 'gesta_previa', 'partos', 'cesareas', 'abortos', 'nacidos_vivos',
            'nacidos_muertos', 'embarazo_ectopico', 'hijos_vivos', 'muertos_primera_semana',
            'muertos_despues_semana', 'fecha_fin_ultimo_embarazo',
            'embarazo_planeado', 'fracaso_metodo_anticonceptivo'
        ]

        for campo in campos_obligatorios:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        fecha_fin = datetime.strptime(data['fecha_fin_ultimo_embarazo'], "%Y-%m-%d")

        documento = {
            "identificacion_id": ObjectId(data['identificacion_id']),
            "usuario_id": ObjectId(usuario_actual['usuario_id']),
            "antecedentes_familiares": data['antecedentes_familiares'],
            "antecedentes_personales": data['antecedentes_personales'],
            "diabetes_tipo": data['diabetes_tipo'],
            "violencia": bool(data['violencia']),
            "gesta_previa": int(data['gesta_previa']),
            "partos": int(data['partos']),
            "cesareas": int(data['cesareas']),
            "abortos": int(data['abortos']),
            "nacidos_vivos": int(data['nacidos_vivos']),
            "nacidos_muertos": int(data['nacidos_muertos']),
            "embarazo_ectopico": int(data['embarazo_ectopico']),
            "hijos_vivos": int(data['hijos_vivos']),
            "muertos_primera_semana": int(data['muertos_primera_semana']),
            "muertos_despues_semana": bool(data['muertos_despues_semana']),
            "fecha_fin_ultimo_embarazo": fecha_fin,
            "embarazo_planeado": bool(data['embarazo_planeado']),
            "fracaso_metodo_anticonceptivo": bool(data['fracaso_metodo_anticonceptivo'])
        }

        resultado = mongo.db.antecedentes.insert_one(documento)
        return jsonify({"mensaje": "Antecedentes guardados", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al guardar", "detalle": str(e)}), 400


# Obtener antecedentes por identificacion_id
def obtener_antecedentes_por_paciente(identificacion_id):
    try:
        doc = mongo.db.antecedentes.find_one({"identificacion_id": ObjectId(identificacion_id)})
        if not doc:
            return jsonify({"mensaje": "No se encontraron antecedentes"}), 404

        doc['_id'] = str(doc['_id'])
        doc['identificacion_id'] = str(doc['identificacion_id'])
        doc['usuario_id'] = str(doc['usuario_id'])
        doc['fecha_fin_ultimo_embarazo'] = doc['fecha_fin_ultimo_embarazo'].strftime("%Y-%m-%d")

        return jsonify(doc), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener", "detalle": str(e)}), 400


# Actualizar antecedentes por identificacion_id
def actualizar_antecedentes(identificacion_id):
    try:
        data = request.get_json()

        if 'fecha_fin_ultimo_embarazo' in data:
            data['fecha_fin_ultimo_embarazo'] = datetime.strptime(data['fecha_fin_ultimo_embarazo'], "%Y-%m-%d")

        mongo.db.antecedentes.update_one(
            {"identificacion_id": ObjectId(identificacion_id)},
            {"$set": data}
        )

        return jsonify({"mensaje": "Antecedentes actualizados"}), 200

    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400


# Eliminar antecedentes por identificacion_id
def eliminar_antecedentes(identificacion_id):
    try:
        resultado = mongo.db.antecedentes.delete_one({"identificacion_id": ObjectId(identificacion_id)})
        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "Antecedentes no encontrados"}), 404
        return jsonify({"mensaje": "Antecedentes eliminados"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
