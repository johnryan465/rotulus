import os
import json
import sqlite3
import shutil
import re

DB_PATH = "rolls.db"
OUTPUT_DIR = "public/api"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def export_data():
    """Exports SQLite data to public/api/ for static hosting."""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Export List of Rolls
    cursor.execute("SELECT * FROM rolls ORDER BY id")
    rolls = [dict(row) for row in cursor.fetchall()]
    with open(os.path.join(OUTPUT_DIR, "rolls.json"), "w") as f:
        json.dump(rolls, f, indent=2)

    # 2. Export Individual Roll Details (Tituli + Footnotes)
    roll_dir = os.path.join(OUTPUT_DIR, "rolls")
    os.makedirs(roll_dir, exist_ok=True)
    
    for roll in rolls:
        roll_id = roll['id']
        
        # Fetch Tituli with their Entities
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
        tituli = [dict(row) for row in cursor.fetchall()]
        for tit in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
            tit["entities"] = [dict(row) for row in cursor.fetchall()]
            
        # Fetch Footnotes
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (roll_id,))
        footnotes = [dict(row) for row in cursor.fetchall()]
            
        detail = {
            "roll": roll,
            "tituli": tituli,
            "footnotes": footnotes
        }
        
        with open(os.path.join(roll_dir, f"{roll_id}.json"), "w") as f:
            json.dump(detail, f, indent=2)

    # 3. Export Travel Data (Pre-calculated)
    # Replicating the logic from server.py to make it static
    cursor.execute("""
        SELECT e.*, r.roll_num, r.date_str 
        FROM entities e
        JOIN tituli t ON e.titulus_id = t.id
        JOIN rolls r ON t.roll_id = r.id
        WHERE e.location_name IS NOT NULL AND e.location_name != ''
    """)
    entities = cursor.fetchall()
    
    # Simple placeholder for travels (in a real scenario, we'd use a geocoding cache)
    # For now, exporting an empty structure or actual data if available
    travels_data = {}
    with open(os.path.join(OUTPUT_DIR, "travels.json"), "w") as f:
        json.dump(travels_data, f)

    conn.close()
    print(f"✅ Database exported to static JSON in {OUTPUT_DIR}")

if __name__ == "__main__":
    export_data()
