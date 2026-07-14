import sqlite3
import re
import json
import os

DB_PATH = "rolls.db"
DELISLE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "reference", "delisle_index.json")

_ROMAN_VALS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}

def _roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = _ROMAN_VALS.get(ch, 0)
        if v == 0:
            return None
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total

_DELISLE_LOCATOR_RE = re.compile(r'n[°ºo]\s*\.?\s*([IVXLCDM]+|\d+)', re.IGNORECASE)

def _extract_delisle_num(locator_or_text):
    """Pull the roll number Dufour cites within Delisle's own catalog out of
    a citation's locator/raw_text, e.g. 'p. 89, n° V' -> 5, 'p. 42, n° XVI'
    -> 16. Delisle numbered his 87 rolls with roman numerals; Dufour's
    apparatus sometimes transcribes them as roman, sometimes as arabic."""
    if not locator_or_text:
        return None
    m = _DELISLE_LOCATOR_RE.search(locator_or_text)
    if not m:
        return None
    token = m.group(1)
    if token.isdigit():
        return int(token)
    return _roman_to_int(token)

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

def citations_report():
    """Research-goal-specific report: every extracted citation to an external
    catalog, grouped by cited work. A citation to a predecessor catalog
    (especially Delisle's 'Rouleaux des morts') is a lead for a roll not
    otherwise referenced in this edition - cross-reference cited_locator
    against that catalog's own index to find gaps."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM citations")
    total = cursor.fetchone()[0]
    print(f"\nTotal citations extracted: {total}")
    if total == 0:
        conn.close()
        return

    cursor.execute("""
        SELECT cited_work, COUNT(*) as n
        FROM citations
        GROUP BY cited_work
        ORDER BY n DESC
    """)
    print(f"\n{'Cited work':<60} | Count")
    print("-" * 70)
    for row in cursor.fetchall():
        print(f"{row['cited_work'][:60]:<60} | {row['n']}")

    print("\n--- Delisle citations, sorted by locator (reconstructed partial index) ---")
    print("Cross-reference this against Delisle's own catalog numbering if/when available;")
    print("in the meantime, duplicate/near locators pointing at different rolls are themselves worth checking.")
    cursor.execute("""
        SELECT r.roll_num, c.cited_locator, c.raw_text
        FROM citations c JOIN rolls r ON r.id = c.roll_id
        WHERE c.cited_work LIKE '%Delisle%'
        ORDER BY c.cited_locator, r.roll_num
    """)
    for row in cursor.fetchall():
        locator = row['cited_locator'] or ''
        print(f"{locator:<20} -> roll {row['roll_num']:<5} | {row['raw_text'][:80]}")

    conn.close()

# Phrases indicating a source explicitly says this document is NOT covered by
# (or was missed by) a predecessor catalog - the direct textual evidence for
# "roll not referenced in the primary source", independent of having an
# external index to cross-reference locators against. French because the
# apparatus is French/Latin; case-insensitive, accent-insensitive.
OMISSION_PATTERNS = [
    r"omis(?:e|es)?\s+par", r"non\s+mentionn", r"absente?\s+(?:de|du|des)",
    r"ignor[ée]e?\s+(?:par|de)", r"inconnue?\s+de", r"manque\s+[àa]",
    r"non\s+catalogu", r"non\s+r[ée]pertori", r"[ée]chapp[ée]e?\s+[àa]",
    r"non\s+recens[ée]e?",
]
_OMISSION_RE = re.compile("|".join(OMISSION_PATTERNS), re.IGNORECASE)

def gap_candidates_report():
    """The direct payoff of the citation/footnote extraction, for the
    project's actual research goal: scan every footnote and citation for
    language that explicitly says a document was missed by/absent from a
    predecessor catalog (e.g. "omise par L. Delisle" - found verbatim in
    this corpus). Each hit is a concrete, human-checkable lead for a roll
    not otherwise referenced in this edition."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    hits = []
    cursor.execute("""
        SELECT r.roll_num, 'footnote' as source, f.text as snippet
        FROM footnotes f JOIN rolls r ON r.id = f.roll_id
    """)
    hits += cursor.fetchall()
    cursor.execute("""
        SELECT r.roll_num, 'citation' as source, c.raw_text as snippet
        FROM citations c JOIN rolls r ON r.id = c.roll_id
    """)
    hits += cursor.fetchall()

    matches = [h for h in hits if h['snippet'] and _OMISSION_RE.search(h['snippet'])]

    print(f"\n--- Gap candidates: explicit omission language found ({len(matches)} hits) ---")
    for m in matches:
        print(f"roll {m['roll_num']:<5} [{m['source']}] {m['snippet'][:150]}")
    if not matches:
        print("(none yet - re-run after the full extraction pass)")

    conn.close()

