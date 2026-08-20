-- Outfits wardrobe schema. Applied idempotently at startup.

CREATE TABLE IF NOT EXISTS items (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  name              TEXT NOT NULL,
  category          TEXT NOT NULL,
  subcategory       TEXT,
  brand             TEXT,
  material          TEXT,
  pattern           TEXT,
  fit               TEXT,
  damage            TEXT NOT NULL DEFAULT 'none',
  takes_belt        INTEGER NOT NULL DEFAULT 1,
  colour_primary    TEXT,
  colour_secondary  TEXT,
  colour_palette    TEXT,
  warmth            INTEGER NOT NULL DEFAULT 5,
  formality         INTEGER NOT NULL DEFAULT 3,
  seasons           TEXT,
  wind_proof        INTEGER NOT NULL DEFAULT 0,
  water_proof       INTEGER NOT NULL DEFAULT 0,
  image_path        TEXT,
  thumb_path        TEXT,
  cutout_path       TEXT,
  status            TEXT NOT NULL DEFAULT 'clean',
  wears_since_wash  INTEGER NOT NULL DEFAULT 0,
  wash_after_wears  INTEGER,
  total_wears       INTEGER NOT NULL DEFAULT 0,
  last_worn         TEXT,
  last_washed       TEXT,
  notes             TEXT,
  ai_provider       TEXT,
  ai_confidence     REAL,
  is_active         INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_status   ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_active   ON items(is_active);

CREATE TABLE IF NOT EXISTS care_instructions (
  item_id        INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  wash_temp      INTEGER,
  wash_cycle     TEXT,
  hand_wash_only INTEGER NOT NULL DEFAULT 0,
  do_not_wash    INTEGER NOT NULL DEFAULT 0,
  tumble_dry     TEXT,
  iron_temp      TEXT,
  bleach         TEXT,
  dry_clean      TEXT,
  colour_group   TEXT,
  raw_symbols    TEXT,
  source         TEXT,
  notes          TEXT,
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outfits (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT NOT NULL,
  occasion     TEXT,
  notes        TEXT,
  is_favourite INTEGER NOT NULL DEFAULT 0,
  times_worn   INTEGER NOT NULL DEFAULT 0,
  last_worn    TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outfit_items (
  outfit_id INTEGER NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
  item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  layer     TEXT,
  PRIMARY KEY (outfit_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_outfit_items_item ON outfit_items(item_id);

CREATE TABLE IF NOT EXISTS wear_log (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  worn_on        TEXT NOT NULL,
  outfit_id      INTEGER REFERENCES outfits(id) ON DELETE SET NULL,
  occasion       TEXT,
  comfort_rating INTEGER,
  rating         INTEGER,
  temp_c         REAL,
  apparent_c     REAL,
  condition      TEXT,
  notes          TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_wear_log_date ON wear_log(worn_on);

CREATE TABLE IF NOT EXISTS wear_log_items (
  wear_log_id INTEGER NOT NULL REFERENCES wear_log(id) ON DELETE CASCADE,
  item_id     INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  PRIMARY KEY (wear_log_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_wear_log_items_item ON wear_log_items(item_id);

CREATE TABLE IF NOT EXISTS wash_batches (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  washed_on  TEXT NOT NULL,
  program    TEXT,
  temp_c     INTEGER,
  notes      TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wash_batch_items (
  batch_id INTEGER NOT NULL REFERENCES wash_batches(id) ON DELETE CASCADE,
  item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  PRIMARY KEY (batch_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_wash_batch_items_item ON wash_batch_items(item_id);

-- Extra categories an item also counts as, beyond items.category. The primary
-- one still decides its layer, wash defaults and how the outfit builder uses it,
-- because a garment can only occupy one slot in an outfit at a time.
CREATE TABLE IF NOT EXISTS item_categories (
  item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  PRIMARY KEY (item_id, category)
);
CREATE INDEX IF NOT EXISTS idx_item_categories_cat ON item_categories(category);

-- The categories a garment can be filed under. Seeded from the built-in set on
-- first run, then owned by the user: they can add their own and remove the ones
-- they do not wear. `layer` is the only field the outfit builder truly needs —
-- it decides which slot the garment fills — so a new category must pick one.
CREATE TABLE IF NOT EXISTS categories (
  key              TEXT PRIMARY KEY,
  label            TEXT NOT NULL,
  layer            TEXT NOT NULL,
  warmth           INTEGER NOT NULL DEFAULT 3,
  formality        INTEGER NOT NULL DEFAULT 3,
  wash_after_wears INTEGER NOT NULL DEFAULT 3,
  one_piece        INTEGER NOT NULL DEFAULT 0,
  takes_belt       INTEGER NOT NULL DEFAULT 0,
  fit_options      TEXT,
  is_builtin       INTEGER NOT NULL DEFAULT 0,
  sort_order       INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS item_tags (
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (item_id, tag_id)
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id    INTEGER REFERENCES items(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'queued',
  payload    TEXT,
  result     TEXT,
  error      TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- Comfort feedback accumulates here; the recommender reads it to learn the
-- wearer's personal warmth offset rather than assuming an average body.
CREATE TABLE IF NOT EXISTS comfort_feedback (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  wear_log_id  INTEGER REFERENCES wear_log(id) ON DELETE CASCADE,
  apparent_c   REAL NOT NULL,
  outfit_warmth REAL NOT NULL,
  verdict      INTEGER NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
