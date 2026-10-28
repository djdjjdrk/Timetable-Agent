from datetime import datetime
from pydantic import BaseModel, ConfigDict


class KbDocumentResponse(BaseModel):
    """上传结果和资料列表共用的资料记录。"""

    id: int
    original_name: str  # 上传时的文件名，供页面显示
    disk_name: str  # 为避免重名而生成的磁盘文件名
    rel_path: str  # 相对于 data/kb 的保存路径
    size: int  # 文件大小，单位为字节
    ext: str  # 小写扩展名，例如 .pdf
    ingested: bool  # 页面展示的入库状态；false 的旧资料可以重新入库
    create_time: datetime  # 资料记录的创建时间

    # 列表和上传服务返回 ORM 记录时，允许直接读取模型属性。
    model_config = ConfigDict(from_attributes=True)


class DocumentPreviewResponse(BaseModel):
    """预览接口返回的资料信息和抽取后的纯文本。"""

    id: int
    original_name: str
    ext: str
    text: str  # 从文件中抽取、用于页面预览的纯文本
    char_count: int  # text 的字符数，不是原文件的字节数
