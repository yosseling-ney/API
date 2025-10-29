from datetime import datetime
import re
from bson import ObjectId
from flask import current_app
from app import mongo

# (opcional) importación del servicio de historiales para agregados
try:
    from app.services import service_historial as svc_his
except Exception:
    svc_his = None

# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code

# ---------------- Reglas / patrones ----------------
_TIPOS_IDENTIFICACION = {"CI", "PSP", "NSS", "LC"}
_RE_IDENTIFICACION_POR_TIPO = {
    "CI": re.compile(r"^\d{3}-\d{6}-\d{4}[A-Z]{1}$"),
    "PSP": re.compile(r"^[A-Z][0-9]{8}$"),
    "NSS": re.compile(r"^[0-9]{8}$"),
    "LC": re.compile(r"^[A-Z][0-9]{7}$"),
}
_RE_EXPED  = re.compile(r"^\d{3}[A-Z9]{4}[MF]\d{6}\d{2}$")
_RE_TEL    = re.compile(r"^[0-9\+\-\s]{8,15}$")
_ARTICULOS = {"DE", "DEL", "LA", "LOS", "LAS", "DA", "DO", "DOS", "DAS"}

# ---------------- Utils ----------------
def _to_oid(v, field):
    try:
        return ObjectId(v)
    except Exception:
        raise ValueError(f"{field} no es un ObjectId válido")

def _parse_date_ymd(s, field):
    if isinstance(s, datetime):
        return s
    if not isinstance(s, str):
        raise ValueError(f"{field} debe ser string (YYYY-MM-DD)")
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d")
    except Exception:
        raise ValueError(f"{field} debe tener formato YYYY-MM-DD")

def _norm_upper(s):
    return s.strip().upper() if isinstance(s, str) else s

def _ensure_indexes():
    try:
        mongo.db.paciente.create_index(
            [("tipo_identificacion", 1), ("numero_identificacion", 1)],
            unique=True,
            name="uq_tipo_num_identificacion",
            partialFilterExpression={"deleted_at": None},
        )
    except Exception:
        pass
    try:
        mongo.db.paciente.create_index(
            "codigo_expediente",
            unique=True,
            name="uq_codigo_expediente",
            partialFilterExpression={"deleted_at": None},
        )
    except Exception:
        pass
    try:
        mongo.db.paciente.create_index("historial_id", name="ix_historial_id")  # no-único, opcional
    except Exception:
        pass


def _validar_tipo_identificacion(tipo):
    if not isinstance(tipo, str):
        raise ValueError("tipo_identificacion es requerido")
    tipo_limpio = tipo.strip().upper()
    if tipo_limpio not in _TIPOS_IDENTIFICACION:
        raise ValueError("tipo_identificacion inválido")
    return tipo_limpio


def _validar_numero_identificacion(tipo: str, numero: str):
    """
    Normaliza y valida el número de identificación según el tipo.
    - Reemplaza guiones raros (– — −) por "-", quita espacios y convierte a MAYÚSCULAS.
    - Para CI:
        * Si ya está en canónico ###-######-####A y es válido, lo devuelve.
        * Si viene compacto, elimina separadores y valida (\d{3})(\d{6})(\d{4})([A-Z]);
          si es válido, devuelve canónico 000-000000-0000X.
        * Si no, 422 (ValueError).
    - Para PSP/NSS/LC:
        * Elimina todo lo no alfanumérico y valida contra su regex (sin separadores).
        * Devuelve el valor limpio (sin separadores).
    """
    if tipo not in _TIPOS_IDENTIFICACION:
        raise ValueError("tipo_identificacion inválido")
    if not isinstance(numero, str):
        raise ValueError("numero_identificacion debe ser string")

    # Normalización básica (espacios extremos, mayúsculas, guiones raros -> "-")
    numero_limpio = (numero.strip()
                           .upper()
                           .replace("–", "-")
                           .replace("—", "-")
                           .replace("−", "-"))

    if tipo == "CI":
        # 1) Si ya está en canónico, validar y devolver igual
        if _RE_IDENTIFICACION_POR_TIPO["CI"].fullmatch(numero_limpio):
            return numero_limpio

        # 2) Quitar todo lo no alfanumérico y validar compacto
        solo = re.sub(r"[^0-9A-Z]", "", numero_limpio)
        m = re.fullmatch(r"(\d{3})(\d{6})(\d{4})([A-Z])", solo)
        if m:
            return f"{m[1]}-{m[2]}-{m[3]}{m[4]}"

        # 3) No pasó ninguna forma válida
        raise ValueError("numero_identificacion inválido para tipo CI")

    # Para otros tipos (PSP, NSS, LC): quitar todo lo no alfanumérico y validar sin separadores
    normal = re.sub(r"[^0-9A-Z]", "", numero_limpio)

    patron = _RE_IDENTIFICACION_POR_TIPO.get(tipo)
    if not patron or not patron.fullmatch(normal):
        raise ValueError(f"numero_identificacion inválido para tipo {tipo}")

    return normal


