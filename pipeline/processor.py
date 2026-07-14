import os
import json
import re
import base64
import httpx
import json_repair
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import PageContent, Roll, Titulus, Footnote, Entity, Citation

DOMAIN_GUIDANCE = """
- A NEW roll only begins where there is an actual roll header block on the page: a number
  (formatted like "N°" followed by a number, or a bare number placed with a date, a French
  scholarly description, and manuscript storage info immediately after it). roll_num MUST be
  the integer from that header block specifically - never copy an example number from these
  instructions, and never output it with "N°" or any other text attached.
- A roll header block has, in order: the roll number and date; then a French prose paragraph
  summarizing the document's content (this paragraph, and ONLY this paragraph, is "title" -
  it reads as a sentence describing who wrote to whom about what, e.g. "L'abbesse ... adresse
  au prêtre ... le nom des sœurs défuntes ..."); then an apparatus block listing manuscript
  witnesses and editions, each on its own line starting with a letter and a period, e.g.
  "A. Original perdu.", "B. Wien, ..., fol. 32v.", "a. M. Tangl, Bonifatius, p. 97, n° 55." -
  this whole apparatus block (every A./B./a./b.-prefixed line) goes verbatim into
  "manuscripts", NOT into "title". A line starting with "INDIQUÉ :" is neither the title nor
  manuscripts - it is itself a citation (the roll being indicated/mentioned in another
  scholar's catalog): add it to "citations" with cited_work as the author/catalog named after
  "INDIQUÉ :" and raw_text as the line verbatim. Never let a citation-shaped line (starting
  with a letter+period, or with "INDIQUÉ", "Cf.", "Éd.") end up in the "title" field.
- A bracketed number printed alone in a page's top corner/margin (e.g. "[762]") is a running
  chronological reference (the approximate year of the content on that page), NOT a roll
  number - do not use it as roll_num. If a page has no roll header block at all (it only
  continues text from a roll that started on a previous page), do not emit anything into
  "rolls" for it - put its tituli/footnotes/citations into "orphaned_tituli"/
  "orphaned_footnotes"/"orphaned_citations" instead, so they attach to the roll already in
  progress. This includes body text that continues a titulus started on a previous page with
  no new header on this page at all - still emit it as an entry in "orphaned_tituli" with
  title/location_name left as empty strings and latin_text/entities filled in from what's on
  this page. Never omit page content just because it lacks a header - every block of Latin
  text, every footnote, and every citation on the page must appear somewhere in the output.
- Tituli are monastic responses, usually starting with a number and a location (formatted like
  "1 [17] S.d.- Ripoll" or "101 [98] S.d.- Villemagne"). This titulus number is COMPLETELY
  DIFFERENT from roll_num and must NEVER be used as one: it counts individual monastic
  responses sequentially across the ENTIRE multi-hundred-page corpus (so it climbs into the
  hundreds even on early pages), it is followed by a SECOND bracketed number (a cross-reference
  to a different scholar's catalog), and the whole thing is immediately followed by a date and
  place inline in running prose ("101 [98] S.d.- Villemagne..."). roll_num, by contrast, is
  rare (far less than one per page), stands alone as a document header (typically centered,
  large, or on its own line) with NO second bracketed number attached, and introduces a
  multi-line French/Latin document with its own separate date + title + manuscripts apparatus
  block - never a single short response line. If a number is immediately followed by a second
  bracketed number and then "S.d.-" or a date and place in the same line/sentence, it is a
  titulus number - do not emit a "rolls" entry for it, however large the number is; put it in
  "orphaned_tituli" (or "tituli" if it's the first titulus of a roll whose real header block IS
  present on this page) instead.
- Body text of tituli is usually Latin.
- Entities: extract any named people (monks, abbots, bishops, saints, kings, etc.) explicitly
  mentioned within a titulus's body text. Only extract entities that are actually named in the
  text - do not invent or infer entities that aren't present.
- Footnotes appear at the bottom of the page, each with a number and its own text - e.g. "(3) Éd.
  supra, p. 56, n. 48." A footnote object ALWAYS has exactly two fields: footnote_num and text.
  footnote_num is SHORT - just the marker itself (e.g. "3", "12", "a", "*") - never a sentence,
  phrase, or any of the footnote's own text.
  NEVER put a footnote in the "footnotes" list that has cited_work/cited_locator fields instead -
  that shape belongs only in "citations" (see below). Extract the footnote's FULL text into
  "footnotes" even when it also contains a citation - footnotes and citations are not
  alternatives, a single footnote commonly produces both a footnotes entry AND a citations entry.
- Citations: this edition's apparatus (both the manuscript/editions header block near the roll
  number, and the footnotes) frequently cites earlier scholarly catalogs and editions - for
  example "L. Delisle, Rouleaux des morts du IXe au XVe s., p. 89, n° V" or "Gallia christiana,
  t. VII, col. 363". For every such citation to an external work, add an entry to "citations":
  cited_work is the author and/or title, cited_locator is the page/volume/catalog number within
  it, raw_text is the citation verbatim. These citations are the key research signal - a citation
  to a predecessor catalog (especially Delisle) may reference a roll not otherwise catalogued in
  this edition, so extract them even if the surrounding text is otherwise unremarkable. Do not
  extract citations for plain prose footnotes that identify a person or place without citing an
  external work - those go in "footnotes" only.
- Do not repeat any JSON key within the same object.
- If a field has no value on this page, use an empty string (or empty list/null where the schema
  allows it) - never copy the schema's own description text as if it were a real value.
"""

