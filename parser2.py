import os
import re
import sqlite3
from database import get_db_connection

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def is_footnote_line(line):
    """Check if a line looks like a footnote entry."""
    # Footnote patterns: e.g. starts with number, punctuation, or symbol, and contains citation-like keywords
    marker_match = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', line)
    if marker_match:
        content = marker_match.group(2)
        # Check for citation keywords: cf., t., p., col., Abbé, Évêque, Évéque, Evéque, Saint, S., Monastère, etc.
        keywords = [
            r'\bcf\.', r'\bp\.', r'\bt\.', r'\bcol\.', r'\b[eéEÉ]v[eêê]que\b', r'\b[aA]bb[eé]\b', 
            r'\b[mM]onast[eè]re\b', r'\b[sS]aint\b', r'\b[sS]\.', r'\b[eé]d\.', r'\bn°', r'\bN°',
            r'\bMünchen\b', r'\bBayer\b', r'\bStaatsbibl\b', r'\b[aA]nno\b', r'\b[aA]n\.', 
            r'\bvol\.', r'\bConc\b', r'\bM\.?\s*G\.?\s*H\b'
        ]
        for kw in keywords:
            if re.search(kw, content, re.IGNORECASE):
                return True
    return False

def clean_roll_num_string(s):
    # Remove common brackets/punctuation
    cleaned = s.strip("()[]{}.-_ \t\n\r/*#@")
    return cleaned

def extract_numbers_from_cleaned(cleaned):
    # Split by Delisle bracket if present
    main_part = cleaned.split('[')[0].strip()
    digits = re.findall(r'\d+', main_part)
    return [int(d) for d in digits]

def is_valid_roll_number_line(line):
    # Strip whitespace and common punctuation
    s = line.strip("()[]{}.-_ \t\n\r/*#@")
    if not s:
        return False
        
    # Pattern 1: pure number, e.g. "1" or "5-6" or "10 [12]" or "20 21"
    if re.match(r'^\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?$', s):
        return True
        
    # Pattern 2: starts with a common roll prefix (like No, Nos, N°, N*, N>, Ne, N) followed by a number
    if re.match(r'^[nN][oOsS]?s?[\*°>\.>e]?\s*\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?$', s):
        return True
        
    return False

import glob

def extract_running_headers(raw_text_dir):
    headers = {}
    regex = r'\bN(?:[o°"\'*\xbb>sS?]?)+(?:[\.\-]?)*\s*(\d+)(?:\s*[-.]\s*(\d+))?'
    for pdf_num in range(1, 5):
        files = glob.glob(os.path.join(raw_text_dir, f"pdf{pdf_num}_*_right.txt"))
        for fpath in files:
            fname = os.path.basename(fpath)
            import re
            m_num = re.findall(r'\d+', fname)
            if len(m_num) < 2: continue
            page_num = int(m_num[1])
            with open(fpath, 'r', encoding='utf-8') as f:
                flines = f.readlines()
            for fline in flines[:5]:
                s = fline.strip()
                if "FOOTNOTES" in s: continue
                m = re.search(regex, s, re.IGNORECASE)
                if m:
                    min_r = int(m.group(1))
                    max_r = int(m.group(2)) if m.group(2) else min_r
                    if min_r <= 150 and max_r <= 150:
                        headers[(pdf_num, page_num)] = (min_r, max_r)
                        break
    return headers

