"""Shared gazetteer + geocoding logic, used by server.py (live API) and
export_static_data.py (static build). Geocoding itself is delegated to
pipeline/geocoding.py (Wikidata-backed, cached in the `locations` table) -
this module no longer hardcodes a place-name dictionary.
"""
import re

from .geocoding import resolve_location
from .entities_index import is_non_signer_role, is_non_signer_name, is_json_fragment


ROMAN_CENTURIES = {'VII': 650, 'VIII': 750, 'IX': 850, 'X': 950, 'XI': 1050, 'XII': 1150,
                    'XIII': 1250, 'XIV': 1350, 'XV': 1450, 'XVI': 1550}

# A normal titulus title/latin_text is a few hundred to ~2000 chars. A small
# number of extraction pages hit a degenerate generation loop and saved
# 10,000-27,000 chars of repeated text (and in at least one case the VLM's
# own reasoning commentary) verbatim into the DB. Movements/entities are
# user-facing, so any field is hard-capped before display rather than
# trusting the source data is always sane.
_MAX_DISPLAY_LEN = 400


def _safe_text(s):
    if not s:
        return s
    s = str(s)
    return s if len(s) <= _MAX_DISPLAY_LEN else s[:_MAX_DISPLAY_LEN].rstrip() + "…"


# Dufour's own convention for a titulus's heading is "<num> [<ms num>]
# <date>.- <place>", where <date> is either "S.d." (sans date - unknown) or
# an actual day/month/year, e.g. "24 [10] 19 mars [1051].– Casseres" or
# "176 [152] 1er novembre 1102 - Mainard, abbé de Cormeny". This is the only
# place a specific date for an individual titulus (as opposed to the whole
# roll's death-date) tends to appear in the extracted text.
_FRENCH_MONTHS = {
    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'août': 8, 'aout': 8, 'septembre': 9, 'octobre': 10,
    'novembre': 11, 'décembre': 12, 'decembre': 12,
}
_TITULUS_DATE_RE = re.compile(
    r'\b(\d{1,2})(?:er)?\s+(' + '|'.join(_FRENCH_MONTHS) + r')\.?\s*\[?(\d{3,4})\]?',
    re.IGNORECASE,
)


def extract_titulus_date(title):
    """Best-effort (year, month, day, display_string) for an individual
    titulus, or None if the text doesn't contain one (the common case -
    most tituli are marked "S.d." because no specific date is known for
    when that monastery responded)."""
    if not title:
        return None
    m = _TITULUS_DATE_RE.search(title)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _FRENCH_MONTHS.get(month_name.lower())
    try:
        day, year = int(day), int(year)
    except ValueError:
        return None
    if not (1 <= day <= 31 and 500 <= year <= 1600):
        return None
    display = re.sub(r'[\[\].]', '', m.group(0)).strip()
    return (year, month, day, display)


def _date_sortval(year, month, day):
    return year + (month - 1) / 12.0 + (day - 1) / 372.0


def _order_movements_temporally(movements):
    """Stable sort by best-available date: entries with an extracted date
    are placed chronologically; entries without one are interpolated
    between their nearest dated neighbors (by original extraction order,
    which is itself a decent proxy for sequence - Dufour's edition follows
    the manuscript's own binding order). If no entry in the roll has a
    date at all, the original order is returned unchanged."""
    dated_val = {i: _date_sortval(*m['date'][:3]) for i, m in enumerate(movements) if m.get('date')}
    if not dated_val:
        return movements
    dated_idx = sorted(dated_val)

    def sortval(i):
        if i in dated_val:
            return dated_val[i]
        before = max((j for j in dated_idx if j < i), default=None)
        after = next((j for j in dated_idx if j > i), None)
        if before is not None and after is not None:
            frac = (i - before) / (after - before)
            return dated_val[before] + frac * (dated_val[after] - dated_val[before])
        if before is not None:
            return dated_val[before] + 0.0001 * (i - before)
        if after is not None:
            return dated_val[after] - 0.0001 * (after - i)
        return 0

    order = sorted(range(len(movements)), key=lambda i: (sortval(i), i))
    return [movements[i] for i in order]


def get_roll_movements(cursor, roll_row):
    """Ordered list of a roll's stops (one per titulus) with every named
    entity at each stop and a best-effort date, sorted temporally where any
    date evidence exists. Distinct from get_roll_travels() below: that
    function only surfaces entities that carry their own location_name
    (9% of entities) for the map; this surfaces every entity regardless.
    Excludes patron saints/Christ/deities (see is_non_signer_role) - a
    titulus names its dedicatee formulaically, but that figure never
    actually signed/wrote it, so this list should be read as "named
    individuals at this stop" rather than literally "who signed"."""
    roll = dict(roll_row)
    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll["id"],))
    tituli = [dict(row) for row in cursor.fetchall()]

    movements = []
    for tit in tituli:
        cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
        entities = [dict(row) for row in cursor.fetchall()]
        # Drop entity rows that carry no information at all (see note in
        # gap_candidates_notes.md re: roll 151's degenerate-loop empty rows).
        entities = [e for e in entities if e.get("original_name") or e.get("normalized_name")]
        # A handful of entities carry a raw undigested JSON fragment as
        # their name (the same JSON-repair-fallback class of bug documented
        # for tituli titles in gap_candidates_notes.md) - '": "' only shows
        # up in genuine JSON key/value syntax, never in a real Latin/French name.
        entities = [e for e in entities
                    if not is_json_fragment(e.get("original_name")) and not is_json_fragment(e.get("normalized_name"))]
        # A titulus formulaically invokes its dedicatee (patron saint),
        # Christ, the Virgin, etc. - real named text, but never the actual
        # respondent who wrote/signed it. Excluded here specifically because
        # this list is presented as "who signed this stop".
        entities = [e for e in entities
                    if not is_non_signer_role(e.get("normalized_role")) and not is_non_signer_name(e.get("normalized_name"))]

        date = extract_titulus_date(tit.get("title"))
        movements.append({
            "titulus_id": tit["id"],
            "location_name": _safe_text(tit.get("location_name")) or None,
            "title": _safe_text(tit.get("title")),
            "date": date,
            "date_display": date[3] if date else None,
            "entities": [
                {
                    "name": _safe_text(e.get("normalized_name") or e.get("original_name")),
                    "role": _safe_text(e.get("normalized_role")),
                    "dates": _safe_text(e.get("normalized_dates")),
                }
                for e in entities
            ],
        })

    movements = _order_movements_temporally(movements)
    for step, m in enumerate(movements):
        m["step"] = step
    return movements


