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
from app.services.rag_service import (
    delete_by_doc_id,
    extract_document_text,
    get_vectorstore,
    ingest_kb_file,
)

logger = logging.getLogger(__name__)
DOC_EXTS = {".txt", ".md", ".pdf", ".docx"}


def _get_document_for_update(db: Session, doc_id: int) -> KbDocument:
    """锁定一份资料，避免删除和重新入库同时改写它的向量。"""
    row = db.scalar(select(KbDocument).where(KbDocument.id == doc_id).with_for_update())
    # 只有存在的资料才能进入后续向量操作，避免按无效 ID 清理。
    if row is None:
        raise BusinessException(message="文档不存在", code=404)
    return row


def list_documents(db: Session) -> list[KbDocumentResponse]:
    rows = db.scalars(select(KbDocument).order_by(KbDocument.id.desc())).all()
    return [KbDocumentResponse.model_validate(row) for row in rows]


def upload_documents(db: Session, files: list[UploadFile]) -> list[KbDocumentResponse]:
    """本批所有文件和向量都成功后才提交资料记录。"""
    if not files:
        raise BusinessException(message="请至少上传一个文件", code=400)

    saved_paths: list[Path] = []  # 本批创建的原文件，失败时逐个删除
    rows: list[KbDocument] = []  # 本批新增的记录，flush 后取得 ID 供向量标记
    names: set[str] = set()  # 本批已使用的原始文件名，防止批内重名
    commit_attempted = False  # 提交确认丢失时先核对数据库，再决定是否补偿
    try:
        for upload in files:
            original = Path(upload.filename or "").name
            # 原名用于展示和唯一约束，空名或超长名称不能入表。
            if not original or len(original) > 255:
                raise BusinessException(
                    message="文件名不能为空且不能超过 255 个字符", code=400
                )
            ext = Path(original).suffix.lower()
            # 前端 accept 只帮助选文件，后端仍要限制格式。
            if ext not in DOC_EXTS:
                raise BusinessException(
                    message="仅支持 .txt / .md / .pdf / .docx", code=400
                )
            exists = db.scalar(
                select(KbDocument.id).where(KbDocument.original_name == original)
            )
            # 同一批或此前已上传的文件都不能覆盖。
            if original in names or exists is not None:
                raise BusinessException(message=f"已存在同名文档：{original}", code=400)
            names.add(original)

            disk_name = f"{uuid.uuid4().hex}{ext}"
            path = KB_DIR / disk_name
            size = 0
            with path.open("xb") as target:
                saved_paths.append(path)
                while True:
                    chunk = upload.file.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    # 用实际读取的字节数判断上限，超过后交给统一清理分支。
                    if size > MAX_FILE_SIZE:
                        raise BusinessException(
                            message="单个文件不能超过 100 MiB", code=400
                        )
                    target.write(chunk)
            # 零字节文件无法提取资料文字，也不能让本批部分成功。
            if size == 0:
                raise BusinessException(message=f"文件不能为空：{original}", code=400)

            row = KbDocument(
                original_name=original,
                disk_name=disk_name,
                rel_path=disk_name,
                size=size,
                ext=ext,
                ingested=False,
            )
            db.add(row)
            rows.append(row)

        # flush 取得每份资料的 ID；数据库事务此时还没有提交。
        db.flush()
        for row in rows:
            path = document_path(row.rel_path)
            ingest_kb_file(path, source=row.original_name, doc_id=row.id)
            row.ingested = True
        db.flush()
        result = [KbDocumentResponse.model_validate(row) for row in rows]
        commit_attempted = True
        db.commit()
        return result
    except Exception as exc:
        cleanup_failed = False  # 记录数据库、向量或文件是否有未清理项
        try:
            db.rollback()
        except Exception:
            cleanup_failed = True
            logger.exception("回滚本批资料记录失败")
        if commit_attempted:
            try:
                # COMMIT 可能已经落库；新会话核对，避免删掉已提交记录的文件和向量。
                with Session(bind=db.get_bind()) as verify_db:
                    committed = verify_db.execute(
                        select(KbDocument.id, KbDocument.ingested).where(
                            KbDocument.id.in_([row.id for row in rows])
                        )
                    ).all()
            except Exception:
                logger.exception("核对本批提交结果失败")
                raise BusinessException(
                    message="上传状态不确定，请查看后端日志", code=500
                ) from exc
            if len(committed) == len(rows) and all(
                ingested for _, ingested in committed
            ):
                return result
            if committed or cleanup_failed:
                raise BusinessException(
                    message="上传状态不确定，请查看后端日志", code=500
                ) from exc
        # 即使某次 add_texts 中途失败，也尝试清理对应 doc_id 的残留片段。
        for row in rows:
            if row.id is None:
                continue
            try:
                delete_by_doc_id(row.id)
            except Exception:
                cleanup_failed = True
                logger.exception("回滚本批向量失败，doc_id=%s", row.id)
        for path in saved_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
                logger.exception("清理本批原文件失败：%s", path)
        # 清理本身失败时不能向管理员声称整批已经撤销。
        if cleanup_failed:
            raise BusinessException(
                message="上传失败且清理未完成，请查看后端日志", code=500
            ) from exc
        if isinstance(exc, BusinessException):
            raise
        logger.exception("批量上传并入库失败")
        raise BusinessException(
            message="上传并入库失败，请查看后端日志", code=500
        ) from exc


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
    """先清理向量和记录，确认删除已提交后再清理原文件。"""
    row = _get_document_for_update(db, doc_id)
    path = document_path(row.rel_path)
    vectors_deleted = False  # 向量已清理但后续删除失败时修正列表状态
    db_write_attempted = False  # 数据库写入失败后要回滚再取得行锁
    try:
        # 向量清理失败就停止，避免留下没有原文件可恢复的片段。
        delete_by_doc_id(row.id)
        vectors_deleted = True
        db_write_attempted = True
        db.delete(row)
        db.commit()
    except Exception as exc:
        if db_write_attempted:
            try:
                db.rollback()
                # COMMIT 可能已经成功；允许查不到记录，不能将此时报成文档不存在。
                row = db.scalar(
                    select(KbDocument).where(KbDocument.id == doc_id).with_for_update()
                )
            except Exception as verify_exc:
                db.rollback()
                logger.exception("核对删除结果失败，doc_id=%s", doc_id)
                raise BusinessException(
                    message="删除状态不确定，原文件已保留，请查看后端日志", code=500
                ) from verify_exc
        # 记录仍在表示删除未完成；保留原文件，修正状态后允许重新入库或再次删除。
        if row is not None:
            if vectors_deleted:
                try:
                    # 重新取得行锁后再清理，避免与另一请求的重新入库交错。
                    delete_by_doc_id(doc_id)
                    row.ingested = False
                    db.commit()
                except Exception as repair_exc:
                    db.rollback()
                    logger.exception("删除失败后修正向量或状态失败，doc_id=%s", doc_id)
                    raise BusinessException(
                        message="删除失败且清理未完成，原文件已保留，请查看后端日志",
                        code=500,
                    ) from repair_exc
            else:
                db.rollback()
            logger.exception("删除文档失败，doc_id=%s", doc_id)
            raise BusinessException(
                message="删除失败，原文件已保留，请查看后端日志", code=500
            ) from exc
        # 已确认记录不存在，继续清理原文件，与正常删除走同一出口。
    finally:
        # 关闭尚未提交的事务；成功提交后的调用不影响已落库结果。
        db.rollback()
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        # 记录已删除，页面无法再次操作；日志保留精确路径供管理员清理。
        logger.exception(
            "资料记录已删除但原文件清理失败，doc_id=%s，path=%s", doc_id, path
        )
        raise BusinessException(
            message="资料记录和向量已删除，但原文件清理失败，请查看后端日志", code=500
        ) from exc


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


