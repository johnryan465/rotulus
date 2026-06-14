import os, re, sqlite3
from database import get_db_connection

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def is_latin_text(text):
    if not text or len(text.strip()) < 15: return False
    fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von "}
    la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
    t = " " + text.lower() + " "
    fr_de = sum(t.count(w) for w in fr_de_stop_words)
    la = sum(t.count(w) for w in la_stop_words)
    return la > fr_de

def get_main_roll_header(lines, i, expected_next):
    line = lines[i].strip()
    if not line or "=== FOOTNOTES ===" in line: return None, None
    m_n = re.match(r'^N[oO°\?]*\s*(\d+)\s*$', line)
    if m_n: 
        n = int(m_n.group(1))
        if expected_next - 2 <= n <= expected_next + 10: return n, i+1
    if line.isdigit() and len(line) < 5:
        n = int(line)
        if expected_next - 1 <= n <= expected_next + 1: return n, i+1
    return None, None

def find_tituli_in_line(line):
    headers = []
    forbidden = ["rouleau", "mortuaire", "original", "bibliothèque", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    def is_valid_loc(l):
        l_low = l.lower()
        if len(l) < 3 or len(l) > 40: return False
        if any(f in l_low for f in forbidden): return False
        if re.search(r'[\[\]\(\)]', l): return False
        return True
    p1 = r'(?:^|\.\s+)((\d+)\s*\[\d+\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,30}))'
    for m in re.finditer(p1, line):
        if is_valid_loc(m.group(4).strip(" .")): headers.append((m.start(1), m.end(1), m.group(4).strip(" .")))
    p2 = r'(?:^|\.\s+)((\d+)\s+(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,30}))'
    for m in re.finditer(p2, line):
        if int(m.group(2)) < 500 and is_valid_loc(m.group(4).strip(" .")): headers.append((m.start(1), m.end(1), m.group(4).strip(" .")))
    p3 = r'(?:^|\.\s+)(T[T]?\.\s+([^0-9,;:\.\n\r]{3,30}))'
    for m in re.finditer(p3, line):
        if is_valid_loc(m.group(2).strip(" .")): headers.append((m.start(1), m.end(1), m.group(2).strip(" .")))
    return sorted(headers, key=lambda x: x[0])

def parse_and_load():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS rolls")
    cursor.execute("CREATE TABLE rolls (id INTEGER PRIMARY KEY AUTOINCREMENT, roll_num INTEGER UNIQUE, date_str TEXT, title TEXT, manuscripts TEXT, pdf_source TEXT, pdf_pages TEXT, is_verified INTEGER DEFAULT 0)")
    cursor.execute("DELETE FROM tituli"); cursor.execute("DELETE FROM footnotes"); cursor.execute("DELETE FROM entities")
    files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.endswith(".txt") and "_full" not in f], key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    active_roll_id = None; expected_next = 1; current_pdf = None
    for fname in files:
        m = re.match(r'^pdf(\d+)_p(\d+)_(\w+)\.txt$', fname)
        if not m: continue
        pdf_idx, page, half = int(m.group(1)), int(m.group(2)), m.group(3)
        if pdf_idx != current_pdf:
            current_pdf = pdf_idx; expected_next = {1:1, 2:74, 3:106, 4:122}.get(pdf_idx, 1); active_roll_id = None
        with open(os.path.join(RAW_TEXT_DIR, fname), "r") as f: lines = f.readlines()
        f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines
        i = 0
        while i < len(main_lines):
            r_num, meta_start = get_main_roll_header(main_lines, i, expected_next)
            if r_num:
                expected_next = r_num + 1; title_parts = []; ms_parts = []; j = meta_start
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l or get_main_roll_header(main_lines, j, expected_next)[0] or find_tituli_in_line(l): break
                    if is_latin_text(l): break
                    if re.match(r'^[A-E]\.\s+|^Original\s+|^B\.\s+|^C\.\s+|^London;|^Paris;|^München;', l): ms_parts.append(l)
                    else: title_parts.append(l)
                    j += 1
                cursor.execute("INSERT OR IGNORE INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages) VALUES (?, ?, ?, ?, ?, ?)", (r_num, "S.d.", " ".join(title_parts), " ".join(ms_parts), f"Dufour T1 ({pdf_idx})", str(page)))
                cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (r_num,)); active_roll_id = cursor.fetchone()[0]; i = j; continue
            if active_roll_id:
                t_headers = find_tituli_in_line(main_lines[i])
                if t_headers:
                    for idx, (start, end, loc) in enumerate(t_headers):
                        next_h_start = t_headers[idx+1][0] if idx + 1 < len(t_headers) else len(main_lines[i])
                        text_lines = [main_lines[i][end:next_h_start].strip()]
                        if idx == len(t_headers) - 1:
                            j = i + 1
                            while j < len(main_lines):
                                l = main_lines[j].strip()
                                if not l or "=== FOOTNOTES ===" in l or find_tituli_in_line(l) or get_main_roll_header(main_lines, j, expected_next)[0]: break
                                text_lines.append(l); j += 1
                            cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", (active_roll_id, main_lines[i][start:end], loc, " ".join(text_lines), page, half)); i = j - 1
                        else: cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", (active_roll_id, main_lines[i][start:end], loc, " ".join(text_lines), page, half))
                    i += 1; continue
            i += 1
        if active_roll_id:
            cursor.execute("SELECT pdf_pages FROM rolls WHERE id = ?", (active_roll_id,))
            row = cursor.fetchone()
            if row:
                rp = row[0]; pl = [p.strip() for p in rp.split(",") if p.strip()]
                if str(page) not in pl: pl.append(str(page)); cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(pl), active_roll_id))
        if f_idx != -1 and active_roll_id:
            cursor.execute("SELECT id FROM rolls WHERE id = ?", (active_roll_id,))
            rid = cursor.fetchone()[0]
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip(); fm = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                if fm: cursor.execute("INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text) VALUES (?, ?, ?, ?, ?)", (rid, page, half, re.findall(r'\d+', fm.group(1))[0] if re.findall(r'\d+', fm.group(1)) else str(idx), fm.group(2)))
    conn.commit(); conn.close(); print("Re-parsing complete.")

if __name__ == "__main__":
    parse_and_load()
