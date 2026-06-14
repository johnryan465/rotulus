import sqlite3
import re

DB_PATH = "rolls.db"

def audit():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM rolls ORDER BY CAST(roll_num AS INTEGER)")
    rolls = cursor.fetchall()
    
    print(f"{'Num':<6} | {'Tituli':<6} | {'FNs':<4} | {'Pages':<15} | {'Issues'}")
    print("-" * 80)
    
    for r in rolls:
        r_id = r['id']
        r_num = r['roll_num']
        
        cursor.execute("SELECT COUNT(*) FROM tituli WHERE roll_id = ?", (r_id,))
        tit_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM footnotes WHERE roll_id = ?", (r_id,))
        fn_count = cursor.fetchone()[0]
        
        issues = []
        if tit_count == 0:
            issues.append("MISSING TITULI")
        if len(r['title']) > 300:
            issues.append("TITLE TOO LONG (OCR Noise?)")
        if r['pdf_pages'] == "0" or not r['pdf_pages']:
            issues.append("MISSING PAGE REF")
            
        print(f"{r_num:<6} | {tit_count:<6} | {fn_count:<4} | {r['pdf_pages']:<15} | {', '.join(issues)}")

    conn.close()

if __name__ == "__main__":
    audit()
