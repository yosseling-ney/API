def serializar_usuario(usuario):
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "apellido": usuario["apellido"],
        "correo": usuario["correo"],
        "telefono": usuario.get("telefono"),
        "username": usuario["username"],
        "rol": usuario["rol"]
    }
