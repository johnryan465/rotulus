"""Cross-roll entity/location aggregation for the Entities browser page.
Shared by server.py (live API) and export_static_data.py (static build).

Deduplicates by lower-cased normalized_name/location_name - this is a
name-string match, not a real identity resolution (a common name like
"Bernard" collapses many distinct historical individuals into one entry,
the same over-eager-matching risk documented in audit_rolls.py's
_significant_words). Good enough for a browsable index; not a claim that
every "Bruno" on the page is the same person.
"""
import re
from collections import defaultdict

_MAX_LIST = 40  # cap connection lists so a very common name doesn't blow up the payload

# Tituli formulaically invoke a church's patron saint, Christ, the Virgin,
# angels, etc. ("Titulus Sancti Petri...", "Anima eius ... per Christum...")
# - DOMAIN_GUIDANCE correctly extracts these as named entities in the text,
# but they are never the respondent who actually wrote/signed that titulus
# (a saint or deity cannot sign a contemporary document). Any UI that
# presents extracted entities as "who signed this" must exclude them.
_NON_SIGNER_ROLE_RE = re.compile(
    r'saint|martyr|apostle|deity|\bgod\b|christ|virgin|\bjesus\b|angel', re.IGNORECASE
)


def is_non_signer_role(role):
    return bool(role) and bool(_NON_SIGNER_ROLE_RE.search(role))


# Role-based filtering above misses formulaic invocations where the model
# didn't extract a role at all (e.g. "Christ" has no normalized_role on
# 69 of its 104 appearances in this corpus, "God" on 24 of 28) - checked
# directly against the DB, not guessed. These specific names are never a
# real historical individual regardless of role, so they're excluded by
# name as a backstop. Deliberately NOT a broader list: common baptismal
# names of real monks (Peter, Paul, Martin, Stephen...) also get "saint"-
# labeled appearances when they're a church's patron, but also have
# plenty of genuine non-saint appearances as real people - only role-based
# filtering is safe for those.
_NON_SIGNER_NAMES = {
    'christ', 'christo', 'christum', 'christus', 'jesus', 'jesus christ', 'jésus-christ',
    'god', 'deus', 'god/christ', 'god/father', 'god/lord', 'father (god)', 'father/god',
    'mary', 'virgin mary', 'mother of god', 'holy spirit', 'trinity', 'savior (christ)',
}


def is_non_signer_name(name):
    return bool(name) and name.strip().lower() in _NON_SIGNER_NAMES


def is_json_fragment(text):
    """True if text is raw undigested JSON-repair-fallback output rather
    than real content - the JSON-repair pipeline occasionally wraps a
    fragment of its own key/value syntax as if it were an extracted name
    instead of discarding it. '": "' and "': '" only occur in genuine
    JSON/Python-repr key/value syntax (double- and single-quoted variants
    both seen in this corpus), never in a real Latin/French name."""
    if not text:
        return False
    return '": "' in text or "': '" in text


