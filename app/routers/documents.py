"""Tenant-scoped document metadata and immutable file versions."""
import hashlib, os, uuid
from urllib.parse import quote
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.audit import record_audit
from app.config import settings
from app.database import get_db
from app.models import Document, DocumentVersion, Contract, Membership
from app.permissions import Role, require_roles
from app.document_utils import safe_filename
from app.document_extraction import extract_text, suggest_fields, ExtractionError

router = APIRouter(prefix="/api/v1/documents", tags=["Документы"])
contract_router = APIRouter(prefix="/api/v1/contracts", tags=["Документы договоров"])
READ = (Role.DIRECTOR, Role.TENDER_SPECIALIST, Role.PROCUREMENT_MANAGER, Role.WAREHOUSE, Role.LOGISTICS, Role.ACCOUNTING)
WRITE = (Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/tiff", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/msword", "application/vnd.ms-excel"}
KINDS = {"contract", "addendum", "invoice", "waybill", "upd", "act", "specification", "other"}

def _version(v):
    return {"id": str(v.id), "version_number": v.version_number, "original_filename": v.original_filename, "media_type": v.media_type, "sha256": v.sha256, "size_bytes": v.size_bytes, "note": v.note, "created_at": v.created_at.isoformat()}

def _document(d, versions):
    return {"id": str(d.id), "contract_id": str(d.contract_id) if d.contract_id else None, "title": d.title, "document_kind": d.document_kind, "status": d.status, "created_at": d.created_at.isoformat(), "versions": [_version(v) for v in versions]}

async def _store_version(request: Request, doc: Document, actor: Membership, db: Session, filename: str, note: str):
    filename = safe_filename(filename)
    media = request.headers.get("content-type", "application/octet-stream").split(";")[0].lower()
    if media not in ALLOWED_TYPES: raise HTTPException(415, "Тип содержимого не поддерживается")
    max_bytes = settings.document_max_bytes
    length = request.headers.get("content-length")
    if length:
        try: declared_length = int(length)
        except ValueError: raise HTTPException(400, "Некорректный Content-Length")
        if declared_length < 0: raise HTTPException(400, "Некорректный Content-Length")
        if declared_length > max_bytes: raise HTTPException(413, "Файл превышает лимит 25 МБ")
    root = Path(settings.document_storage_path).resolve() / str(actor.company_id)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    key = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    final = root / key; temp = root / (key + ".part")
    digest = hashlib.sha256(); size = 0
    try:
        with temp.open("xb") as out:
            os.chmod(temp, 0o600)
            async for chunk in request.stream():
                if not chunk: continue
                size += len(chunk)
                if size > max_bytes: raise HTTPException(413, "Файл превышает лимит 25 МБ")
                digest.update(chunk); out.write(chunk)
        if size == 0: raise HTTPException(422, "Пустой файл загружать нельзя")
        os.replace(temp, final)
        last = db.query(DocumentVersion).filter(DocumentVersion.company_id == actor.company_id, DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc()).first()
        version = DocumentVersion(company_id=actor.company_id, document_id=doc.id, version_number=(last.version_number + 1 if last else 1), original_filename=filename, media_type=media, storage_key=str(final), sha256=digest.hexdigest(), size_bytes=size, note=note, uploaded_by_membership_id=actor.id)
        db.add(version); db.flush()
        record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="document.version_uploaded", entity_type="document", entity_id=str(doc.id), details={"version": version.version_number, "sha256": version.sha256, "size": size})
        db.commit(); return version
    except Exception:
        db.rollback()
        if temp.exists(): temp.unlink()
        if final.exists(): final.unlink()
        raise

@router.post("", status_code=201)
async def create_document(request: Request, title: str = Query(min_length=2, max_length=250), document_kind: str = Query(default="other"), contract_id: UUID | None = None, note: str = Query(default="", max_length=1000), actor: Membership = Depends(require_roles(*WRITE)), db: Session = Depends(get_db)):
    if document_kind not in KINDS: raise HTTPException(422, "Неизвестный вид документа")
    if contract_id and not db.query(Contract).filter(Contract.id == contract_id, Contract.company_id == actor.company_id).first(): raise HTTPException(404, "Договор не найден")
    filename = request.headers.get("x-file-name", "")
    if not filename: raise HTTPException(422, "Передайте имя файла в заголовке X-File-Name")
    doc = Document(company_id=actor.company_id, contract_id=contract_id, title=title.strip(), document_kind=document_kind, created_by_membership_id=actor.id)
    db.add(doc); db.flush()
    try:
        v = await _store_version(request, doc, actor, db, filename, note)
        return _document(doc, [v])
    except Exception:
        db.rollback(); raise

@router.get("")
def list_documents(contract_id: UUID | None = None, document_kind: str | None = None, actor: Membership = Depends(require_roles(*READ)), db: Session = Depends(get_db)):
    q = db.query(Document).filter(Document.company_id == actor.company_id, Document.status == "active")
    if contract_id: q = q.filter(Document.contract_id == contract_id)
    if document_kind: q = q.filter(Document.document_kind == document_kind)
    result=[]
    for d in q.order_by(Document.created_at.desc()).limit(500).all():
        vs = db.query(DocumentVersion).filter(DocumentVersion.company_id == actor.company_id, DocumentVersion.document_id == d.id).order_by(DocumentVersion.version_number.desc()).all()
        result.append(_document(d, vs))
    return result

