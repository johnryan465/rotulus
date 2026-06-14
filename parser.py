import os
import re
import sqlite3
from database import get_db_connection

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def is_latin_text(text):
    if not text or len(text.strip()) < 15: return False
    fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von ", " une "}
    la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
    t = " " + text.lower() + " "
    fr_de = sum(t.count(w) for w in fr_de_stop_words)
    la = sum(t.count(w) for w in la_stop_words)
    return la > fr_de

def get_roll_numbers(line, expected_next, pdf_idx, line_idx):
    """
    Identifies a MAIN roll header.
    Returns list of numbers.
    """
    s = line.strip()
    if not s or "=== FOOTNOTES ===" in s: return None
    
    # 1. Page Headers (Running Headers) - IGNORE
    # Usually in first 2 lines of a page and very short
    if line_idx < 3 and re.match(r'^(?:N[oO°\?]*\s*)?\d+(?:\s*-\s*\d+)?\s*$', s):
        return None
    
    # PDF volume bounds
    bounds = {1: (1, 74), 2: (74, 105), 3: (106, 121), 4: (122, 200)}
    min_r, max_roll = bounds.get(pdf_idx, (1, 200))

    # Pattern: N° X-Y or N° X or standalone X
    m = re.match(r'^(?:N[oO°\?]*\s*)?(\d+)(?:\s*[\-\/]\s*(\d+))?', s)
    if m:
        nums = [int(m.group(1))]
        if m.group(2): nums.extend(range(int(m.group(1)) + 1, int(m.group(2)) + 1))
        
        # Validation: check if at least one number is in range and follows sequence
        if any(min_r <= n <= max_roll for n in nums):
            if any(expected_next - 2 <= n <= expected_next + 10 for n in nums):
                # Ensure it's not a titulus (no [X] immediately after)
                remainder = s[m.end():].strip()
                if not remainder.startswith("["):
                    return nums
                    
    return None

def get_titulus_info(line):
    s = line.strip()
    # "Num [Global] Date - Location"
    m = re.match(r'^(\d+)\s*\[(\d+)\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
    if m: return m.group(4).strip(" ."), s
    # "T. Location"
    if re.match(r'^T[T]?\.\s+([^0-9,;:\.\n\r]{3,40})', s):
        loc = s.split(".", 1)[1].split(".")[0].strip() if "." in s else s
        return loc, s
    return None, None

def parse_and_load():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS rolls")
    cursor.execute("""
        CREATE TABLE rolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_num TEXT UNIQUE,
            date_str TEXT, title TEXT, manuscripts TEXT, pdf_source TEXT, pdf_pages TEXT,
            is_verified INTEGER DEFAULT 0
        )
    """)
    cursor.execute("DELETE FROM tituli"); cursor.execute("DELETE FROM footnotes"); cursor.execute("DELETE FROM entities")
    
    files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.endswith(".txt") and "_full" not in f], key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    
    active_roll_id = None; expected_next = 1
    
    for fname in files:
        m = re.match(r'^pdf(\d+)_p(\d+)_(\w+)\.txt$', fname)
        if not m: continue
        pdf_idx, page, half = int(m.group(1)), int(m.group(2)), m.group(3)
        
        with open(os.path.join(RAW_TEXT_DIR, fname), "r") as f: lines = f.readlines()
        f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines
        
        i = 0
        while i < len(main_lines):
            line = main_lines[i].strip()
            
            # Check for New Roll
            r_nums = get_roll_numbers(main_lines[i], expected_next, pdf_idx, i)
            if r_nums:
                # Metadata extraction
                m_start = i
                title_parts = []
                ms_parts = []
                j = i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l: j += 1; continue
                    if get_titulus_info(l)[0] or is_latin_text(l) or get_roll_numbers(l, expected_next, pdf_idx, j): break
                    
                    if re.match(r'^[A-E]\.\s+|^Original\s+|^B\.\s+|^C\.\s+|^London;|^Paris;|^München;', l):
                        ms_parts.append(l)
                    else:
                        title_parts.append(l)
                    j += 1
                
                # If title was on the header line
                header_text = main_lines[i].strip()
                # Remove number prefix from header text for title
                header_clean = re.sub(r'^(?:N[oO°\?]*\s*)?[\d\s\-\/]+', '', header_text).strip()
                if header_clean: title_parts.insert(0, header_clean)

                # Create roll entries (handle ranges)
                for n in r_nums:
                    n_s = str(n)
                    cursor.execute("INSERT OR IGNORE INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (n_s, "S.d.", " ".join(title_parts), " ".join(ms_parts), f"Dufour T1 ({pdf_idx})", str(page)))
                
                # Set active roll to the LAST one in the range
                cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (str(r_nums[-1]),))
                active_roll_id = cursor.fetchone()[0]
                expected_next = max(r_nums) + 1
                i = j; continue
            
            # Check for Titulus
            if active_roll_id:
                loc, h_text = get_titulus_info(main_lines[i])
                if loc:
                    text_parts = []
                    j = i + 1
                    while j < len(main_lines):
                        l = main_lines[j].strip()
                        if not l or "=== FOOTNOTES ===" in l: j += 1; continue
                        if get_titulus_info(l)[0] or get_roll_numbers(l, expected_next, pdf_idx, j): break
                        text_parts.append(l); j += 1
                    cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (active_roll_id, h_text[:100], loc, " ".join(text_parts), page, half))
                    i = j; continue
            i += 1
            
        # Update PDF pages for ALL rolls currently active in this range
        if active_roll_id:
            # Re-find the roll_num for active_roll_id
            cursor.execute("SELECT roll_num FROM rolls WHERE id = ?", (active_roll_id,))
            r_num_curr = cursor.fetchone()[0]
            cursor.execute("SELECT pdf_pages FROM rolls WHERE roll_num = ?", (r_num_curr,))
            rp_row = cursor.fetchone()
            if rp_row:
                pl = [p.strip() for p in rp_row[0].split(",") if p.strip()]
                if str(page) not in pl:
                    pl.append(str(page)); cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE roll_num = ?", (",".join(pl), r_num_curr))
                    
        # Footnotes
        if f_idx != -1 and active_roll_id:
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip()
                if not fn_s: continue
                fm = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                fn_num = re.findall(r'\d+', fm.group(1))[0] if fm and re.findall(r'\d+', fm.group(1)) else str(idx)
                cursor.execute("INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text) VALUES (?, ?, ?, ?, ?)", 
                             (active_roll_id, page, half, fn_num, fm.group(2) if fm else fn_s))

    conn.commit(); conn.close(); print("Sequence integrity established.")

if __name__ == "__main__":
    parse_and_load()
