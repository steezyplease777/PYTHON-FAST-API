import re
from urllib.parse import quote


def sanitize_sheet_name(name: str, used_names: set[str]) -> str:
    safe = str(name or "Sheet")
    for char in ['\\', '/', '?', '*', '[', ']', ':']:
        safe = safe.replace(char, "")
    safe = safe.strip() or "Sheet"
    safe = safe[:31]

    final_name = safe
    counter = 1

    while final_name in used_names:
        suffix = f"_{counter}"
        final_name = safe[: 31 - len(suffix)] + suffix
        counter += 1

    used_names.add(final_name)
    return final_name


def sanitize_path_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\- ]+", "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "UNKNOWN"


def normalize_combined_filename(title: str) -> str:
    return sanitize_path_part(str(title or "").strip().upper())


def encode_storage_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in str(path).split("/"))