def _schema_block() -> str:
    """The JSON schema shared by every LLM/VLM prompt. Deliberately omits
    pdf_source/pdf_pages/page_num/half - those are already known from the
    page being processed and get injected programmatically after parsing
    (see _inject_page_metadata), rather than trusting the model to echo
    back fields that aren't actually being extracted from anything."""
    return """{
  "rolls": [
    {
      "roll_num": 1,
      "date_str": "string",
      "title": "French description",
      "manuscripts": "storage info",
      "tituli": [
        {
          "title": "header text",
          "location_name": "extracted place",
          "latin_text": "body text",
          "entities": [
            {
              "original_name": "name as written in the Latin text",
              "original_title": "title/role as written, or empty string",
              "footnote_num": "footnote marker number if annotated, else null",
              "normalized_name": "cleaned modern form of the name",
              "normalized_role": "e.g. abbot, monk, bishop, king, or empty string",
              "normalized_dates": "known/inferred dates, or empty string",
              "location_name": "place associated with this entity, or null"
            }
          ]
        }
      ],
      "footnotes": [
        {
          "footnote_num": "the number printed with this footnote, e.g. '3'",
          "text": "the footnote's full text verbatim"
        }
      ],
      "citations": [
        {
          "cited_work": "author and/or title of the cited work, e.g. 'L. Delisle, Rouleaux des morts du IXe au XVe s.'",
          "cited_locator": "page/volume/catalog number within it, e.g. 'p. 89, n° V'",
          "raw_text": "the citation verbatim as it appears in the source"
        }
      ]
    }
  ],
  "orphaned_tituli": [],
  "orphaned_footnotes": [],
  "orphaned_citations": []
}"""

_STRAY_STRING_SHAPE = {
    'titulus': lambda s: {'title': s},
    'orphaned titulus': lambda s: {'title': s},
    'footnote': lambda s: {'footnote_num': '', 'text': s},
    'orphaned footnote': lambda s: {'footnote_num': '', 'text': s},
    'citation': lambda s: {'cited_work': s, 'raw_text': s},
    'orphaned citation': lambda s: {'cited_work': s, 'raw_text': s},
    'entity': lambda s: {'original_name': s, 'normalized_name': s},
}