def parse_roll_header(lines):
    import re
    for i, l in enumerate(lines):
        if is_valid_roll_number_line(l):
            matched_num = None
            nums = extract_numbers_from_cleaned(clean_roll_num_string(l))
            if nums:
                matched_num = nums[0]
                
            if matched_num is not None:
                date_idx = None
                date_str = None
                
                search_indices = [i + 1, i + 2, i + 3, i + 4, i - 1, i - 2, i - 3]
                for j in search_indices:
                    if 0 <= j < len(lines):
                        test_l = lines[j].strip()
                        if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', test_l):
                            if not any(w in test_l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                date_idx = j
                                date_str = test_l
                                break
                
                if date_idx is not None:
                    if date_idx > i + 1:
                        has_intervening_number = False
                        for k2 in range(i + 1, date_idx):
                            inter_line = lines[k2].strip()
                            inter_test = inter_line.replace('|', '1').replace('I', '1')
                            if len(inter_line) < 15:
                                inter_test = inter_test.replace('l', '1')
                            if is_valid_roll_number_line(inter_test):
                                has_intervening_number = True
                                break
                        if has_intervening_number:
                            continue
                    
                    item_num = str(matched_num)
                    
                    title_parts = []
                    k = date_idx + 1 if date_idx != i else i + 1
                    while k < len(lines):
                        tl = lines[k].strip()
                        if not tl:
                            k += 1
                            continue
                        if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen|^T[T]?\.\s+', tl):
                            break
                        
                        sub_cleaned = clean_roll_num_string(tl)
                        sub_nums = extract_numbers_from_cleaned(sub_cleaned)
                        if sub_nums and len(sub_cleaned) < 15:
                            next_is_date = False
                            sub_count = 0
                            sub_j = k + 1
                            while sub_j < len(lines) and sub_count < 3:
                                sub_l = lines[sub_j].strip()
                                if not sub_l:
                                    sub_j += 1
                                    continue
                                sub_count += 1
                                if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', sub_l):
                                    if not any(w in sub_l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                        next_is_date = True
                                        break
                                sub_j += 1
                            if next_is_date:
                                break
                                
                        title_parts.append(tl)
                        k += 1
                        
                    title = " ".join(title_parts)
                    return item_num, date_str, title, lines[k:]
                    
    return None, None, None, lines
def parse_manuscripts(lines):
    """
    Extract manuscripts list.
    Returns (manuscripts_str, remaining_lines)
    """
    manuscripts = []
    remaining = []
    in_manuscripts = False
    
    for idx, line in enumerate(lines):
        l = line.strip()
        if not l:
            if in_manuscripts:
                # Keep empty lines inside manuscripts if short
                manuscripts.append(line)
            else:
                remaining.append(line)
            continue
            
        # Check if we hit a new roll number
        if is_valid_roll_number_line(l):
            in_manuscripts = False
            remaining.extend(lines[idx:])
            break
            
        # Check if we hit footnote marker
        if "=== FOOTNOTES ===" in l:
            in_manuscripts = False
            remaining.extend(lines[idx:])
            break
            
        # Check if we hit a titulus
        if re.match(r'^T[T]?\.\s+', l, re.IGNORECASE):
            in_manuscripts = False
            remaining.extend(lines[idx:])
            break
            
        # Determine if this line belongs to manuscripts/bibliography
        is_ms_line = False
        # 1. Matches A. or B. (possibly preceded by digits)
        if re.match(r'^(\d+\s+)?([A-Z])\.\s+', l):
            is_ms_line = True
        # 2. Matches bibliography letter: a. or b.
        elif re.match(r'^([a-z])\.\s+', l):
            is_ms_line = True
        # 3. Contains bibliography keywords at the start
        elif re.match(r'^(indique|traduction|ed\.|edition|original|manuscrit|ms\.)', l, re.IGNORECASE):
            is_ms_line = True
        # 4. If we are already in manuscripts, we can allow lines that are part of the description
        elif in_manuscripts:
            first_word_match = re.match(r'^([A-Za-zÀ-ÿ]+)', l)
            if first_word_match:
                w = first_word_match.group(1)
                if w[0].isupper() and len(w) >= 3 and not re.match(r'^(indique|traduction|ed\.|edition|original)', w, re.IGNORECASE):
                    is_ms_line = False
                else:
                    is_ms_line = True
            else:
                is_ms_line = True
                
        if is_ms_line:
            in_manuscripts = True
            manuscripts.append(line)
        else:
            in_manuscripts = False
            remaining.append(line)
            
    # Clean trailing empty lines from manuscripts
    while manuscripts and not manuscripts[-1].strip():
        manuscripts.pop()
        
    return "".join(manuscripts).strip(), remaining

def parse_tituli_and_footnotes(lines, pdf_idx, page_num, half_name):
    """
    Separate tituli text from footnotes, and return structured tituli and footnotes.
    Uses '=== FOOTNOTES ===' marker if present.
    """
    footnote_idx = -1
    for idx, line in enumerate(lines):
        if "=== FOOTNOTES ===" in line:
            footnote_idx = idx
            break
            
    tituli_raw = []
    footnotes_raw = []
    
    if footnote_idx != -1:
        # Clean division
        for line in lines[:footnote_idx]:
            if line.strip():
                tituli_raw.append(line.strip())
        for line in lines[footnote_idx+1:]:
            if line.strip():
                # Avoid keeping metadata as footnote text
                footnotes_raw.append(line.strip())
    else:
        # Fallback to the original heuristic
        for line in lines:
            if not line.strip():
                continue
            if is_footnote_line(line):
                footnotes_raw.append(line.strip())
            else:
                tituli_raw.append(line.strip())
            
    tituli = []
    current_titulus = None
    
    for line in tituli_raw:
        tit_match = re.match(r'^T[T]?\.\s+(.+)$', line, re.IGNORECASE)
        if tit_match:
            if current_titulus:
                tituli.append(current_titulus)
            current_titulus = {
                "title": line,
                "text_lines": [],
                "page": page_num,
                "half": half_name
            }
        elif current_titulus:
            current_titulus["text_lines"].append(line)
        else:
            current_titulus = {
                "title": "Implicit Titulus",
                "text_lines": [line],
                "page": page_num,
                "half": half_name
            }
            
    if current_titulus:
        tituli.append(current_titulus)
        
    footnotes = []
    for idx, fn in enumerate(footnotes_raw, 1):
        m = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn)
        if m:
            marker = m.group(1)
            content = m.group(2)
            digits = re.findall(r'\d+', marker)
            fn_num = digits[0] if digits else str(idx)
        else:
            fn_num = str(idx)
            content = fn
            
        footnotes.append({
            "num": fn_num,
            "text": content,
            "page": page_num,
            "half": half_name
        })
        
KNOWN_LOCATIONS = {
    "montecassino", "mont cassin", "mainz", "glastonbury", "jumièges", "jumieges",
    "flavigny", "novalesa", "rebais", "saint-wandrille", "wandrille", "corbie", "niederaltaich", "altaich",
    "reichenau", "salzburg", "salzbourg", "saint-denis", "denis", "saint-germain", "germain", "saint-maurice",
    "maurice", "agaune", "verdun", "besançon", "besancon", "moosburg", "mondsee", "tegernsee", "metten",
    "benediktbeuern", "weltenburg", "saint-cloud", "cloud", "eichstätt", "eichstatt", "würzburg", "wurzburg",
    "noyon", "murbach", "bayeux", "tours", "chur", "coire", "angers", "winchester", "saint-riquier", "centula",
    "riquier", "pfifers", "pfäfers", "nesle", "saint-evroult", "evroult", "scharnitz", "isen", "oberaltaich",
    "berg", "schliersee", "northumbrie", "northumbria"
}

def extract_entities(titulus, footnotes):
    """
    Scan titulus text for names of people/offices and link to footnotes.
    """
    entities = []
    text = " ".join(titulus["text_lines"])
    
    ref_pattern = r'\b([A-Z][a-z\-]+)\s*[\(\[]?([®©§%#@\d\w\?]+)[\)\]]?\b'
    matches = list(re.finditer(ref_pattern, text))
    
    for idx, m in enumerate(matches):
        name = m.group(1)
        fn_ref = m.group(2)
        
        fn_text = ""
        fn_num = ""
        
        # 1. Try to find footnote by digit match
        digits = re.findall(r'\d+', fn_ref)
        if digits:
            num_str = digits[0]
            for fn in footnotes:
                if fn["num"] == num_str:
                    fn_text = fn["text"]
                    fn_num = num_str
                    break
                    
        # 2. Try to find footnote by exact sequence index
        if not fn_text:
            if idx < len(footnotes):
                fn_text = footnotes[idx]["text"]
                fn_num = footnotes[idx]["num"]
                
        # Get role from remaining text in titulus
        start_idx = m.end()
        remaining_text = text[start_idx:start_idx+100].strip()
        role_match = re.match(r'^([^.,;]+)', remaining_text)
        role = role_match.group(1).strip() if role_match else ""
        
        norm_name = name
        norm_role = role
        norm_dates = ""
        loc_name = ""
        
        if fn_text:
            fn_cleaned = clean_text(fn_text)
            
            # Robust location extraction pattern
            loc_match = re.search(
                r'\b(?:[eéEÉ]v[eêê]?que|[aA]bb[eéE]|episcopus|episcopo|monasterio|monasterii)\s+(?:de\s+|d\')([A-Z][a-zA-Z\-\s]+?)(?:\b|\s*\(|\s*;|\s*,|\s*$)',
                fn_cleaned,
                re.IGNORECASE
            )
            if loc_match:
                extracted = loc_match.group(1).strip()
                # Remove trailing words/junk
                extracted = re.split(r'\b(?:cité|dans|qui|selon|ou|et|cf)\b', extracted, flags=re.IGNORECASE)[0].strip()
                loc_name = extracted.strip(".,;()- ")
            else:
                # Fallback: scan for any known location name in footnote text
                for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]+\b', fn_cleaned):
                    wl = word.lower()
                    if wl in KNOWN_LOCATIONS:
                        loc_name = word
                        break
                        
            # Normalize role and dates
            role_norm_match = re.match(r'^([^;,\(]+)', fn_cleaned)
            if role_norm_match:
                norm_role = role_norm_match.group(1).strip()
            date_match = re.search(r'\((\d{3,4}(?:\-\d{3,4})?|\d{3,4}\s*.*?)\)', fn_cleaned)
            if date_match:
                norm_dates = date_match.group(1).strip()
                
        entity = {
            "original_name": name,
            "original_title": role,
            "footnote_num": fn_num,
            "footnote_text": fn_text,
            "normalized_name": norm_name,
            "normalized_role": norm_role,
            "normalized_dates": norm_dates,
            "location_name": loc_name
        }
        entities.append(entity)
        
    return entities

