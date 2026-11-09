from pathlib import Path
from zipfile import ZipFile
import pytest
from app.document_extraction import extract_text, suggest_fields, ExtractionError

DOCX='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
XLSX='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def test_docx_text_extraction(tmp_path):
    p=tmp_path/'a.docx'
    with ZipFile(p,'w') as z:
        z.writestr('word/document.xml','''<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Счёт № АБ-123 ИНН 1234567890</w:t></w:r></w:p></w:body></w:document>''')
    text, method=extract_text(p,DOCX)
    assert 'АБ-123' in text and method=='docx_xml'

def test_xlsx_text_extraction(tmp_path):
    p=tmp_path/'a.xlsx'
    with ZipFile(p,'w') as z:
        z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c><v>Счёт</v></c><c><v>1250,00</v></c></row></sheetData></worksheet>''')
    text, method=extract_text(p,XLSX)
    assert '1250,00' in text and method=='xlsx_xml'

def test_field_suggestions_are_candidates():
    result=suggest_fields('ИНН 1234567890 КПП 123456789 Счёт № АБ-123 дата 08.11.2026 сумма 12 500,00 НДС 20%')
    assert result['inn']==['1234567890']
    assert result['kpp']==['123456789']
    assert result['document_number']==['АБ-123']
    assert result['date']==['08.11.2026']
    assert result['amount_candidates']==['12 500,00']
    assert result['vat_mentions']==['НДС 20%']

def test_unsupported_type_rejected(tmp_path):
    p=tmp_path/'x.png'; p.write_bytes(b'fake')
    with pytest.raises(ExtractionError): extract_text(p,'image/png')