def _validar_telefono(t):
    if not isinstance(t, str):
        raise ValueError("telefono debe ser string")
    t = t.strip()
    if not _RE_TEL.match(t):
        raise ValueError("telefono inválido (8–15 caracteres, solo dígitos, +, -, espacio)")
    return t

def _validar_min_nonempty(s, field):
    if not isinstance(s, str) or not s.strip():
        raise ValueError(f"{field} es requerido")
    return s.strip()

def _validar_gesta_actual(g):
    try:
        gi = int(g)
        if gi < 1:
            raise ValueError
        return gi
    except Exception:
        raise ValueError("gesta_actual debe ser entero >= 1")

def _ddmmaa(dt: datetime) -> str:
    return dt.strftime("%d%m%y")

def _tomar_inicial(palabra: str) -> str:
    if not palabra:
        return "9"
    p = _norm_upper(palabra)
    return p[0] if p and p[0].isalpha() else "9"

def _extraer_iniciales(nombre: str, apellido: str) -> str:
    n_tokens = [_norm_upper(t) for t in (nombre or "").split() if _norm_upper(t) not in _ARTICULOS]
    a_tokens = [_norm_upper(t) for t in (apellido or "").split() if _norm_upper(t) not in _ARTICULOS]
    n1 = _tomar_inicial(n_tokens[0]) if len(n_tokens) >= 1 else "9"
    n2 = _tomar_inicial(n_tokens[1]) if len(n_tokens) >= 2 else "9"
    a1 = _tomar_inicial(a_tokens[0]) if len(a_tokens) >= 1 else "9"
    a2 = _tomar_inicial(a_tokens[1]) if len(a_tokens) >= 2 else "9"
    return f"{n1}{n2}{a1}{a2}"

def _generar_codigo_expediente(nombre, apellido, fecha_nac_dt: datetime,
                               sexo: str | None = None,
                               municipio_codigo: str | None = None,
                               control: int | None = None) -> str:
    mmm = (municipio_codigo or "800").strip()
    if not re.match(r"^\d{3}$", mmm):
        raise ValueError("municipio_codigo debe ser 3 dígitos (ej. '161' o '800')")
    iniciales = _extraer_iniciales(nombre, apellido)
    s = (sexo or "F").strip().upper()
    if s not in ("M", "F"):
        raise ValueError("sexo debe ser 'M' o 'F' si se envía")
    ddmmaa = _ddmmaa(fecha_nac_dt)
    cc = control if isinstance(control, int) and 0 <= control <= 99 else 0
    codigo = f"{mmm}{iniciales}{s}{ddmmaa}{cc:02d}"
    if not _RE_EXPED.match(codigo):
        raise ValueError("No se pudo formar codigo_expediente válido")
    return codigo

