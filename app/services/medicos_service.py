import re
from bson import ObjectId

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[0-9()+\-\s]{7,20}$")
FOLIO_RE = re.compile(r"^MED-\d{4,}$")

ESPECIALIDADES_VALIDAS = [
    "Ginecología y Obstetricia",
    "Medicina Materno-Fetal",
    "Medicina Interna",
    "Endocrinología",
    "Cardiología",
    "Hematología",
    "Neonatología",
    "Anestesiología y Reanimación",
    "Psicología Perinatal",
    "Nutrición Materna y Perinatal",
]

SEXOS_VALIDOS = ["femenino", "masculino", "otro", "no_especificado"]


def _coerce_str(value, *, max_len=None, allow_none=True):
    if value is None:
        return None if allow_none else ""
    s = str(value).strip()
    if max_len:
        s = s[:max_len]
    return s


def _coerce_oid(value, *, allow_none=True):
    if value is None:
        return None if allow_none else None
    if isinstance(value, ObjectId):
        return value
    if ObjectId.is_valid(str(value)):
        return ObjectId(str(value))
    return None if allow_none else None


def validar_payload_medico(payload: dict, modo: str = "crear"):
    errors, cleaned = {}, {}

    # Requeridos en crear (folio se puede generar si no viene)
    if modo == "crear":
        for campo in ["nombre_completo", "cedula", "especialidad", "sexo", "fecha_nacimiento"]:
            if not payload.get(campo):
                errors[campo] = f"El campo '{campo}' es obligatorio"

    # folio (opcional en crear si lo vamos a autogenerar en el controller)
    if "folio" in payload and payload.get("folio"):
        folio = _coerce_str(payload.get("folio"), max_len=40, allow_none=False).upper()
        if not FOLIO_RE.match(folio):
            errors["folio"] = "El folio debe tener formato MED-0001"
        else:
            cleaned["folio"] = folio

    # nombre
    if "nombre_completo" in payload:
        nombre = _coerce_str(payload.get("nombre_completo"), max_len=120, allow_none=False)
        if len(nombre) < 3:
            errors["nombre_completo"] = "Debe tener al menos 3 caracteres"
        else:
            cleaned["nombre_completo"] = nombre

    # cédula
    if "cedula" in payload:
        cedula = _coerce_str(payload.get("cedula"), max_len=40, allow_none=False)
        if len(cedula) < 3:
            errors["cedula"] = "Debe tener al menos 3 caracteres"
        else:
            cleaned["cedula"] = cedula

    # especialidad
    if "especialidad" in payload:
        especialidad = payload.get("especialidad")
        if especialidad not in ESPECIALIDADES_VALIDAS:
            errors["especialidad"] = "Especialidad no válida"
        else:
            cleaned["especialidad"] = especialidad

    # subespecialidad
    if "subespecialidad" in payload:
        cleaned["subespecialidad"] = _coerce_str(payload.get("subespecialidad"), max_len=80)

    # sexo
    if "sexo" in payload:
        sexo = payload.get("sexo")
        if sexo not in SEXOS_VALIDOS:
            errors["sexo"] = "Sexo inválido"
        else:
            cleaned["sexo"] = sexo

    # fecha_nacimiento
    if "fecha_nacimiento" in payload:
        fn = payload.get("fecha_nacimiento")
        if not isinstance(fn, str):
            cleaned["fecha_nacimiento"] = fn  # ya es datetime si llega así
        else:
            from datetime import datetime
            try:
                cleaned["fecha_nacimiento"] = datetime.fromisoformat(fn)
            except Exception:
                errors["fecha_nacimiento"] = "Formato de fecha inválido (usa ISO 8601, ej. 1990-05-23)"

    # correo
    if "correo" in payload:
        correo = _coerce_str(payload.get("correo"), max_len=120)
        if correo and not EMAIL_RE.match(correo):
            errors["correo"] = "Formato de correo inválido"
        cleaned["correo"] = correo or None

    # telefono
    if "telefono" in payload:
        tel = _coerce_str(payload.get("telefono"), max_len=20)
        if tel and not PHONE_RE.match(tel):
            errors["telefono"] = "Formato de teléfono inválido"
        cleaned["telefono"] = tel or None

    # usuario_id
    if "usuario_id" in payload:
        cleaned["usuario_id"] = _coerce_oid(payload.get("usuario_id"))

    # estado
    if "estado" in payload:
        est = payload.get("estado")
        if est not in ("activo", "inactivo"):
            errors["estado"] = "Debe ser 'activo' o 'inactivo'"
        else:
            cleaned["estado"] = est
    elif modo == "crear":
        cleaned["estado"] = "activo"

    # observaciones
    if "observaciones" in payload:
        cleaned["observaciones"] = _coerce_str(payload.get("observaciones"), max_len=500)

    ok = len(errors) == 0
    return ok, errors, cleaned


def serializar_medico(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "_id": str(doc.get("_id")),
        "folio": doc.get("folio"),
        "nombre_completo": doc.get("nombre_completo"),
        "cedula": doc.get("cedula"),
        "especialidad": doc.get("especialidad"),
        "subespecialidad": doc.get("subespecialidad"),
        "sexo": doc.get("sexo"),
        "fecha_nacimiento": doc.get("fecha_nacimiento").isoformat() if doc.get("fecha_nacimiento") else None,
        "telefono": doc.get("telefono"),
        "correo": doc.get("correo"),
        "usuario_id": str(doc.get("usuario_id")) if doc.get("usuario_id") else None,
        "estado": doc.get("estado"),
        "observaciones": doc.get("observaciones"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        "created_by": str(doc.get("created_by")) if doc.get("created_by") else None,
        "updated_by": str(doc.get("updated_by")) if doc.get("updated_by") else None,
    }