def parse_page_content(lines, current_roll_id, pdf_num_str, page_num, half):
    import re
    items = []
    
    while True:
        item_num, date_str, title, remaining = parse_roll_header(lines)
        if item_num is None:
            break
            
        items.append(('roll', {
            'roll_num': str(current_roll_id),
            'date_str': date_str,
            'title': title
        }))
        current_roll_id += 1
        lines = remaining
        
    manuscripts_str, lines = parse_manuscripts(lines)
    if items and manuscripts_str and items[-1][0] == 'roll':
        items[-1][1]['manuscripts'] = manuscripts_str
        
    if current_roll_id > 1:
        titulus_num = None
        titulus_church = None
        titulus_body = []
        
        for line in lines:
            l = line.strip()
            if not l: continue
                
            m = re.match(r'^T[T]?\.\s+(\d+)(?:\s+(.*))?$', l, re.IGNORECASE)
            if m:
                if titulus_num is not None:
                    items.append(('titulus', {
                        'roll_num': str(current_roll_id - 1),
                        'titulus_num': titulus_num,
                        'church': titulus_church,
                        'body': " ".join(titulus_body)
                    }))
                titulus_num = int(m.group(1))
                titulus_church = m.group(2) if m.group(2) else ""
                titulus_body = []
            elif titulus_num is not None:
                if "=== FOOTNOTES ===" in l:
                    break
                titulus_body.append(l)
                
        if titulus_num is not None:
            items.append(('titulus', {
                'roll_num': str(current_roll_id - 1),
                'titulus_num': titulus_num,
                'church': titulus_church,
                'body': " ".join(titulus_body)
            }))
            
    return items, current_roll_id
