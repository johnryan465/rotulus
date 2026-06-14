import sqlite3
import sys

DB_PATH = "rolls.db"

def test_roll_sequence():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all individual roll numbers (expanding ranges for the test)
    cursor.execute("SELECT roll_num FROM rolls")
    rows = cursor.fetchall()
    
    found_nums = set()
    for (raw_num,) in rows:
        if "-" in str(raw_num):
            start, end = map(int, str(raw_num).split("-"))
            for n in range(start, end + 1):
                found_nums.add(n)
        else:
            try:
                found_nums.add(int(raw_num))
            except ValueError:
                continue
                
    if not found_nums:
        print("❌ Error: No rolls found in database.")
        sys.exit(1)
        
    min_roll = 1
    max_roll = max(found_nums)
    
    missing = []
    for n in range(min_roll, max_roll + 1):
        if n not in found_nums:
            missing.append(n)
            
    if missing:
        print(f"❌ Integrity Check Failed: Missing rolls in sequence: {missing}")
        print(f"Total found: {len(found_nums)} / Expected: {max_roll}")
        sys.exit(1)
    else:
        print(f"✅ Integrity Check Passed: Continuous sequence from {min_roll} to {max_roll} (Total: {len(found_nums)})")
        sys.exit(0)

if __name__ == "__main__":
    test_roll_sequence()
