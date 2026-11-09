from fastapi import HTTPException
from app.document_utils import safe_filename

def test_safe_filename_removes_path_traversal():
    assert safe_filename("../../договор №1.pdf") == "договор _1.pdf"

def test_safe_filename_rejects_executable():
    try: safe_filename("payload.exe")
    except HTTPException as exc: assert exc.status_code == 415
    else: assert False

def test_safe_filename_rejects_empty():
    try: safe_filename("../")
    except HTTPException as exc: assert exc.status_code == 422
    else: assert False
