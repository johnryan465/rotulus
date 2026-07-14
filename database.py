import sqlite3
import os

DB_PATH = "/home/john/rolls/rolls.db"

# Canonical schema - this is the single source of truth. pipeline/orchestrator.py
# calls init_db() rather than maintaining its own copy of the schema.
SCHEMA = """
CREATE TABLE IF NOT EXISTS rolls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_num INTEGER UNIQUE,
    date_str TEXT,
    title TEXT,
    manuscripts TEXT,
    pdf_source TEXT,
    pdf_pages TEXT,
    is_verified INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tituli (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_id INTEGER,
    title TEXT,
    location_name TEXT,
    latin_text TEXT,
    pdf_page INTEGER,
    pdf_half TEXT,
    FOREIGN KEY (roll_id) REFERENCES rolls (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS footnotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_id INTEGER,
    pdf_page INTEGER,
    pdf_half TEXT,
    footnote_num TEXT,
    text TEXT,
    FOREIGN KEY (roll_id) REFERENCES rolls (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_id INTEGER,
    cited_work TEXT,
    cited_locator TEXT,
    raw_text TEXT,
    FOREIGN KEY (roll_id) REFERENCES rolls (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulus_id INTEGER,
    original_name TEXT,
    original_title TEXT,
    footnote_num TEXT,
    footnote_text TEXT,
    normalized_name TEXT,
    normalized_role TEXT,
    normalized_dates TEXT,
    location_name TEXT,
    FOREIGN KEY (titulus_id) REFERENCES tituli (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spatial_regions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_idx INTEGER,
    page_num INTEGER,
    half TEXT,
    region_type TEXT,
    x_min INTEGER,
    y_min INTEGER,
    x_max INTEGER,
    y_max INTEGER,
    text TEXT,
    confidence REAL
);

-- Tracks which (pdf_idx, page_num, half) pages have already been run through
-- the extraction pipeline, so a run can be safely resumed after an
-- interruption instead of always wiping and restarting from page 1.
CREATE TABLE IF NOT EXISTS processed_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_idx INTEGER,
    page_num INTEGER,
    half TEXT,
    status TEXT DEFAULT 'done',
    UNIQUE(pdf_idx, page_num, half)
);

-- Geocoding cache: resolves a raw location name (as it appears in the source
-- text) to coordinates, once. Deliberately NOT wiped by reset_db() - this is
-- a durable cache, not extraction output, so re-running the pipeline never
-- re-spends Wikidata lookups on names already resolved (or confirmed
-- unresolvable).
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_name TEXT UNIQUE,
    display_name TEXT,
    lat REAL,
    lon REAL,
    is_approximate INTEGER DEFAULT 0,
    source TEXT,
    wikidata_id TEXT,
    resolved_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

ALL_TABLES = ["processed_pages", "spatial_regions", "entities", "citations", "footnotes", "tituli", "rolls"]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn=None):
    """Create all tables if they don't already exist. Safe to call repeatedly."""
    owns_conn = conn is None
    conn = conn or sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    if owns_conn:
        conn.close()


def reset_db(conn=None):
    """Drop and recreate every table, consistently (previously rolls/tituli/
    footnotes were reset but entities/spatial_regions were left stale across runs)."""
    owns_conn = conn is None
    conn = conn or sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for table in ALL_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    init_db(conn)
    if owns_conn:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