def _try_reassemble_fragment_run(fragments: list):
    """Recover from a severe json_repair failure mode: a single malformed
    nested object gets shredded into a run of bare strings, one per
    original '"key": value' line, instead of surviving as one dict (seen on
    a page where a titulus with 5 nested entities came back as 30+ fake
    single-field tituli). Since these fragments are literally sequential
    pieces of the original JSON text, rejoining them with commas and
    wrapping in braces can often reconstruct something json_repair can
    parse - recovering one coherent record instead of many garbled ones."""
    if len(fragments) < 2:
        return None
    try:
        obj = json_repair.loads("{" + ",".join(fragments) + "}")
    except Exception:
        return None
    return obj if isinstance(obj, dict) and obj else None

def _coerce_dicts(items: list, label: str) -> list:
    """Models occasionally emit a bare string instead of an object in a list
    that should contain only objects (e.g. "footnotes": ["some text"]).
    Salvage it into the minimal valid shape for that list rather than
    discarding it - a malformed fragment is still real extracted content,
    and losing it to a formatting slip defeats the point of an exhaustive
    extraction pipeline. Only drop entries with no usable content at all
    (empty/whitespace-only strings, or types with no sane salvage shape).
    A consecutive run of bare strings is tried as one shredded object
    first (see _try_reassemble_fragment_run) before falling back to
    wrapping each fragment individually."""
    wrap = _STRAY_STRING_SHAPE.get(label)
    items = items or []
    kept = []
    i, n = 0, len(items)
    while i < n:
        x = items[i]
        if isinstance(x, dict):
            kept.append(x)
            i += 1
            continue
        if isinstance(x, str) and x.strip():
            run, j = [x], i + 1
            while j < n and isinstance(items[j], str) and items[j].strip():
                run.append(items[j])
                j += 1
            reassembled = _try_reassemble_fragment_run(run) if len(run) > 1 else None
            if reassembled is not None:
                print(f"  Reassembled {len(run)} shredded fragments into one {label} object.")
                kept.append(reassembled)
            elif wrap:
                for s in run:
                    print(f"  Salvaging malformed {label} entry (was a bare string, not an object): {s[:80]!r}")
                    kept.append(wrap(s))
            else:
                for s in run:
                    print(f"  Dropping unsalvageable {label} entry: {s!r}")
            i = j
            continue
        print(f"  Dropping unsalvageable {label} entry: {x!r}")
        i += 1
    return kept

def _only_dicts(items: list, label: str) -> list:
    """For lists where no safe salvage shape exists (rolls: a bare string
    can't be turned into a fake roll_num without corrupting the sequence
    validation that guards against hallucinated roll numbers). Still logs
    what was dropped so it's visible, never silent."""
    kept = []
    for x in items or []:
        if isinstance(x, dict):
            kept.append(x)
        else:
            print(f"  Dropping unsalvageable {label} entry: {x!r}")
    return kept

def _null_to_str(d: dict, *keys) -> dict:
    """Coerce required-string fields to an actual string, treating a
    MISSING key the same as an explicit JSON null: both -> "" (a Pydantic
    field default only kicks in when the key is absent, so this also
    covers fields - like Titulus.title or Citation.cited_work - that are
    required with no default at all, where a missing key would otherwise
    crash validation for the whole page). A stray list -> newline-joined
    text (models sometimes emit a multi-line field, like the manuscripts
    apparatus block, as a JSON array of lines instead of one string).
    Never let a shape slip on one field crash validation for the whole
    page."""
    for k in keys:
        v = d.get(k)
        if v is None:
            d[k] = ''
        elif isinstance(v, list):
            d[k] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str):
            d[k] = str(v)
    return d

def _stringify(v):
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return str(v)

_TITULUS_SHAPED_TITLE_RE = re.compile(r'^\s*S\.?\s*-?\s*d\.?\s*[-.]', re.IGNORECASE)

