from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.user import User
from app.services import document_service

# 路由统一使用 /documents 前缀，各接口仍分别声明管理员鉴权依赖。
router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.get(
    "",
    summary="获取文档列表",
    description="管理员查看全部课程资料，按 ID 倒序返回。",
)
def list_documents(
    _current_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(data=document_service.list_documents(db))


@router.post(
    "",
    summary="批量上传文档",
    description="管理员在一次请求中上传多个资料文件；任一文件失败则撤销本批上传。",
)
def upload_documents(
    files: Annotated[list[UploadFile], File(description="本批上传的资料文件")],
    _current_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(data=document_service.upload_documents(db, files))


@router.delete(
    "/{doc_id}",
    summary="删除文档",
    description="管理员根据文档 ID 删除资料记录及其保存的文件。",
)
def delete_document(
    doc_id: int,
    _current_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    document_service.delete_document(db, doc_id)
    return Response.success()


@router.get(
    "/{doc_id}/preview",
    summary="预览文档文本",
    description="管理员根据文档 ID 提取并查看资料中的纯文本。",
)
def preview_document(
    doc_id: int,
    _current_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(data=document_service.preview_document(db, doc_id))


@router.post(
    "/{doc_id}/reingest",
    summary="重新入库文档",
    description="管理员清理指定资料的旧向量片段并重新入库。",
)
def reingest_document(
    doc_id: int,
    _current_user: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(data=document_service.reingest_document(db, doc_id))
