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
        # We check the dominant language. 'la' is not natively supported perfectly by langdetect,
        # but it usually categorizes Latin as 'it', 'es', or 'ro' rather than 'fr' or 'de'.
        # However, a much more robust historian approach for this specific corpus is to check
        # for high-frequency French/German editorial stop words vs Latin stop words.
        fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von "}
        la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
        
        text_lower = " " + text.lower() + " "
        fr_de_count = sum(text_lower.count(w) for w in fr_de_stop_words)
        la_count = sum(text_lower.count(w) for w in la_stop_words)
        
        # If it has overwhelming Latin markers compared to French/German, it's the source text.
        return la_count > fr_de_count
    except:
        return False

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
    """
    Find all roll numbers in a line, supporting ranges (e.g. 8-10) 
    and individual numbers (e.g. 13).
    """
    found = set()
    # Robust range expansion:
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
    # e.g., "1-3 5" -> [1, 2, 3, 5] -> [1, 2, 3, 4, 5]
    if found:
        sorted_found = sorted(list(found))
        expanded = set(sorted_found)
        for i in range(len(sorted_found) - 1):
            a, b = sorted_found[i], sorted_found[i+1]
            if 1 < b - a <= 3: # Fill small gaps of 1 or 2 missing rolls
                for n in range(a + 1, b):
                    expanded.add(n)
        return sorted(list(expanded))
            
    return []

def is_valid_roll_number_line(line):
    # Strip whitespace and common punctuation
    s = line.strip("()[]{}.-_ \t\n\r/*#@")
    if not s:
        return False
        
    # Pattern 1: pure number, e.g. "1" or "5-6" or "10 [12]" or "20 21"
    if re.match(r'^\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?$', s):
        return True
        
    # Pattern 2: starts with a common roll prefix (like No, Nos, N°, N*, N>, Ne, N, N", N's) followed by a number
    if re.match(r'^[nN][oOsS]?[\*°>\.>e\"\'P]?s?\s*\d+(\s*[\-\/\&\.\/\s]\s*\d+)?(\s*\[\d+\])?', s):
        return True
        
    return False

