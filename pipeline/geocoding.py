"""Wikidata-backed geocoding, cached in the `locations` table (database.py).

Wikidata was picked over GeoNames/Pleiades specifically because it has good
coverage of medieval abbeys/dioceses *including their Latin name variants*
(e.g. "Sanctigallensis" as an alias of St. Gallen) - which is exactly what
appears in this corpus. Every resolved (or confirmed-unresolvable) name is
cached permanently, so a name is only ever looked up once across all runs.
"""
import re
import time
import httpx
from typing import Optional

USER_AGENT = "Rotulus-Research/1.0 (medieval mortuary rolls digitization project)"
SEARCH_LANGUAGES = ["la", "fr", "en"]  # try Latin first: most location_names are Latin toponyms
REQUEST_DELAY_S = 0.5  # be polite to the public Wikidata endpoints
MAX_RETRIES = 2
MAX_WAIT_S = 10.0  # cap on any single backoff sleep, regardless of Retry-After

# Once Wikidata hands out a 429 that survives MAX_RETRIES, its ban window is
# typically minutes long - retrying per-name (x3 languages, each with its own
# retry loop) burns tens of minutes without making progress. Trip a
# process-wide breaker instead: stop hitting the network for the rest of this
# run and let names fall through as unresolved-but-not-cached, so the next
# run (after the ban lifts) picks up where this one left off.
_circuit_open = False


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip().lower()


class _RateLimited(Exception):
    pass


def _get_with_retry(client: httpx.Client, url: str, params: dict):
    global _circuit_open
    if _circuit_open:
        raise _RateLimited("circuit open")
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        resp = client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        wait = min(float(resp.headers.get("Retry-After", delay)), MAX_WAIT_S)
        time.sleep(wait)
        delay *= 2
    _circuit_open = True
    raise _RateLimited(f"Wikidata still 429 after {MAX_RETRIES} retries - backing off for the rest of this run")


def _wbsearchentities(client: httpx.Client, name: str, lang: str):
    resp = _get_with_retry(client, "https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities",
        "search": name,
        "language": lang,
        "uselang": lang,
        "type": "item",
        "limit": 5,
        "format": "json",
    })
    return resp.json().get("search", [])


def _get_coordinates(client: httpx.Client, qid: str):
    """Returns (lat, lon, label) for a QID if it has a P625 (coordinate
    location) claim, else None."""
    resp = _get_with_retry(client, "https://www.wikidata.org/w/api.php", {
        "action": "wbgetentities",
        "ids": qid,
        "props": "claims|labels",
        "languages": "en|fr|la",
        "format": "json",
    })
    entity = resp.json().get("entities", {}).get(qid, {})
    claims = entity.get("claims", {}).get("P625")
    if not claims:
        return None
    coord = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    if not coord:
        return None
    labels = entity.get("labels", {})
    label = (labels.get("en") or labels.get("fr") or labels.get("la") or {}).get("value", qid)
    return coord["latitude"], coord["longitude"], label


def _search_wikidata(name: str) -> Optional[tuple]:
    """Try each search language in turn; return (lat, lon, label, qid) for
    the first candidate that actually has coordinates, else None. Lets
    _RateLimited propagate so callers can distinguish "genuinely not on
    Wikidata" from "couldn't check right now" - only the former should be
    cached as unresolved."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0) as client:
        for lang in SEARCH_LANGUAGES:
            try:
                candidates = _wbsearchentities(client, name, lang)
            except _RateLimited:
                raise
            except Exception as e:
                print(f"  Wikidata search failed ({lang}) for '{name}': {e}")
                continue
            time.sleep(REQUEST_DELAY_S)
            for cand in candidates:
                qid = cand.get("id")
                if not qid:
                    continue
                try:
                    result = _get_coordinates(client, qid)
                except _RateLimited:
                    raise
                except Exception as e:
                    print(f"  Wikidata coordinate lookup failed for {qid}: {e}")
                    continue
                time.sleep(REQUEST_DELAY_S)
                if result:
                    lat, lon, label = result
                    return lat, lon, label, qid
    return None


def resolve_location(cursor, raw_name: str):
    """Resolve a raw location name to (lat, lon, display_name, is_approximate),
    or None if it can't be resolved. Checks the `locations` cache first;
    only hits Wikidata on a genuine cache miss, and caches the outcome
    either way (including "unresolved", so we don't retry known misses) -
    unless the miss is due to rate limiting, in which case it's left
    uncached so a later run can actually retry it.
    """
    if not raw_name or not raw_name.strip():
        return None
    key = _normalize(raw_name)

    cursor.execute("SELECT display_name, lat, lon, is_approximate, source FROM locations WHERE query_name = ?", (key,))
    row = cursor.fetchone()
    if row:
        if row[4] == "unresolved":
            return None
        return row[1], row[2], row[0], bool(row[3])

    try:
        found = _search_wikidata(raw_name)
    except _RateLimited:
        return None

    if found:
        lat, lon, label, qid = found
        cursor.execute("""
            INSERT OR IGNORE INTO locations (query_name, display_name, lat, lon, is_approximate, source, wikidata_id)
            VALUES (?, ?, ?, ?, 0, 'wikidata', ?)
        """, (key, label, lat, lon, qid))
        return lat, lon, label, False

    cursor.execute("""
        INSERT OR IGNORE INTO locations (query_name, display_name, lat, lon, is_approximate, source)
        VALUES (?, NULL, NULL, NULL, 0, 'unresolved')
    """, (key,))
    return None