def _split_orphan_shaped_rolls(rolls: list):
    """Two cases where a "roll" entry from the model isn't a real roll:
    1. No roll_num at all - usually the mirror image of
       _reclaim_misplaced_top_level: the model nests orphaned_tituli/
       orphaned_footnotes/orphaned_citations as an extra item inside the
       "rolls" list instead of as top-level siblings.
    2. A titulus number/header mistaken for a roll header - DOMAIN_GUIDANCE
       explains the difference (titulus numbers are frequent, paired with a
       second bracketed cross-reference number, and inline with "S.d.-
       Place"; roll numbers are rare, standalone document headers), but the
       model doesn't reliably follow it. A real roll title is a French
       descriptive sentence; "S.d.- Villemagne, S. Martin, S. Majan." is
       exactly the titulus-header shape and is a much more reliable signal
       than trusting whatever roll_num the model attached to it - trust
       this over the model's own roll_num claim, however plausible-looking.
    In both cases: Pydantic can't (case 1) or shouldn't (case 2) construct a
    real Roll from this, so rather than letting it crash validation for the
    WHOLE page or silently fabricate a roll from titulus content - either of
    which would misattribute or lose an otherwise-good roll sitting right
    next to it - pull out any usable content (including the roll's own
    nested tituli/footnotes/citations, which is where the real extracted
    text usually lives when case 2 happens) before the real rolls are built."""
    good, salvaged = [], {'orphaned_tituli': [], 'orphaned_footnotes': [], 'orphaned_citations': []}
    for r in rolls:
        title = (r.get('title') or '').strip()
        is_titulus_shaped = bool(_TITULUS_SHAPED_TITLE_RE.match(title))
        if r.get('roll_num') is None or is_titulus_shaped:
            reason = "no roll_num" if r.get('roll_num') is None else f"title {title!r} is titulus-shaped, not a real roll title"
            print(f"  Roll entry rejected ({reason}) - salvaging its content instead of failing/misattributing the whole page: keys={list(r.keys())}")
            for k in salvaged:
                v = r.get(k)
                if v:
                    salvaged[k].extend(v if isinstance(v, list) else [v])
            for nested_key, orphan_key in [('tituli', 'orphaned_tituli'), ('footnotes', 'orphaned_footnotes'), ('citations', 'orphaned_citations')]:
                v = r.get(nested_key)
                if v:
                    salvaged[orphan_key].extend(v if isinstance(v, list) else [v])
        else:
            good.append(r)
    return good, salvaged

def _reclaim_misplaced_top_level(parsed: dict) -> dict:
    """The model sometimes emits footnotes/citations/tituli as top-level keys
    sibling to "rolls" instead of nested inside the roll object they belong
    to (a schema-shape slip, not a value error) - e.g. {"rolls": [{...}],
    "footnotes": [...]} instead of the footnotes living inside that roll.
    Pydantic silently drops unknown top-level keys, which would otherwise
    discard real extracted content. Reclaim them into the last roll (the
    most likely owner of trailing page content like footnotes), or into
    orphaned_* if there's no roll on this page at all."""
    rolls = parsed.get('rolls') or []
    target = rolls[-1] if rolls and isinstance(rolls[-1], dict) else None
    for key, orphan_key in [('footnotes', 'orphaned_footnotes'), ('citations', 'orphaned_citations'), ('tituli', 'orphaned_tituli')]:
        stray = parsed.pop(key, None)
        if not stray:
            continue
        stray_list = stray if isinstance(stray, list) else [stray]
        print(f"  Reclaiming {len(stray_list)} misplaced top-level {key!r} entries (model put them outside the roll object).")
        dest_key = key if target is not None else orphan_key
        dest = target if target is not None else parsed
        dest[dest_key] = (dest.get(dest_key) or []) + stray_list
    return parsed

