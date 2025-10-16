from datetime import datetime
import re
from bson import ObjectId
from app import mongo

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
URL_RE   = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

def _now():
    return datetime.utcnow()

def _oid(x):
    return ObjectId(x) if x else None

def _validate_by_key(key: str, value):
    if key == "notifications.primary_email":
        if not isinstance(value, str) or not EMAIL_RE.match(value):
            raise ValueError("Correo inválido para notifications.primary_email")
    elif key == "notifications.auto_alerts":
        if not isinstance(value, bool):
            raise ValueError("notifications.auto_alerts debe ser booleano (true/false)")
    elif key == "integrations.webhook":
        if not isinstance(value, str) or not URL_RE.match(value):
            raise ValueError("URL inválida para integrations.webhook")
    # integrations.token: string libre (se enmascara al leer)

def upsert_setting(*, key: str, value, scope: str = "global",
                   tenant_id=None, user_id=None, user_oid=None, description=None):
    key = (key or "").strip()
    if not key:
        raise ValueError("key es requerido")
    if scope not in ("global","tenant","user"):
        raise ValueError("scope inválido")

    _validate_by_key(key, value)

    doc = {
        "key": key,
        "scope": scope,
        "tenant_id": _oid(tenant_id),
        "user_id": _oid(user_id),
        "value": value,
        "description": description or None,
        "updated_at": _now(),
        "updated_by": _oid(user_oid) if user_oid else None,
    }
    q = {"key": key, "scope": scope}
    if scope == "tenant": q["tenant_id"] = doc["tenant_id"]
    if scope == "user":   q["user_id"]   = doc["user_id"]

    set_on_insert = {"created_at": _now()}
    res = mongo.db.settings.update_one(q, {"$set": doc, "$setOnInsert": set_on_insert}, upsert=True)
    return res.upserted_id or mongo.db.settings.find_one(q, {"_id":1})["_id"]

def get_setting(*, key: str, scope: str = "global", tenant_id=None, user_id=None):
    q = {"key": key, "scope": scope}
    if scope == "tenant": q["tenant_id"] = _oid(tenant_id)
    if scope == "user":   q["user_id"]   = _oid(user_id)
    return mongo.db.settings.find_one(q)

def list_settings(*, scope=None, tenant_id=None, user_id=None, prefix=None, limit: int = 100):
    q = {}
    if scope: q["scope"] = scope
    if tenant_id: q["tenant_id"] = _oid(tenant_id)
    if user_id:   q["user_id"]   = _oid(user_id)
    if prefix:    q["key"] = {"$regex": f"^{prefix}"}
    return list(mongo.db.settings.find(q).limit(limit))

def delete_setting(*, key: str, scope: str = "global", tenant_id=None, user_id=None):
    q = {"key": key, "scope": scope}
    if scope == "tenant": q["tenant_id"] = _oid(tenant_id)
    if scope == "user":   q["user_id"]   = _oid(user_id)
    return mongo.db.settings.delete_one(q).deleted_count
