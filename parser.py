import os
import re
import sqlite3
from database import get_db_connection

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def is_latin_text(text, relaxed=False):
    if not text or len(text.strip()) < 10: return False
    fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von "}
    la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
    t = " " + text.lower() + " "
    fr_de = sum(t.count(w) for w in fr_de_stop_words)
    la = sum(t.count(w) for w in la_stop_words)
    if relaxed: return la > 0 or len(re.findall(r'[aeiou]{2,}', t)) > 2
    return la > fr_de

def extract_numbers(s):
    found = set()
    for start, end in re.findall(r'(\d+)\s*[\-\/]\s*(\d+)', s):
        found.update(range(int(start), int(end) + 1))
    for n in re.findall(r'\d+', s):
        n_val = int(n)
        if 0 < n_val <= 145: found.add(n_val)
    return sorted(list(found))

def parse_page_content(lines, expected_next, pdf_max):
    items = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or "=== FOOTNOTES ===" in line: continue
        
        # 1. Roll Header (Strict N prefix)
        m_roll = re.match(r'^[nN][oOsS\?]*[\*°>\.>e\"\'P]?s?[\s\?]*(\d+[\d\s\-\/\&\.\[\]]*)', line)
        if m_roll:
            nums = extract_numbers(m_roll.group(1))
            if any(expected_next - 2 <= n <= expected_next + 50 for n in nums) or expected_next <= 1:
                # Capture metadata (Title and Manuscripts)
                title_parts = [line[m_roll.end():].strip()]
                ms_parts = []
                j = i + 1
                while j < len(lines):
                    l = lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l: j += 1; continue
                    # Termination: next roll or titulus or Body text
                    if re.match(r'^[nN][oO\?]', l) or re.match(r'^\d+\s*\[\d+\]', l) or is_latin_text(l):
                        break
                    # Manuscript markers
                    if re.match(r'^[A-E]\.\s+', l):
                        ms_parts.append(l)
                    else:
                        title_parts.append(l)
                    j += 1
                    
                items.append({
                    'type': 'roll', 
                    'nums': nums, 
                    'line_idx': i, 
                    'title': " ".join([p for p in title_parts if p]).strip(),
                    'manuscripts': " ".join(ms_parts).strip()
                })
                expected_next = nums[-1] + 1
                continue
                
        # 2. Sub-Roll Header
        m_sub = re.match(r'^(\d+)\s*(?:\[\d+\])?\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,30})', line)
        if m_sub:
            n = int(m_sub.group(1))
            if expected_next - 1 <= n <= expected_next + 2:
                items.append({'type': 'roll', 'nums': [n], 'line_idx': i, 'title': line, 'manuscripts': ""})
                expected_next = n + 1
                continue

        # 3. Titulus Header
        m_tit = re.search(r'(\d+)\s*(\[\d+\])\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,30})', line)
        if m_tit:
            items.append({'type': 'titulus', 'loc': m_tit.group(4).strip(" ."), 'line_idx': i, 'full': line})
            continue

        # 4. Explicit T. Location
        m_t = re.search(r'T[T]?\.\s+([^0-9,;:\.\n\r]{3,30})', line)
        if m_t:
            items.append({'type': 'titulus', 'loc': m_t.group(1).strip(" ."), 'line_idx': i, 'full': line})
            continue
            
    return items, expected_next

def parse_and_load():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM rolls"); cursor.execute("DELETE FROM tituli"); cursor.execute("DELETE FROM footnotes"); cursor.execute("DELETE FROM entities")
    files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.endswith(".txt") and "_full" not in f], key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    
    active_roll_ids = []
    expected_next = 1
    current_pdf = None
    last_header_page = 0
    
    for fname in files:
        m = re.match(r'^pdf(\d+)_p(\d+)_(\w+)\.txt$', fname)
        if not m: continue
        pdf_idx, page, half = int(m.group(1)), int(m.group(2)), m.group(3)
        
        if pdf_idx != current_pdf:
            current_pdf = pdf_idx
            bounds = {1: (1, 73), 2: (74, 105), 3: (106, 121), 4: (122, 145)}
            expected_next, pdf_max = bounds.get(pdf_idx, (1, 145))
            active_roll_ids = []
            
        with open(os.path.join(RAW_TEXT_DIR, fname), "r") as f: lines = f.readlines()
        f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines
        
        anchors, expected_next = parse_page_content(main_lines, expected_next, pdf_max)
        
        if anchors:
            last_header_page = page
            for idx, anchor in enumerate(anchors):
                if anchor['type'] == 'roll':
                    active_roll_ids = []
                    for n in anchor['nums']:
                        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (str(n),))
                        row = cursor.fetchone()
                        if row: rid = row[0]
                        else:
                            cursor.execute("INSERT INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages) VALUES (?, ?, ?, ?, ?, ?)", 
                                         (str(n), "S.d.", anchor['title'], anchor['manuscripts'], f"Dufour T1 ({pdf_idx})", str(page)))
                            rid = cursor.lastrowid
                        active_roll_ids.append(rid)
                    
                    # Capture Latin body as first titulus
                    next_anchor_idx = anchors[idx+1]['line_idx'] if idx + 1 < len(anchors) else len(main_lines)
                    body = []
                    for l in main_lines[anchor['line_idx']+1:next_anchor_idx]:
                        if is_latin_text(l, relaxed=True): body.append(l.strip())
                    if body:
                        cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", 
                                     (active_roll_ids[-1], "[Original Document / Letter]", "", " ".join(body), page, half))

                elif anchor['type'] == 'titulus' and active_roll_ids:
                    next_line = anchors[idx+1]['line_idx'] if idx + 1 < len(anchors) else len(main_lines)
                    text = " ".join([l.strip() for l in main_lines[anchor['line_idx']:next_line]])
                    cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (active_roll_ids[-1], anchor['full'][:100], anchor['loc'], text, page, half))
                                 
        if active_roll_ids and (page - last_header_page <= 2):
            for rid in active_roll_ids:
                cursor.execute("SELECT pdf_pages FROM rolls WHERE id = ?", (rid,))
                rp_row = cursor.fetchone()
                if rp_row:
                    pl = [p.strip() for p in rp_row[0].split(",") if p.strip()]
                    if str(page) not in pl:
                        pl.append(str(page)); cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(pl), rid))

        if f_idx != -1 and active_roll_ids:
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip()
                if not fn_s: continue
                fm = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                fn_num = re.findall(r'\d+', fm.group(1))[0] if fm and re.findall(r'\d+', fm.group(1)) else str(idx)
                cursor.execute("INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text) VALUES (?, ?, ?, ?, ?)", 
                             (active_roll_ids[-1], page, half, fn_num, fm.group(2) if fm else fn_s))

    conn.commit(); conn.close(); print("Re-parsing complete.")

if __name__ == "__main__":
    parse_and_load()