def _inject_page_metadata(parsed: dict, metadata: Dict[str, Any]) -> dict:
    """Fill in pdf_source/pdf_pages/page_num/half from what we already know
    about the page being processed, rather than trusting the model to
    generate them - these are deterministic, not extracted data, and
    asking the model to produce them just adds output length and a class
    of type/value errors (e.g. pdf_source coming back as an int). Also
    defensively coerces/repairs a handful of shapes models commonly get
    wrong (see helpers below) rather than losing the whole page to one
    malformed field.
    """
    pdf_idx, page_num, half = metadata.get('pdf_idx'), metadata.get('page_num'), metadata.get('half')
    parsed = _reclaim_misplaced_top_level(parsed)

    def fix_footnote_num(d):
        # Models frequently emit a bare number (or other non-string) here;
        # Pydantic's str fields don't auto-coerce, so this would otherwise
        # be a validation failure on nearly every page with numbered footnotes.
        if d.get('footnote_num') is not None and not isinstance(d['footnote_num'], str):
            d['footnote_num'] = _stringify(d['footnote_num'])
        return d

    def fix_entity(e):
        # Models occasionally use a shorthand key instead of the schema's
        # original_name - rename rather than lose the whole page to a
        # missing-required-field validation error over a naming slip.
        if 'original' in e and 'original_name' not in e:
            e['original_name'] = e.pop('original')
        if 'name' in e and 'original_name' not in e:
            e['original_name'] = e.pop('name')
        e = fix_footnote_num(_null_to_str(e, 'original_name', 'normalized_name'))
        # Both original_name and normalized_name are required with no schema
        # default - if only one survived extraction, cross-fill from it
        # rather than crash on the other being absent.
        e.setdefault('original_name', e.get('normalized_name') or '')
        e.setdefault('normalized_name', e.get('original_name') or '')
        return e

    def fix_titulus(t):
        t['page_num'] = page_num
        t['half'] = half
        _null_to_str(t, 'title', 'location_name', 'latin_text')
        t['entities'] = [fix_entity(e) for e in _coerce_dicts(t.get('entities'), 'entity')]
        return t

    def fix_footnote(f):
        f['page_num'] = page_num
        f['half'] = half
        f = fix_footnote_num(_null_to_str(f, 'text'))
        # Unlike Entity.footnote_num (legitimately optional), Footnote.footnote_num
        # is required - a footnote without a number is a marker of a degenerate/
        # placeholder entry, not real data, so coerce rather than crash.
        if f.get('footnote_num') is None:
            f['footnote_num'] = ''
        return f

    rolls_list, salvaged_orphans = _split_orphan_shaped_rolls(_only_dicts(parsed.get('rolls'), 'roll'))
    for key, vals in salvaged_orphans.items():
        if vals:
            parsed[key] = (parsed.get(key) or []) + vals

    good_rolls = []
    for roll in rolls_list:
        roll['pdf_source'] = str(pdf_idx)
        roll['pdf_pages'] = [page_num]
        roll['date_str'] = _stringify(roll.get('date_str'))
        _null_to_str(roll, 'title', 'manuscripts')
        roll.setdefault('title', '')
        roll.setdefault('manuscripts', '')
        tituli, footnotes = _repair_titulus_footnote_confusion(
            _coerce_dicts(roll.get('tituli'), 'titulus'), _coerce_dicts(roll.get('footnotes'), 'footnote'))
        footnotes, citations = _repair_footnote_citation_confusion(
            footnotes, _coerce_dicts(roll.get('citations'), 'citation'))
        roll['tituli'] = [fix_titulus(t) for t in tituli]
        roll['footnotes'] = _drop_empty_footnotes(fix_footnote(f) for f in footnotes)
        roll['citations'] = [_null_to_str(c, 'cited_work', 'raw_text') for c in citations]
        good_rolls.append(roll)
    parsed['rolls'] = good_rolls

    ot, of = _repair_titulus_footnote_confusion(
        _coerce_dicts(parsed.get('orphaned_tituli'), 'orphaned titulus'),
        _coerce_dicts(parsed.get('orphaned_footnotes'), 'orphaned footnote'))
    of, oc = _repair_footnote_citation_confusion(
        of, _coerce_dicts(parsed.get('orphaned_citations'), 'orphaned citation'))
    parsed['orphaned_tituli'] = [fix_titulus(t) for t in ot]
    parsed['orphaned_footnotes'] = _drop_empty_footnotes(fix_footnote(f) for f in of)
    parsed['orphaned_citations'] = [_null_to_str(c, 'cited_work', 'raw_text') for c in oc]
    return parsed

