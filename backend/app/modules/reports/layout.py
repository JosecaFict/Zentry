from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from math import ceil
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xlsxwriter import Workbook

from app.modules.reports.branding import ReportBrand

INK = "#152235"
MUTED = "#4E6075"
PALE = "#F0F4F8"
WHITE = colors.white


@dataclass(frozen=True)
class ReportSection:
    title: str
    headers: list[str]
    rows: list[list]


@dataclass(frozen=True)
class ReportLayout:
    title: str
    brand: ReportBrand
    kind: str
    metrics: list[tuple[str, int | float | Decimal]]
    filters: list[tuple[str, object]]
    sections: list[ReportSection]
    insight: str | None = None


def _money_field(label: str) -> bool:
    return "(Bs)" in label


def _header_color(brand: ReportBrand) -> colors.Color:
    return colors.linearlyInterpolatedColor(
        colors.HexColor(INK), colors.HexColor(brand.accent), 0, 1, 0.36
    )


def _localized(value: object, label: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float, Decimal)):
        places = 2 if _money_field(label) or "(%)" in label else 0
        number = f"{value:,.{places}f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"Bs {number}" if _money_field(label) else number
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _logo_size(logo: ImageReader, width: float, height: float) -> tuple[float, float]:
    original_width, original_height = logo.getSize()
    scale = min(width / original_width, height / original_height)
    return original_width * scale, original_height * scale


def _style(name: str, size: float, color: str = INK, bold: bool = False, **kwargs):
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=size * 1.22,
        textColor=colors.HexColor(color),
        **kwargs,
    )


