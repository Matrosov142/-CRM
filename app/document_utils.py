import re
from pathlib import Path
from fastapi import HTTPException

ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx", ".xls", ".xlsx"}

def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._() -]", "_", name).strip(" .")
    if not name or len(name) > 255:
        raise HTTPException(422, "Некорректное имя файла")
    if Path(name).suffix.lower() not in ALLOWED_EXT:
        raise HTTPException(415, "Формат файла не поддерживается")
    return name