def reingest_document(db: Session, doc_id: int) -> KbDocumentResponse:
    """清理旧片段，重新抽取已有原文件并入库。"""
    row = _get_document_for_update(db, doc_id)
    path = document_path(row.rel_path)
    db_write_attempted = False  # flush 或提交失败时先回滚，再重取行锁
    try:
        # 先删旧片段，避免每次重试都把同一份资料追加一遍。
        delete_by_doc_id(row.id)
        ingest_kb_file(path, source=row.original_name, doc_id=row.id)
        row.ingested = True
        db_write_attempted = True
        db.flush()
        result = KbDocumentResponse.model_validate(row)
        db.commit()
        return result
    except Exception as exc:
        if db_write_attempted:
            db.rollback()
            row = _get_document_for_update(db, doc_id)
        try:
            delete_by_doc_id(doc_id)
        except Exception:
            db.rollback()
            logger.exception("重新入库失败后清理残留向量失败，doc_id=%s", doc_id)
            raise BusinessException(
                message="重新入库失败且向量清理未完成，请查看后端日志", code=500
            ) from exc
        try:
            row.ingested = False
            db.commit()
        except Exception as status_exc:
            db.rollback()
            logger.exception("修正重新入库状态失败，doc_id=%s", doc_id)
            raise BusinessException(
                message="重新入库失败且状态未更新，请查看后端日志", code=500
            ) from status_exc
        if isinstance(exc, BusinessException):
            raise
        logger.exception("重新入库失败，doc_id=%s", doc_id)
        raise BusinessException(
            message="重新入库失败，请查看后端日志", code=500
        ) from exc
    finally:
        # 返回前关闭 Session 当前事务；异常路径兜底回滚。
        db.rollback()


def search_docs(query: str) -> dict:
    """检索最相近的 3 个片段，区分服务失败与没有可用片段。"""
    question = query.strip()
    # 空白问题没有可检索的含义，直接返回输入错误，不调用向量模型。
    if not question:
        return {"ok": False, "error": "检索问题不能为空", "items": []}
    try:
        # 问题向量与资料向量使用同一模型，最多取三个相近片段供模型判断依据。
        documents = get_vectorstore().similarity_search(question, k=3)
    except BusinessException as exc:
        return {"ok": False, "error": exc.message, "items": []}
    except Exception:
        logger.exception("检索课程资料失败")
        return {"ok": False, "error": "资料检索服务异常，请查看后端日志", "items": []}
    # 过滤空片段；只把回答需要的正文与来源交给 MCP，不暴露存储元数据。
    items = [
        {
            "content": document.page_content.strip(),
            "source": (document.metadata or {}).get("source", "未知来源"),
        }
        for document in documents
        if document.page_content.strip()
    ]
    # 请求成功但无可用正文，区别于前面捕获的配置或服务故障。
    if not items:
        return {"ok": True, "items": [], "message": "没有检索到资料片段"}
    return {"ok": True, "items": items}
