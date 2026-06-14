import re
import parser

with open('parser.py', 'r') as f:
    content = f.read()

# 1. Add extract_running_headers
new_funcs = """
import glob

def extract_running_headers(raw_text_dir):
    headers = {}
    regex = r'\bN(?:[o°"\'*™»>sS?]?)+(?:[\.\-]?)*\s*(\d+)(?:\s*[-.]\s*(\d+))?'
    for pdf_num in range(1, 5):
        files = glob.glob(os.path.join(raw_text_dir, f"pdf{pdf_num}_*_right.txt"))
        for fpath in files:
            fname = os.path.basename(fpath)
            m_num = re.findall(r'\d+', fname)
            if len(m_num) < 2: continue
            page_num = int(m_num[1])
            with open(fpath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines[:5]:
                s = line.strip()
                if "FOOTNOTES" in s: continue
                m = re.search(regex, s, re.IGNORECASE)
                if m:
                    min_r = int(m.group(1))
                    max_r = int(m.group(2)) if m.group(2) else min_r
                    if min_r <= 150 and max_r <= 150:
                        headers[(pdf_num, page_num)] = (min_r, max_r)
                        break
    return headers

"""

content = content.replace("import glob", new_funcs)
if "def extract_running_headers" not in content:
    content = new_funcs + content

# 2. Modify parse_roll_header
content = re.sub(r'def parse_roll_header\(lines, expected_next, pdf_max_roll=145\):.*?(?=def parse_manuscripts)', 
'''def parse_roll_header(lines):
    """
    Extracts the roll header (number, date, title) from lines.
    Returns (item_num, date_str, title, remaining_lines) or (None, None, None, lines)
    """
    for i, l in enumerate(lines):
        if is_valid_roll_number_line(l):
            matched_num = None
            nums = extract_numbers_from_cleaned(clean_roll_num_string(l))
            if nums:
                matched_num = nums[0]
                
            if matched_num is not None:
                # Look for the date in the neighborhood of i
                date_idx = None
                date_str = None
                
                search_indices = [i + 1, i + 2, i + 3, i + 4, i - 1, i - 2, i - 3]
                for j in search_indices:
                    if 0 <= j < len(lines):
                        test_l = lines[j].strip()
                        if re.match(r'^\\s*([sS58\\$]\\.?\\s*[d4]\\b|[vV]ers\\b|\\[?\\d{3,4}\\b)', test_l):
                            if not any(w in test_l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                date_idx = j
                                date_str = test_l
                                break
                
                if date_idx is not None:
                    # Disambiguation: check if another standalone number exists between i and date_idx
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
                            # Skip this i, it's a book page number
                            continue
                    
                    item_num = str(matched_num)
                    
                    # Title starts after the date line
                    title_parts = []
                    k = date_idx + 1 if date_idx != i else i + 1
                    while k < len(lines):
                        tl = lines[k].strip()
                        if not tl:
                            k += 1
                            continue
                        if re.match(r'^[A-Z]\\.\\s+Original|^[A-Z]\\.\\s+[M|Mü]nchen|^T[T]?\\.\\s+', tl):
                            break
                        
                        # Stop if we see another number line followed by a date
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
                                if re.match(r'^\\s*([sS58\\$]\\.?\\s*[d4]\\b|[vV]ers\\b|\\[?\\d{3,4}\\b)', sub_l):
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

''', content, flags=re.DOTALL)

# 3. Modify parse_page_content
content = re.sub(r'def parse_page_content\(lines, expected_next, pdf_num_str, page_num, half, pdf_max_roll=145\):.*?(?=def clean_up_titulus)',
'''def parse_page_content(lines, current_roll_id, pdf_num_str, page_num, half):
    """
    Parse a single page\'s content to find rolls and tituli.
    Returns (items, new_current_roll_id)
    where items is a list of tuples: (\'roll\', data_dict) or (\'titulus\', data_dict)
    """
    items = []
    
    # 1. Look for roll headers
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
        
    # 2. Extract manuscripts if remaining (optional)
    manuscripts_str, lines = parse_manuscripts(lines)
    if items and manuscripts_str and items[-1][0] == 'roll':
        items[-1][1]['manuscripts'] = manuscripts_str
        
    # 3. Extract tituli
    if current_roll_id > 1:
        titulus_num = None
        titulus_church = None
        titulus_body = []
        
        for line in lines:
            l = line.strip()
            if not l:
                continue
                
            m = re.match(r'^T[T]?\\.\\s+(\\d+)(?:\\s+(.*))?$', l, re.IGNORECASE)
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

''', content, flags=re.DOTALL)

# 4. Modify parse_and_load
content = re.sub(r'def parse_and_load\(db_path="rolls\.db"\):.*',
'''def parse_and_load(db_path="rolls.db"):
    db = RollDatabase(db_path)
    
    # Extract running headers
    header_map = extract_running_headers(RAW_TEXT_DIR)
    
    current_roll_id = 1
    
    for pdf_num in range(1, 5):
        files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.startswith(f'pdf{pdf_num}_') and f.endswith('.txt')])
        
        # Group files by page
        pages = {}
        for fname in files:
            page_num = int(re.findall(r'\\d+', fname)[1])
            half = 'left' if 'left' in fname else 'right'
            if page_num not in pages:
                pages[page_num] = {}
            pages[page_num][half] = fname
            
        for page_num in sorted(pages.keys()):
            # Update current_roll_id based on running headers
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
                    
                    items, current_roll_id = parse_page_content(
                        main_lines, current_roll_id, f"pdf{pdf_num}", page_num, half
                    )
                    
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
                            print(f"Parsed Roll {data['roll_num']}: {data['title'][:50]}...")
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
''', content, flags=re.DOTALL)

with open('parser.py', 'w') as f:
    f.write(content)

