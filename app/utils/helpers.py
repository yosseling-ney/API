from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta
import pytz

def encriptar_password(password):
    return generate_password_hash(password)

def verificar_password(password_plano, password_encriptado):
    return check_password_hash(password_encriptado, password_plano)

# Utilidades de tiempo (zona America/Managua)

TZ = pytz.timezone("America/Managua")

def today_range_utc():
    """
    Retorna (inicio_utc, fin_utc) del día actual en base a la zona 'America/Managua'.
    Ejemplo: para filtrar citas del día actual en UTC.
    """
    now_local = datetime.now(TZ)
    start_local = datetime.combine(now_local.date(), time.min).replace(tzinfo=TZ)
    end_local = datetime.combine(now_local.date(), time.max).replace(tzinfo=TZ)
    return start_local.astimezone(pytz.UTC), end_local.astimezone(pytz.UTC)

def next_days_range_utc(days: int):
    """
    Retorna (inicio_utc, fin_utc) para un rango de días futuros a partir de hoy
    según la zona 'America/Managua'.
    Ejemplo: para citas próximas a N días.
    """
    now_local = datetime.now(TZ)
    end_local = now_local + timedelta(days=days)
    return now_local.astimezone(pytz.UTC), end_local.astimezone(pytz.UTC)
