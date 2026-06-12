import os

from reportlab.lib import colors
from reportlab.lib.units import inch

# ---------- Supabase ----------
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_BUCKET = "excel-image-formatted-api"

# ---------- Auth ----------
API_TOKEN = os.environ.get("API_TOKEN", "")

# ---------- Excel export ----------
IMAGE_KEY = "product_image"

# Faster settings
IMAGE_EXPORT_SIZE = 180
DISPLAY_IMAGE_WIDTH = 80
DISPLAY_IMAGE_HEIGHT = 80

ROW_HEIGHT = 62
IMAGE_COL_WIDTH = 12

DEFAULT_COL_WIDTH = 16
TITLE_COL_WIDTH = 30
SKU_COL_WIDTH = 24
UPC_COL_WIDTH = 24

# ---------- UPC labels ----------
LABELS_DEFAULT_BUCKET = os.environ.get("LABELS_BUCKET", "labels")
LABEL_WIDTH_IN = float(os.environ.get("LABEL_WIDTH_IN", "3"))
LABEL_HEIGHT_IN = float(os.environ.get("LABEL_HEIGHT_IN", "1.5"))
MAX_BATCH_LABELS = int(os.environ.get("MAX_BATCH_LABELS", "500"))

LABEL_WIDTH_PT = LABEL_WIDTH_IN * inch
LABEL_HEIGHT_PT = LABEL_HEIGHT_IN * inch

GRAY_TEXT = colors.Color(0.45, 0.45, 0.45)
GRAY_LINE = colors.Color(0.8, 0.8, 0.8)