def parse_roll_header(lines, expected_next, pdf_max_roll=145):
    """
    Look for a roll header in the lines, matching the expected consecutive sequence.
    Returns (roll_num, date_str, title, remaining_lines)
    """
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # Rule 4: If expected is 6 and header digit is missing, match by its date line
        if expected_next == 6:
            if "769" in line and "770" in line:
                if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', line):
                    # Make sure it's not a running header
                    if not any(w in line.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux"]):
                        roll_num = "6"
                        date_str = line
                        title_parts = []
                        k = i + 1
                        while k < len(lines):
                            l = lines[k].strip()
                            if not l:
                                k += 1
                                continue
                            if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen|^T[T]?\.\s+', l):
                                break
                            title_parts.append(l)
                            k += 1
                        title = " ".join(title_parts)
                        return roll_num, date_str, title, lines[k:]

        # Pre-clean OCR digit misreads (pipe, capital I, lowercase l) for short line candidates
        test_line = line.replace('|', '1').replace('I', '1')
        if len(line.strip()) < 15:
            test_line = test_line.replace('l', '1')
            
        if not is_valid_roll_number_line(test_line):
            continue
            
        cleaned = clean_roll_num_string(test_line)
        nums = extract_numbers_from_cleaned(cleaned)
        
        # Require it to be short, UNLESS it explicitly starts with an N prefix
        has_n_prefix = bool(re.match(r'^[nN]', cleaned))
        if nums and (len(cleaned) < 15 or has_n_prefix):
            # Rule 1 & 2: Allow the roll number if it is within the expected sequence.
            # If it has an N prefix, we are VERY LIKELY looking at a real roll header,
            # so we allow a huge window (+50) to jump over gaps.
            # If it's a pure number, we keep it strict to avoid margin numbers (10, 15, 20).
            forward_window = 50 if has_n_prefix else 2
            backward_window = 5 if has_n_prefix else 2
            
            matched_num = None
            for n in nums:
                if (expected_next - backward_window <= n <= min(pdf_max_roll, expected_next + forward_window)):
                    matched_num = n
                    break
            
            # Special case: If we have an N prefix but it's outside the window, 
            # we STILL trust it if it's within the PDF's total max roll.
            if matched_num is None and has_n_prefix:
                for n in nums:
                    if n <= pdf_max_roll:
                        matched_num = n
                        break
                    
            if matched_num is not None:
                # Look for the date in the neighborhood of i (from i-3 to i+4)
                date_idx = None
                date_str = None
                
                search_indices = []
                for offset in range(1, 5):
                    search_indices.append(i + offset)
                for offset in range(-1, -4, -1):
                    search_indices.append(i + offset)
                    
                for j in search_indices:
                    if 0 <= j < len(lines):
                        l = lines[j].strip()
                        if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', l):
                            if not any(w in l.lower() for w in ["rouleaux", "morts", "ouleanx", "jouleaux", "lat.", "clm", "fol.", "bibl.", "cod."]):
                                date_idx = j
                                date_str = l
                                break
                
                # Disambiguation: On left pages, the format is:
                # [book page num] / [roll num] / [date] / [title]
                # If a SECOND standalone number appears between candidate (i) and date (j),
                # the candidate is a book page number, not a roll number.
                # Use the intervening number as the true roll number.
                if date_idx is not None and date_idx > i + 1:
                    for k2 in range(i + 1, date_idx):
                        inter_line = lines[k2].strip()
                        inter_test = inter_line.replace('|', '1').replace('I', '1')
                        if len(inter_line) < 15:
                            inter_test = inter_test.replace('l', '1')
                        if is_valid_roll_number_line(inter_test):
                            inter_cleaned = clean_roll_num_string(inter_test)
                            inter_nums = extract_numbers_from_cleaned(inter_cleaned)
                            if inter_nums:
                                inter_n = inter_nums[0]
                                # Check if the interleaved number is also in range
                                if expected_next - 2 <= inter_n <= min(pdf_max_roll, expected_next + 20):
                                    # The original candidate was the book page number; use inter_n
                                    matched_num = inter_n
                                break  # Stop after first intervening number

                
                is_valid = False
                if date_idx is not None:
                    is_valid = True
                elif matched_num == expected_next:
                    # Rule 3: Allow a roll header match without a date line if n == expected_next
                    is_valid = True
                    date_str = "S.d."
                    date_idx = i  # Treat current line as date line index for title parsing
                    
                if is_valid:
                    # Use the tight window rules to determine the range
                    valid_nums = [n for n in nums if expected_next - backward_window <= n <= min(pdf_max_roll, expected_next + forward_window)]
                    if len(valid_nums) >= 2:
                        roll_num = f"{min(valid_nums)}-{max(valid_nums)}"
                    else:
                        roll_num = str(matched_num)
                    
                    # Title starts after the date line
                    title_parts = []
                    k = date_idx + 1 if date_idx != i else i + 1
                    while k < len(lines):
                        l = lines[k].strip()
                        if not l:
                            k += 1
                            continue
                        if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen|^T[T]?\.\s+', l):
                            break
                        # Stop if we see another number line followed by a date (new roll)
                        sub_cleaned = clean_roll_num_string(l)
                        sub_nums = extract_numbers_from_cleaned(sub_cleaned)
                        next_is_date = False
                        if sub_nums and (len(sub_cleaned) < 15 or re.match(r'^[nN]', sub_cleaned)):
                            # Strict break: only if it looks like the NEXT logical roll
                            # and is NOT a margin number (usually 5, 10, 15, 20)
                            if any(n == expected_next or (re.match(r'^[nN]', sub_cleaned) and n > expected_next) for n in sub_nums):
                                # check if it is followed by a date
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
                                
                        title_parts.append(l)
                        k += 1
                        
                    title = " ".join(title_parts)
                    return roll_num, date_str, title, lines[k:]
                    
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
    "berg", "schliersee", "northumbrie", "northumbria", "ripoll", "limoges", "lobbes", "reims", "paris",
    "cluny", "cîteaux", "clairvaux", "bec", "fécamp", "fecamp", "caen", "rouen", "chartres", "orléans", "orleans",
    "bourges", "sens", "auxerre", "troyes", "langres", "metz", "toul", "liège", "liege", "utrecht", "cologne",
    "mayence", "trèves", "treves", "worms", "spire", "strasbourg", "basle", "bâle", "genève", "geneve",
    "lausanne", "sion", "aoste", "turin", "milan", "pavie", "gênes", "genes", "lucques", "pise", "florence",
    "sienne", "orvieto", "rome", "naples", "amalfi", "salerne", "bari", "brindisi", "otrante", "palerme",
    "messine", "catane", "syracuse", "girgenti", "agrigente", "mazara", "marsala", "trapani", "lipari",
    "cerami", "troina", "paternò", "paterno", "adranò", "adrano", "centuripe", "agirò", "agira", "leonforte",
    "enna", "calascibetta", "nicastro", "squillace", "mileto", "regio", "reggio", "gerace", "stilo",
    "rossano", "corigliano", "sibari", "cassano", "castrovillari", "morano", "laino", "rotonda", "viggianello",
    "fardella", "chiaromonte", "senise", "noepoli", "san giorgio", "san chirico", "tursi", "angona", "tricarico",
    "matera", "altamura", "gravina", "venosa", "acerenza", "melfi", "lavello", "canosa", "barletta", "trani",
    "bisceglie", "molfetta", "giovinazzo", "bitonto", "ruvo", "terlizzi", "corato", "andria", "minervino",
    "spinazzola", "montemilone", "palazzo", "genzano", "banzi", "oppido", "tolve", "potenza", "avigliano",
    "bella", "muro lucano", "atella", "rionero", "rapolla", "ripacandida", "maschito", "forenza", "acerenza",
    "ghent", "gent", "bruges", "bruxelles", "louvain", "anvers", "malines", "tournai", "mons", "namur",
    "dinant", "huy", "stavelot", "malmedy", "nivelles", "gembloux", "lobbes", "hautmont", "maubeuge",
    "valenciennes", "arras", "cambrai", "douai", "saint-omer", "saint-bertin", "saint-vaast", "saint-amand",
    "saint-ghislain", "saint-quentin", "saint-valery", "corbie", "saint-riquier", "amiens", "beauvais",
    "senlis", "soissons", "laon", "reims", "chalons", "troyes", "sens", "auxerre", "nevers", "bourges",
    "limoges", "poitiers", "angers", "tours", "nantes", "rennes", "vannes", "quimper", "saint-brieuc",
    "saint-malo", "dol", "avranches", "coutances", "bayeux", "lisieux", "evreux", "sées", "sees", "le mans"
}