def _drop_empty_footnotes(footnotes):
    """Placeholder footnotes with neither a number nor text carry no
    information - a real footnote always has at least one of the two."""
    return [f for f in footnotes if f.get('footnote_num') or f.get('text')]

def _repair_footnote_citation_confusion(footnotes: list, citations: list):
    """Best-effort recovery for two distinct shape slips:
    1. A pure citation-shaped object (cited_work/cited_locator, no text)
       ends up in the footnotes list - move it into citations instead of
       losing the data to a validation error.
    2. A footnote legitimately has BOTH footnote_num/text AND cited_work -
       exactly the dual-purpose case DOMAIN_GUIDANCE asks for ("a single
       footnote commonly produces both a footnotes entry AND a citations
       entry"). Keep it as a footnote (so 'text' isn't lost), but also
       emit the citation half - Footnote has no cited_work field, so if we
       don't copy it out here Pydantic silently drops it when the object is
       later parsed as a Footnote."""
    good_footnotes = []
    for f in footnotes:
        has_citation = 'cited_work' in f
        if has_citation and 'text' not in f:
            citations.append({
                'cited_work': f.get('cited_work', ''),
                'cited_locator': f.get('cited_locator', ''),
                'raw_text': f.get('raw_text') or f.get('cited_work', ''),
            })
        else:
            if has_citation:
                citations.append({
                    'cited_work': f.get('cited_work', ''),
                    'cited_locator': f.get('cited_locator', ''),
                    'raw_text': f.get('raw_text') or f.get('cited_work', ''),
                })
            good_footnotes.append(f)
    return good_footnotes, citations

def _repair_titulus_footnote_confusion(tituli: list, footnotes: list):
    """Mirror of the above: if the model puts a footnote-shaped object
    (footnote_num, no title) into the tituli list, move it into footnotes."""
    good_tituli = []
    for t in tituli:
        if 'title' not in t and 'footnote_num' in t:
            footnotes.append(t)
        else:
            good_tituli.append(t)
    return good_tituli, footnotes

def build_text_prompt(text: str, metadata: Dict[str, Any]) -> str:
    return f"""
Extract structured data from the following OCR text of a medieval mortuary rolls edition.
{DOMAIN_GUIDANCE}
Metadata: {metadata}
Text: {text}

Return ONLY a JSON object matching this exact schema:
{_schema_block()}
"""

def build_vision_prompt(metadata: Dict[str, Any]) -> str:
    return f"""
You are an expert paleographer and historian.
Attached is a page image from a scholarly edition of medieval mortuary rolls (Jean Dufour, Recueil des rouleaux des morts, 2005).

This is public historical data for academic research.
Please transcribe and extract all document entries (Rolls) and monastic responses (Tituli) into structured JSON.
{DOMAIN_GUIDANCE}

Return ONLY a JSON object matching this exact schema:
{_schema_block()}
"""

def extract_json(raw: str) -> dict:
    """Extract a JSON object from raw LLM output, tolerating leading/trailing
    prose or markdown fences, AND - critically - truncated/malformed output
    (a model hitting its context limit mid-generation, a dangling key with no
    value, a stray unquoted fragment). We never want to throw away an entire
    page's worth of otherwise-valid extraction because the last few tokens
    got cut off: json_repair recovers everything up to the truncation point
    by balancing/closing whatever structure is still open, rather than
    failing the whole parse. This is the difference between losing one
    trailing footnote and losing the whole page to a regex fallback."""
    start = raw.find('{')
    candidate = raw[start:] if start != -1 else raw
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return json_repair.loads(candidate)


