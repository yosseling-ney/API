from pymongo import ASCENDING, DESCENDING
from flask import current_app
from contextlib import contextmanager

def get_db():
    """Devuelve la DB actual sin importar directamente 'mongo' para evitar ciclos."""
    return current_app.extensions["pymongo"].db

def _safe_create(collection, keys, **kwargs):
    """
    Crea un índice si no existe. No rompe si ya existe o si hay race-conditions.
    keys: lista de tuplas [("campo", ASCENDING|DESCENDING)]
    kwargs: name=..., unique=True, etc.
    """
    db = get_db()
    try:
        db[collection].create_index(keys, **kwargs)
    except Exception as e:
        # Loguea y continúa para no frenar el arranque
        print(f"[indexes] WARN {collection}:{kwargs.get('name')} -> {e}")

def init_indexes():
    db = get_db()

    # ---------------- pacientes ----------------
    _safe_create("pacientes", [("identificacion", ASCENDING)], name="uq_identificacion", unique=True)
    _safe_create("pacientes", [("codigo_expediente", ASCENDING)], name="uq_codigo_expediente", unique=True)

    # ---------------- identificacion ----------------
    _safe_create("identificacion", [("paciente_id", ASCENDING)], name="paciente_idx")
    _safe_create("identificacion", [("created_at", DESCENDING)], name="created_desc_idx")

    # ---------------- antecedentes ----------------
    _safe_create("antecedentes", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- gestacion_actual ----------------
    _safe_create("gestacion_actual", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- parto_aborto ----------------
    _safe_create("parto_aborto", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")
    _safe_create("parto_aborto", [("paciente_id", ASCENDING), ("fecha_ingreso", DESCENDING)], name="paciente_fecha_ingreso_idx")
    _safe_create("parto_aborto", [("fecha_ingreso", DESCENDING)], name="fecha_ingreso_idx")  # opcional

    # ---------------- patologias ----------------
    _safe_create("patologias", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- recien_nacido ----------------
    _safe_create("recien_nacido", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- puerperio ----------------
    _safe_create("puerperio", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- egreso_neonatal ----------------
    _safe_create("egreso_neonatal", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    # ---------------- egreso_materno ----------------
    _safe_create("egreso_materno", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")
    _safe_create("egreso_materno", [("paciente_id", ASCENDING), ("egreso_materno.fecha", DESCENDING)], name="paciente_fecha_egreso_idx")

    # ---------------- anticoncepcion ----------------
    _safe_create("anticoncepcion", [("paciente_id", ASCENDING), ("created_at", DESCENDING)], name="paciente_created_desc_idx")

    print("[indexes] OK – índices creados/actualizados")

@contextmanager
def start_session_if_possible():
    """
    Intenta abrir una sesión de Mongo (para transacciones si usas replicaset).
    Si no es posible (p. ej., sin replicaset), no falla: yield None.
    Uso:
        with start_session_if_possible() as s:
            if s:
                s.start_transaction()
                ... operaciones con session=s ...
    """
    try:
        client = current_app.extensions["pymongo"].cx  # PyMongo MongoClient
        session = client.start_session()
    except Exception as e:
        # No hay replicaset / driver no soporta / etc.
        current_app.logger.warning(f"[db] No se pudo iniciar sesión de Mongo: {e}")
        yield None
        return

    try:
        yield session
    finally:
        try:
            session.end_session()
        except Exception:
            pass
