-- PostgreSQL：已有资料默认标记为尚未入库。
BEGIN;

ALTER TABLE kb_documents
    ADD COLUMN IF NOT EXISTS ingested BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN kb_documents.ingested IS '向量片段是否已写入 Chroma';

COMMIT;
