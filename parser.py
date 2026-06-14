import os
import re
import sqlite3
from database import get_db_connection

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def is_latin_text(text):
    """
    Robust historian-level check to determine if a block of text is Latin (medieval source)
    or French/German (modern scholarly apparatus).
    """
    if not text or len(text.strip()) < 15:
        return False
    try:
        fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von "}
        la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
        
        text_lower = " " + text.lower() + " "
        fr_de_count = sum(text_lower.count(w) for w in fr_de_stop_words)
        la_count = sum(text_lower.count(w) for w in la_stop_words)
        return la_count > fr_de_count
    except:
        return False

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def clean_roll_num_string(s):
    # Remove common brackets/punctuation
    cleaned = s.strip("()[]{}.-_ \t\n\r/*#@")
    return cleaned

def extract_numbers_from_cleaned(cleaned):
    """
    Find all roll numbers in a line, supporting ranges (e.g. 8-10) 
    and individual numbers (e.g. 13).
    """
    found = set()
    # 1. Find all explicit ranges (8-10)
    ranges = re.findall(r'(\d+)\s*[\-\/]\s*(\d+)', cleaned)
    for s_str, e_str in ranges:
        s, e = int(s_str), int(e_str)
        if 0 < e - s <= 20: # Sanity check for range size
            for n in range(s, e + 1):
                found.add(n)
    
    # 2. Find all individual numbers
    nums = re.findall(r'\d+', cleaned)
    for n_str in nums:
        found.add(int(n_str))
        
    # 3. Gap Filling: If we have multiple numbers, fill small gaps
    if found:
        sorted_found = sorted(list(found))
        expanded = set(sorted_found)
        for i in range(len(sorted_found) - 1):
            a, b = sorted_found[i], sorted_found[i+1]
            if 1 < b - a <= 3:
                for n in range(a + 1, b):
                    expanded.add(n)
        return sorted(list(expanded))
    return []

def is_valid_roll_number_line(line):
    s = line.strip("()[]{}.-_ \t\n\r/*#@")
    if not s: return False
    if re.match(r'^\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?$', s):
        return True
    if re.match(r'^[nN][oOsS]?[\*°>\.>e\"\'P]?s?\s*\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?', s):
        return True
    return False