class PageProcessor(ABC):
    """Base class for processing a page of the mortuary rolls edition."""

    @abstractmethod
    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        pass


class LegacyRegexProcessor(PageProcessor):
    """Fallback implementation using refined regex logic."""
    def __init__(self):
        import re
        self.re = re

    def is_latin_text(self, text):
        if not text or len(text.strip()) < 15: return False
        fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von ", " une "}
        la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
        t = " " + text.lower() + " "
        fr_de = sum(t.count(w) for w in fr_de_stop_words)
        la = sum(t.count(w) for w in la_stop_words)
        return la > fr_de

    def get_roll_numbers(self, line, expected_next, pdf_idx, line_idx):
        from .validation import PDF_ROLL_BOUNDS
        if line_idx < 3 and self.re.match(r'^(?:N[oO°\?]*\s*)?\d+(?:\s*-\s*\d+)?\s*$', line.strip()): return None
        min_r, max_roll = PDF_ROLL_BOUNDS.get(pdf_idx, (1, 200))
        m = self.re.match(r'^(?:N[oO°\?]*\s*)?(\d+)(?:\s*[\-\/]\s*(\d+))?', line.strip())
        if m:
            nums = [int(m.group(1))]
            if m.group(2): nums.extend(range(int(m.group(1)) + 1, int(m.group(2)) + 1))
            if any(min_r <= n <= max_roll for n in nums) and any(expected_next - 2 <= n <= expected_next + 10 for n in nums):
                if not line.strip()[m.end():].strip().startswith("["): return nums
        return None

    def get_titulus_info(self, line):
        s = line.strip()
        m1 = self.re.match(r'^(\d+)\s*\[(\d+)\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m1: return m1.group(4).strip(" ."), s
        m2 = self.re.match(r'^(\d+)\s+(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m2 and int(m2.group(1)) < 500: return m2.group(3).strip(" ."), s
        if self.re.match(r'^T[T]?\.\s+([^0-9,;:\.\n\r]{3,40})', s):
            return (s.split(".", 1)[1].split(".")[0].strip() if "." in s else s), s
        return None, None

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        pdf_idx, page_num, half, expected_next = metadata.get('pdf_idx', 1), metadata.get('page_num', 1), metadata.get('half', 'full'), metadata.get('expected_next_roll', 1)
        lines = text.split('\n'); f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines; content = PageContent()
        i = 0
        while i < len(main_lines):
            r_nums = self.get_roll_numbers(main_lines[i], expected_next, pdf_idx, i)
            if r_nums:
                title_parts, ms_parts, j = [], [], i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l or self.get_titulus_info(l)[0] or self.is_latin_text(l) or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    if self.re.match(r'^[A-E]\.\s+|^Original\s+|^B\.\s+|^C\.\s+|^London;|^Paris;|^München;', l): ms_parts.append(l)
                    else: title_parts.append(l)
                    j += 1
                h_clean = self.re.sub(r'^(?:N[oO°\?]*\s*)?[\d\s\-\/]+', '', main_lines[i].strip()).strip()
                if h_clean: title_parts.insert(0, h_clean)
                for n in r_nums:
                    content.rolls.append(Roll(roll_num=n, title=" ".join(title_parts), manuscripts=" ".join(ms_parts), pdf_source=f"Dufour T1 ({pdf_idx})", pdf_pages=[page_num]))
                expected_next, i = max(r_nums) + 1, j; continue
            loc, h_text = self.get_titulus_info(main_lines[i])
            if loc:
                text_parts, j = [], i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l or self.get_titulus_info(l)[0] or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    text_parts.append(l); j += 1
                tit = Titulus(title=h_text[:100], location_name=loc, latin_text=" ".join(text_parts), page_num=page_num, half=half)
                if content.rolls: content.rolls[-1].tituli.append(tit)
                else: content.orphaned_tituli.append(tit)
                i = j; continue
            i += 1
        if f_idx != -1:
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip()
                if not fn_s: continue
                fm = self.re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                fn_obj = Footnote(footnote_num=self.re.findall(r'\d+', fm.group(1))[0] if fm and self.re.findall(r'\d+', fm.group(1)) else str(idx), text=fm.group(2) if fm else fn_s, page_num=page_num, half=half)
                if content.rolls: content.rolls[-1].footnotes.append(fn_obj)
                else: content.orphaned_footnotes.append(fn_obj)
        return content


class LocalOllamaProcessor(PageProcessor):
    """
    Processor using Ollama on the remote 3090 machine (Stanley).
    Expects OLLAMA_HOST environment variable (e.g. http://192.168.0.116:11434).
    """
    def __init__(self, model="gemma4:26b", host=None, num_ctx=16384, num_predict=7000):
        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
        # num_ctx is the model's total context window (prompt + response combined) -
        # must match what the specific model actually supports, so it's tunable per
        # instance rather than a shared hardcoded constant (an 8B model like llama3:8b
        # tops out at 8192; a newer/larger model may support far more).
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        prompt = build_text_prompt(text, metadata)
        try:
            with httpx.Client(timeout=600.0) as client:
                response = client.post(f"{self.host}/api/generate", json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_predict": self.num_predict,
                        "num_ctx": self.num_ctx,
                        "temperature": 0,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256
                    }
                })
                response.raise_for_status()
                data = response.json().get("response", "{}")
                try:
                    parsed = _inject_page_metadata(extract_json(data), metadata)
                    return PageContent(**parsed)
                except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                    print(f"JSON Parsing Error: {e}")
                    print(f"Raw Output:\n{data}")
                    raise
        except Exception as e:
            print(f"Local Ollama failed: {e}. Falling back to Regex.")
            return LegacyRegexProcessor().process_page(text, metadata)