def _serialize(doc: dict):
    nombres = doc.get("nombres", doc.get("nombre"))
    apellidos = doc.get("apellidos", doc.get("apellido"))
    deleted_at = doc.get("deleted_at")
    return {
        "id": str(doc["_id"]),
        "historial_id": str(doc.get("historial_id")) if isinstance(doc.get("historial_id"), ObjectId) else (doc.get("historial_id") or None),
        "nombres": nombres,
        "apellidos": apellidos,
        # Alias legacy para compatibilidad con UI existente
        "nombre": nombres,
        "apellido": apellidos,
        "nombre_completo": doc.get("nombre_completo") or (f"{nombres} {apellidos}".strip() if (nombres or apellidos) else None),
        "tipo_identificacion": doc.get("tipo_identificacion"),
        "numero_identificacion": doc.get("numero_identificacion"),
        "codigo_expediente": doc.get("codigo_expediente"),
        "fecha_nac": doc["fecha_nac"].strftime("%Y-%m-%d") if isinstance(doc.get("fecha_nac"), datetime) else None,
        "telefono": doc.get("telefono"),
        "direccion": doc.get("direccion"),
        "bairro": doc.get("bairro"),
        "gesta_actual": doc.get("gesta_actual"),
        "contacto_emergencia": doc.get("contacto_emergencia"),
        "activo": deleted_at in (None,) if ("deleted_at" in doc) else True,
        # Asegurar serialización JSON (datetime -> ISO8601 string)
        "created_at": (doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at")),
        "updated_at": (doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at")),
        "deleted_at": (deleted_at.isoformat() if isinstance(deleted_at, datetime) else deleted_at),
        "deleted_by": (str(doc.get("deleted_by")) if isinstance(doc.get("deleted_by"), ObjectId) else doc.get("deleted_by")),
    }


# Migración ad-hoc removida a pedido: mantener código sin endpoint de migración.

# ---------------- Services ----------------
def buscar_paciente_por_identificacion(tipo_identificacion: str, numero_identificacion: str):
    try:
        tipo = _validar_tipo_identificacion(tipo_identificacion)
        numero = _validar_numero_identificacion(tipo, numero_identificacion)
        doc = mongo.db.paciente.find_one({
            "tipo_identificacion": tipo,
            "numero_identificacion": numero,
            "$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}],
        })
        if not doc:
            return _fail("No existe paciente con esa identificacion", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al buscar paciente", 400)


def buscar_paciente_por_cedula(identificacion: str):
    return buscar_paciente_por_identificacion('CI', identificacion)


def crear_paciente(payload: dict, session=None):
    """
    Crea un paciente. `historial_id` es OPCIONAL:
      - Si viene, debe ser ObjectId válido y existir en `historiales` (FK suave).
      - Si no viene, el paciente queda sin historial asociado.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        _ensure_indexes()

        # Compat: aceptar `nombres/apellidos` o `nombre/apellido`
        nombres_in   = payload.get("nombres", payload.get("nombre"))
        apellidos_in = payload.get("apellidos", payload.get("apellido"))
        nombre   = _validar_min_nonempty(nombres_in, "nombres")
        apellido = _validar_min_nonempty(apellidos_in, "apellidos")
        tipo_identificacion = _validar_tipo_identificacion(payload.get("tipo_identificacion"))
        numero_identificacion = _validar_numero_identificacion(tipo_identificacion, payload.get("numero_identificacion"))
        fecha_nac_dt   = _parse_date_ymd(payload.get("fecha_nac"), "fecha_nac")
        telefono = _validar_telefono(payload.get("telefono"))
        direccion = _validar_min_nonempty(payload.get("direccion"), "direccion")
        bairro    = _validar_min_nonempty(payload.get("bairro"), "bairro")
        gesta_actual = _validar_gesta_actual(payload.get("gesta_actual"))

        # ya existe?
        ya = mongo.db.paciente.find_one({
            "tipo_identificacion": tipo_identificacion,
            "numero_identificacion": numero_identificacion,
            "$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}],
        })
        if ya:
            return {"ok": False, "data": _serialize(ya), "error": "Paciente ya existe"}, 409

        # opcionales codigo_expediente
        municipio_codigo = payload.get("municipio_codigo")
        sexo = (payload.get("sexo") or "F").upper()

        # Generar codigo_expediente único
        control = 0
        while control <= 99:
            codigo = _generar_codigo_expediente(nombre, apellido, fecha_nac_dt, sexo, municipio_codigo, control)
            if not mongo.db.paciente.find_one({
                "codigo_expediente": codigo,
                "$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}],
            }):
                break
            control += 1
        if control > 99:
            return _fail("No se pudo generar un codigo_expediente único (CC agotado)", 400)

        # historial_id opcional
        historial_oid = None
        if payload.get("historial_id") not in (None, "",):
            historial_oid = _to_oid(payload.get("historial_id"), "historial_id")
            # Validar existencia del historial (FK suave)
            if not mongo.db.historiales.find_one({"_id": historial_oid}):
                return _fail("historial_id no encontrado en historiales", 404)

        doc = {
            "nombres": nombre.strip(),
            "apellidos": apellido.strip(),
            "nombre_completo": f"{nombre.strip()} {apellido.strip()}".strip(),
            "tipo_identificacion": tipo_identificacion,
            "numero_identificacion": numero_identificacion,
            "codigo_expediente": codigo,
            "fecha_nac": fecha_nac_dt,
            "telefono": telefono,
            "direccion": direccion,
            "bairro": bairro,
            "gesta_actual": gesta_actual,
            "deleted_at": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if historial_oid is not None:
            doc["historial_id"] = historial_oid  # solo guardar si existe

        ce = payload.get("contacto_emergencia")
        if isinstance(ce, dict):
            ce_nombre = _validar_min_nonempty(ce.get("nombre"), "contacto_emergencia.nombre")
            ce_tel    = _validar_telefono(ce.get("telefono"))
            doc["contacto_emergencia"] = {"nombre": ce_nombre, "telefono": ce_tel}

        try:
            current_app.logger.info(f"[pacientes] Insert doc: {doc}")
        except Exception:
            pass

        res = (mongo.db.paciente.insert_one(doc, session=session)
               if session else mongo.db.paciente.insert_one(doc))
        return _ok({"id": str(res.inserted_id), "codigo_expediente": codigo}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        msg = str(e)
        try:
            current_app.logger.exception("Error al crear paciente")
        except Exception:
            pass
        if "duplicate key" in msg.lower():
            return _fail("Duplicado: tipo/numero de identificacion o codigo_expediente ya existen", 409)
        return _fail(f"Error al crear paciente: {msg}", 400)

def actualizar_paciente_por_id(paciente_id: str, payload: dict, session=None):
    """
    Permite actualizar campos básicos y opcionalmente:
      - setear historial_id (validando existencia),
      - o limpiarlo pasando null/None.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(paciente_id, "paciente_id")
        upd = {}
        doc_actual = None

        def _obtener_doc_actual():
            nonlocal doc_actual
            if doc_actual is None:
                doc_actual = mongo.db.paciente.find_one({"_id": oid})
            return doc_actual

        if "historial_id" in payload:
            h = payload.get("historial_id")
            if h in (None, ""):
                upd["historial_id"] = None
            else:
                h_oid = _to_oid(h, "historial_id")
                if not mongo.db.historiales.find_one({"_id": h_oid}):
                    return _fail("historial_id no encontrado en historiales", 404)
                upd["historial_id"] = h_oid

        # Aceptar nombres/apellidos o nombre/apellido (legacy)
        if "nombres" in payload or "nombre" in payload:
            val = payload.get("nombres", payload.get("nombre"))
            if val is not None:
                upd["nombres"] = _validar_min_nonempty(val, "nombres")
        if "apellidos" in payload or "apellido" in payload:
            val = payload.get("apellidos", payload.get("apellido"))
            if val is not None:
                upd["apellidos"] = _validar_min_nonempty(val, "apellidos")

        if any(k in payload for k in ("tipo_identificacion", "numero_identificacion")):
            doc = _obtener_doc_actual()
            if not doc:
                return _fail("Paciente no encontrado", 404)
    
            tipo_actual = doc.get("tipo_identificacion")
            numero_actual = doc.get("numero_identificacion")

            if tipo_actual is None or numero_actual is None:
                raise ValueError("Paciente sin datos de identificacion")

            if "tipo_identificacion" in payload and payload["tipo_identificacion"] is not None:
                tipo_validado = _validar_tipo_identificacion(payload["tipo_identificacion"])
            elif "tipo_identificacion" in payload:
                raise ValueError("tipo_identificacion es requerido")
            else:
                tipo_validado = _validar_tipo_identificacion(tipo_actual)

            if "numero_identificacion" in payload and payload["numero_identificacion"] is not None:
                numero_fuente = payload["numero_identificacion"]
            elif "numero_identificacion" in payload:
                raise ValueError("numero_identificacion es requerido")
            else:
                numero_fuente = numero_actual

            numero_validado = _validar_numero_identificacion(tipo_validado, numero_fuente)
            upd["tipo_identificacion"] = tipo_validado
            upd["numero_identificacion"] = numero_validado

            existe = mongo.db.paciente.find_one({
                "tipo_identificacion": tipo_validado,
                "numero_identificacion": numero_validado,
                "_id": {"$ne": oid},
            })
            if existe:
                return _fail("Duplicado: tipo/numero de identificacion ya existen", 409)

        if "fecha_nac" in payload and payload["fecha_nac"] is not None:
            upd["fecha_nac"] = _parse_date_ymd(payload["fecha_nac"], "fecha_nac")
        if "telefono" in payload and payload["telefono"] is not None:
            upd["telefono"] = _validar_telefono(payload["telefono"])
        if "direccion" in payload and payload["direccion"] is not None:
            upd["direccion"] = _validar_min_nonempty(payload["direccion"], "direccion")
        if "bairro" in payload and payload["bairro"] is not None:
            upd["bairro"] = _validar_min_nonempty(payload["bairro"], "bairro")
        if "gesta_actual" in payload and payload["gesta_actual"] is not None:
            upd["gesta_actual"] = _validar_gesta_actual(payload["gesta_actual"])

        if payload.get("regenerate_codigo"):
            doc_actual = _obtener_doc_actual()
            if not doc_actual:
                return _fail("Paciente no encontrado", 404)
            nombre = upd.get("nombres", doc_actual.get("nombres", doc_actual.get("nombre")))
            apellido = upd.get("apellidos", doc_actual.get("apellidos", doc_actual.get("apellido")))
            fecha_nac_dt = upd.get("fecha_nac", doc_actual.get("fecha_nac"))
            if not isinstance(fecha_nac_dt, datetime):
                return _fail("fecha_nac inválida para regenerar código", 422)
            sexo = (payload.get("sexo") or "F").upper()
            municipio_codigo = payload.get("municipio_codigo") or "800"

            control = 0
            while control <= 99:
                codigo = _generar_codigo_expediente(nombre, apellido, fecha_nac_dt, sexo, municipio_codigo, control)
                existe = mongo.db.paciente.find_one({"codigo_expediente": codigo, "_id": {"$ne": oid}, "$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]})
                if not existe:
                    upd["codigo_expediente"] = codigo
                    break
                control += 1
            if "codigo_expediente" not in upd:
                return _fail("No se pudo generar un codigo_expediente único", 400)

        if not upd:
            return _ok({"mensaje": "Nada para actualizar"}, 200)

        upd["updated_at"] = datetime.utcnow()
        # mantener nombre_completo si hay cambios en nombres o apellidos
        if "nombres" in upd or "apellidos" in upd:
            doc_base = doc_actual or mongo.db.paciente.find_one({"_id": oid})
            n_final = upd.get("nombres", doc_base.get("nombres", doc_base.get("nombre", "")))
            a_final = upd.get("apellidos", doc_base.get("apellidos", doc_base.get("apellido", "")))
            upd["nombre_completo"] = f"{n_final} {a_final}".strip()

        res = mongo.db.paciente.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("Paciente no encontrado", 404)
        return _ok({"mensaje": "Paciente actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return _fail("Duplicado: tipo/numero de identificacion o codigo_expediente ya existen", 409)
        return _fail("Error al actualizar paciente", 400)


def eliminar_paciente_por_id(paciente_id: str, hard: bool = False, session=None):
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        if hard:
            res = mongo.db.paciente.delete_one({"_id": oid}, session=session)
            if res.deleted_count == 0:
                return _fail("Paciente no encontrado", 404)
            return _ok({"mensaje": "Paciente eliminado definitivamente"}, 200)
        else:
            res = mongo.db.paciente.update_one({"_id": oid}, {"$set": {"deleted_at": datetime.utcnow()}}, session=session)
            if res.matched_count == 0:
                return _fail("Paciente no encontrado", 404)
            return _ok({"mensaje": "Paciente desactivado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar paciente", 400)

def listar_pacientes(q: str | None = None, page: int = 1, per_page: int = 20, solo_activos: bool = True):
    try:
        page = max(int(page or 1), 1)
        per_page = max(min(int(per_page or 20), 100), 1)

        filtro = {}
        if solo_activos:
            filtro["$or"] = [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]

        if q and isinstance(q, str) and q.strip():
            rx = {"$regex": re.escape(q.strip()), "$options": "i"}
            filtro["$or"] = [
                {"nombre": rx},
                {"apellido": rx},
                {"numero_identificacion": rx},
                {"codigo_expediente": rx},
            ]

        total = mongo.db.paciente.count_documents(filtro)
        cursor = (mongo.db.paciente.find(filtro)
                  .sort("created_at", -1)
                  .skip((page - 1) * per_page)
                  .limit(per_page))
        items = [_serialize(d) for d in cursor]
        return _ok({"items": items, "page": page, "per_page": per_page, "total": total}, 200)

    except Exception:
        return _fail("Error al listar pacientes", 400)

def obtener_paciente(paciente_id: str):
    """
    Retorna el paciente y, si está disponible `service_historial`,
    agrega sus historiales (lista) y marca la referencia `historial_id` del paciente.
    """
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.paciente.find_one({"_id": oid})
        if not doc:
            return _fail("Paciente no encontrado", 404)

        out = _serialize(doc)

        # Agregado: historiales del paciente (si el servicio está disponible)
        out["historiales"] = None
        out["historial_actual"] = None
        if svc_his and hasattr(svc_his, "listar_historiales"):
            try:
                lr, lc = svc_his.listar_historiales(paciente_id=paciente_id, page=1, per_page=50)
                if lc == 200 and lr.get("ok"):
                    out["historiales"] = lr["data"]
                    # más reciente (si el servicio ordena por created_at desc)
                    items = (lr["data"] or {}).get("items", [])
                    out["historial_actual"] = items[0] if items else None
            except Exception:
                pass

        return _ok(out, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener paciente", 400)
    
# service_paciente.py
def buscar_paciente_por_codigo_expediente(codigo: str):
    try:
        if not isinstance(codigo, str):
            return _fail("codigo_expediente debe ser string", 422)
        # Normalizar: mayúsculas y eliminar separadores no alfanuméricos
        codigo = (codigo or "").strip().upper()
        codigo_limpio = re.sub(r"[^0-9A-Z]", "", codigo)
        # Validar contra el patrón canónico (sin separadores)
        if not _RE_EXPED.match(codigo_limpio):
            return _fail("codigo_expediente con formato inválido", 422)
        # Buscar usando valor limpio
        doc = mongo.db.paciente.find_one({"codigo_expediente": codigo_limpio})
        if not doc:
            return _fail("No existe paciente con ese codigo_expediente", 404)
        return _ok(_serialize(doc), 200)
    except Exception:
        return _fail("Error al buscar paciente por codigo_expediente", 400)
