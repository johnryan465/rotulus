import sqlite3
import os

DB_PATH = "/home/john/rolls/rolls.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create rolls table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rolls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_num TEXT,
        date_str TEXT,
        title TEXT,
        manuscripts TEXT,
        pdf_source TEXT,
        pdf_pages TEXT,
        is_verified INTEGER DEFAULT 0
    )
    """)
    
    # Create tituli table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tituli (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_id INTEGER,
        title TEXT,
        latin_text TEXT,
        pdf_page INTEGER,
        pdf_half TEXT,
        FOREIGN KEY (roll_id) REFERENCES rolls (id) ON DELETE CASCADE
    )
    """)
    
    # Create footnotes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS footnotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_id INTEGER,
        pdf_page INTEGER,
        pdf_half TEXT,
        footnote_num TEXT,
        text TEXT,
        FOREIGN KEY (roll_id) REFERENCES rolls (id) ON DELETE CASCADE
    )
    """)
    
    # Create entities table
    cursor.execute("""
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
    )
    """)
    
    # Create spatial_regions table
    cursor.execute("""
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
    )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully at:", DB_PATH)

if __name__ == "__main__":
    init_db()
