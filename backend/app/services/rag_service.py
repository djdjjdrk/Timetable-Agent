import logging
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.common.exceptions import BusinessException

logger = logging.getLogger(__name__)


def extract_document_text(path: Path) -> str:
    """从支持的资料文件中提取纯文本，空内容或解析失败时抛出业务异常。"""
    # 数据库记录可能存在，但磁盘文件已被手动移走。
    if not path.is_file():
        raise BusinessException(message="资料文件不存在", code=404)
    ext = path.suffix.lower()
    try:
        # 文本文件直接读取；utf-8-sig 同时接受带 BOM 和不带 BOM 的 UTF-8。
        if ext in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8-sig")
        # PDF 按页提取文字，没有文字的页用空字符串连接。
        elif ext == ".pdf":
            with path.open("rb") as source:
                reader = PdfReader(source)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
        # DOCX 读取正文段落与表格单元格，不保留排版。
        elif ext == ".docx":
            doc = Document(str(path))
            parts = [p.text for p in doc.paragraphs]
            parts.extend(
                "\t".join(cell.text for cell in row.cells)
                for table in doc.tables
                for row in table.rows
            )
            text = "\n".join(parts)
        # 只处理已约定的四种格式，旧版 .doc 也不在范围内。
        else:
            raise BusinessException(message="不支持的文档格式", code=400)
    except BusinessException:
        raise
    except Exception as exc:
        logger.exception("提取文档文字失败：%s", path.name)
        raise BusinessException(
            message="无法读取文档，请确认文件未损坏、未加密，且文本文件采用 UTF-8 编码",
            code=400,
        ) from exc

    text = text.strip()
    # 空白文档或没有文字层的扫描件不能提供文字预览。
    if not text:
        raise BusinessException(
            message="未能抽取到文本，空白文档或扫描件无法预览", code=400
        )
    return text