def parse_and_load(db_path="rolls.db"):
    db = RollDatabase(db_path)
    header_map = extract_running_headers(RAW_TEXT_DIR)
    current_roll_id = 1
    
    for pdf_num in range(1, 5):
        import re, os
        files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.startswith(f'pdf{pdf_num}_') and f.endswith('.txt')])
        
        pages = {}
        for fname in files:
            page_num = int(re.findall(r'\d+', fname)[1])
            half = 'left' if 'left' in fname else 'right'
            if page_num not in pages:
                pages[page_num] = {}
            pages[page_num][half] = fname
            
        for page_num in sorted(pages.keys()):
            if (pdf_num, page_num) in header_map:
                min_r, max_r = header_map[(pdf_num, page_num)]
                if min_r >= current_roll_id and min_r <= current_roll_id + 5:
                    current_roll_id = max(current_roll_id, min_r)
            
            for half in ['left', 'right']:
                if half in pages[page_num]:
                    fpath = os.path.join(RAW_TEXT_DIR, pages[page_num][half])
                    with open(fpath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    cleaned_lines = clean_lines_of_running_headers(lines)
                    fn_idx = next((i for i, l in enumerate(cleaned_lines) if "=== FOOTNOTES ===" in l), -1)
                    main_lines = cleaned_lines[:fn_idx] if fn_idx != -1 else cleaned_lines
                    
                    items, current_roll_id = parse_page_content(main_lines, current_roll_id, f"pdf{pdf_num}", page_num, half)
                    
                    for item_type, data in items:
                        if item_type == 'roll':
                            db.insert_roll(
                                data['roll_num'],
                                data['date_str'],
                                data['title'],
                                data.get('manuscripts', ''),
                                f"Dufour T1 ({pdf_num})",
                                str(page_num)
                            )
                        elif item_type == 'titulus':
                            db.insert_titulus(
                                data['roll_num'],
                                data['titulus_num'],
                                data['church'],
                                data['body']
                            )
    db.close()
if __name__ == "__main__":
    parse_and_load()
