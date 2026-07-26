CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  created_at TEXT NOT NULL
);

INSERT INTO audit_log(actor, action, created_at)
VALUES ('commons-demo', 'migration-applied', CURRENT_TIMESTAMP);
