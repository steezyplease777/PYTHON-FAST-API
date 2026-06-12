import re
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.eanbc import UPCA
from reportlab.graphics.shapes import Drawing, Group, Rect, String
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


class LabelUPCA(UPCA):
    """UPC-A symbol tuned for retail labels: tall guard bars and digits that
    overlap the bottom of the data bars (standard UPC-A appearance)."""

    def draw(self):
        g = Group()
        g_add = g.add
        bar_width = self.barWidth
        width = self.width
        bar_height = self.barHeight
        x = self.x
        y = self.y
        g_add(Rect(x, y, width, bar_height, fillColor=None, strokeColor=None, strokeWidth=0))

        s = self.value + self._checkdigit(self.value)
        self._lquiet = lquiet = self._calc_quiet(self.lquiet)
        rquiet = self._calc_quiet(self.rquiet)
        b = [lquiet * "0", self._tail]
        append = b.append
        self._encode_left(s, append)
        append(self._sep)

        z = ord("0")
        _right = self._right
        for c in s[self._start_right :]:
            append(_right[ord(c) - z])
        append(self._tail)
        append(rquiet * "0")

        font_size = self.fontSize
        bar_fill = self.barFillColor
        bar_stroke_w = self.barStrokeWidth
        bar_stroke = self.barStrokeColor
        digit_gap = font_size * 0.5

        lrect = None
        for i, c in enumerate("".join(b)):
            if c == "1":
                dh = self._short_bar(i) and digit_gap or 0
                yh = y + dh
                if lrect and lrect.y == yh:
                    lrect.width += bar_width
                else:
                    lrect = Rect(
                        x,
                        yh,
                        bar_width,
                        bar_height - dh,
                        fillColor=bar_fill,
                        strokeWidth=bar_stroke_w,
                        strokeColor=bar_stroke,
                    )
                    g_add(lrect)
            else:
                lrect = None
            x += bar_width

        if self.humanReadable:
            self._add_human_readable(s, g_add)
        return g

    def _add_human_readable(self, s, g_add):
        bar_width = self.barWidth
        font_size = self.fontSize
        text_color = self.textColor
        font_name = self.fontName
        # Place the digits so their top half sits inside the shortened data-bar
        # zone while their bottom half drops below the barcode.
        y = self.y + font_size * -0.35

        g_add(String(
            self.x + bar_width * (self._lquiet - 7.5),
            y,
            s[0],
            fontName=font_name,
            fontSize=font_size,
            fillColor=text_color,
        ))

        x = self.x + (38 - 7.5 + self._lquiet) * bar_width
        g_add(String(x, y, s[1:6], fontName=font_name, fontSize=font_size, fillColor=text_color, textAnchor="middle"))

        x += 36 * bar_width
        g_add(String(x, y, s[6:11], fontName=font_name, fontSize=font_size, fillColor=text_color, textAnchor="middle"))

        x += 30.5 * bar_width
        g_add(String(x, y, s[11], fontName=font_name, fontSize=font_size, fillColor=text_color))


def _make_upca_drawing(upc: str, bar_width: float, bar_height: float, font_size: float) -> Drawing:
    code = LabelUPCA(
        value=upc[:11],
        barWidth=bar_width,
        barHeight=bar_height,
        fontSize=font_size,
        humanReadable=True,
    )
    # code.width covers bars/quiet zones only; rendered bounds also include
    # the outside first/check digits ReportLab draws beyond the bar block.
    _x0, _y0, x1, y1 = code.draw().getBounds()
    drawing = Drawing(x1, y1)
    drawing.add(code)
    return drawing


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

    pad = 8 * scale
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

    # --- Title, then ID and SKU lines, all bold black (kept compact so the
    # barcode gets the bulk of the vertical space) ---
    title_text, title_size = fit_text(title, "Helvetica-Bold", 8.5 * scale, 6 * scale, text_max_w)
    title_y = H - pad - title_size
    c.setFont("Helvetica-Bold", title_size)
    c.drawString(pad, title_y, title_text)

    line_size = 6.5 * scale
    id_prefix = "ID: "
    id_value, id_size = fit_text(product_id, "Helvetica", line_size, 5 * scale, text_max_w - stringWidth(id_prefix, "Helvetica-Bold", line_size))
    id_y = title_y - id_size - 2.5 * scale
    c.setFont("Helvetica-Bold", id_size)
    c.drawString(pad, id_y, id_prefix)
    c.setFont("Helvetica", id_size)
    c.drawString(pad + stringWidth(id_prefix, "Helvetica-Bold", id_size), id_y, id_value)

    sku_prefix = "SKU: "
    sku_value, sku_size = fit_text(sku, "Helvetica", line_size, 5 * scale, text_max_w - stringWidth(sku_prefix, "Helvetica-Bold", line_size))
    sku_y = id_y - sku_size - 2.5 * scale
    c.setFont("Helvetica-Bold", sku_size)
    c.drawString(pad, sku_y, sku_prefix)
    c.setFont("Helvetica", sku_size)
    c.drawString(pad + stringWidth(sku_prefix, "Helvetica-Bold", sku_size), sku_y, sku_value)

    # --- Bottom: dashed divider with MSRP row underneath ---
    msrp_size = 11 * scale
    msrp_y = pad * 0.4
    c.setFont("Helvetica-Bold", msrp_size)
    c.drawString(pad, msrp_y, "MSRP:")
    if msrp_text:
        c.setFont("Helvetica", msrp_size)
        c.drawRightString(W - pad, msrp_y, msrp_text)

    dash_y = msrp_y + msrp_size + 1 * scale
    c.setLineWidth(1 * scale)
    c.setDash(3 * scale, 1.5 * scale)
    c.line(pad, dash_y, W - pad, dash_y)
    c.setDash([])

    # --- Middle: UPC-A barcode between SKU and dashed divider ---
    area_top = sku_y - 6 * scale
    area_bottom = dash_y + -0.50 * scale
    barcode_area_h = area_top - area_bottom
    barcode_area_w = content_w

    # 107 modules covers the bar block plus the outside first/check digits.
    module_width = barcode_area_w / 120
    font_size = max(18 , 18 * scale)
    bar_height = barcode_area_h * 1

    barcode = _make_upca_drawing(upc, module_width, bar_height, font_size)

    bscale = min(barcode_area_w / barcode.width, barcode_area_h / barcode.height, .80)
    bx = (W - barcode.width * bscale) / 2
    by = area_bottom + (barcode_area_h - barcode.height * bscale) / 1

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