class LLMStructuredProcessor(PageProcessor):
    """Cloud-based structured extraction using Gemini 1.5 Pro."""
    def __init__(self, model_name="gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        prompt = build_text_prompt(text, metadata)
        try:
            response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            return PageContent(**extract_json(response.text))
        except Exception as e:
            print(f"Gemini processor failed: {e}. Falling back to Regex.")
            return LegacyRegexProcessor().process_page(text, metadata)


class LocalVLLMProcessor(PageProcessor):
    """
    Vision-based extraction using Gemma 4 (26B) via Ollama on the 3090 (Stanley).
    Primary extraction path: reads the page image directly instead of relying
    on the OCR text pipeline, which is known to miss content on some pages.
    """
    def __init__(self, model="gemma4:26b", host=None, num_ctx=16384, num_predict=7000):
        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        image_path = metadata.get('image_path')
        if not image_path or not os.path.exists(image_path):
            return LegacyRegexProcessor().process_page(text, metadata)

        with open(image_path, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode('utf-8')

        prompt = build_vision_prompt(metadata)
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(f"{self.host}/api/generate", json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "format": "json",
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_predict": self.num_predict,
                        "num_ctx": self.num_ctx,
                        "temperature": 0,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256
                    }
                })
                response.raise_for_status()
                body = response.json()
                if body.get("done_reason") == "length":
                    print(f"  WARNING: response hit num_predict budget ({self.num_predict}) for "
                          f"{metadata.get('filename')} - likely truncated (possibly mid-repetition-loop); "
                          f"trailing content on this page may be incomplete or missing.")
                data = body.get("response", "{}")
                try:
                    parsed = _inject_page_metadata(extract_json(data), metadata)
                    return PageContent(**parsed)
                except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                    print(f"VLLM JSON Parsing Error: {e}")
                    print(f"Raw VLLM Output (first 500 chars):\n{data[:500]}...")
                    print(f"Raw VLLM Output (last 500 chars):\n...{data[-500:]}")
                    return LegacyRegexProcessor().process_page(text, metadata)
        except Exception as e:
            print(f"Local VLLM failed: {e}. Falling back to Regex.")
            return LegacyRegexProcessor().process_page(text, metadata)
