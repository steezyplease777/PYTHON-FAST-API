import re

from pydantic import BaseModel, field_validator


class LabelPayload(BaseModel):
    token: str | None = None
    title: str = ""
    productId: str
    sku: str = ""
    upc: str
    msrp: float | None = None
    size: str = ""
    mode: str = "upload"
    supabase_bucket: str | None = None
    supabase_path: str | None = None

    @field_validator("msrp", mode="before")
    @classmethod
    def parse_msrp(cls, value):
        # Supports numbers as well as strings such as "$148.00".
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(re.sub(r"[$,\s]", "", str(value)))
        except ValueError:
            return None

    @field_validator("title", "sku", "size", mode="before")
    @classmethod
    def normalize_upper(cls, value):
        return str(value or "").strip().upper()

    @field_validator("productId", "upc", mode="before")
    @classmethod
    def normalize_trim(cls, value):
        return str(value or "").strip()


class BatchVariant(BaseModel):
    productId: str
    title: str = ""
    sku: str = ""
    upc: str
    msrp: float | None = None
    size: str = ""

    parse_msrp = field_validator("msrp", mode="before")(LabelPayload.parse_msrp.__func__)
    normalize_upper = field_validator("title", "sku", "size", mode="before")(LabelPayload.normalize_upper.__func__)
    normalize_trim = field_validator("productId", "upc", mode="before")(LabelPayload.normalize_trim.__func__)


class BatchPayload(BaseModel):
    token: str | None = None
    title: str = ""
    mode: str = "upload"
    supabase_bucket: str | None = None
    supabase_path: str | None = None
    variants: list[BatchVariant] = []

    normalize_upper = field_validator("title", mode="before")(LabelPayload.normalize_upper.__func__)
