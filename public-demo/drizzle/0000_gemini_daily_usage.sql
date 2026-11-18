CREATE TABLE gemini_daily_usage (
  day TEXT PRIMARY KEY NOT NULL,
  requests INTEGER NOT NULL CHECK (requests >= 0)
);