def get_entity_index(cursor):
    cursor.execute("""
        SELECT e.titulus_id, e.original_name, e.normalized_name, e.normalized_role,
               e.normalized_dates, t.location_name AS titulus_location,
               t.roll_id, r.roll_num
        FROM entities e
        JOIN tituli t ON t.id = e.titulus_id
        JOIN rolls r ON r.id = t.roll_id
        WHERE e.normalized_name IS NOT NULL AND e.normalized_name != ''
    """)
    rows = [dict(row) for row in cursor.fetchall()]

    by_titulus = defaultdict(list)
    for r in rows:
        by_titulus[r['titulus_id']].append(r)

    people = defaultdict(lambda: {
        'name': None, 'roles': set(), 'dates': set(),
        'rolls': set(), 'locations': set(), 'co_occurring': set(), 'appearance_count': 0,
    })
    for ents in by_titulus.values():
        # A titulus formulaically invokes its dedicatee (patron saint),
        # Christ, the Virgin, etc. - real named text, but never the actual
        # respondent, so these specific appearances are excluded from the
        # index entirely (a person with other, real appearances - e.g.
        # Bruno of Cologne, who also appears as "abbot"/"founder" elsewhere -
        # still shows up via those; a purely liturgical name like "Christ"
        # or "God" drops out completely since it has no other kind).
        ents = [e for e in ents
                if not is_non_signer_role(e['normalized_role']) and not is_non_signer_name(e['normalized_name'])
                and not is_json_fragment(e['normalized_name']) and not is_json_fragment(e['original_name'])]
        names_here = {e['normalized_name'].strip() for e in ents if e['normalized_name'].strip()}
        for e in ents:
            name = (e['normalized_name'] or '').strip()
            if not name:
                continue
            key = name.lower()
            p = people[key]
            p['name'] = p['name'] or name
            p['appearance_count'] += 1
            if e['normalized_role']:
                p['roles'].add(e['normalized_role'].strip())
            if e['normalized_dates']:
                p['dates'].add(e['normalized_dates'].strip())
            if e['roll_id'] is not None:
                p['rolls'].add((e['roll_id'], e['roll_num']))
            if e['titulus_location']:
                p['locations'].add(e['titulus_location'].strip())
            for other in names_here:
                if other.lower() != key:
                    p['co_occurring'].add(other)

    result = []
    for p in people.values():
        result.append({
            'name': p['name'],
            'roles': sorted(p['roles'])[:_MAX_LIST],
            'dates': sorted(p['dates'])[:_MAX_LIST],
            'appearance_count': p['appearance_count'],
            'rolls': sorted(({'id': rid, 'roll_num': rn} for rid, rn in p['rolls']),
                             key=lambda x: (x['roll_num'] is None, x['roll_num']))[:_MAX_LIST],
            'locations': sorted(p['locations'])[:_MAX_LIST],
            'co_occurring': sorted(p['co_occurring'])[:_MAX_LIST],
        })
    result.sort(key=lambda p: (-p['appearance_count'], p['name'].lower()))
    return result


def get_location_index(cursor):
    cursor.execute("""
        SELECT t.id AS titulus_id, t.location_name, t.roll_id, r.roll_num
        FROM tituli t JOIN rolls r ON r.id = t.roll_id
        WHERE t.location_name IS NOT NULL AND t.location_name != ''
    """)
    rows = [dict(row) for row in cursor.fetchall()]

    locs = defaultdict(lambda: {'name': None, 'rolls': set(), 'titulus_ids': []})
    for r in rows:
        key = r['location_name'].strip().lower()
        l = locs[key]
        l['name'] = l['name'] or r['location_name'].strip()
        if r['roll_id'] is not None:
            l['rolls'].add((r['roll_id'], r['roll_num']))
        l['titulus_ids'].append(r['titulus_id'])

    cursor.execute("SELECT titulus_id, normalized_name, normalized_role FROM entities WHERE normalized_name IS NOT NULL AND normalized_name != ''")
    ent_by_titulus = defaultdict(set)
    for row in cursor.fetchall():
        name = (row['normalized_name'] or '').strip()
        if name and not is_non_signer_role(row['normalized_role']) and not is_non_signer_name(name) and not is_json_fragment(name):
            ent_by_titulus[row['titulus_id']].add(name)

    result = []
    for l in locs.values():
        people = set()
        for tid in l['titulus_ids']:
            people |= ent_by_titulus.get(tid, set())
        result.append({
            'name': l['name'],
            'roll_count': len(l['rolls']),
            'rolls': sorted(({'id': rid, 'roll_num': rn} for rid, rn in l['rolls']),
                             key=lambda x: (x['roll_num'] is None, x['roll_num']))[:_MAX_LIST],
            'people': sorted(people)[:_MAX_LIST],
        })
    result.sort(key=lambda l: (-l['roll_count'], l['name'].lower()))
    return result
