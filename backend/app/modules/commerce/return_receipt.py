"""Printable, non-fiscal proof of an inspected return and its settlement."""

from io import BytesIO
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def return_receipt_pdf(receipt: dict, sale_id: int, branch: str, customer: str) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    story = []
    date_label = datetime.fromisoformat(receipt['fecha']).astimezone(timezone(timedelta(hours=-4))).strftime('%d/%m/%Y %H:%M')

    def paragraph(value: str, style: str = "BodyText") -> Paragraph:
        return Paragraph(escape(value), styles[style])

    story.extend([
        paragraph(f"Comprobante {receipt['comprobante']}", "Title"),
        paragraph("Cambio / devolución de prendas · constancia interna, no factura fiscal"),
        Spacer(1, 0.4 * cm),
        paragraph(f"Venta original: #{sale_id} · Sucursal: {branch}"),
        paragraph(f"Cliente: {customer} · Fecha: {date_label} (Bolivia)"),
        paragraph(f"Responsable: empleado #{receipt['id_empleado']}"),
        Spacer(1, 0.4 * cm),
    ])
    rows = [["Prenda devuelta", "Cantidad", "Importe reconocido", "Reemplazo"]]
    for line in receipt["items"]:
        replacement = (
            f"{line['producto']} · {line['talla']} / {line['color']} · Bs {line['importe_reemplazo']}"
            if "id_variante" in line else "Reembolso"
        )
        rows.append([
            paragraph(f"{line.get('producto_original', 'Prenda')} · {line.get('talla_original', '')} / {line.get('color_original', '')} · Variante #{line['id_variante_original']}"),
            str(line["cantidad"]), f"Bs {line['importe_original']}", paragraph(replacement),
        ])
    table = Table(rows, colWidths=[4 * cm, 2 * cm, 4 * cm, 7 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eceef1")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd0d6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([
        table, Spacer(1, 0.5 * cm),
        paragraph(f"Importe devuelto: Bs {receipt['importe_devuelto']}"),
        paragraph(f"Reemplazos: Bs {receipt['importe_reemplazos']}"),
        paragraph(f"Liquidación: {receipt['accion']} · Bs {receipt['monto']}", "Heading2"),
        paragraph(f"Medio registrado: {receipt.get('medio') or 'Sin diferencia'}"),
        paragraph(f"Referencia: {receipt.get('referencia') or '—'}"),
        paragraph(f"Notas de entrada: {', '.join(map(str, receipt['notas_entrada'])) or 'No apta para reingreso'}"),
        paragraph(f"Notas de salida: {', '.join(map(str, receipt['notas_salida'])) or 'No corresponde'}"),
        Spacer(1, 0.5 * cm),
        paragraph("El personal confirmó la inspección y la entrega del reemplazo o liquidación indicada. "
                  "Este registro no ejecuta transferencias bancarias ni reembolsos automáticos de la pasarela."),
    ])
    SimpleDocTemplate(buffer, rightMargin=2 * cm, leftMargin=2 * cm).build(story)
    return buffer.getvalue()
