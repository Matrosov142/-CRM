"""Conservative text extraction and field suggestions for human review.
No OCR is performed: scanned images return an explicit unsupported-text result.
"""
from __future__ import annotations
import re, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_TEXT_CHARS = 200_000
MAX_ARCHIVE_FILES = 300
MAX_UNCOMPRESSED = 40 * 1024 * 1024

class ExtractionError(ValueError):
    pass

def _clean(text: str) -> str:
    text = text.replace('\x00', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text[:MAX_TEXT_CHARS].strip()

def _xml_text(data: bytes) -> str:
    root = ET.fromstring(data)
    return ' '.join(t.strip() for t in root.itertext() if t and t.strip())

def extract_text(path: Path, media_type: str) -> tuple[str, str]:
    """Return (text, method). Only parses allow-listed office/pdf formats."""
    if media_type == 'application/pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ExtractionError('Для извлечения текста из PDF требуется пакет pypdf') from exc
        try:
            reader = PdfReader(str(path), strict=True)
            if len(reader.pages) > 300:
                raise ExtractionError('В документе более 300 страниц')
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError('Не удалось прочитать PDF') from exc
        return _clean(text), 'pdf_text'
    if media_type in {
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }:
        try:
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                if len(infos) > MAX_ARCHIVE_FILES or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
                    raise ExtractionError('Содержимое офисного файла превышает безопасный лимит')
                names = set(zf.namelist())
                if media_type.endswith('wordprocessingml.document'):
                    if 'word/document.xml' not in names: raise ExtractionError('Некорректный DOCX')
                    text = _xml_text(zf.read('word/document.xml'))
                    return _clean(text), 'docx_xml'
                chunks=[]
                for name in sorted(n for n in names if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)):
                    chunks.append(_xml_text(zf.read(name)))
                if 'xl/sharedStrings.xml' in names:
                    chunks.insert(0, _xml_text(zf.read('xl/sharedStrings.xml')))
                return _clean('\n'.join(chunks)), 'xlsx_xml'
        except ExtractionError:
            raise
        except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as exc:
            raise ExtractionError('Некорректный офисный документ') from exc
    raise ExtractionError('Формат пока не поддерживает извлечение текста')

def suggest_fields(text: str) -> dict:
    """Heuristic candidates only; never authoritative or auto-posted."""
    patterns = {
        'inn': r'(?i)(?:ИНН\s*[:№]?\s*)(\d{10}|\d{12})',
        'kpp': r'(?i)(?:КПП\s*[:№]?\s*)(\d{9})',
        'document_number': r'(?i)(?:сч[её]т(?:а)?\s*[-№:]|УПД\s*[-№:]|накладн(?:ая|ой)\s*[-№:]|акт\s*[-№:]|№\s*)([А-ЯA-Z0-9][А-ЯA-Z0-9_./-]{0,39})',
        'date': r'(?<!\d)(\d{2}[.]\d{2}[.]\d{4})(?!\d)',
        'amount_candidates': r'(?<![\d.])(\d{1,3}(?:[ \u00a0]\d{3})*(?:[,.]\d{2}))(?![\d.]|[,.]\d{4}\b)',
        'vat_mentions': r'(?i)(без НДС|НДС\s*(?:0|5|7|10|20)\s*%|в том числе НДС)',
    }
    out={}
    for key, pattern in patterns.items():
        vals=[]
        for match in re.finditer(pattern, text):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.strip()
            if value not in vals: vals.append(value)
            if len(vals) == 10: break
        out[key]=vals
    return out