def extract_entities(titulus, footnotes):
    """
    Scan titulus text for names of people/offices and link to footnotes.
    Uses structural parsing of Latin syntax and language verification
    to separate historical entities from modern editorial apparatus.
    """
    text = " ".join(titulus["text_lines"])
    
    # 1. Verification: Only extract entities from actual Latin medieval text
    if not is_latin_text(text):
        return []

    entities = []
    
    # 2. Structural Entity Extraction
    # We look for the classic Latin mortuary roll formula: 
    # [Capitalized Name] + [optional footnote marker] + [Ecclesiastical Title] + [Location]
    # e.g., "Hrodegangus (1) episcopus civitas Mettis" or "Williharius episcopus de Megingo"
    
    # We first find all capitalized words that have footnote markers attached to them
    ref_pattern = r'\b([A-Z][a-zA-ZÀ-ÿ\-]{2,})\s*[\(\[]?([®©§%#@\d\w\?]{1,5})[\)\]]?\b'
    matches = list(re.finditer(ref_pattern, text))
    
    for idx, m in enumerate(matches):
        name = m.group(1)
        fn_ref = m.group(2)
        
        # Verify the name doesn't look like a modern citation artifact (all caps, or single letters)
        if name.isupper() and len(name) > 3:
            continue
            
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
                
        # 3. Extract Role and Location from surrounding Latin syntax
        start_idx = m.end()
        # Look ahead 150 characters to find the role and location
        remaining_text = text[start_idx:start_idx+150].strip()
        
        norm_name = name
        norm_role = ""
        norm_dates = ""
        loc_name = ""
        
        # Parse role from the Latin text directly following the name
        role_match = re.match(r'^([^.,;]+)', remaining_text)
        original_role = role_match.group(1).strip() if role_match else ""
        
        # Try to identify formal ecclesiastical titles in the immediate text
        latin_titles = ["episcopus", "abbas", "monachus", "sacerdos", "presbiter", "diaconus", "clericus", "frater", "soror", "abbatissa", "prior", "prepositus"]
        for title in latin_titles:
            if title in original_role.lower():
                norm_role = title.capitalize()
                break
        
        if not norm_role:
            norm_role = original_role

        if fn_text:
            fn_cleaned = clean_text(fn_text)
            
            # Robust location extraction patterns
            # Titles: Évêque, Abbé, Comte, Prieur, Doyen, Monastère, Église, Diocèse, etc.
            titles_pattern = r'\b(?:[eéEÉ]v[eêê]?que|[aA]bb[eéE]|episcopus|episcopo|monasterio|monasterii|ecclesia|ecclesie|prior|comte|dux|duch[eé]|diocese|dioc[eè]se|archiepiscopus|archidiaconus|decanus|canonicus)\s+(?:de\s+|d\'|in\s+)?([A-Z][a-zA-ZÀ-ÿ\-\s]{2,30}?)(?:\b|\s*\(|\s*;|\s*,|\s*$)'
            loc_match = re.search(titles_pattern, fn_cleaned, re.IGNORECASE)
            
            if loc_match:
                extracted = loc_match.group(1).strip()
                # Remove common trailing noise/phrases
                extracted = re.split(r'\b(?:cité|dans|qui|selon|ou|et|cf|au|du|en|le|la|les|un|une)\b', extracted, flags=re.IGNORECASE)[0].strip()
                loc_name = extracted.strip(".,;()- ")
            
            # Fallback/Validation: If no match or match is noise, check for direct mention of KNOWN_LOCATIONS
            if not loc_name or loc_name.lower() in {"la", "par", "le", "de"}:
                for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]{3,}\b', fn_cleaned):
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
            "original_title": original_role,
            "footnote_num": fn_num,
            "footnote_text": fn_text,
            "normalized_name": norm_name,
            "normalized_role": norm_role,
            "normalized_dates": norm_dates,
            "location_name": loc_name
        }
        entities.append(entity)
        
    return entities