def _paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _pdf_section(section: ReportSection, width: float, heading_fill: colors.Color) -> Table:
    heading = _style("column", 8, "#FFFFFF", True)
    body = _style("cell", 8.5)
    numeric = _style("number", 8.5, alignment=TA_RIGHT)
    weights = {
        "Producto": 3.3,
        "Correo": 2.5,
        "Cliente": 1.8,
        "Sucursal": 1.75,
        "SKU": 1.5,
        "Posición": 0.75,
        "Talla": 0.65,
    }
    sizes = [weights.get(header, 1.2) for header in section.headers]
    rows = [[_paragraph(header, heading) for header in section.headers]]
    rows.extend(
        [
            _paragraph(
                _localized(value, header),
                numeric if isinstance(value, (int, float, Decimal)) else body,
            )
            for header, value in zip(section.headers, row, strict=True)
        ]
        for row in section.rows
    )
    if not section.rows:
        rows.append([_paragraph("Sin datos", body), *([""] * (len(section.headers) - 1))])
    table = Table(rows, colWidths=[width * size / sum(sizes) for size in sizes], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), heading_fill),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor(PALE)]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#DBE4ED")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def render_pdf(report: ReportLayout) -> bytes:
    output = BytesIO()
    pagesize = landscape(A4) if any(len(s.headers) > 6 for s in report.sections) else A4
    document = SimpleDocTemplate(
        output,
        pagesize=pagesize,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=report.title,
        author=report.brand.name,
    )
    width = document.width - 12
    logo = ImageReader(BytesIO(report.brand.logo)) if report.brand.logo else None
    accent = colors.HexColor(report.brand.accent)
    small = _style("small", 9, MUTED)
    title = _style("title", 23, bold=True)
    brand = _style("brand", 10, bold=True)
    section_style = _style("section", 13, bold=True, keepWithNext=True)
    generated = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    heading = [
        _paragraph(report.brand.name, brand),
        Spacer(1, 4),
        _paragraph(report.title, title),
        Spacer(1, 4),
        _paragraph(report.kind, small),
    ]
    if logo:
        logo_width, logo_height = _logo_size(logo, 82, 48)
        header = Table(
            [[Image(BytesIO(report.brand.logo), logo_width, logo_height), heading]],
            colWidths=[98, width - 98],
        )
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story = [header]
    else:
        story = list(heading)
    rule = Table([[""]], colWidths=[width], rowHeights=[3])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), accent)]))
    story.extend([Spacer(1, 9), rule, Spacer(1, 12)])

    if report.metrics:
        metric_rows = [
            [
                [
                    _paragraph(_localized(value, label), _style("metric", 16, bold=True)),
                    Spacer(1, 3),
                    _paragraph(label.replace(" (Bs)", ""), small),
                ]
                for label, value in report.metrics
            ]
        ]
        cards = Table(metric_rows, colWidths=[width / len(report.metrics)] * len(report.metrics))
        cards.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALE)),
                    ("LINEBEFORE", (0, 0), (0, 0), 2, accent),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.extend([cards, Spacer(1, 12)])
    if report.insight:
        story.extend([_paragraph(report.insight, _style("insight", 11, bold=True)), Spacer(1, 12)])
    if report.filters:
        filters = [
            [
                _paragraph(label, _style("filter label", 8, MUTED, True)),
                Spacer(1, 2),
                _paragraph(_localized(value), _style("filter value", 9)),
            ]
            for label, value in report.filters
        ]
        columns = min(3, len(filters))
        filters.extend([""] * (-len(filters) % columns))
        story.extend(
            [
                _paragraph("Filtros aplicados", section_style),
                Spacer(1, 3),
                Table(
                    [filters[i : i + columns] for i in range(0, len(filters), columns)],
                    colWidths=[width / columns] * columns,
                    style=[("VALIGN", (0, 0), (-1, -1), "TOP")],
                ),
                Spacer(1, 12),
            ]
        )
    for section in report.sections:
        story.extend(
            [
                _paragraph(section.title, section_style),
                Spacer(1, 5),
                _pdf_section(section, width, _header_color(report.brand)),
                Spacer(1, 12),
            ]
        )

    def draw_page(canvas, doc):
        page_width, _ = doc.pagesize
        if logo:
            w, h = _logo_size(logo, 185, 115)
            canvas.saveState()
            canvas.setFillAlpha(0.065)
            canvas.drawImage(
                logo,
                page_width - doc.rightMargin - w,
                doc.bottomMargin + 14,
                width=w,
                height=h,
                mask="auto",
            )
            canvas.restoreState()
        left, right = doc.leftMargin + 6, page_width - doc.rightMargin - 6
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.65)
        canvas.line(left, 36, right, 36)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(left, 24, f"Generado por Zentry · {generated}")
        canvas.drawRightString(right, 24, f"Página {doc.page}")

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()


