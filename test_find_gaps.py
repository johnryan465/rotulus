import sqlite3
import re

DB_PATH = "rolls.db"

def find_gaps():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT roll_num FROM rolls")
    found = set()
    for (rn,) in cursor.fetchall():
        if "-" in str(rn):
            try:
                s, e = map(int, str(rn).split("-"))
                for n in range(s, e + 1): found.add(n)
            except: pass
        else:
            try: found.add(int(rn))
            except: pass
    
    missing = []
    for n in range(1, 146):
        if n not in found:
            missing.append(n)
            
    print(f"Missing Rolls: {missing}")
    
    # Try to find these numbers in raw text
    for n in missing:
        import subprocess
        print(f"\nSearching for Roll {n}:")
        cmd = f"grep -rE '^[nN][oO\\\"\\\'P]* {n}\\b' raw_text/ | head -n 1"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.stdout:
            print(f"  FOUND: {res.stdout.strip()}")
        else:
            print(f"  NOT FOUND in standard header format.")

if __name__ == "__main__":
    find_gaps()
