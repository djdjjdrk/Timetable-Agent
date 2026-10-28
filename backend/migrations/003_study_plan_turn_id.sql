-- PostgreSQL；项目实际表名为 study_plans。已有业务数据保持不变。
BEGIN;

ALTER TABLE study_plans ADD COLUMN IF NOT EXISTS turn_id VARCHAR(32) NULL;
COMMENT ON COLUMN study_plans.turn_id IS 'MCP对话轮次ID';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'study_plans'::regclass
          AND conname = 'uq_study_plan_user_turn'
    ) THEN
        ALTER TABLE study_plans ADD CONSTRAINT uq_study_plan_user_turn
            UNIQUE (user_id, turn_id);
    END IF;
END $$;

COMMIT;
