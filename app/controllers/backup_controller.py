from flask import request, jsonify, current_app, send_file, after_this_request
import tempfile
import subprocess
import shutil
import os
from datetime import datetime
import zipfile


def _ok(data, code=200):
    return {"ok": True, "data": data, "error": None}, code


def _fail(msg, code=400):
    return {"ok": False, "data": None, "error": msg}, code


def download_backup():
    """
    Genera un respaldo de MongoDB y lo devuelve como archivo descargable.

    Query params:
      - format: "gz" (default) o "zip"
    """
    fmt = (request.args.get("format") or "gz").lower()
    if fmt not in ("gz", "zip"):
        return jsonify(_fail("format debe ser 'gz' o 'zip'", 422)[0]), 422

    mongo_uri = current_app.config.get("MONGO_URI") or os.getenv("MONGO_URI")
    if not mongo_uri:
        return jsonify(_fail("MONGO_URI no configurada", 500)[0]), 500

    mongodump_bin = os.getenv("MONGODUMP_BIN") or shutil.which("mongodump")
    if not mongodump_bin:
        return jsonify(_fail("mongodump no encontrado en el PATH del servidor", 500)[0]), 500

    tmpdir = tempfile.mkdtemp(prefix="sigepren_dump_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    @after_this_request
    def _cleanup(response):
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
        return response

    try:
        if fmt == "gz":
            outfile = os.path.join(tmpdir, f"sigepren_backup_{ts}.gz")
            cmd = [
                mongodump_bin,
                f"--uri={mongo_uri}",
                f"--archive={outfile}",
                "--gzip",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not os.path.exists(outfile):
                err = proc.stderr.strip() or proc.stdout.strip() or "Error desconocido ejecutando mongodump"
                return jsonify(_fail(f"mongodump fallo: {err}", 500)[0]), 500
            return send_file(
                outfile,
                as_attachment=True,
                download_name=os.path.basename(outfile),
                mimetype="application/gzip",
            )
        else:  # zip
            outdir = os.path.join(tmpdir, "dump")
            os.makedirs(outdir, exist_ok=True)
            cmd = [
                mongodump_bin,
                f"--uri={mongo_uri}",
                f"--out={outdir}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip() or "Error desconocido ejecutando mongodump"
                return jsonify(_fail(f"mongodump fallo: {err}", 500)[0]), 500

            zip_path = os.path.join(tmpdir, f"sigepren_backup_{ts}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(outdir):
                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, outdir)
                        zf.write(full_path, rel_path)

            return send_file(
                zip_path,
                as_attachment=True,
                download_name=os.path.basename(zip_path),
                mimetype="application/zip",
            )
    except Exception as e:
        return jsonify(_fail(str(e), 500)[0]), 500