@router.post("/{document_id}/versions", status_code=201)
async def add_version(document_id: UUID, request: Request, note: str = Query(default="", max_length=1000), actor: Membership = Depends(require_roles(*WRITE)), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.company_id == actor.company_id, Document.status == "active").with_for_update().first()
    if not doc: raise HTTPException(404, "Документ не найден")
    filename = request.headers.get("x-file-name", "")
    if not filename: raise HTTPException(422, "Передайте имя файла в заголовке X-File-Name")
    v = await _store_version(request, doc, actor, db, filename, note)
    return _document(doc, [v])

@contract_router.get("/{contract_id}/documents")
def contract_documents(contract_id: UUID, actor: Membership = Depends(require_roles(*READ)), db: Session = Depends(get_db)):
    if not db.query(Contract.id).filter(Contract.id == contract_id, Contract.company_id == actor.company_id).first(): raise HTTPException(404, "Договор не найден")
    docs = db.query(Document).filter(Document.company_id == actor.company_id, Document.contract_id == contract_id, Document.status == "active").order_by(Document.created_at.desc()).all()
    return [_document(d, db.query(DocumentVersion).filter(DocumentVersion.company_id == actor.company_id, DocumentVersion.document_id == d.id).order_by(DocumentVersion.version_number.desc()).all()) for d in docs]


@router.get("/{document_id}/versions/{version_id}/download")
def download_document_version(document_id: UUID, version_id: UUID, actor: Membership = Depends(require_roles(*READ)), db: Session = Depends(get_db)):
    """Download an immutable version after tenant, relationship and integrity checks."""
    row = (db.query(DocumentVersion, Document)
           .join(Document, (Document.id == DocumentVersion.document_id) & (Document.company_id == DocumentVersion.company_id))
           .filter(DocumentVersion.id == version_id, DocumentVersion.document_id == document_id,
                   DocumentVersion.company_id == actor.company_id, Document.company_id == actor.company_id,
                   Document.status == "active")
           .first())
    if not row:
        raise HTTPException(404, "Документ или версия не найдены")
    version, doc = row
    root = Path(settings.document_storage_path).resolve() / str(actor.company_id)
    candidate = Path(version.storage_key)
    if candidate.is_symlink():
        raise HTTPException(404, "Файл документа не найден")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        raise HTTPException(404, "Файл документа не найден")
    if not resolved.is_file() or resolved.is_symlink():
        raise HTTPException(404, "Файл документа не найден")
    digest = hashlib.sha256()
    size = 0
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if size != version.size_bytes or digest.hexdigest() != version.sha256:
        record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                     action="document.integrity_check_failed", entity_type="document_version",
                     entity_id=str(version.id), outcome="failure",
                     details={"document_id": str(doc.id), "version": version.version_number})
        db.commit()
        raise HTTPException(409, "Целостность файла нарушена. Скачивание заблокировано")
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="document.version_downloaded", entity_type="document_version",
                 entity_id=str(version.id), details={"document_id": str(doc.id), "version": version.version_number})
    db.commit()
    encoded_name = quote(version.original_filename)
    return FileResponse(
        path=str(resolved), media_type=version.media_type,
        filename=version.original_filename,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                 "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.post("/{document_id}/versions/{version_id}/extract")
def extract_document_version(document_id: UUID, version_id: UUID, actor: Membership = Depends(require_roles(*READ)), db: Session = Depends(get_db)):
    """Extract searchable text and field candidates; human confirmation is mandatory."""
    row = (db.query(DocumentVersion, Document)
           .join(Document, (Document.id == DocumentVersion.document_id) & (Document.company_id == DocumentVersion.company_id))
           .filter(DocumentVersion.id == version_id, DocumentVersion.document_id == document_id,
                   DocumentVersion.company_id == actor.company_id, Document.company_id == actor.company_id,
                   Document.status == "active").first())
    if not row:
        raise HTTPException(404, "Документ или версия не найдены")
    version, doc = row
    root = (Path(settings.document_storage_path).resolve() / str(actor.company_id)).resolve()
    candidate = Path(version.storage_key)
    try:
        if candidate.is_symlink(): raise ValueError()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file() or resolved.is_symlink(): raise ValueError()
    except (OSError, ValueError):
        raise HTTPException(404, "Файл документа не найден")
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != version.sha256 or resolved.stat().st_size != version.size_bytes:
        record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="document.integrity_check_failed", entity_type="document_version", entity_id=str(version.id), outcome="failure", details={"document_id": str(doc.id), "operation": "extract"})
        db.commit()
        raise HTTPException(409, "Целостность файла нарушена. Обработка заблокирована")
    try:
        text, method = extract_text(resolved, version.media_type)
    except ExtractionError as exc:
        raise HTTPException(422, str(exc))
    duplicates = (db.query(DocumentVersion, Document)
                  .join(Document, (Document.id == DocumentVersion.document_id) & (Document.company_id == DocumentVersion.company_id))
                  .filter(DocumentVersion.company_id == actor.company_id, DocumentVersion.sha256 == version.sha256,
                          DocumentVersion.id != version.id, Document.status == "active")
                  .limit(20).all())
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="document.text_extracted", entity_type="document_version", entity_id=str(version.id), details={"document_id": str(doc.id), "method": method, "characters": len(text), "duplicate_count": len(duplicates)})
    db.commit()
    return {"document_id": str(doc.id), "version_id": str(version.id), "method": method,
            "text_available": bool(text), "text_preview": text[:12000],
            "truncated": len(text) > 12000, "suggested_fields": suggest_fields(text),
            "possible_duplicates": [{"document_id": str(d.id), "title": d.title, "kind": d.document_kind, "version_id": str(v.id), "version_number": v.version_number} for v, d in duplicates],
            "requires_human_confirmation": True,
            "notice": "Это извлечение текста, не OCR. Подсказки и совпадения не подтверждены; сверьте их с оригиналом."}
