from flask import request, jsonify
from app import mongo
import re
from bson import ObjectId
from bson.errors import InvalidId

def crear_identificacion_prenatal():
    try:
        data = request.get_json()

        # 1. Limpieza y validación básica
        required_fields = {
            'tipo_identificacion': str,
            'numero_identificacion': str,
            'gesta_actual': int,
            'formulario': str
        }
        
        # Verificar campos requeridos
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"error": f"Campos faltantes: {', '.join(missing_fields)}"}), 400

        # Limpiar espacios y convertir tipos
        cleaned_data = {}
        for field, field_type in required_fields.items():
            value = data[field]
            if field_type == str:
                cleaned_data[field] = value.strip() if value else value
            elif field_type == int:
                try:
                    cleaned_data[field] = int(value)
                except (ValueError, TypeError):
                    return jsonify({"error": f"{field} debe ser un número entero"}), 400

        # 2. Validación específica
        # Tipo identificación
        tipos_validos = ['CI', 'PSP', 'NSS', 'LC']
        if cleaned_data['tipo_identificacion'] not in tipos_validos:
            return jsonify({"error": f"tipo_identificacion debe ser uno de: {', '.join(tipos_validos)}"}), 400

        # Gesta actual
        if cleaned_data['gesta_actual'] < 1:
            return jsonify({"error": "gesta_actual debe ser ≥ 1"}), 400

        # Formulario
        if cleaned_data['formulario'] != "Historia clínica prenatal":
            return jsonify({"error": "formulario debe ser 'Historia clínica prenatal'"}), 400

        # 3. Validación de patrones
        tipo = cleaned_data['tipo_identificacion']
        numero = cleaned_data['numero_identificacion']
        
        patrones = {
            'CI': r'^\d{3}-\d{6}-\d{4}[A-Z]{1}$',
            'PSP': r'^[A-Z]{3}\d{6}$',
            'NSS': r'^[A-Z0-9]{10,15}$',
            'LC': r'^\d{8}[A-Z]$'
        }
        
        if not re.fullmatch(patrones[tipo], numero):
            return jsonify({
                "error": f"Formato inválido para {tipo}",
                "detalle": f"El formato debe ser: {patrones[tipo]}",
                "ejemplo_valido": {
                    'CI': '281-090403-1006K',
                    'PSP': 'ABC123456',
                    'NSS': 'A1B2C3D4E5',
                    'LC': '12345678A'
                }
            }), 400

        # 4. Construir documento final
        documento = {
            "tipo_identificacion": cleaned_data['tipo_identificacion'],
            "numero_identificacion": cleaned_data['numero_identificacion'],
            "gesta_actual": cleaned_data['gesta_actual'],
            "formulario": cleaned_data['formulario']
        }

        # Verificar duplicados
        existente = mongo.db.identificaciones_prenatales.find_one({
            'tipo_identificacion': documento['tipo_identificacion'],
            'numero_identificacion': documento['numero_identificacion']
        })
        
        if existente:
            return jsonify({
                "error": "Ya existe una identificación con estos datos",
                "id_existente": str(existente['_id'])
            }), 409

        # 5. Insertar en MongoDB
        resultado = mongo.db.identificaciones_prenatales.insert_one(documento)

        return jsonify({
            "mensaje": "Documento creado exitosamente",
            "id": str(resultado.inserted_id),
            "datos": documento
        }), 201

    except Exception as e:
        return jsonify({
            "error": "Error al guardar la identificación",
            "detalle": str(e),
            "sugerencia": "Verifique: 1) Nombre exacto de campos, 2) Formatos específicos, 3) Sin campos adicionales"
        }), 500

def obtener_identificacion_prenatal(id):
    try:
        # Validar formato del ID
        if not ObjectId.is_valid(id):
            return jsonify({"error": "ID inválido"}), 400

        # Buscar en la base de datos
        documento = mongo.db.identificaciones_prenatales.find_one({"_id": ObjectId(id)})
        
        if not documento:
            return jsonify({"error": "Identificación no encontrada"}), 404

        # Convertir ObjectId a string para la respuesta JSON
        documento['_id'] = str(documento['_id'])
        
        return jsonify(documento), 200

    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400
    except Exception as e:
        return jsonify({
            "error": "Error al obtener la identificación",
            "detalle": str(e)
        }), 500

def obtener_todas_identificaciones():
    try:
        # Obtener todos los documentos
        documentos = list(mongo.db.identificaciones_prenatales.find())
        
        # Convertir ObjectId a string para cada documento
        for doc in documentos:
            doc['_id'] = str(doc['_id'])
        
        return jsonify(documentos), 200

    except Exception as e:
        return jsonify({
            "error": "Error al obtener las identificaciones",
            "detalle": str(e)
        }), 500

def eliminar_identificacion_prenatal(id):
    try:
        # Validar formato del ID
        if not ObjectId.is_valid(id):
            return jsonify({"error": "ID inválido"}), 400

        # Verificar si existe el documento
        documento = mongo.db.identificaciones_prenatales.find_one({"_id": ObjectId(id)})
        
        if not documento:
            return jsonify({"error": "Identificación no encontrada"}), 404

        # Eliminar el documento
        resultado = mongo.db.identificaciones_prenatales.delete_one({"_id": ObjectId(id)})
        
        if resultado.deleted_count == 1:
            return jsonify({
                "mensaje": "Identificación eliminada exitosamente",
                "id": id
            }), 200
        else:
            return jsonify({
                "error": "No se pudo eliminar la identificación",
                "detalle": "El documento no fue eliminado"
            }), 500

    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400
    except Exception as e:
        return jsonify({
            "error": "Error al eliminar la identificación",
            "detalle": str(e)
        }), 500