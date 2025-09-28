
def crear_paciente(body):
    return {"message": "Paciente creado exitosamente", "data": body}, 200


def obtener_paciente(paciente_id):
    paciente_response = dict()
    paciente_response = mongo.db.pacientes.find_one({"_id": ObjectId(paciente_id)})

    antencedentes_response = dict()
    antencedentes_response = service_antencedentes.get_antencedentes_by_id_paciente(paciente_id)

    paciente_response['antencedentes'] = antencedentes_response


    return paciente_response