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
    _safe_create("paciente", [("identificacion", ASCENDING)], name="uq_identificacion", unique=True)
    _safe_create("paciente", [("codigo_expediente", ASCENDING)], name="uq_codigo_expediente", unique=True)

    # ---------------- historiales ----------------
    _safe_create("historiales", [("paciente_id", ASCENDING), ("numero_gesta", ASCENDING)],
                 name="uq_paciente_gesta", unique=True)
    _safe_create("historiales", [("paciente_id", ASCENDING)], name="ix_paciente")
    _safe_create("historiales", [("created_at", DESCENDING), ("numero_gesta", DESCENDING)],
                 name="ix_created_gesta")
    for ref in [
        "identificacion_id", "antecedentes_id", "gestacion_actual_id",
        "parto_aborto_id", "patologias_id", "recien_nacido_id",
        "puerperio_id", "egreso_neonatal_id", "egreso_materno_id",
        "anticoncepcion_id"
    ]:
        _safe_create("historiales", [(ref, ASCENDING)], name=f"ix_{ref}")

    # ---------------- identificacion ----------------
    _safe_create("identificacion", [("historial_id", ASCENDING)], name="historial_idx")
    _safe_create("identificacion", [("created_at", DESCENDING)], name="created_desc_idx")

    # ---------------- antecedentes ----------------
    _safe_create("antecedentes", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- gestacion_actual ----------------
    _safe_create("gestacion_actual", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- parto_aborto ----------------
    _safe_create("parto_aborto", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")
    _safe_create("parto_aborto", [("historial_id", ASCENDING), ("fecha_ingreso", DESCENDING)],
                 name="historial_fecha_ingreso_idx")
    _safe_create("parto_aborto", [("fecha_ingreso", DESCENDING)], name="fecha_ingreso_idx")  # opcional

    # ---------------- patologias ----------------
    _safe_create("patologias", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- recien_nacidos (ojo: plural) ----------------
    _safe_create("recien_nacidos", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- mensajes ----------------
    _safe_create("mensajes", [("paciente_id", ASCENDING), ("created_at", DESCENDING)],
                 name="ix_mensajes_paciente_created")
    _safe_create("mensajes", [("created_at", DESCENDING)], name="ix_mensajes_created")

    # ---------------- citas ----------------
    _safe_create("citas", [("start_at", ASCENDING)], name="ix_citas_start_at")
    _safe_create("citas", [("paciente_id", ASCENDING)], name="ix_citas_paciente")
    _safe_create("citas", [("status", ASCENDING)], name="ix_citas_status")
    # Evitar doble reserva exacta: mismo doctor (provider) y misma hora (start_at) mientras esté programada
    try:
        get_db()["citas"].create_index(
            [("provider", ASCENDING), ("start_at", ASCENDING)],
            name="uq_provider_start_scheduled",
            unique=True,
            partialFilterExpression={"status": "scheduled", "provider": {"$type": "string"}},
        )
    except Exception as e:
        print(f"[indexes] WARN citas:uq_provider_start_scheduled -> {e}")

    # ---------------- puerperio ----------------
    _safe_create("puerperio", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- egreso_neonatal ----------------
    _safe_create("egreso_neonatal", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

    # ---------------- egreso_materno ----------------
    _safe_create("egreso_materno", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")
    _safe_create("egreso_materno", [("egreso_materno.fecha", DESCENDING)],
                 name="paciente_fecha_egreso_idx")  # si ese path existe

    # ---------------- anticoncepcion ----------------
    _safe_create("anticoncepcion", [("historial_id", ASCENDING), ("created_at", DESCENDING)],
                 name="historial_created_desc_idx")

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
