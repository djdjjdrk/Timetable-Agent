import logging
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import KB_DIR, MAX_FILE_SIZE
from app.models.kb_document import KbDocument
from app.schemas.document import DocumentPreviewResponse, KbDocumentResponse
from app.services.rag_service import extract_document_text

logger = logging.getLogger(__name__)
DOC_EXTS = {".txt", ".md", ".pdf", ".docx"}


def list_documents(db: Session) -> list[KbDocumentResponse]:
    rows = db.scalars(select(KbDocument).order_by(KbDocument.id.desc())).all()
    return [KbDocumentResponse.model_validate(row) for row in rows]


def upload_documents(db: Session, files: list[UploadFile]) -> list[KbDocumentResponse]:
    """同一请求中的文件全部成功后才提交；失败则清理本批文件。"""
    # 没有文件就没有可保存的记录，直接拒绝。
    if not files:
        raise BusinessException(message="请至少上传一个文件", code=400)

    saved_paths: list[Path] = []  # 本批创建的文件路径，失败时逐个删除
    rows: list[KbDocument] = []  # 本批新增的数据库记录，提交前转为响应数据
    names: set[str] = set()  # 本批已处理的原始文件名，用于检查批内重名
    try:
        for upload in files:
            original = Path(upload.filename or "").name
            # 文件名用于列表展示，空名称或过长名称不能写入表。
            if not original or len(original) > 255:
                raise BusinessException(
                    message="文件名不能为空且不能超过 255 个字符", code=400
                )
            ext = Path(original).suffix.lower()
            # 文件选择框的 accept 可被绕过，格式限制仍由后端执行。
            if ext not in DOC_EXTS:
                raise BusinessException(
                    message="仅支持 .txt / .md / .pdf / .docx", code=400
                )
            exists = db.scalar(
                select(KbDocument.id).where(KbDocument.original_name == original)
            )
            # names 检查本批重复，数据库查询检查此前已经上传的名称。
            if original in names or exists is not None:
                raise BusinessException(message=f"已存在同名文档：{original}", code=400)
            names.add(original)

            disk_name = f"{uuid.uuid4().hex}{ext}"
            path = KB_DIR / disk_name
            size = 0
            with path.open("xb") as target:
                # 只记录本次实际创建的文件，失败时不会删除旧资料。
                saved_paths.append(path)
                while True:
                    chunk = upload.file.read(64 * 1024)
                    # 读到空字节表示文件结束，此时才能结束写入。
                    if not chunk:
                        break
                    size += len(chunk)
                    # 按实际读取量限制单文件大小，超限时交给外层统一回滚。
                    if size > MAX_FILE_SIZE:
                        raise BusinessException(
                            message="单个文件不能超过 100 MiB", code=400
                        )
                    target.write(chunk)
            # 零字节文件没有资料内容，本批上传一起撤销。
            if size == 0:
                raise BusinessException(message=f"文件不能为空：{original}", code=400)

            row = KbDocument(
                original_name=original,
                disk_name=disk_name,
                rel_path=disk_name,
                size=size,
                ext=ext,
            )
            db.add(row)
            rows.append(row)

        # flush 执行 INSERT 并取得 ID，但尚未提交，仍可整批 rollback。
        db.flush()
        result = [KbDocumentResponse.model_validate(row) for row in rows]
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        for path in saved_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("清理本批上传文件失败：%s", path)
        # 输入错误保留具体提示；磁盘或数据库异常保留日志后返回统一提示。
        if isinstance(exc, BusinessException):
            raise
        logger.exception("批量上传文档失败")
        raise BusinessException(message="上传失败，请查看后端日志", code=500) from exc


def get_document(db: Session, doc_id: int) -> KbDocument:
    row = db.get(KbDocument, doc_id)
    # 预览与删除都必须先确认目标记录存在。
    if not row:
        raise BusinessException(message="文档不存在", code=404)
    return row


def document_path(rel_path: str) -> Path:
    path = (KB_DIR / rel_path).resolve()
    # 只允许读取、删除资料目录内的文件，不能让路径越过目录边界。
    if not path.is_relative_to(KB_DIR.resolve()):
        raise BusinessException(message="非法资料路径", code=400)
    return path


def delete_document(db: Session, doc_id: int) -> None:
    row = get_document(db, doc_id)
    path = document_path(row.rel_path)
    try:
        # 原文件已丢失时，仍允许管理员删除残留记录。
        path.unlink(missing_ok=True)
        db.delete(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("删除文档失败，doc_id=%s", doc_id)
        raise BusinessException(message="删除失败，请查看后端日志", code=500) from exc


def preview_document(db: Session, doc_id: int) -> DocumentPreviewResponse:
    row = get_document(db, doc_id)
    text = extract_document_text(document_path(row.rel_path))
    return DocumentPreviewResponse(
        id=row.id,
        original_name=row.original_name,
        ext=row.ext,
        text=text,
        char_count=len(text),
    )