def parse_page_content(lines, expected_next_roll, pdf_name, page_num, half_name, pdf_max_roll=145):
    """
    Parses the lines of a page, extracting rolls and tituli sequentially.
    Skips '=== FOOTNOTES ===' marker lines but tracks line indices.
    """
    items = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "=== FOOTNOTES ===" in line:
            i += 1
            continue
        if not line:
            i += 1
            continue
            
        # Check if a roll header starts here
        roll_num, date_str, title, remaining = parse_roll_header(lines[i:], expected_next_roll, pdf_max_roll=pdf_max_roll)
        if roll_num:
            ms_str, remaining = parse_manuscripts(remaining)
            items.append(('roll', {
                "roll_num": roll_num,
                "date_str": date_str,
                "title": title,
                "manuscripts": ms_str,
                "start_idx": i
            }))
            
            if "-" in str(roll_num):
                expected_next_roll = int(str(roll_num).split("-")[1]) + 1
            else:
                expected_next_roll = int(roll_num) + 1
                
            i += len(lines[i:]) - len(remaining)
            continue
            
        # Check if it is an Explicit Dufour Titulus Header (e.g., "25 S.d.- Jouarre, N.-D." or "75 [76] S.d. ~ Trier")
        dufour_header_match = re.match(r'^(\d+)\s*(?:\[\d+\])?\s*(?:S\.?d\.?[~-]*|\d+\s+[a-zA-ZÀ-ÿ]+\s+\d+\s*-?)\s*(?:\[.*?\])?\s*([^,;:]+)', line)
        if dufour_header_match:
            tit_num = dufour_header_match.group(1)
            loc_name = dufour_header_match.group(2).strip(" .")
            
            tit_lines = []
            j = i + 1
            while j < len(lines):
                sub_line = lines[j].strip()
                if "=== FOOTNOTES ===" in sub_line:
                    j += 1
                    continue
                if not sub_line:
                    j += 1
                    continue
                # Break if next explicit header or T. marker is found
                if re.match(r'^\d+\s*(?:\[\d+\])?\s*(?:S\.?d\.?[~-]*|\d+\s+[a-zA-ZÀ-ÿ]+\s+\d+\s*-?)', sub_line) or re.match(r'^T[T]?\.\s+', sub_line, re.IGNORECASE):
                    break
                sub_roll_num, _, _, _ = parse_roll_header(lines[j:], expected_next_roll, pdf_max_roll=pdf_max_roll)
                if sub_roll_num:
                    break
                tit_lines.append(sub_line)
                j += 1
                
            items.append(('titulus', {
                "title": line,
                "location_name": loc_name,
                "text_lines": tit_lines,
                "start_idx": i
            }))
            i = j
            continue

        # Check if it is a classic T. titulus without Dufour header
        tit_match = re.match(r'^T[T]?\.\s+(.+)$', line, re.IGNORECASE)
        if tit_match:
            tit_lines = []
            j = i + 1
            while j < len(lines):
                sub_line = lines[j].strip()
                if "=== FOOTNOTES ===" in sub_line:
                    j += 1
                    continue
                if not sub_line:
                    j += 1
                    continue
                if re.match(r'^T[T]?\.\s+', sub_line, re.IGNORECASE):
                    break
                sub_roll_num, _, _, _ = parse_roll_header(lines[j:], expected_next_roll, pdf_max_roll=pdf_max_roll)
                if sub_roll_num:
                    break
                tit_lines.append(sub_line)
                j += 1
                
            items.append(('titulus', {
                "title": line,
                "text_lines": tit_lines,
                "start_idx": i
            }))
            i = j
            continue
            
        # Implicit titulus
        # HEURISTIC: Only treat as titulus if it looks medieval (has capitalized names or Latin markers)
        # and doesn't look bibliographic
        if any(marker in line.lower() for marker in ["werminghoff", "duchesne", "delisle", "éd.", "vol.", "col."]):
            i += 1
            continue

        tit_lines = [line]
        j = i + 1
        while j < len(lines):
            sub_line = lines[j].strip()
            if "=== FOOTNOTES ===" in sub_line:
                j += 1
                continue
            if not sub_line:
                j += 1
                continue
            if re.match(r'^T[T]?\.\s+', sub_line, re.IGNORECASE):
                break
            sub_roll_num, _, _, _ = parse_roll_header(lines[j:], expected_next_roll, pdf_max_roll=pdf_max_roll)
            if sub_roll_num:
                break
            tit_lines.append(sub_line)
            j += 1
            
        items.append(('titulus', {
            "title": "Implicit Titulus",
            "text_lines": tit_lines,
            "start_idx": i
        }))
        i = j
        
    return items, expected_next_roll

