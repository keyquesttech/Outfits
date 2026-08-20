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
  total_wears       INTEGER NOT NULL DEFAULT 0,
  last_worn         TEXT,
  notes             TEXT,
  ai_provider       TEXT,
  ai_confidence     REAL,
  is_active         INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_active   ON items(is_active);

CREATE TABLE IF NOT EXISTS outfits (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT NOT NULL,
  occasion     TEXT,
  notes        TEXT,
  -- A base is a partial outfit used as a starting point — trainers + joggers
  -- saved as "Gym", with the suggester filling in the rest around it.
  is_base      INTEGER NOT NULL DEFAULT 0,
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

-- Extra categories an item also counts as, beyond items.category. The primary
-- one still decides its layer and how the outfit builder uses it,
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

-- Past weather, one row per day and place. Back-dating a wear needs the weather
-- of that day, and the comfort calibration is only honest if it gets the real
-- one rather than today's temperature stamped on a week-old outfit. Cached
-- because a day that has already happened does not change.
CREATE TABLE IF NOT EXISTS weather_days (
  day        TEXT NOT NULL,
  lat        REAL NOT NULL,
  lon        REAL NOT NULL,
  temp_c     REAL,
  apparent_c REAL,
  rain_chance REAL,
  wind_kph   REAL,
  code       INTEGER,
  condition  TEXT,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (day, lat, lon)
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

-- Like/dislike verdicts on suggested outfits. Each row keeps the score
-- components the suggestion had at the moment it was judged — that snapshot is
-- the training example the taste model learns from.
CREATE TABLE IF NOT EXISTS suggestion_feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  verdict    INTEGER NOT NULL,             -- 1 liked, -1 disliked
  item_ids   TEXT NOT NULL,                -- JSON list of the outfit's items
  occasion   TEXT,
  apparent_c REAL,
  score      REAL,
  breakdown  TEXT NOT NULL,                -- JSON of the score components
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
