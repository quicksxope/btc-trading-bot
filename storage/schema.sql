-- SQLite schema: users, presets, jobs, artifacts

CREATE TABLE IF NOT EXISTS users (
  telegram_id INTEGER PRIMARY KEY,
  username TEXT,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS presets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  config_yaml TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (telegram_id, name),
  FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  telegram_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  progress_pct REAL NOT NULL DEFAULT 0,
  progress_stage TEXT NOT NULL DEFAULT 'Queued',
  config_yaml TEXT NOT NULL,
  result_json TEXT,
  error_message TEXT,
  compare_job_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  finished_at TEXT,
  notify_on_done INTEGER NOT NULL DEFAULT 1,
  progress_message_id INTEGER,
  chat_id INTEGER,
  FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_telegram_status ON jobs(telegram_id, status);

CREATE TABLE IF NOT EXISTS job_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  path TEXT NOT NULL,
  FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS job_queue (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL UNIQUE,
  enqueued_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS indicator_favorites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_id INTEGER NOT NULL,
  name TEXT,
  indicators_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_favorites_user ON indicator_favorites(telegram_id);

CREATE TABLE IF NOT EXISTS studies (
  job_id TEXT PRIMARY KEY,
  telegram_id INTEGER NOT NULL,
  indicator_pool_json TEXT NOT NULL,
  instrument TEXT NOT NULL,
  primary_tf TEXT NOT NULL,
  date_from TEXT NOT NULL,
  date_to TEXT NOT NULL,
  prop_pack TEXT,
  mix_count INTEGER NOT NULL DEFAULT 0,
  pass_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT,
  FOREIGN KEY (job_id) REFERENCES jobs(id),
  FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS study_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  mix_label TEXT NOT NULL,
  mix_json TEXT NOT NULL,
  rank INTEGER NOT NULL,
  prop_pass INTEGER NOT NULL,
  net_pnl_pct REAL NOT NULL,
  result_json TEXT NOT NULL,
  FOREIGN KEY (job_id) REFERENCES studies(job_id)
);

CREATE INDEX IF NOT EXISTS idx_study_results_job ON study_results(job_id);
