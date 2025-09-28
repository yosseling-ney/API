from datetime import datetime
import re
from bson import ObjectId
from app import mongo

# (opcionales) importaciones de otros servicios para el GET agregado
try:
    from app.services import service_antencedentes as svc_ant  # nombre original del usuario
except Exception:
    svc_ant = None

try:
    from app.services import service_identificacion as svc_ident
except Exception:
    svc_ident = None

try:
    from app.services import service_gestacion_actual as svc_ga
except Exception:
    svc_ga = None

try:
    from app.services import service_parto_aborto as svc_pa
except Exception:
    svc_pa = None

try:
    from app.services import service_patologias as svc_pat
except Exception:
    svc_pat = None

try:
    from app.services import service_puerperio as svc_puer
except Exception:
    svc_puer = None

try:
    from app.services import service_recien_nacido as svc_rn
except Exception:
    svc_rn = None

try:
    from app.services import service_egreso_neonatal as svc_en
except Exception:
    svc_en = None

try:
    from app.services import service_egreso_materno as svc_em
except Exception:
    svc_em = None

try:
    from app.services import service_anticoncepcion as svc_antico
except Exception:
    svc_antico = None


# ---------------- Respuestas estándar ----------------
def _ok(data, code=200):   return {"ok": True, "data": data, "error": None}, code
def _fail(msg, code=400):  return {"ok": False, "data": None, "error": msg}, code


# ---------------- Reglas / patrones ----------------
_RE_CEDULA = re.compile(r"^\d{3}-\d{6}-\d{4}[A-Z]{1}$")
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
    # Únicos recomendados
    try:
        mongo.db.pacientes.create_index("identificacion", unique=True, name="uq_identificacion")
    except Exception:
        pass
    try:
        mongo.db.pacientes.create_index("codigo_expediente", unique=True, name="uq_codigo_expediente")
    except Exception:
        pass