def extract_year(date_str):
    if not date_str:
        return None
    years = re.findall(r'\b(5\d{2}|[6-9]\d{2}|1\d{3})\b', date_str)
    if years:
        return int(years[0])
    for rom, yr in ROMAN_CENTURIES.items():
        if f"{rom}'" in date_str or f"{rom}\"" in date_str or f"{rom} " in date_str:
            return yr
    return None


def geocode_location(cursor, name):
    """Resolve a location name via the cached Wikidata resolver
    (pipeline/geocoding.py). Returns (lat, lon, display_name, is_approximate)
    or None. Requires a DB cursor since resolution results are cached in the
    `locations` table."""
    return resolve_location(cursor, name)


_EXCLUDE_WORDS = {
    "T", "S", "Sancti", "Sancte", "Sanctorum", "Sanctique", "Sanctus", "Sanctis",
    "Anima", "Amen", "Orate", "Oravimus", "Abbas", "Abbatis", "Titulus", "Implicit",
    "Deus", "Domini", "Domino", "Dominus", "Christo", "Christi", "Maria", "Marie",
    "Petri", "Martyris", "Apostolorum", "Pauli", "Johannis", "Trinitatis", "Ecclesie",
    "Monasterii", "Cenobii", "Cujus", "Vitalis", "Vitali", "Hospitalitatis",
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "Original", "Communication", "Wien", "Paris", "Bibliotheque", "Nationalbibl", "Briefe", "Brief",
    "EpP", "M", "G", "H", "R", "Rau", "Lul",
}
_EXCLUDE_WORDS_LOWER = {w.lower() for w in _EXCLUDE_WORDS}


def _fallback_place_name(text):
    """Best-effort place name from capitalized words when nothing geocodes."""
    words = re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\-]+\b', text)
    filtered = [w for w in words if w.lower() not in _EXCLUDE_WORDS_LOWER]
    return filtered[0] if filtered else None


def get_roll_travels(cursor, roll_row):
    """Build a travel path for a roll: origin (from title/manuscripts) followed
    by stops. Prefers entity-level locations (richer: named person + role) when
    entities have been extracted for a titulus, falling back to the titulus's
    own location_name otherwise.
    """
    roll = dict(roll_row)
    roll_year = extract_year(roll.get("date_str"))
    travels = []

    origin_geo = None
    origin_name = "Origin"
    for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]{3,}\b', (roll.get("title") or "") + " " + (roll.get("manuscripts") or "")):
        geo = geocode_location(cursor, word)
        if geo:
            origin_geo, origin_name = geo, geo[2]
            break

    if origin_geo:
        travels.append({
            "step": 0, "type": "origin", "name": origin_name, "coords": origin_geo[:2],
            "year": roll_year, "date_str": roll.get("date_str"), "is_approximate": origin_geo[3],
            "description": f"Origin: {(roll.get('title') or '')[:50]}...",
        })
    else:
        fallback = _fallback_place_name((roll.get("title") or "") + " " + (roll.get("manuscripts") or ""))
        if fallback:
            travels.append({
                "step": 0, "type": "origin", "name": fallback, "coords": None,
                "year": roll_year, "date_str": roll.get("date_str"), "is_approximate": True,
                "description": f"Origin: {(roll.get('title') or '')[:50]}...",
            })

    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll["id"],))
    tituli = [dict(row) for row in cursor.fetchall()]

    step = len(travels)
    for tit in tituli:
        cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
        entities = [dict(row) for row in cursor.fetchall()]
        entity_locations = [e for e in entities if e.get("location_name")]

        stops = []
        if entity_locations:
            for ent in entity_locations:
                geo = geocode_location(cursor, ent["location_name"])
                name = geo[2] if geo else ent["location_name"]
                coords = geo[:2] if geo else None
                approx = geo[3] if geo else True
                desc = f"{ent.get('normalized_name') or ent.get('original_name') or ''} ({ent.get('normalized_role') or ''})"
                stops.append((name, coords, approx, desc))
        elif tit.get("location_name"):
            geo = geocode_location(cursor, tit["location_name"])
            name = geo[2] if geo else tit["location_name"].strip()
            coords = geo[:2] if geo else None
            approx = geo[3] if geo else True
            stops.append((name, coords, approx, f"Titulus Header: {tit['location_name']}"))

        for name, coords, approx, desc in stops:
            is_dup = False
            if travels:
                last = travels[-1]
                is_dup = (last["coords"] == coords) if (coords and last["coords"]) else (last["name"].lower() == name.lower())
            if not is_dup:
                travels.append({
                    "step": step, "type": "stop", "name": name, "coords": coords,
                    "year": roll_year, "date_str": roll.get("date_str"), "is_approximate": approx,
                    "description": desc,
                })
                step += 1

    return travels
