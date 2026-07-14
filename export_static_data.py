import os
import sqlite3
import json
import shutil

from pipeline.geo import extract_year, get_roll_travels as _get_roll_travels

DB_PATH = "rolls.db"
OUTPUT_DIR = "public/api"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def get_roll_travels(conn, db_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (db_id,))
    row = cursor.fetchone()
    if not row: return []
    return _get_roll_travels(cursor, row)

def export_data():
    conn = get_db_connection(); cursor = conn.cursor()
    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR); roll_dir = os.path.join(OUTPUT_DIR, "rolls"); os.makedirs(roll_dir, exist_ok=True)
    
    cursor.execute("SELECT * FROM rolls ORDER BY CAST(roll_num AS INTEGER)")
    rolls = [dict(row) for row in cursor.fetchall()]
    all_travels = {}; rolls_with_stops = []

    for roll in rolls:
        db_id = roll['id']; r_num = roll['roll_num']
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (db_id,))
        tituli = [dict(row) for row in cursor.fetchall()]
        for tit in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
            tit["entities"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (db_id,))
        detail = {"roll": roll, "tituli": tituli, "footnotes": [dict(row) for row in cursor.fetchall()]}
        
        # KEY CHANGE: Filename is back to db_id for uniqueness across sources
        with open(os.path.join(roll_dir, f"{db_id}.json"), "w") as f: json.dump(detail, f, indent=2)

        travels = get_roll_travels(conn, db_id)
        num_stops = len([t for t in travels if t['type'] == 'stop'])

        # Individual travels.json per roll - matches server.py's live
        # /api/rolls/{id}/travels endpoint shape, which App.jsx's prod
        # build fetches when a single roll (not "all") is selected on the map.
        roll_travel_dir = os.path.join(roll_dir, str(db_id))
        os.makedirs(roll_travel_dir, exist_ok=True)
        with open(os.path.join(roll_travel_dir, "travels.json"), "w") as f: json.dump(travels, f, indent=2)
        year = extract_year(roll["date_str"])
        
        # KEY CHANGE: Key is back to db_id
        all_travels[db_id] = {"id": db_id, "roll_num": r_num, "title": roll["title"], "date_str": roll["date_str"], "year": year, "travels": travels, "num_stops": num_stops, "manuscripts": roll["manuscripts"]}
        
        roll_dict = dict(roll); roll_dict["num_stops"] = num_stops; roll_dict["year"] = year
        rolls_with_stops.append(roll_dict)

    with open(os.path.join(OUTPUT_DIR, "rolls.json"), "w") as f: json.dump(rolls_with_stops, f, indent=2)
    with open(os.path.join(OUTPUT_DIR, "travels.json"), "w") as f: json.dump(all_travels, f, indent=2)
    
    conn.close(); print(f"✅ Database exported to static JSON using ROLL_NUM as keys.")

if __name__ == "__main__":
    export_data()