def _validar_cedula(c):
    if not isinstance(c, str): 
        raise ValueError("identificacion debe ser string")
    c = _norm_upper(c)
    if not _RE_CEDULA.match(c):
        raise ValueError("identificacion con formato inválido (###-######-####X)")
    return c

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
    """
    Retorna 4 caracteres (A-Z o 9):
    - 1er y 2do nombre (si no existe 2do => '9')
    - 1er y 2do apellido (si no existe 2do => '9')
    Ignora artículos comunes.
    """
    # nombres
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
    """
    MMM + IIII + S + DDMMAA + CC
    - MMM: 3 dígitos (por defecto '800' si no se envía)
    - IIII: iniciales (A-Z) o '9' como comodín
    - S: 'M' | 'F' (por defecto 'F' dado el contexto obstétrico)
    - DDMMAA: desde fecha_nac
    - CC: control 00..99 (si no se envía, usa 00 y luego intenta incrementar si colisiona)
    """
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
    return {
        "id": str(doc["_id"]),
        "nombre": doc.get("nombre"),
        "apellido": doc.get("apellido"),
        "identificacion": doc.get("identificacion"),
        "codigo_expediente": doc.get("codigo_expediente"),
        "fecha_nac": doc["fecha_nac"].strftime("%Y-%m-%d") if isinstance(doc.get("fecha_nac"), datetime) else None,
        "telefono": doc.get("telefono"),
        "direccion": doc.get("direccion"),
        "bairro": doc.get("bairro"),
        "gesta_actual": doc.get("gesta_actual"),
        "contacto_emergencia": doc.get("contacto_emergencia"),
        "activo": doc.get("activo", True),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# ---------------- Services ----------------
def buscar_paciente_por_cedula(identificacion: str):
    """Busca por cédula exacta (normalizada)."""
    try:
        ident = _validar_cedula(identificacion)
        doc = mongo.db.pacientes.find_one({"identificacion": ident})
        if not doc:
            return _fail("No existe paciente con esa identificación", 404)
        return _ok(_serialize(doc), 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        return _fail("Error al buscar paciente", 400)


def crear_paciente(payload: dict, session=None):
    """
    Crea un paciente nuevo.
    Comportamiento:
      - Si ya existe por 'identificacion' => 409 y retorno del existente.
      - Genera 'codigo_expediente' siguiendo el patrón MINSA.
        * sexo (opcional, default 'F').
        * municipio_codigo (opcional, default '800').
        * control se ajusta si hay colisión.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        _ensure_indexes()

        nombre   = _validar_min_nonempty(payload.get("nombre"), "nombre")
        apellido = _validar_min_nonempty(payload.get("apellido"), "apellido")
        identificacion = _validar_cedula(payload.get("identificacion"))
        fecha_nac_dt   = _parse_date_ymd(payload.get("fecha_nac"), "fecha_nac")
        telefono = _validar_telefono(payload.get("telefono"))
        direccion = _validar_min_nonempty(payload.get("direccion"), "direccion")
        bairro    = _validar_min_nonempty(payload.get("bairro"), "bairro")
        gesta_actual = _validar_gesta_actual(payload.get("gesta_actual"))

        # ¿paciente ya existe?
        ya = mongo.db.pacientes.find_one({"identificacion": identificacion})
        if ya:
            # 409 -> conflicto: ya existe. Devolvemos el existente.
            return {"ok": False, "data": _serialize(ya), "error": "Paciente ya existe"}, 409

        # opcionales para codigo_expediente
        municipio_codigo = payload.get("municipio_codigo")  # "161", "800", etc.
        sexo = (payload.get("sexo") or "F").upper()

        # Generar codigo_expediente y resolver posibles colisiones incrementando CC
        control = 0
        while control <= 99:
            codigo = _generar_codigo_expediente(nombre, apellido, fecha_nac_dt, sexo, municipio_codigo, control)
            if not mongo.db.pacientes.find_one({"codigo_expediente": codigo}):
                break
            control += 1
        if control > 99:
            return _fail("No se pudo generar un codigo_expediente único (CC agotado)", 400)

        doc = {
            "nombre": nombre.strip(),
            "apellido": apellido.strip(),
            "identificacion": identificacion,
            "codigo_expediente": codigo,
            "fecha_nac": fecha_nac_dt,
            "telefono": telefono,
            "direccion": direccion,
            "bairro": bairro,
            "gesta_actual": gesta_actual,
            "contacto_emergencia": None,
            "activo": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # contacto_emergencia opcional (si viene)
        ce = payload.get("contacto_emergencia")
        if isinstance(ce, dict):
            ce_nombre = _validar_min_nonempty(ce.get("nombre"), "contacto_emergencia.nombre")
            ce_tel    = _validar_telefono(ce.get("telefono"))
            doc["contacto_emergencia"] = {"nombre": ce_nombre, "telefono": ce_tel}

        res = mongo.db.pacientes.insert_one(doc, session=session) if session else mongo.db.pacientes.insert_one(doc)
        return _ok({"id": str(res.inserted_id), "codigo_expediente": codigo}, 201)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        # Si es por índice único, intenta detectarlo
        msg = str(e)
        if "duplicate key" in msg.lower():
            return _fail("Duplicado: identificacion o codigo_expediente ya existen", 409)
        return _fail("Error al crear paciente", 400)


def actualizar_paciente_por_id(paciente_id: str, payload: dict, session=None):
    """
    Actualiza datos básicos (NO regenera codigo_expediente salvo que se pida explícito).
    Si cambias nombre/apellido/fecha_nac y quieres re-generar el código, envía regenerate_codigo=True.
    """
    try:
        if not isinstance(payload, dict):
            return _fail("JSON inválido", 400)

        oid = _to_oid(paciente_id, "paciente_id")
        upd = {}

        if "nombre" in payload and payload["nombre"] is not None:
            upd["nombre"] = _validar_min_nonempty(payload["nombre"], "nombre")

        if "apellido" in payload and payload["apellido"] is not None:
            upd["apellido"] = _validar_min_nonempty(payload["apellido"], "apellido")

        if "identificacion" in payload and payload["identificacion"] is not None:
            upd["identificacion"] = _validar_cedula(payload["identificacion"])

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

        if "contacto_emergencia" in payload and payload["contacto_emergencia"] is not None:
            ce = payload["contacto_emergencia"]
            if ce is None:
                upd["contacto_emergencia"] = None
            elif isinstance(ce, dict):
                ce_nombre = _validar_min_nonempty(ce.get("nombre"), "contacto_emergencia.nombre")
                ce_tel    = _validar_telefono(ce.get("telefono"))
                upd["contacto_emergencia"] = {"nombre": ce_nombre, "telefono": ce_tel}
            else:
                raise ValueError("contacto_emergencia debe ser objeto o null")

        # Regeneración del código (opcional y controlada)
        if payload.get("regenerate_codigo"):
            doc_actual = mongo.db.pacientes.find_one({"_id": oid})
            if not doc_actual:
                return _fail("Paciente no encontrado", 404)
            nombre   = upd.get("nombre",   doc_actual.get("nombre"))
            apellido = upd.get("apellido", doc_actual.get("apellido"))
            fecha_nac_dt = upd.get("fecha_nac", doc_actual.get("fecha_nac"))
            if not isinstance(fecha_nac_dt, datetime):
                raise ValueError("fecha_nac inválida para regenerar código")
            sexo = (payload.get("sexo") or "F").upper()
            municipio_codigo = payload.get("municipio_codigo") or "800"

            control = 0
            while control <= 99:
                codigo = _generar_codigo_expediente(nombre, apellido, fecha_nac_dt, sexo, municipio_codigo, control)
                existe = mongo.db.pacientes.find_one({"codigo_expediente": codigo, "_id": {"$ne": oid}})
                if not existe:
                    upd["codigo_expediente"] = codigo
                    break
                control += 1
            if "codigo_expediente" not in upd:
                return _fail("No se pudo generar un codigo_expediente único", 400)

        if not upd:
            return _ok({"mensaje": "Nada para actualizar"}, 200)

        upd["updated_at"] = datetime.utcnow()
        res = mongo.db.pacientes.update_one({"_id": oid}, {"$set": upd}, session=session)
        if res.matched_count == 0:
            return _fail("Paciente no encontrado", 404)
        return _ok({"mensaje": "Paciente actualizado"}, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception as e:
        msg = str(e)
        if "duplicate key" in msg.lower():
            return _fail("Duplicado: identificacion o codigo_expediente ya existen", 409)
        return _fail("Error al actualizar paciente", 400)


def eliminar_paciente_por_id(paciente_id: str, hard: bool = False, session=None):
    """
    Baja lógica por defecto (activo=False). Si hard=True elimina físicamente.
    """
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        if hard:
            res = mongo.db.pacientes.delete_one({"_id": oid}, session=session)
            if res.deleted_count == 0:
                return _fail("Paciente no encontrado", 404)
            return _ok({"mensaje": "Paciente eliminado definitivamente"}, 200)
        else:
            res = mongo.db.pacientes.update_one({"_id": oid}, {"$set": {"activo": False, "updated_at": datetime.utcnow()}}, session=session)
            if res.matched_count == 0:
                return _fail("Paciente no encontrado", 404)
            return _ok({"mensaje": "Paciente desactivado"}, 200)
    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al eliminar paciente", 400)


def listar_pacientes(q: str | None = None, page: int = 1, per_page: int = 20, solo_activos: bool = True):
    """
    Listado simple con búsqueda por nombre/apellido/identificacion.
    """
    try:
        page = max(int(page or 1), 1)
        per_page = max(min(int(per_page or 20), 100), 1)

        filtro = {}
        if solo_activos:
            filtro["activo"] = True

        if q and isinstance(q, str) and q.strip():
            rx = {"$regex": re.escape(q.strip()), "$options": "i"}
            filtro["$or"] = [
                {"nombre": rx},
                {"apellido": rx},
                {"identificacion": rx},
                {"codigo_expediente": rx},
            ]

        total = mongo.db.pacientes.count_documents(filtro)
        cursor = mongo.db.pacientes.find(filtro).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
        items = [_serialize(d) for d in cursor]
        return _ok({"items": items, "page": page, "per_page": per_page, "total": total}, 200)

    except Exception:
        return _fail("Error al listar pacientes", 400)


def obtener_paciente(paciente_id: str, identificacion_id: str | None = None):
    """
    GET agregado del paciente:
    - Retorna los datos del paciente.
    - Agrega, si están disponibles, los segmentos de otros servicios.
      Si se pasa identificacion_id, intenta priorizar datos de ese episodio.
      Si no, devuelve el MÁS RECIENTE por paciente.
    """
    try:
        oid = _to_oid(paciente_id, "paciente_id")
        doc = mongo.db.pacientes.find_one({"_id": oid})
        if not doc:
            return _fail("Paciente no encontrado", 404)

        out = _serialize(doc)

        # Episodios (identificaciones) – opcional
        out["episodios"] = None
        if svc_ident and hasattr(svc_ident, "listar_identificaciones_por_paciente"):
            try:
                eps = svc_ident.listar_identificaciones_por_paciente(paciente_id)
                # eps puede venir como (_ok(data), code)
                if isinstance(eps, tuple) and isinstance(eps[0], dict) and eps[0].get("ok"):
                    out["episodios"] = eps[0]["data"]
            except Exception:
                pass

        # Helper para elegir por episodio o por paciente
        def _get_segment(fn_by_paciente, fn_by_identificacion):
            if identificacion_id and fn_by_identificacion:
                try:
                    return fn_by_identificacion(identificacion_id)
                except Exception:
                    return None
            if fn_by_paciente:
                try:
                    return fn_by_paciente(paciente_id)
                except Exception:
                    return None
            return None

        # Antecedentes
        out["antecedentes"] = None
        if svc_ant and hasattr(svc_ant, "get_antencedentes_by_id_paciente"):
            try:
                res = svc_ant.get_antencedentes_by_id_paciente(paciente_id)
                if isinstance(res, dict) and res.get("ok"):
                    out["antecedentes"] = res["data"]
                elif isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                    out["antecedentes"] = res[0]["data"]
            except Exception:
                pass

        # Gestación actual
        out["gestacion_actual"] = None
        if svc_ga and hasattr(svc_ga, "get_gestacion_actual_by_id_paciente"):
            res = _get_segment(svc_ga.get_gestacion_actual_by_id_paciente,
                               getattr(svc_ga, "obtener_gestacion_actual_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["gestacion_actual"] = res[0]["data"]

        # Parto / Aborto
        out["parto_aborto"] = None
        if svc_pa and hasattr(svc_pa, "get_parto_aborto_by_id_paciente"):
            res = _get_segment(svc_pa.get_parto_aborto_by_id_paciente,
                               getattr(svc_pa, "obtener_parto_aborto_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["parto_aborto"] = res[0]["data"]

        # Patologías
        out["patologias"] = None
        if svc_pat and hasattr(svc_pat, "get_patologias_by_id_paciente"):
            res = _get_segment(svc_pat.get_patologias_by_id_paciente,
                               getattr(svc_pat, "obtener_patologias_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["patologias"] = res[0]["data"]

        # Puerperio
        out["puerperio"] = None
        if svc_puer and hasattr(svc_puer, "get_puerperio_by_id_paciente"):
            res = _get_segment(svc_puer.get_puerperio_by_id_paciente,
                               getattr(svc_puer, "obtener_puerperio_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["puerperio"] = res[0]["data"]

        # Recién Nacido
        out["recien_nacido"] = None
        if svc_rn and hasattr(svc_rn, "get_recien_nacido_by_id_paciente"):
            res = _get_segment(svc_rn.get_recien_nacido_by_id_paciente,
                               getattr(svc_rn, "obtener_recien_nacido_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["recien_nacido"] = res[0]["data"]

        # Egreso Neonatal
        out["egreso_neonatal"] = None
        if svc_en and hasattr(svc_en, "get_egreso_neonatal_by_id_paciente"):
            res = _get_segment(svc_en.get_egreso_neonatal_by_id_paciente,
                               getattr(svc_en, "obtener_egreso_neonatal_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["egreso_neonatal"] = res[0]["data"]

        # Egreso Materno
        out["egreso_materno"] = None
        if svc_em and hasattr(svc_em, "get_egreso_materno_by_id_paciente"):
            res = _get_segment(svc_em.get_egreso_materno_by_id_paciente,
                               getattr(svc_em, "obtener_egreso_materno_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["egreso_materno"] = res[0]["data"]

        # Anticoncepción
        out["anticoncepcion"] = None
        if svc_antico and hasattr(svc_antico, "get_anticoncepcion_by_id_paciente"):
            res = _get_segment(svc_antico.get_anticoncepcion_by_id_paciente,
                               getattr(svc_antico, "obtener_anticoncepcion_por_identificacion", None))
            if isinstance(res, tuple) and isinstance(res[0], dict) and res[0].get("ok"):
                out["anticoncepcion"] = res[0]["data"]

        return _ok(out, 200)

    except ValueError as ve:
        return _fail(str(ve), 422)
    except Exception:
        return _fail("Error al obtener paciente", 400)