def parse_roll_header(lines, expected_next, pdf_max_roll=145):
    for i in range(len(lines)):
        line = lines[i].strip()
        if expected_next == 6 and "769" in line and "770" in line:
             if not any(w in line.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux"]):
                return "6", line, line, lines[i+1:]

        test_line = line.replace('|', '1').replace('I', '1')
        if len(line.strip()) < 15: test_line = test_line.replace('l', '1')
        if not is_valid_roll_number_line(test_line): continue
            
        cleaned = clean_roll_num_string(test_line)
        nums = extract_numbers_from_cleaned(cleaned)
        
        has_n_prefix = bool(re.match(r'^[nN]', cleaned))
        if nums and (len(cleaned) < 15 or has_n_prefix):
            forward_window = 50 if has_n_prefix else 2
            backward_window = 5 if has_n_prefix else 2
            
            matched_num = None
            for n in nums:
                if (expected_next - backward_window <= n <= min(pdf_max_roll, expected_next + forward_window)):
                    matched_num = n; break
            
            if matched_num is None and has_n_prefix:
                for n in nums:
                    if n <= pdf_max_roll: matched_num = n; break
                    
            if matched_num is not None:
                date_idx = None; date_str = None
                for offset in [1, 2, 3, 4, -1, -2, -3]:
                    j = i + offset
                    if 0 <= j < len(lines):
                        l = lines[j].strip()
                        if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', l):
                            if not any(w in l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                date_idx = j; date_str = l; break
                
                if date_str is None:
                    date_str = "S.d."
                    date_idx = i
                    
                valid_nums = [n for n in nums if expected_next - backward_window <= n <= min(pdf_max_roll, expected_next + forward_window)]
                if len(valid_nums) >= 2:
                    roll_num = f"{min(valid_nums)}-{max(valid_nums)}"
                else:
                    roll_num = str(matched_num)
                
                title_parts = []
                k = date_idx + 1 if date_idx != i else i + 1
                while k < len(lines):
                    l = lines[k].strip()
                    if not l: k += 1; continue
                    if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen|^T[T]?\.\s+', l): break
                    sub_cleaned = clean_roll_num_string(l); sub_nums = extract_numbers_from_cleaned(sub_cleaned)
                    next_is_date = False
                    if sub_nums and (len(sub_cleaned) < 15 or re.match(r'^[nN]', sub_cleaned)):
                        if any(n == expected_next or (re.match(r'^[nN]', sub_cleaned) and n > expected_next) for n in sub_nums):
                            sub_count = 0; sub_j = k + 1
                            while sub_j < len(lines) and sub_count < 3:
                                sub_l = lines[sub_j].strip()
                                if not sub_l: sub_j += 1; continue
                                sub_count += 1
                                if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', sub_l):
                                    if not any(w in sub_l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                        next_is_date = True; break
                                sub_j += 1
                    if next_is_date: break
                    title_parts.append(l); k += 1
                return roll_num, date_str, " ".join(title_parts), lines[k:]
    return None, None, None, lines

def parse_manuscripts(lines):
    manuscripts = []; remaining = []; in_manuscripts = False
    for idx, line in enumerate(lines):
        l = line.strip()
        if not l: continue
        if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen', l): in_manuscripts = True
        if re.match(r'^T[T]?\.\s+', l) or is_latin_text(l):
             remaining = lines[idx:]; break
        if in_manuscripts: manuscripts.append(l)
        else: manuscripts.append(l)
    return " ".join(manuscripts), remaining

KNOWN_LOCATIONS = { "montecassino", "mainz", "jumièges", "corbie", "reichenau", "salzburg", "saint-denis", "saint-germain", "cluny", "cîteaux", "clairvaux", "reims", "paris", "poitiers", "angers", "tours", "caen", "rouen", "chartres" }

def extract_entities(titulus, footnotes):
    text = " ".join(titulus["text_lines"])
    if not is_latin_text(text): return []
    entities = []
    ref_pattern = r'\b([A-Z][a-zA-ZÀ-ÿ\-]{2,})\s*[\(\[]?([®©§%#@\d\w\?]{1,5})[\)\]]?\b'
    matches = list(re.finditer(ref_pattern, text))
    for idx, m in enumerate(matches):
        name = m.group(1); fn_ref = m.group(2)
        if name.isupper() and len(name) > 3: continue
        fn_text = ""; fn_num = ""
        digits = re.findall(r'\d+', fn_ref)
        if digits:
            num_str = digits[0]
            for fn in footnotes:
                if fn["num"] == num_str:
                    fn_text = fn["text"]; fn_num = num_str; break
        if not fn_text and idx < len(footnotes):
            fn_text = footnotes[idx]["text"]; fn_num = footnotes[idx]["num"]
        start_idx = m.end(); remaining_text = text[start_idx:start_idx+150].strip()
        role_match = re.match(r'^([^.,;]+)', remaining_text)
        original_role = role_match.group(1).strip() if role_match else ""
        norm_role = original_role
        latin_titles = ["episcopus", "abbas", "monachus", "sacerdos", "presbiter", "diaconus", "clericus", "frater", "soror", "abbatissa", "prior", "prepositus"]
        for title in latin_titles:
            if title in original_role.lower(): norm_role = title.capitalize(); break
        norm_name = name; norm_dates = ""; loc_name = ""
        if fn_text:
            fn_cleaned = clean_text(fn_text)
            titles_pattern = r'\b(?:[eéEÉ]v[eêê]?que|[aA]bb[eéE]|episcopus|episcopo|monasterio|monasterii|ecclesia|ecclesie|prior|comte|dux|duch[eé]|diocese|dioc[eè]se|archiepiscopus|archidiaconus|decanus|canonicus)\s+(?:de\s+|d\'|in\s+)?([A-Z][a-zA-ZÀ-ÿ\-\s]{2,30}?)(?:\b|\s*\(|\s*;|\s*,|\s*$)'
            loc_match = re.search(titles_pattern, fn_cleaned, re.IGNORECASE)
            if loc_match:
                extracted = loc_match.group(1).strip()
                extracted = re.split(r'\b(?:cité|dans|qui|selon|ou|et|cf|au|du|en|le|la|les|un|une)\b', extracted, flags=re.IGNORECASE)[0].strip()
                loc_name = extracted.strip(".,;()- ")
            if not loc_name or loc_name.lower() in {"la", "par", "le", "de"}:
                for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]{3,}\b', fn_cleaned):
                    if word.lower() in KNOWN_LOCATIONS: loc_name = word; break
            date_match = re.search(r'\((\d{3,4}(?:\-\d{3,4})?|\d{3,4}\s*.*?)\)', fn_cleaned)
            if date_match: norm_dates = date_match.group(1).strip()
        entities.append({ "original_name": name, "original_title": original_role, "footnote_num": fn_num, "footnote_text": fn_text, "normalized_name": norm_name, "normalized_role": norm_role, "normalized_dates": norm_dates, "location_name": loc_name })
    return entities

def parse_page_content(lines, expected_next_roll, pdf_name, page_num, half_name, pdf_max_roll=145):
    items = []; i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "=== FOOTNOTES ===" in line or not line: i += 1; continue
        roll_num, date_str, title, remaining = parse_roll_header(lines[i:], expected_next_roll, pdf_max_roll=pdf_max_roll)
        if roll_num:
            ms_str, remaining = parse_manuscripts(remaining)
            items.append(('roll', { "roll_num": roll_num, "date_str": date_str, "title": title, "manuscripts": ms_str, "start_idx": i }))
            expected_next_roll = int(str(roll_num).split("-")[1]) + 1 if "-" in str(roll_num) else int(roll_num) + 1
            i += len(lines[i:]) - len(remaining); continue
        dufour_header_match = re.match(r'^(\d+)\s*(?:\[\d+\])?\s*(?:S\.?d\.?[~-]*|\d+\s+[a-zA-ZÀ-ÿ]+\s+\d+\s*-?)\s*(?:\[.*?\])?\s*([^,;:]+)', line)
        if dufour_header_match:
            loc_name = dufour_header_match.group(2).strip(" ."); tit_lines = []; j = i + 1
            while j < len(lines):
                sub_line = lines[j].strip()
                if "=== FOOTNOTES ===" in sub_line or not sub_line: j += 1; continue
                if re.match(r'^\d+\s*(?:\[\d+\])?\s*(?:S\.?d\.?[~-]*|\d+\s+[a-zA-ZÀ-ÿ]+\s+\d+\s*-?)', sub_line) or re.match(r'^T[T]?\.\s+', sub_line, re.IGNORECASE): break
                sub_roll_num, _, _, _ = parse_roll_header(lines[j:], expected_next_roll, pdf_max_roll=pdf_max_roll)
                if sub_roll_num: break
                tit_lines.append(sub_line); j += 1
            items.append(('titulus', { "title": line, "location_name": loc_name, "text_lines": tit_lines, "start_idx": i }))
            i = j; continue
        tit_match = re.match(r'^T[T]?\.\s+(.+)$', line, re.IGNORECASE)
        if tit_match:
            tit_lines = [tit_match.group(1)]; j = i + 1
            while j < len(lines):
                sub_line = lines[j].strip()
                if "=== FOOTNOTES ===" in sub_line or not sub_line: j += 1; continue
                if re.match(r'^T[T]?\.\s+', sub_line, re.IGNORECASE): break
                sub_roll_num, _, _, _ = parse_roll_header(lines[j:], expected_next_roll, pdf_max_roll=pdf_max_roll)
                if sub_roll_num: break
                tit_lines.append(sub_line); j += 1
            items.append(('titulus', { "title": line, "text_lines": tit_lines, "start_idx": i })); i = j; continue
        i += 1
    return items, expected_next_roll

def parse_and_load():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM rolls"); cursor.execute("DELETE FROM tituli"); cursor.execute("DELETE FROM footnotes"); cursor.execute("DELETE FROM entities")
    files_list = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.endswith(".txt") and "_full" not in f], key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    files = []
    for f in files_list:
        m = re.match(r'^pdf(\d+)_p(\d+)_(\w+)\.txt$', f)
        if m: files.append((int(m.group(1)), int(m.group(2)), m.group(3), f))
    
    active_roll_id = None; expected_next_roll = 1; pdf_max_roll = 145; current_pdf_idx = None
    for pdf_idx, page_num, half, fname in files:
        if pdf_idx != current_pdf_idx:
            current_pdf_idx = pdf_idx
            if pdf_idx == 1: expected_next_roll = 1; pdf_max_roll = 73
            elif pdf_idx == 2: expected_next_roll = 74; pdf_max_roll = 105
            elif pdf_idx == 3: expected_next_roll = 106; pdf_max_roll = 121
            elif pdf_idx == 4: expected_next_roll = 122; pdf_max_roll = 145
        with open(os.path.join(RAW_TEXT_DIR, fname), "r") as f: lines = f.readlines()
        footnote_idx = -1
        for idx, line in enumerate(lines):
            if "=== FOOTNOTES ===" in line: footnote_idx = idx; break
        main_lines = lines[:footnote_idx] if footnote_idx != -1 else lines
        items, expected_next_roll = parse_page_content(main_lines, expected_next_roll, f"Dufour T1 ({pdf_idx})", page_num, half, pdf_max_roll=pdf_max_roll)
        fn_lines = lines[footnote_idx+1:] if footnote_idx != -1 else []
        footnotes = []
        for idx, fn in enumerate(fn_lines, 1):
            fn_strip = fn.strip()
            if not fn_strip: continue
            m = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_strip)
            fn_num = re.findall(r'\d+', m.group(1))[0] if m and re.findall(r'\d+', m.group(1)) else str(idx)
            footnotes.append({ "num": fn_num, "text": m.group(2) if m else fn_strip, "page": page_num, "half": half })
        fn_to_roll = {}; roll_num_to_id = {}; active_roll_ids = []
        for item_type, data in items:
            if item_type == 'roll':
                nums = [str(n) for n in extract_numbers_from_cleaned(clean_roll_num_string(str(data["roll_num"])))]
                if not nums: nums = [str(data["roll_num"])]
                current_group_ids = []
                for num in nums:
                    cursor.execute("SELECT id, pdf_pages FROM rolls WHERE roll_num = ?", (num,))
                    existing = cursor.fetchone()
                    if existing:
                        r_id = existing[0]; p_list = [p.strip() for p in existing[1].split(",") if p.strip()]
                        if str(page_num) not in p_list: p_list.append(str(page_num)); cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(p_list), r_id))
                    else:
                        cursor.execute("INSERT INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages) VALUES (?, ?, ?, ?, ?, ?)", (num, data["date_str"], data["title"], data["manuscripts"], f"Dufour T1 ({pdf_idx})", str(page_num)))
                        r_id = cursor.lastrowid
                    roll_num_to_id[num] = r_id; current_group_ids.append(r_id)
                active_roll_ids = current_group_ids; active_roll_id = active_roll_ids[-1]
            elif item_type == 'titulus' and active_roll_id:
                text = " ".join(data["text_lines"]); matches = re.finditer(r'\b([A-Z][a-z\-]+)\s*[\(\[]?([®©§%#@\d\w]+)[\)\]]?\b', text)
                for m in matches:
                    ds = re.findall(r'\d+', m.group(2)); fn_to_roll[ds[0] if ds else m.group(2)] = active_roll_id
        if active_roll_id is None:
            cursor.execute("SELECT id FROM rolls WHERE roll_num = '1'"); r1 = cursor.fetchone()
            if r1: active_roll_id = r1[0]
        if active_roll_id:
            cursor.execute("SELECT pdf_pages FROM rolls WHERE id = ?", (active_roll_id,)); r_pages = cursor.fetchone()[0]; p_list = [p.strip() for p in r_pages.split(",") if p.strip()]
            if str(page_num) not in p_list: p_list.append(str(page_num)); cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(p_list), active_roll_id))
        for fn in footnotes:
            rid = fn_to_roll.get(fn["num"], active_roll_id)
            if rid: cursor.execute("INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text) VALUES (?, ?, ?, ?, ?)", (rid, fn["page"], fn["half"], fn["num"], fn["text"]))
        for item_type, data in items:
            if item_type == 'roll':
                nums = [str(n) for n in extract_numbers_from_cleaned(clean_roll_num_string(str(data["roll_num"])))]; active_roll_ids = [roll_num_to_id[n] for n in nums if n in roll_num_to_id]; active_roll_id = active_roll_ids[-1] if active_roll_ids else active_roll_id
            elif item_type == 'titulus':
                t_ids = active_roll_ids if active_roll_ids else [active_roll_id]
                for r_id in t_ids:
                    if not r_id: continue
                    cursor.execute("INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half) VALUES (?, ?, ?, ?, ?, ?)", (r_id, data["title"], data.get("location_name", ""), " ".join(data["text_lines"]), page_num, half))
                    tid = cursor.lastrowid; cursor.execute("SELECT footnote_num, text FROM footnotes WHERE roll_id = ?", (r_id,)); rfns = [{"num": r["footnote_num"], "text": r["text"]} for r in cursor.fetchall()]
                    for ent in extract_entities(data, rfns): cursor.execute("INSERT INTO entities (titulus_id, original_name, original_title, footnote_num, footnote_text, normalized_name, normalized_role, normalized_dates, location_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (tid, ent["original_name"], ent["original_title"], ent["footnote_num"], ent["footnote_text"], ent["normalized_name"], ent["normalized_role"], ent["normalized_dates"], ent["location_name"]))
    conn.commit(); conn.close(); print("All rolls successfully parsed and loaded into SQLite!")

if __name__ == "__main__":
    parse_and_load()
