"""Cross-roll entity/location aggregation for the Entities browser page.
Shared by server.py (live API) and export_static_data.py (static build).

Deduplicates by lower-cased normalized_name/location_name - this is a
name-string match, not a real identity resolution (a common name like
"Bernard" collapses many distinct historical individuals into one entry,
the same over-eager-matching risk documented in audit_rolls.py's
_significant_words). Good enough for a browsable index; not a claim that
every "Bruno" on the page is the same person.
"""
from collections import defaultdict

_MAX_LIST = 40  # cap connection lists so a very common name doesn't blow up the payload


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

    cursor.execute("SELECT titulus_id, normalized_name FROM entities WHERE normalized_name IS NOT NULL AND normalized_name != ''")
    ent_by_titulus = defaultdict(set)
    for row in cursor.fetchall():
        name = (row['normalized_name'] or '').strip()
        if name:
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
