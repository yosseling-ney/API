from flask import request, jsonify
from bson import ObjectId
from datetime import datetime
from app import mongo
from decimal import Decimal

def crear_gestacion_actual(usuario_actual):
    try:
        data = request.get_json()

        # Campos requeridos
        campos_requeridos = [
            "identificacion_id", "peso_anterior", "talla", "fum", "fpp", "eg_confiable",
            "fumadora_activa", "fumadora_pasiva", "drogas", "alcohol", "violencia",
            "vacuna_rubeola", "vacuna_antitetanica", "examen_mamas", "examen_odonto",
            "cervix_normal", "grupo_sanguineo", "rh", "inmunizada", "gammaglobulina",
            "toxoplasmosis_igg", "toxoplasmosis_igm", "hierro_acido_folico", "hemoglobina",
            "vih_solicitado", "vih_resultado", "tratamiento_vih", "sifilis",
            "sifilis_tratamiento", "pareja_tratada", "chagas", "malaria", "bacteriuria",
            "glucemia1", "glucemia2", "estreptococo", "plan_parto", "consejeria_lactancia"
        ]

        # Verificar campos requeridos
        for campo in campos_requeridos:
            if campo not in data:
                return jsonify({"error": f"Campo requerido: {campo}"}), 400

        # Preparar documento para MongoDB
        documento = {
            "identificacion_id": ObjectId(data["identificacion_id"]),
            "usuario_id": ObjectId(usuario_actual["usuario_id"]),
            # Convertir Decimal a float para MongoDB
            "peso_anterior": float(Decimal(data["peso_anterior"])),
            "talla": float(Decimal(data["talla"])),
            # Convertir fechas de string a datetime
            "fum": datetime.strptime(data["fum"], "%d/%m/%Y"),
            "fpp": datetime.strptime(data["fpp"], "%d/%m/%Y"),
            # Resto de campos
            "eg_confiable": data["eg_confiable"],
            "fumadora_activa": data["fumadora_activa"],
            "fumadora_pasiva": data["fumadora_pasiva"],
            "drogas": data["drogas"],
            "alcohol": data["alcohol"],
            "violencia": data["violencia"],
            "vacuna_rubeola": data["vacuna_rubeola"],
            "vacuna_antitetanica": data["vacuna_antitetanica"],
            "examen_mamas": data["examen_mamas"],
            "examen_odonto": data["examen_odonto"],
            "cervix_normal": data["cervix_normal"],
            "grupo_sanguineo": data["grupo_sanguineo"],
            "rh": data["rh"],
            "inmunizada": data["inmunizada"],
            "gammaglobulina": data["gammaglobulina"],
            "toxoplasmosis_igg": data["toxoplasmosis_igg"],
            "toxoplasmosis_igm": data["toxoplasmosis_igm"],
            "hierro_acido_folico": data["hierro_acido_folico"],
            "hemoglobina": float(Decimal(data["hemoglobina"])),
            "vih_solicitado": data["vih_solicitado"],
            "vih_resultado": data["vih_resultado"],
            "tratamiento_vih": data["tratamiento_vih"],
            "sifilis": data["sifilis"],
            "sifilis_tratamiento": data["sifilis_tratamiento"],
            "pareja_tratada": data["pareja_tratada"],
            "chagas": data["chagas"],
            "malaria": data["malaria"],
            "bacteriuria": data["bacteriuria"],
            "glucemia1": float(Decimal(data["glucemia1"])),
            "glucemia2": float(Decimal(data["glucemia2"])),
            "estreptococo": data["estreptococo"],
            "plan_parto": data["plan_parto"],
            "consejeria_lactancia": data["consejeria_lactancia"]
        }

        # Insertar en MongoDB
        resultado = mongo.db.gestacion_actual.insert_one(documento)
        return jsonify({"mensaje": "Segmento guardado", "id": str(resultado.inserted_id)}), 201

    except Exception as e:
        return jsonify({"error": "Error al guardar", "detalle": str(e)}), 400

# Obtener segmento por identificacion_id
def obtener_gestacion_actual(usuario_actual, identificacion_id):
    try:
        # Buscar en MongoDB
        datos = mongo.db.gestacion_actual.find_one({"identificacion_id": ObjectId(identificacion_id)})

        if not datos:
            return jsonify({"mensaje": "No se encontraron datos"}), 404

        # Convertir ObjectId a strings y formatear fechas
        datos["_id"] = str(datos["_id"])
        datos["identificacion_id"] = str(datos["identificacion_id"])
        datos["usuario_id"] = str(datos["usuario_id"])
        datos["fum"] = datos["fum"].strftime("%d/%m/%Y")
        datos["fpp"] = datos["fpp"].strftime("%d/%m/%Y")

        # Nota: Los valores numéricos ya están como float (no necesitan conversión)

        return jsonify(datos), 200
    except Exception as e:
        return jsonify({"error": "Error al obtener", "detalle": str(e)}), 400

# Actualizar segmento por identificacion_id
def actualizar_gestacion_actual(usuario_actual, identificacion_id):
    try:
        data = request.get_json()

        # Convertir campos según sea necesario
        if "fum" in data:
            data["fum"] = datetime.strptime(data["fum"], "%d/%m/%Y")
        if "fpp" in data:
            data["fpp"] = datetime.strptime(data["fpp"], "%d/%m/%Y")
        if "peso_anterior" in data:
            data["peso_anterior"] = float(Decimal(data["peso_anterior"]))
        if "talla" in data:
            data["talla"] = float(Decimal(data["talla"]))
        if "hemoglobina" in data:
            data["hemoglobina"] = float(Decimal(data["hemoglobina"]))
        if "glucemia1" in data:
            data["glucemia1"] = float(Decimal(data["glucemia1"]))
        if "glucemia2" in data:
            data["glucemia2"] = float(Decimal(data["glucemia2"]))

        # Actualizar en MongoDB
        resultado = mongo.db.gestacion_actual.update_one(
            {"identificacion_id": ObjectId(identificacion_id)},
            {"$set": data}
        )

        if resultado.matched_count == 0:
            return jsonify({"mensaje": "No se encontró el documento para actualizar"}), 404

        return jsonify({"mensaje": "Segmento actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al actualizar", "detalle": str(e)}), 400

# Eliminar segmento por identificacion_id
def eliminar_gestacion_actual(usuario_actual, identificacion_id):
    try:
        resultado = mongo.db.gestacion_actual.delete_one({"identificacion_id": ObjectId(identificacion_id)})

        if resultado.deleted_count == 0:
            return jsonify({"mensaje": "No se encontró el documento a eliminar"}), 404

        return jsonify({"mensaje": "Segmento eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": "Error al eliminar", "detalle": str(e)}), 400
