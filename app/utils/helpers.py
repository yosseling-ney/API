from werkzeug.security import generate_password_hash, check_password_hash

def encriptar_password(password):
    return generate_password_hash(password)

def verificar_password(password_plano, password_encriptado):
    return check_password_hash(password_encriptado, password_plano)