_CENTURY_WORDS = {
    'neuvième': 9, 'dixième': 10, 'onzième': 11, 'douzième': 12,
    'treizième': 13, 'quatorzième': 14, 'quinzième': 15, 'seizième': 16,
}
_CENTURY_RE = re.compile(r'\b(' + '|'.join(_CENTURY_WORDS) + r')\b', re.IGNORECASE)
# OCR in this particular scan very commonly misreads a leading "1" as "4"
# in four-digit years (e.g. Delisle's own "1233" comes out as "4233",
# "1004" as "^004"/"4004") - accept both and normalize back to a real year.
# It also sometimes substitutes a lowercase "l" for the leading "1" ("1398"
# -> "l398"), and drops a stray space *somewhere* inside the 4 digits ("1305"
# -> "4 305", but also "1181" -> "11 81" - the split point isn't fixed at
# one position) - collapsing any space between two digits before matching
# handles all of these in one pass instead of hardcoding each split point.
_YEAR_RE = re.compile(r'\b([14l]\d{3})\b')

def _collapse_ocr_digit_gaps(text: str) -> str:
    return re.sub(r'(?<=\d)\s+(?=\d)', '', text)

def _normalize_ocr_year(token: str) -> int:
    return int(('1' if token[0] in ('4', 'l') else token[0]) + token[1:])
# Volume 1 of Dufour's edition covers up to 1180 - a Delisle roll dated
# later can never legitimately appear in this corpus, so flagging it as a
# "gap" would be a false positive against our own edition's scope, not
# evidence of anything. A century word only gives a coarse upper bound
# (e.g. "douzième siècle" could be 1100 or 1199), so treat it as in-scope
# unless it's unambiguously 13th-century or later.
_CUTOFF_YEAR = 1180

def _delisle_entry_out_of_scope(title):
    m = _YEAR_RE.search(_collapse_ocr_digit_gaps(title))
    if m and _normalize_ocr_year(m.group(1)) > _CUTOFF_YEAR:
        return True, m.group(0)
    m = _CENTURY_RE.search(title)
    if m and _CENTURY_WORDS[m.group(1).lower()] >= 13:
        return True, f"{m.group(1)} siècle"
    return False, None

_STOPWORDS = {'de', 'du', 'des', 'la', 'le', 'les', 'un', 'une', 'et', 'sur', 'à', 'd', 'l',
              'rouleau', 'rouleaux', 'fragment', 'fragments', 'fragments', 'encyclique',
              'extraits', 'extrait', 'mention', 'formule', 'mort', 'mention', 'abbé',
              'abbesse', 'abbaye', 'évêque', 'comte', 'comtesse', 'siècle', 'vers', 'commencement',
              # Bibliographic/institutional boilerplate that appears in nearly
              # every entry regardless of subject - these were producing real
              # false matches (e.g. Delisle's "Abbon, abbé de Fleury" title-
              # matched a completely unrelated Mont-Saint-Michel monk-list
              # roll via the shared words "Bibliothèque" and "Saint-", not
              # anything actually about Abbon).
              'bibliothèque', 'saint-', 'manuscrit', 'manuscrits', 'ms', 'imp', 'impériale',
              'nationale', 'fonds', 'latin', 'bibl',
              # Prolific 17th-19th c. antiquarians/collections whose names
              # recur as a generic citation source across dozens of unrelated
              # entries (e.g. "Coll. Baluze" at the BNF) - not remotely
              # distinctive of any one roll's subject. "Baluze" specifically
              # produced a false match for Delisle's Bernard de Bésalu entry
              # against an unrelated Bernard, abbé de Marmoutier; "Martène"
              # (another such recurring editor/source name) did the same for
              # Delisle's Bernard, abbé de Marmoutier against a third,
              # unrelated Marmoutier abbot (Gauzbert). NOTE: "Gallia
              # christiana" (the standard diocesan-history reference work)
              # was deliberately NOT added here despite being similarly
              # generic - doing so broke a confirmed-correct match (Delisle
              # n° 43, Odouin abbé de Saint-Ghislain, d. 1142) with no
              # confirmed false positive to justify it. Blocklisting a word
              # is only safe once a specific false match traces to it.
              'baluze', 'martène'}

