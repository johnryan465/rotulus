import os
import json
import sqlite3
import shutil

DB_PATH = "rolls.db"
OUTPUT_DIR = "public/api"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def export_data():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Export /api/rolls -> public/api/rolls.json
    cursor.execute("SELECT * FROM rolls ORDER BY id")
    rolls = [dict(row) for row in cursor.fetchall()]
    with open(os.path.join(OUTPUT_DIR, "rolls.json"), "w") as f:
        json.dump(rolls, f)

    # 2. Export /api/travels -> public/api/travels.json
    with open(os.path.join(OUTPUT_DIR, "travels.json"), "w") as f:
        json.dump({}, f)

    # 3. Export /api/rolls/{id} -> public/api/rolls/{id}.json
    roll_dir = os.path.join(OUTPUT_DIR, "rolls")
    os.makedirs(roll_dir, exist_ok=True)
    
    for roll in rolls:
        roll_id = roll['id']
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
        tituli = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (roll_id,))
        footnotes = [dict(row) for row in cursor.fetchall()]
        
        for tit in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
            tit["entities"] = [dict(row) for row in cursor.fetchall()]
            
        detail = {
            "roll": roll,
            "tituli": tituli,
            "footnotes": footnotes
        }
        
        with open(os.path.join(roll_dir, f"{roll_id}.json"), "w") as f:
            json.dump(detail, f)

    conn.close()
    print(f"Static data exported to {OUTPUT_DIR}")

if __name__ == "__main__":
    export_data()
