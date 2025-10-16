from flask import request
from app.services import service_settings as svc

def _ok(data, code=200):   return ({"ok": True, "data": data, "error": None}, code)
def _fail(msg, code=400):  return ({"ok": False, "data": None, "error": msg}, code)

def _serialize(doc: dict | None):
    if not doc: return None
    out = dict(doc)
    for f in ("_id","tenant_id","user_id","updated_by"):
        if out.get(f): out[f] = str(out[f])
    return out

def _mask_value_if_token(item: dict):
    if item and item.get("key") == "integrations.token":
        v = item.get("value")
        if isinstance(v, str):
            item["value"] = (v[:2] + "••••" + v[-2:]) if len(v) >= 4 else "••••"

# --- Endpoints ---

def upsert():
    try:
        data = request.get_json(force=True) or {}
        _id = svc.upsert_setting(
            key=data["key"],
            value=data.get("value"),
            scope=data.get("scope","global"),
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            user_oid=None,  # TODO: inyectar user_id del JWT si lo tienes
            description=data.get("description")
        )
        return _ok({"_id": str(_id)})
    except KeyError as e:
        return _fail(f"Falta campo requerido: {e.args[0]}", 422)
    except ValueError as e:
        return _fail(str(e), 422)
    except Exception as e:
        return _fail(str(e), 500)

def list_():
    try:
        items = svc.list_settings(
            scope=request.args.get("scope"),
            tenant_id=request.args.get("tenant_id"),
            user_id=request.args.get("user_id"),
            prefix=request.args.get("prefix"),
            limit=int(request.args.get("limit", "100"))
        )
        # enmascarar token
        for it in items:
            _mask_value_if_token(it)
        return _ok([_serialize(it) for it in items])
    except Exception as e:
        return _fail(str(e), 500)

def get_one(key):
    try:
        item = svc.get_setting(
            key=key,
            scope=request.args.get("scope","global"),
            tenant_id=request.args.get("tenant_id"),
            user_id=request.args.get("user_id")
        )
        if not item:
            return _fail("not_found", 404)
        _mask_value_if_token(item)
        return _ok(_serialize(item))
    except Exception as e:
        return _fail(str(e), 500)

def delete_one(key):
    try:
        deleted = svc.delete_setting(
            key=key,
            scope=request.args.get("scope","global"),
            tenant_id=request.args.get("tenant_id"),
            user_id=request.args.get("user_id")
        )
        return _ok({"deleted": deleted})
    except Exception as e:
        return _fail(str(e), 500)