def _significant_words(title):
    """Proper-noun-shaped words from a Delisle title, for fuzzy matching
    against Dufour citation text when Dufour cites a Delisle roll by
    subject name instead of by roman numeral (both styles are seen in the
    extracted apparatus, e.g. 'L. Delisle, Vital de Sauvigny, p. 8' has no
    'n°' locator our numeral regex can catch). Deduplicated (order-preserving)
    - a name like "Bernard" repeated between a Delisle entry's title and its
    own commentary paragraph must not count as two independent matching
    words against a haystack that only contains it once, or a >=2-word
    threshold gets satisfied by one coincidental shared first name instead
    of genuine distinct overlap (this produced a real false match: Delisle's
    "Bernard, comte de Bésalu" spuriously "matched" an unrelated roll for a
    different "Bernard, abbé de Marmoutier")."""
    words = re.findall(r"[A-ZÀ-Ý][a-zà-ÿ'-]{2,}", title)
    return list(dict.fromkeys(w for w in words if w.lower() not in _STOPWORDS))

def delisle_cross_reference():
    """The direct payoff of pulling in Delisle's own 1866 catalog (87
    numbered rolls, I-LXXXVII): cross-reference every Delisle citation
    Dufour's apparatus makes against Delisle's own numbering. A Delisle
    roll number that's cited nowhere in Dufour's whole corpus is the
    strongest available candidate for "referenced by prior scholarship,
    not (yet found) referenced in Dufour's own edition" - exactly the
    research goal. Not proof (Dufour may cite it under a different
    locator format, have deliberately excluded a non-genuine roll, or
    simply fall in a later volume than what's been extracted), but the
    most concrete lead this pipeline can produce automatically. Two
    passes are applied before treating an entry as a real gap: (1) known
    out-of-scope entries (dated after this corpus's 1180 cutoff) are
    reported separately, not as gaps; (2) a fuzzy name match catches
    citations Dufour makes by subject name rather than Delisle's number."""
    if not os.path.exists(DELISLE_INDEX_PATH):
        print("\n(Delisle index not found at reference/delisle_index.json - skipping cross-reference)")
        return
    with open(DELISLE_INDEX_PATH, encoding='utf-8') as f:
        delisle_entries = json.load(f)
    delisle_by_num = {e['num']: e['title'] for e in delisle_entries}

    # Delisle was a prolific scholar; "cited_work LIKE '%Delisle%'" alone also
    # catches citations to his *other* books - "Vital de Savigny" (a saint's
    # biography), "Notes sur les poesies de Baudri de Bourgueil",
    # "Rouleaux des largesses de France" (a different genre/publication),
    # etc. Those are unrelated to the 1866 mortuary-rolls catalog this
    # cross-reference is built against, and letting them in produced real
    # false matches (e.g. a citation to "Vital de Savigny" mentioning
    # Norman place names coincidentally word-matched an unrelated Delisle
    # catalog entry about a Norman abbey). Require both "rouleau" and "mort"
    # (case-insensitive) in cited_work to isolate the target catalog - every
    # OCR/VLM spelling variant seen in this corpus keeps both words, and no
    # other Delisle work cited in the corpus has both.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.roll_num, c.cited_work, c.cited_locator, c.raw_text
        FROM citations c JOIN rolls r ON r.id = c.roll_id
        WHERE c.cited_work LIKE '%Delisle%'
          AND LOWER(c.cited_work) LIKE '%rouleau%'
          AND LOWER(c.cited_work) LIKE '%mort%'
    """)
    delisle_citation_rows = cursor.fetchall()
    conn.close()

    referenced = {}
    unmatched_delisle_citations = []
    for row in delisle_citation_rows:
        num = _extract_delisle_num(row['cited_locator']) or _extract_delisle_num(row['raw_text'])
        if num is not None:
            referenced.setdefault(num, []).append(row['roll_num'])
        else:
            unmatched_delisle_citations.append(row)

    # Entries dated after this corpus's 1180 cutoff can never legitimately
    # appear in it - computed up front so the fuzzy/title-word passes below
    # can skip them. Without this, a common first name (e.g. "Guillaume",
    # "Bernard", "Marie") on a provably out-of-scope entry (Delisle n° 62,
    # dated 1233) can spuriously "match" an unrelated in-scope roll that
    # happens to share the name - the entry is impossible to actually be
    # in Volume 1 regardless of what the word-overlap heuristic finds.
    out_of_scope_nums = {num for num, title in delisle_by_num.items()
                          if _delisle_entry_out_of_scope(title)[0]}

    # Second pass: fuzzy name match for Delisle entries not yet found by
    # number, against citations that mention Delisle but had no "n°" to
    # extract (e.g. cited by the roll's subject instead of its number).
    fuzzy_matched = {}
    for num, title in delisle_by_num.items():
        if num in referenced or num in out_of_scope_nums:
            continue
        sig_words = _significant_words(title)
        if not sig_words:
            continue
        for row in unmatched_delisle_citations:
            haystack = f"{row['cited_work']} {row['raw_text']}"
            # Require 2+ distinct significant words, same bar as the title-
            # match pass below - a single shared word (e.g. "Vital", from
            # Delisle's "Orderic Vital" coincidentally also appearing in an
            # unrelated citation to Delisle's *other* book "Vital de
            # Savigny") previously produced a real false match: Lanfranc's
            # entry spuriously "matched" a citation with no actual
            # connection to Lanfranc, Canterbury, or Orderic Vitalis at all.
            hits = {w for w in sig_words if w in haystack}
            if len(hits) >= 2:
                fuzzy_matched.setdefault(num, []).append((row['roll_num'], sorted(hits)))
                break

    # Third pass: match against roll titles/manuscripts directly, not just
    # citations that happen to mention "Delisle" by name - the same event
    # can clearly already be covered by our own corpus (e.g. Delisle's
    # "Abbon, abbé de Fleury, 1004" is our own roll 64, "...pour Abbéon,
    # abbé de Fleury, 13 novembre 1004") without Dufour's apparatus ever
    # cross-citing Delisle explicitly for that particular roll. Require 2+
    # matching significant words to avoid spurious single-word matches.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT roll_num, title, manuscripts FROM rolls")
    all_roll_rows = cursor.fetchall()
    conn.close()

    title_matched = {}
    for num, title in delisle_by_num.items():
        if num in referenced or num in fuzzy_matched or num in out_of_scope_nums:
            continue
        sig_words = _significant_words(title)
        if len(sig_words) < 2:
            continue
        for row in all_roll_rows:
            haystack = f"{row['title']} {row['manuscripts'] or ''}"
            hits = [w for w in sig_words if w in haystack]
            if len(hits) >= 2:
                title_matched[num] = (row['roll_num'], hits)
                break

    all_nums = set(delisle_by_num)
    cited_nums = set(referenced) | set(fuzzy_matched) | set(title_matched)

    in_scope, out_of_scope = {}, {}
    for num in all_nums - cited_nums:
        oos, reason = _delisle_entry_out_of_scope(delisle_by_num[num])
        (out_of_scope if oos else in_scope)[num] = reason

    print(f"\n--- Delisle cross-reference: {len(all_nums)} known Delisle rolls "
          f"({len(delisle_entries)} parsed of 87 total, 9 lost to OCR noise) ---")
    print(f"  {len(referenced)} cited by Delisle roll number (n°)")
    print(f"  {len(fuzzy_matched)} cited by subject name only (fuzzy-matched):")
    for num, matches in sorted(fuzzy_matched.items()):
        roll_num, sig_words = matches[0]
        print(f"    Delisle n° {num:<4} matched via {sig_words} -> roll {roll_num}")
    print(f"  {len(title_matched)} matched directly against a roll's own title/manuscripts "
          f"(same event, no explicit Delisle citation needed):")
    for num, (roll_num, hits) in sorted(title_matched.items()):
        print(f"    Delisle n° {num:<4} matched via {hits} -> roll {roll_num}")
    print(f"  {len(out_of_scope)} never cited but dated after this corpus's 1180 cutoff (expected absence, NOT a gap):")
    for num, reason in sorted(out_of_scope.items()):
        print(f"    Delisle n° {num:<4} ({reason}) {delisle_by_num[num][:70]}")

    print(f"\n*** {len(in_scope)} REAL gap candidates: in-scope (<=1180) Delisle rolls with "
          f"NO citation anywhere in the extracted Dufour corpus, by number or by name ***")
    for num in sorted(in_scope):
        print(f"  Delisle n° {num:<4} {delisle_by_num[num][:90]}")
    if not in_scope:
        print("  (none survive both filters yet - re-run once more of the corpus is extracted)")

if __name__ == "__main__":
    audit()
    citations_report()
    gap_candidates_report()
    delisle_cross_reference()