def clean_lines_of_running_headers(lines):
    cleaned = []
    for idx, line in enumerate(lines):
        if idx < 6:
            s = line.strip().lower()
            if not s:
                cleaned.append(line)
                continue
            is_header = False
            # Only treat as a running header if the line length is short (< 120 chars)
            if len(line.strip()) < 120:
                if "rouleaux" in s or "morts" in s or "des mort" in s or "ouleanx" in s or "jouleaux" in s:
                    is_header = True
                elif re.search(r'\bn[°*™»>oOsS]?s?[\*°>\.>e™»]?\s*\d+', s):
                    is_header = True
                elif re.match(r'^[\(\{\[\'\"]?\d{3,4}[\)\}\]\'\"]?$', s):
                    is_header = True
                elif re.match(r'^[\(\{\[\'\"]?\d{1,2}[\)\}\]\'\"]?$', s):
                    has_other = False
                    for other_line in lines[:6]:
                        ol = other_line.strip().lower()
                        if len(other_line.strip()) < 120:
                            if "rouleaux" in ol or "morts" in ol or "des mort" in ol or "n°" in ol or "n™" in ol or "n»" in ol or "n*" in ol or "n>" in ol or "nos" in ol or re.search(r'\(?\b\d{3,4}\b\)?', ol):
                                has_other = True
                                break
                    
                    # Verify that it's not actually followed by a date line or title line in its neighborhood
                    is_followed_by_date_or_title = False
                    for j in range(idx + 1, min(idx + 5, len(lines))):
                        l = lines[j].strip()
                        if not l:
                            continue
                        if re.match(r'^\s*([sS58\$]\.?\s*[d4]\b|[vV]ers\b|\[?\d{3,4}\b)', l):
                            is_followed_by_date_or_title = True
                            break
                        if re.match(r'^[A-Z]\.\s+Original|^[A-Z]\.\s+[M|Mü]nchen|^T[T]?\.\s+', l):
                            is_followed_by_date_or_title = True
                            break
                            
                    if has_other and not is_followed_by_date_or_title:
                        is_header = True
            if is_header:
                cleaned.append("\n")
                continue
        cleaned.append(line)
    return cleaned

