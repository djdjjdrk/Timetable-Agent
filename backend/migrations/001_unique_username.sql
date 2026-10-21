-- 执行前检查：如有重复账号，先人工处理，再添加约束。
SELECT username, COUNT(*) FROM users GROUP BY username HAVING COUNT(*) > 1;

ALTER TABLE users ADD CONSTRAINT uq_users_username UNIQUE (username);
