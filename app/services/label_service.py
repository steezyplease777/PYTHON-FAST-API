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
    """Draw one label on the current PDF page."""
    W, H = LABEL_WIDTH_PT, LABEL_HEIGHT_PT
    scale = H / (1.5 * inch)

    pad = 9 * scale
    content_w = W - 2 * pad

    title = label["title"]
    product_id = label["productId"]
    sku = label["sku"]
    upc = label["upc"]
    size_text = label["size"]
    msrp = label["msrp"]

    msrp_text = f"${msrp:,.2f}" if msrp is not None else ""

    # --- Top section: title + size, productId underneath ---
    size_font = 13 * scale
    size_w = stringWidth(size_text, "Helvetica-Bold", size_font) if size_text else 0

    title_max_w = content_w - (size_w + 8 * scale if size_text else 0)
    title_text, title_size = fit_text(title, "Helvetica-Bold", 10.5 * scale, 6.5 * scale, title_max_w)

    title_y = H - pad - title_size
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", title_size)
    c.drawString(pad, title_y, title_text)

    if size_text:
        c.setFont("Helvetica-Bold", size_font)
        c.drawRightString(W - pad, H - pad - size_font, size_text)

    pid_size = 5.5 * scale
    pid_text = ellipsize(product_id, "Helvetica", pid_size, content_w)
    pid_y = title_y - pid_size - 2.5 * scale
    c.setFillColor(GRAY_TEXT)
    c.setFont("Helvetica", pid_size)
    c.drawString(pad, pid_y, pid_text)

    divider1_y = pid_y - 4 * scale
    c.setStrokeColor(GRAY_LINE)
    c.setLineWidth(0.6)
    c.line(pad, divider1_y, W - pad, divider1_y)

    # --- Middle section: SKU + MSRP ---
    label_size = 5.5 * scale
    labels_y = divider1_y - label_size - 3.5 * scale
    c.setFillColor(GRAY_TEXT)
    c.setFont("Helvetica", label_size)
    c.drawString(pad, labels_y, "SKU")
    c.drawRightString(W - pad, labels_y, "MSRP")

    value_max = 8 * scale
    msrp_w = stringWidth(msrp_text, "Helvetica-Bold", value_max) if msrp_text else 0
    sku_max_w = content_w - (msrp_w + 10 * scale if msrp_text else 0)
    sku_text, sku_size = fit_text(sku, "Helvetica-Bold", value_max, 5.5 * scale, sku_max_w)

    values_y = labels_y - value_max - 2.5 * scale
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", sku_size)
    c.drawString(pad, values_y, sku_text)

    if msrp_text:
        c.setFont("Helvetica-Bold", value_max)
        c.drawRightString(W - pad, values_y, msrp_text)

    divider2_y = values_y - 4 * scale
    c.setStrokeColor(GRAY_LINE)
    c.line(pad, divider2_y, W - pad, divider2_y)

    # --- Bottom section: vector UPC-A barcode with human-readable digits ---
    barcode_area_h = divider2_y - pad
    barcode_area_w = content_w

    # ReportLab's UPCA widget takes the first 11 digits and renders the
    # check digit itself (already validated to match upc[11]).
    barcode = createBarcodeDrawing(
        "UPCA",
        value=upc[:11],
        humanReadable=True,
        barHeight=max(barcode_area_h * 0.62, 10),
    )

    bscale = min(barcode_area_w / barcode.width, barcode_area_h / barcode.height, 1.0)
    bx = (W - barcode.width * bscale) / 2
    by = pad + (barcode_area_h - barcode.height * bscale) / 2

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
