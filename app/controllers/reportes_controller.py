from flask import jsonify, request, send_file
from io import BytesIO
from datetime import datetime, timezone, timedelta
import csv

# reportlab se importa de forma diferida dentro del handler PDF

from app.services.service_reportes import generar_resumen_panel, build_dashboard


def _to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        v = s.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        return _to_utc_naive(dt if dt.tzinfo else dt)
    except Exception:
        return None


def _month_range_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = _to_utc_naive(now or datetime.utcnow())
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    end = next_month - timedelta(microseconds=1)
    return start, end


def get_dashboard():
    try:
        start_iso = request.args.get("from") or request.args.get("start")
        end_iso = request.args.get("to") or request.args.get("end")
        data = generar_resumen_panel(start_iso=start_iso, end_iso=end_iso)
        return jsonify(data), 200
    except Exception as e:
        # Respuesta simple en caso de error inesperado
        return jsonify({
            "cards": {
                "pacientes_activos": {"value": 0, "suffix": "gestantes"},
                "citas_cumplidas": {"value": 0, "suffix": "%", "precision": 0},
                "alertas_generadas": {"value": 0, "suffix": "en seguimiento"},
            },
            "indicadores": {
                "altas": {"percent": 0},
                "medias": {"percent": 0},
                "alertas": {"percent": 0},
            },
            "error": str(e),
        }), 500


def get_dashboard_pdf():
    # Importar reportlab de forma diferida para no exigir la dependencia si no se usa
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    # Preparar rango de fechas para subtítulo y cálculo
    start_iso = request.args.get("from") or request.args.get("start")
    end_iso = request.args.get("to") or request.args.get("end")
    start_dt = _parse_iso_utc(start_iso)
    end_dt = _parse_iso_utc(end_iso)
    if start_dt is None or end_dt is None:
        start_dt, end_dt = _month_range_utc()

    # Obtener datos (misma lógica del dashboard)
    data = build_dashboard(start_iso=start_dt.isoformat() + "Z", end_iso=end_dt.isoformat() + "Z")

    # Crear PDF en memoria
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2 * cm
    y = height - margin

    # Encabezado
    try:
        logo_path = "app/Images/Ministerio de Salud.jpg"
        logo = ImageReader(logo_path)
        logo_w = 3.5 * cm
        c.drawImage(logo, margin, y - 2.5 * cm, width=logo_w, height=2.5 * cm, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    c.setFillColor(colors.HexColor("#01579B"))  # azul institucional
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y - 0.5 * cm, "Centro De Salud Jose Rubi")
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y - 1.2 * cm, "Reporte de Indicadores del Sistema Prenatal")

    # Subtítulo con fechas
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    rango_txt = f"Rango: {start_dt.strftime('%Y-%m-%d')}   {end_dt.strftime('%Y-%m-%d')}"
    generado_txt = f"Generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    c.drawCentredString(width / 2, y - 2.0 * cm, rango_txt)
    c.drawCentredString(width / 2, y - 2.6 * cm, generado_txt)

    y = y - 3.3 * cm

    # Tabla de métricas principales
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Métricas principales")
    y -= 0.6 * cm
    c.setFont("Helvetica", 11)
    cards = data.get("cards", {})
    c.drawString(margin, y, f"- Pacientes activos: {cards.get('pacientes_activos', {}).get('value', 0)} gestantes")
    y -= 0.5 * cm
    c.drawString(margin, y, f"- Citas cumplidas: {cards.get('citas_cumplidas', {}).get('value', 0)}%")
    y -= 0.5 * cm
    c.drawString(margin, y, f"- Alertas generadas: {cards.get('alertas_generadas', {}).get('value', 0)} en seguimiento")

    # Indicadores de riesgo
    y -= 1.0 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Indicadores de riesgo")
    y -= 0.6 * cm
    c.setFont("Helvetica", 11)
    indicadores = data.get("indicadores", {})
    c.drawString(margin, y, f"- Altas: {indicadores.get('altas', {}).get('percent', 0)}%")
    y -= 0.5 * cm
    c.drawString(margin, y, f"- Medias: {indicadores.get('medias', {}).get('percent', 0)}%")
    y -= 0.5 * cm
    c.drawString(margin, y, f"- Alertas: {indicadores.get('alertas', {}).get('percent', 0)}%")

    # Pie de página
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString(margin, margin + 1.2 * cm, "Firma o sello digital: _________________________________")
    c.setFillColor(colors.black)
    c.drawString(margin, margin + 0.6 * cm, "Sistema SIGEPREN – Ministerio de Salud de Nicaragua – Reporte generado automáticamente")

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"reporte_dashboard_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def get_dashboard_excel():
    # Preparar rango y datos
    start_iso = request.args.get("from") or request.args.get("start")
    end_iso = request.args.get("to") or request.args.get("end")
    start_dt = _parse_iso_utc(start_iso)
    end_dt = _parse_iso_utc(end_iso)
    if start_dt is None or end_dt is None:
        start_dt, end_dt = _month_range_utc()
    data = build_dashboard(start_iso=start_dt.isoformat() + "Z", end_iso=end_dt.isoformat() + "Z")

    # Construir CSV (compatible con Excel)
    buf = BytesIO()
    writer = csv.writer(buf)
    writer.writerow(["Reporte de Indicadores del Sistema Prenatal"])
    writer.writerow([f"Rango", start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d')])
    writer.writerow([f"Generado", datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')])
    writer.writerow([])
    writer.writerow(["Métricas principales"])    
    cards = data.get("cards", {})
    writer.writerow(["Pacientes activos", cards.get('pacientes_activos', {}).get('value', 0), "gestantes"])    
    writer.writerow(["Citas cumplidas (%)", cards.get('citas_cumplidas', {}).get('value', 0)])
    writer.writerow(["Alertas generadas (en seguimiento)", cards.get('alertas_generadas', {}).get('value', 0)])
    writer.writerow([])
    writer.writerow(["Indicadores de riesgo"]) 
    ind = data.get("indicadores", {})
    writer.writerow(["Altas", ind.get('altas', {}).get('percent', 0)])
    writer.writerow(["Medias", ind.get('medias', {}).get('percent', 0)])
    writer.writerow(["Alertas", ind.get('alertas', {}).get('percent', 0)])

    # Preparar respuesta
    buf.seek(0)
    filename = f"reporte_dashboard_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return send_file(
        BytesIO(buf.getvalue()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


def get_dashboard_json_download():
    start_iso = request.args.get("from") or request.args.get("start")
    end_iso = request.args.get("to") or request.args.get("end")
    start_dt = _parse_iso_utc(start_iso)
    end_dt = _parse_iso_utc(end_iso)
    if start_dt is None or end_dt is None:
        start_dt, end_dt = _month_range_utc()
    data = build_dashboard(start_iso=start_dt.isoformat() + "Z", end_iso=end_dt.isoformat() + "Z")

    # Enviar como descarga JSON
    from flask import json as flask_json
    payload = flask_json.dumps(data, ensure_ascii=False).encode("utf-8")
    filename = f"reporte_dashboard_{datetime.utcnow().strftime('%Y%m%d')}.json"
    return send_file(
        BytesIO(payload),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )
