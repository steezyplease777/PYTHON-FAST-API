import re
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdf_canvas

from app.config import (
    LABEL_WIDTH_PT,
    LABEL_HEIGHT_PT,
    GRAY_TEXT,
    GRAY_LINE,
)
from app.utils.errors import LabelError


def validate_upc(upc: str):
    if not re.fullmatch(r"\d{12}", upc):
        if not upc:
            raise LabelError(400, "UPC is required.")
        if not upc.isdigit():
            raise LabelError(400, "UPC must contain only digits.")
        raise LabelError(400, "UPC must be exactly 12 digits.")

    digits = [int(d) for d in upc]
    odd_sum = sum(digits[0:11:2])
    even_sum = sum(digits[1:11:2])
    check = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10

    if check != digits[11]:
        raise LabelError(
            400,
            f"Invalid UPC-A check digit: expected {check}, got {digits[11]}.",
        )


def fit_text(text: str, font_name: str, max_size: float, min_size: float, max_width: float) -> tuple[str, float]:
    """Shrink the font size until the text fits, then ellipsize as a last resort."""
    size = max_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.5

    if stringWidth(text, font_name, size) > max_width:
        text = ellipsize(text, font_name, size, max_width)

    return text, size


def ellipsize(text: str, font_name: str, size: float, max_width: float) -> str:
    if stringWidth(text, font_name, size) <= max_width:
        return text

    ellipsis = "…"
    while text and stringWidth(text + ellipsis, font_name, size) > max_width:
        text = text[:-1]

    return text + ellipsis if text else ellipsis


def draw_label(c, label: dict):
    """Draw one label on the current PDF page, matching the original
    Google Slides template: title/ID/SKU top-left, boxed size top-right,
    barcode centered, dashed divider and MSRP row at the bottom."""
    W, H = LABEL_WIDTH_PT, LABEL_HEIGHT_PT
    scale = H / (1.5 * inch)

    pad = 10 * scale
    content_w = W - 2 * pad

    title = label["title"]
    product_id = label["productId"]
    sku = label["sku"]
    upc = label["upc"]
    size_text = label["size"]
    msrp = label["msrp"]

    msrp_text = f"${msrp:,.2f}" if msrp is not None else ""

    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)

    # --- Size in a bold bordered box, top-right ---
    box_w = 0.0
    if size_text:
        box_font = 10 * scale
        text_w = stringWidth(size_text, "Helvetica-Bold", box_font)
        box_w = max(text_w + 10 * scale, 22 * scale)
        box_h = 17 * scale
        box_x = W - pad - box_w
        box_y = H - pad - box_h

        c.setLineWidth(1.8 * scale)
        c.rect(box_x, box_y, box_w, box_h)
        c.setFont("Helvetica-Bold", box_font)
        c.drawCentredString(box_x + box_w / 2, box_y + (box_h - box_font * 0.72) / 2, size_text)

    text_max_w = content_w - (box_w + 8 * scale if size_text else 0)

    # --- Title, then ID and SKU lines, all bold black ---
    title_text, title_size = fit_text(title, "Helvetica-Bold", 9.5 * scale, 6 * scale, text_max_w)
    title_y = H - pad - title_size
    c.setFont("Helvetica-Bold", title_size)
    c.drawString(pad, title_y, title_text)

    line_size = 7 * scale
    id_text, id_size = fit_text(f"ID: {product_id}", "Helvetica-Bold", line_size, 5 * scale, text_max_w)
    id_y = title_y - id_size - 3 * scale
    c.setFont("Helvetica-Bold", id_size)
    c.drawString(pad, id_y, id_text)

    sku_line, sku_size = fit_text(f"SKU: {sku}", "Helvetica-Bold", line_size, 5 * scale, text_max_w)
    sku_y = id_y - sku_size - 3 * scale
    c.setFont("Helvetica-Bold", sku_size)
    c.drawString(pad, sku_y, sku_line)

    # --- Bottom: dashed divider with MSRP row underneath ---
    msrp_size = 11 * scale
    msrp_y = pad * 0.6
    c.setFont("Helvetica-Bold", msrp_size)
    c.drawString(pad, msrp_y, "MSRP:")
    if msrp_text:
        c.drawRightString(W - pad, msrp_y, msrp_text)

    dash_y = msrp_y + msrp_size + 3 * scale
    c.setLineWidth(1.1 * scale)
    c.setDash(3 * scale, 2.5 * scale)
    c.line(pad, dash_y, W - pad, dash_y)
    c.setDash([])

    # --- Middle: vector UPC-A barcode centered between SKU and divider ---
    area_top = sku_y - 4 * scale
    area_bottom = dash_y + 4 * scale
    barcode_area_h = area_top - area_bottom
    barcode_area_w = content_w * 0.85

    # Size the symbol explicitly so it fills the label width like the classic
    # barcodeapi.org rendering: UPC-A is 95 modules wide plus ~9-module quiet
    # zones per side (~113 total). Sizing via barWidth instead of canvas
    # scaling keeps the bars wide and the digits large and legible.
    module_width = barcode_area_w / 113.0
    font_size = max(6.0, min(11.0, module_width * 8.5))

    # ReportLab's UPCA widget takes the first 11 digits and renders the
    # check digit itself (already validated to match upc[11]).
    barcode = createBarcodeDrawing(
        "UPCA",
        value=upc[:11],
        humanReadable=True,
        barWidth=module_width,
        barHeight=max(barcode_area_h - font_size * 1.1, 10),
        fontSize=font_size,
    )

    bscale = min(barcode_area_w / barcode.width, barcode_area_h / barcode.height, 1.0)
    bx = (W - barcode.width * bscale) / 2
    by = area_bottom + (barcode_area_h - barcode.height * bscale) / 2

    c.saveState()
    c.translate(bx, by)
    c.scale(bscale, bscale)
    renderPDF.draw(barcode, c, 0, 0)
    c.restoreState()


def generate_pdf(labels: list[dict]) -> bytes:
    """Generate an in-memory PDF with one label per page."""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=(LABEL_WIDTH_PT, LABEL_HEIGHT_PT), pageCompression=1)

    for label in labels:
        draw_label(c, label)
        c.showPage()

    c.save()
    return buffer.getvalue()