def parse_and_load():
    files = []
    for f in os.listdir(RAW_TEXT_DIR):
        if f.endswith(".txt"):
            m = re.match(r'^pdf(\d+)_p(\d+)_(left|right|full)\.txt$', f)
            if m:
                pdf_idx = int(m.group(1))
                page_num = int(m.group(2))
                half = m.group(3)
                files.append((pdf_idx, page_num, half, f))
                
    files.sort(key=lambda x: (x[0], x[1], 0 if x[2] == 'left' else (1 if x[2] == 'right' else 2)))
    
    print(f"Found {len(files)} raw text files. Starting parsing...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM rolls")
    cursor.execute("DELETE FROM tituli")
    cursor.execute("DELETE FROM footnotes")
    cursor.execute("DELETE FROM entities")
    
    active_roll_num = "Unknown"
    active_roll_date = "S.d."
    active_roll_title = "Untitled Roll"
    active_roll_manuscripts = ""
    active_roll_id = None
    
    expected_next_roll = 1
    pdf_max_roll = 73  # Upper bound for PDF1
    current_pdf_idx = None
    
    for pdf_idx, page_num, half, fname in files:
        if pdf_idx != current_pdf_idx:
            current_pdf_idx = pdf_idx
            # Reset expected_next_roll and max based on the PDF boundaries.
            # PDF1: rolls 1-73  (running headers N°1 -> N°74, PDF1 ends there)
            # PDF2: rolls 74-105 (running headers N°74 -> N°106)
            # PDF3: rolls 106-121 (running headers N°106 -> N°122)
            # PDF4: rolls 122-145 (running headers N°122 -> N°145)
            if pdf_idx == 1:
                expected_next_roll = 1
                pdf_max_roll = 73
            elif pdf_idx == 2:
                expected_next_roll = 74
                pdf_max_roll = 105
            elif pdf_idx == 3:
                expected_next_roll = 106
                pdf_max_roll = 121
            elif pdf_idx == 4:
                expected_next_roll = 122
                pdf_max_roll = 145
                
        # Save active roll ID at the start of the page
        start_page_roll_id = active_roll_id
        
        fpath = os.path.join(RAW_TEXT_DIR, fname)
        with open(fpath, "r") as f:
            lines = f.readlines()
            
        # Split any line containing the start of the Latin text of Aelfwald's letter (Roll 1)
        new_lines = []
        for line in lines:
            m = re.search(r'Domino\s+Bonifacio', line)
            if m and "Aelbwaldus" in line:
                idx = m.start()
                new_lines.append(line[:idx].strip() + "\n")
                new_lines.append("T. " + line[idx:])
            else:
                new_lines.append(line)
        lines = new_lines
            
        lines = clean_lines_of_running_headers(lines)
        pdf_name = f"Dufour T1 ({pdf_idx})"
        
        # Find footnote marker
        footnote_idx = -1
        for idx, line in enumerate(lines):
            if "=== FOOTNOTES ===" in line:
                footnote_idx = idx
                break
                
        # Parse main content items sequentially on main text lines only
        main_lines = lines[:footnote_idx] if footnote_idx != -1 else lines
        items, expected_next_roll = parse_page_content(main_lines, expected_next_roll, pdf_name, page_num, half, pdf_max_roll=pdf_max_roll)
        
        # Determine footnote lines based on footnote_idx and any roll starting after it
        first_roll_after_fn = None
        for item_type, data in items:
            if item_type == 'roll' and footnote_idx != -1 and data["start_idx"] > footnote_idx:
                first_roll_after_fn = data["start_idx"]
                break
                
        if footnote_idx != -1:
            if first_roll_after_fn is not None:
                fn_lines = lines[footnote_idx+1 : first_roll_after_fn]
            else:
                fn_lines = lines[footnote_idx+1 :]
        else:
            fn_lines = []
            
        # Parse footnotes
        footnotes = []
        for idx, fn in enumerate(fn_lines, 1):
            fn_strip = fn.strip()
            if not fn_strip:
                continue
            m = re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_strip)
            if m:
                marker = m.group(1)
                content = m.group(2)
                digits = re.findall(r'\d+', marker)
                fn_num = digits[0] if digits else str(idx)
            else:
                fn_num = str(idx)
                content = fn_strip
            footnotes.append({
                "num": fn_num,
                "text": content,
                "page": page_num,
                "half": half
            })
            
        fn_to_roll = {}
        roll_num_to_id = {}
        
        # First pass over items to insert rolls and map referenced footnote numbers to roll IDs
        active_roll_ids = []
        for item_type, data in items:
            if item_type == 'roll':
                raw_roll_num = data["roll_num"]
                active_roll_date = data["date_str"]
                active_roll_title = data["title"]
                active_roll_manuscripts = data["manuscripts"]
                
                # Expand ranges using the improved logic
                cleaned_num = clean_roll_num_string(str(raw_roll_num))
                nums_to_process = [str(n) for n in extract_numbers_from_cleaned(cleaned_num)]
                if not nums_to_process:
                    nums_to_process = [str(raw_roll_num)]

                current_group_ids = []
                for active_roll_num in nums_to_process:
                    cursor.execute("SELECT id, title, manuscripts, pdf_pages FROM rolls WHERE roll_num = ?", (active_roll_num,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        r_id = existing[0]
                        if len(active_roll_title) > len(existing[1]):
                            cursor.execute("UPDATE rolls SET title = ?, manuscripts = ?, date_str = ? WHERE id = ?", 
                                         (active_roll_title, active_roll_manuscripts, active_roll_date, r_id))
                        pages_list = [p.strip() for p in existing[3].split(",") if p.strip()]
                        if str(page_num) not in pages_list:
                            pages_list.append(str(page_num))
                            cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(pages_list), r_id))
                    else:
                        cursor.execute("""
                        INSERT INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (active_roll_num, active_roll_date, active_roll_title, active_roll_manuscripts, pdf_name, str(page_num)))
                        r_id = cursor.lastrowid
                    
                    roll_num_to_id[active_roll_num] = r_id
                    current_group_ids.append(r_id)
                
                active_roll_ids = current_group_ids
                active_roll_id = active_roll_ids[-1]
                
            elif item_type == 'titulus' and active_roll_id is not None:
                text = " ".join(data["text_lines"])
                ref_pattern = r'\b([A-Z][a-z\-]+)\s*[\(\[]?([®©§%#@\d\w]+)[\)\]]?\b'
                matches = re.finditer(ref_pattern, text)
                for m in matches:
                    fn_ref = m.group(2)
                    digits = re.findall(r'\d+', fn_ref)
                    fn_num = digits[0] if digits else fn_ref
                    fn_to_roll[fn_num] = active_roll_id
                    
        if active_roll_id is None:
            # Fallback to roll 1 if nothing found on page
            cursor.execute("SELECT id FROM rolls WHERE roll_num = '1'")
            row1 = cursor.fetchone()
            if row1: active_roll_id = row1[0]
            
        if active_roll_id is not None:
            cursor.execute("SELECT pdf_pages FROM rolls WHERE id = ?", (active_roll_id,))
            pages_str = cursor.fetchone()[0]
            pages_list = [p.strip() for p in pages_str.split(",") if p.strip()]
            if str(page_num) not in pages_list:
                pages_list.append(str(page_num))
                cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE id = ?", (",".join(pages_list), active_roll_id))
            
        # Insert footnotes
        for fn in footnotes:
            fn_roll_id = fn_to_roll.get(fn["num"], active_roll_id)
            if fn_roll_id is not None:
                cursor.execute("""
                INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text)
                VALUES (?, ?, ?, ?, ?)
                """, (fn_roll_id, fn["page"], fn["half"], fn["num"], fn["text"]))
            
        # Restore state for second pass
        active_roll_ids = []
        if start_page_roll_id is not None:
            active_roll_id = start_page_roll_id
            cursor.execute("SELECT roll_num FROM rolls WHERE id = ?", (active_roll_id,))
            rn = cursor.fetchone()[0]
            active_roll_ids = [active_roll_id]
        else:
            if roll_num_to_id:
                first_num = sorted(roll_num_to_id.keys(), key=lambda x: int(x.split('-')[0]) if '-' in x else int(x))[0]
                active_roll_id = roll_num_to_id[first_num]
                active_roll_ids = [active_roll_id]

        # Second pass over items to insert tituli and extract/insert entities
        for item_type, data in items:
            if item_type == 'roll':
                cleaned_num = clean_roll_num_string(str(data["roll_num"]))
                nums_to_process = [str(n) for n in extract_numbers_from_cleaned(cleaned_num)]
                if not nums_to_process:
                    nums_to_process = [str(data["roll_num"])]
                active_roll_ids = [roll_num_to_id[n] for n in nums_to_process]
                active_roll_id = active_roll_ids[-1]
                print(f"Aggregating Roll {nums_to_process}: {data['title'][:50]}...")
            elif item_type == 'titulus':
                latin_text = " ".join(data["text_lines"])
                loc_name = data.get("location_name", "")
                
                # Use current group
                target_ids = active_roll_ids if active_roll_ids else [active_roll_id]
                for r_id in target_ids:
                    if r_id is None: continue
                    cursor.execute("""
                    INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (r_id, data["title"], loc_name, latin_text, page_num, half))
                    titulus_id = cursor.lastrowid
                    
                    cursor.execute("SELECT footnote_num, text FROM footnotes WHERE roll_id = ?", (r_id,))
                    roll_fns = [{"num": r["footnote_num"], "text": r["text"]} for r in cursor.fetchall()]
                    
                    entities = extract_entities(data, roll_fns)
                    if re.search(r'Domino\s+Bonifacio', data["title"]):
                        entities.append({
                            "original_name": "Bonifacio",
                            "original_title": "archiepiscopo",
                            "footnote_num": "3",
                            "footnote_text": "Boniface, archevêque de Mainz",
                            "normalized_name": "Boniface",
                            "normalized_role": "archbishop",
                            "normalized_dates": "747-749",
                            "location_name": "Mainz"
                        })
                    for ent in entities:
                        cursor.execute("""
                        INSERT INTO entities (
                            titulus_id, original_name, original_title, footnote_num, footnote_text,
                            normalized_name, normalized_role, normalized_dates, location_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            titulus_id, ent["original_name"], ent["original_title"], ent["footnote_num"], ent["footnote_text"],
                            ent["normalized_name"], ent["normalized_role"], ent["normalized_dates"], ent["location_name"]
                        ))
                
    conn.commit()
    conn.close()
    print("All rolls successfully parsed and loaded into SQLite!")

if __name__ == "__main__":
    parse_and_load()
