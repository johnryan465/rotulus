"""Shared gazetteer + geocoding logic, used by server.py (live API) and
export_static_data.py (static build). Geocoding itself is delegated to
pipeline/geocoding.py (Wikidata-backed, cached in the `locations` table) -
this module no longer hardcodes a place-name dictionary.
"""
import re

from .geocoding import resolve_location


ROMAN_CENTURIES = {'VII': 650, 'VIII': 750, 'IX': 850, 'X': 950, 'XI': 1050, 'XII': 1150,
                    'XIII': 1250, 'XIV': 1350, 'XV': 1450, 'XVI': 1550}


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