def render_excel(report: ReportLayout) -> bytes:
    output = BytesIO()
    options = {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    with Workbook(output, options) as book:
        book.set_properties({"title": report.title, "company": report.brand.name})
        title = book.add_format(
            {"font_size": 21, "bold": True, "font_color": INK, "valign": "vcenter"}
        )
        company = book.add_format({"bold": True, "font_color": INK, "valign": "vcenter"})
        subtitle = book.add_format({"font_color": MUTED})
        bar = book.add_format({"bg_color": report.brand.accent})
        heading = book.add_format(
            {
                "bold": True,
                "bg_color": _header_color(report.brand).hexval().replace("0x", "#"),
                "font_color": "#FFFFFF",
                "valign": "vcenter",
            }
        )
        money_format = '"Bs " #,##0.00'
        number = book.add_format({"num_format": "#,##0"})
        money = book.add_format({"num_format": money_format})
        date_format = book.add_format({"num_format": "dd/mm/yyyy"})
        percent = book.add_format({"num_format": "0.00"})
        text = book.add_format({"font_color": INK, "text_wrap": True, "valign": "vcenter"})
        metric = {
            False: book.add_format(
                {
                    "bold": True,
                    "font_size": 18,
                    "font_color": INK,
                    "bg_color": PALE,
                    "num_format": "#,##0",
                }
            ),
            True: book.add_format(
                {
                    "bold": True,
                    "font_size": 18,
                    "font_color": INK,
                    "bg_color": PALE,
                    "num_format": money_format,
                }
            ),
        }
        metric_label = book.add_format({"font_color": MUTED, "bg_color": PALE})
        summary = book.add_worksheet("Resumen")
        summary.hide_gridlines(2)
        summary.set_tab_color(report.brand.accent)
        summary.set_column("A:A", 23)
        summary.set_column("B:H", 13)
        start_col = 0
        if report.brand.logo:
            logo = ImageReader(BytesIO(report.brand.logo))
            w, h = _logo_size(logo, 140, 56)
            original_w, original_h = logo.getSize()
            summary.insert_image(
                "A1",
                "logo.png",
                {
                    "image_data": BytesIO(report.brand.logo),
                    "x_scale": w / original_w,
                    "y_scale": h / original_h,
                    "x_offset": 6,
                    "y_offset": 5,
                    "description": f"Logo de {report.brand.name}",
                },
            )
            start_col = 1
        summary.set_row(0, 22)
        summary.set_row(1, 31)
        summary.merge_range(0, start_col, 0, 7, report.brand.name, company)
        summary.merge_range(1, start_col, 1, 7, report.title, title)
        summary.merge_range(2, start_col, 2, 7, report.kind, subtitle)
        summary.set_row(3, 3)
        summary.merge_range("A4:H4", "", bar)
        summary.merge_range(
            "A5:H5", f"Generado por Zentry · {datetime.now(UTC):%d/%m/%Y %H:%M} UTC", subtitle
        )
        row = 6
        for index, (label, value) in enumerate(report.metrics):
            if index and index % 3 == 0:
                row += 3
            col = (index % 3) * 2
            summary.set_row(row, 28)
            summary.merge_range(row, col, row, col + 1, value, metric[_money_field(label)])
            summary.merge_range(
                row + 1, col, row + 1, col + 1, label.replace(" (Bs)", ""), metric_label
            )
        if report.metrics:
            row += 3
        if report.insight:
            insight_style = book.add_format(
                {"bold": True, "font_color": INK, "text_wrap": True, "valign": "vcenter"}
            )
            summary.set_row(row, 33)
            summary.merge_range(row, 0, row, 7, report.insight, insight_style)
            row += 2
        if report.filters:
            summary.merge_range(row, 0, row, 7, "Filtros aplicados", heading)
            for filter_row, (label, value) in enumerate(report.filters, row + 1):
                summary.write(filter_row, 0, label, company)
                summary.merge_range(filter_row, 1, filter_row, 7, _localized(value), text)

        for section in report.sections:
            sheet = book.add_worksheet(section.title)
            sheet.hide_gridlines(2)
            sheet.set_tab_color(report.brand.accent)
            sheet.set_row(0, 24)
            sheet.freeze_panes(1, 0)
            column_widths = []
            for column, header in enumerate(section.headers):
                longest = max((len(str(row[column])) for row in section.rows), default=0)
                width = min(65, max(13, len(header) + 4, longest + 3))
                column_widths.append(width)
                sheet.set_column(column, column, width)
                sheet.write(0, column, header, heading)
            for index, row_values in enumerate(section.rows, 1):
                line_count = max(
                    ceil(len(str(value)) / max(width - 3, 1))
                    for value, width in zip(row_values, column_widths, strict=True)
                )
                sheet.set_row(index, max(18, 16 * line_count))
                for column, (header, value) in enumerate(
                    zip(section.headers, row_values, strict=True)
                ):
                    if isinstance(value, str) and header in {"Fecha", "Última compra"}:
                        try:
                            value = date.fromisoformat(value)
                        except ValueError:
                            pass
                    fmt = (
                        money
                        if _money_field(header)
                        else date_format
                        if isinstance(value, date)
                        else percent
                        if "(%)" in header
                        else number
                        if isinstance(value, (int, float, Decimal))
                        else text
                    )
                    sheet.write(index, column, value, fmt)
            sheet.autofilter(0, 0, len(section.rows), len(section.headers) - 1)
    return output.getvalue()
