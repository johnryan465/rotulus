# Gap candidates: mortuary rolls not referenced in Dufour's edition

Working notes from cross-referencing Dufour's *Recueil des rouleaux des
morts* (full corpus now extracted, Volume 1: 8th c.–1180, 136 rolls) against
Delisle's 1866 catalog and independent literature search.

**Status: pipeline complete, cross-reference tool substantially hardened.**
`audit_rolls.py`'s `delisle_cross_reference()` runs against the full Volume 1
corpus (136 rolls, 3602 tituli, 1347 citations). A second round of work on
this tool (see "Precision bugs fixed this round" below) found and fixed
**six distinct false-positive/false-negative bugs** in the matcher itself -
the previous "final 7" list (n° 6, 11, 12, 17, 24, 55, 65) turned out to
contain both wrongly-included and wrongly-excluded entries. The corrected,
re-vetted list is **7 in-scope Delisle rolls with no match anywhere in the
corpus**: n° 2, 6, 18, 24, 35, 45, 55. Two are now headline-tier findings
with strong independent evidence: n° 24 (Lanfranc of Canterbury) and, new
this round, **n° 35 (Odo/Eudes, bishop of Cambrai)** - see below.

## Best-evidenced candidate: Lanfranc of Canterbury's roll (d. 1089) - confirmed to have existed, now lost

**This is the strongest finding of the whole search.** Delisle's own catalog
entry XXIV is titled *"**Mention** du rouleau de Lanfranc, archevêque de
Cantorbéry"* ("**Mention** of Lanfranc's roll") - not an edition of the roll,
because the roll itself does not survive. Delisle's own commentary (raw text,
line 6414) explains why he included it anyway:

> *"Orderic Vital mentionne le rouleau de Lanfranc, archevêque de Cantorbéry,
> sur lequel saint Anselme consigna une pièce de vers hexamètres: 'Compatriotae
> sui memoriam heroico carmine volumini lacrymabiliter indidit.'"*
> ("Orderic Vitalis mentions the roll of Lanfranc, archbishop of Canterbury,
> on which Saint Anselm tearfully set down his compatriot's memory in a piece
> of heroic [hexameter] verse.")

This is about as strong as "evidence of an unfound roll" gets within this
project's reach:
- **Independent, named, near-contemporary source**: Orderic Vitalis (writing
  ~1114-1141, a generation after Lanfranc's 1089 death) explicitly attests
  the roll's existence in his own *Historia Ecclesiastica* - this is not a
  guess or inference, it's a direct textual citation Delisle himself quotes.
- **A specific, identifiable contributor**: St. Anselm of Canterbury (Lanfranc's
  own successor as prior of Bec and as archbishop) is named as having
  personally written hexameter verses on it - Anselm is one of the most
  thoroughly studied and edited authors of the period, so his collected works
  are a plausible place to search for whether this specific poem survived
  independently of the roll (not yet checked - see next steps).
- **Not a citation-format mismatch** like most of the other candidates ruled
  out below - Delisle himself never had roll text to catalog, so there is
  nothing for Dufour to have "missed" by omission; the interesting fact is
  that the roll's *historical existence* is independently documented even
  though no edition of it exists in either catalog.
- Not in Dufour's extracted corpus either (checked directly - no roll or
  citation for Lanfranc anywhere in the 136-roll corpus).

**Next step if pursued further**: check critical editions of Anselm's
letters/poems (e.g. F.S. Schmitt's *Opera Omnia*) for whether this specific
hexameter piece was preserved and printed independently of the lost roll -
that would let us recover actual text "from" an otherwise-uncatalogued roll.

## New this round - second headline candidate: Odo/Eudes, bishop of Cambrai (d. 19 June 1113)

**Unlike Lanfranc, this roll's text actually survives and was published** -
this is arguably stronger evidence than Lanfranc's, just for a less
famous-to-modern-readers subject. Delisle's catalog entry n° XXXV ("Encyclique
sur la mort d'Eudes, évêque de Cambrai") is not a mention-in-passing - Delisle
prints the full encyclical text.

- **Identity**: "Eudes" is Delisle's French rendering of **Odo of Cambrai**
  (also called Odo of Tournai), a genuinely significant figure - founder and
  first abbot of Saint-Martin de Tournai, and author of *De peccato
  originali*, an important early-Scholastic theological treatise still
  studied today. He became bishop of Cambrai in 1105, was forced from his
  see by political opposition, retired to the abbey of Anchin, and died
  there 19 June 1113. This date and location are independently corroborated
  (Anchin's own necrology lists him under 19 June).
- **The encyclical's own text names him directly**: raw Delisle text (line
  8020ff) quotes the circular verbatim, issued by "Aquicinensis coenobii
  humilis congregatio" (the monks of Anchin), which states outright: *"domnum
  Odonem, Cameracensem episcopum, qui nuper apud nos de hoc mundo recessit"*
  ("our lord Odo, bishop of Cambrai, who recently departed this world among
  us").
- **Publication history**: Delisle's footnote states the encyclical "a été
  publiée par Martène, *Thesaurus anecdotorum*, V, 855" (published by Dom
  Edmond Martène in his major 18th-century primary-source collection), and
  that Delisle himself worked from two independent manuscript witnesses, one
  from the abbey of Aulne and one from Tournai - i.e. this isn't a single
  fragile copy, it's a text with an independent transmission history and a
  standard critical edition already in print, long before Dufour's Volume 1.
- **Checked directly against the complete 136-roll corpus**: no roll,
  titulus, or citation anywhere mentions Odo, Eudes, Cambrai, or Anchin in
  this context.

**Why this is absent from Dufour's Volume 1** is not yet established (unlike
Lanfranc, where Delisle's own text explains why no edition could exist - the
roll itself is lost). Here the text demonstrably exists and was already in
print via Martène. Possible explanations, not yet checked: Dufour may have
judged the Martène text insufficiently roll-like to include (cf. the Hervé
de Bourgdieu caveat below - not every circulaire funèbre was necessarily
attached to a touring rotulus), or simply reserved it for a later volume.
**Next step if pursued further**: locate Martène's *Thesaurus novus
anecdotorum* vol. V, p. 855 directly and check whether Delisle's or Martène's
apparatus describes the physical object (a bound circular vs. a genuine
touring rotulus with multiple monasteries' responses) - that distinction is
exactly what would confirm or break this as a "missing roll" rather than a
"published circular that was never a rotulus."

## Second candidate: a mortuary roll for Odilo of Cluny (d. 1049) and/or Hugues de Semur (d. 1109)

**The claim**: no dedicated mortuary roll for either of Cluny's two most
consequential abbots — Odilo (994–1049) and his successor Hugues de Semur
(1049–1109) — appears in Delisle's 1866 catalog, nor (as of this corpus's
partial extraction) in Dufour's edition.

**Evidence for their expected prominence in the roll network**:
- Our own extraction (roll 74, titulus id 662) contains a response *sent
  by Cluny* to an unrelated roll, quoting: *"Quem regit Hugo modo, dudum
  pius Odilo pastor"* ("whom Hugh now rules, formerly the pious shepherd
  Odilo") — proving Cluny was an active respondent in the circulation
  network during both men's tenures, and that both were locally
  significant enough to be named in passing by their own community.
- Multiple other rolls in our corpus (e.g. roll 106, roll 111) contain
  substantial responses *from* Cluny, confirming it as a major hub
  (visited/cited repeatedly across the corpus).
- Odilo specifically is credited with institutionalizing All Souls' Day
  and the formal liturgy of intercession for the dead across the Cluniac
  network (Nov. 2) — the exact devotional context the mortuary-roll genre
  belongs to. That his own death apparently did not generate one of the
  genre's landmark rolls is a striking irony, if true.
- Cluny was, by scholarly consensus, one of the largest producers and
  recipients of mortuary rolls of the entire period — the near-total
  absence of Cluny's own abbots as roll *subjects* (as opposed to
  respondents) is the anomaly.

**Verification performed**:
- Checked all 78 of 87 successfully parsed entries in Delisle's 1866
  catalog (`reference/delisle_index.json`) — no title mentions Odilo,
  Odilon, or Hugues/Hugo in a Cluny context.
- Manually grepped the raw Delisle OCR text (`delisle_1866_raw.txt`) for
  the 9 entries lost to parsing noise (XXXIX, XLVII, LII, LIII, LVII,
  LXIII, LXXIII, LXXX, LXXXIII) - confirmed titles for XXXIX (Marbode,
  évêque de Rennes), LXXX (Robert de Teissier, abbé de Saint-Evroul),
  LXXXIII (Elisabeth Sconinch, abbesse de Vorst) - none are Cluny-related.
  Could not locate the exact text for XLVII/LII/LIII/LVII/LXIII/LXXIII in
  the raw OCR (still genuinely missing, not ruled out).
- Checked Delisle's own alphabetical name/place index (the "TABLE" section
  at the end of his book): the "Cluny (Abbaye de)" entry lists page
  references (85, 157, 165, 372, 396, 425, 478, 479) and a specific
  sub-entry for "Odon, abbé, 361" (an earlier, 10th-century Cluny abbot) -
  but no entry at all for "Odilo"/"Odilon" or "Hugues" tied to Cluny,
  despite both being demonstrably more historically consequential than
  Odo.
- Calibration check: Bruno of Cologne's roll (d. 1101, extensively
  studied, book-length scholarship exists on it) IS present in both
  Delisle's catalog (as an entry titled "Extraits du rouleau de saint
  Bruno") and in our own extraction (roll 105) - confirming the method
  correctly finds famous rolls that do exist, which makes the Odilo/Hugues
  absence more meaningful by contrast rather than a general blind spot.
- Web search (French and English) for any existing scholarship discussing
  an Odilo or Hugues de Semur mortuary roll, or explicitly noting its
  absence/loss, came up empty.

**Update - important nuance found**: Odilo's death WAS formally announced in
writing - the "Epistola monachorum Silviniacensium de obitu Odilonis
abbatis" ("Letter of the monks of Souvigny concerning the death of Abbot
Odilo," addressed to Albert, abbot of Saint-Denis, accompanied by the
announcement of Hugues de Semur's succession) is a real, catalogued
hagiographic letter - it has a Bollandist reference number, **BHL 6280**,
meaning it is edited/known, not lost or unpublished. Its author was
Jotsald(us), Odilo's close disciple and biographer (also wrote the *Vita
Odilonis*). This is genuinely important but cuts a different way than a
simple "missing roll": BHL 6280 is a single letter to one specific
recipient (Saint-Denis), which is structurally distinct from a *rotulus*
(a physical parchment that toured dozens of monasteries accumulating
responses, growing to meters in length - the genre Delisle/Dufour
specifically catalog). So the refined finding is: Odilo's death was
documented via targeted correspondence, but there is still no evidence
either catalog knows of a *touring roll* for him specifically - meaning
either (a) Cluny used letters rather than a full rotulus for Odilo's own
death (a genuinely interesting historical point, if true, given his
central role in institutionalizing this exact commemorative practice), or
(b) a rotulus existed but is separately unattested. Not yet checked:
whether BHL 6280 has been edited/printed anywhere accessible (would let us
read its actual content for clues about how his death was communicated
more broadly), and whether the "Vita Odilonis" (multiple redactions exist,
by Jotsald and separately by Peter Damian) describes the funeral
communication practice in more detail.

**Caveats / what would strengthen or break this candidate**:
- This is absence-of-evidence, not evidence of a specific lost/uncatalogued
  document - it's possible no roll was ever made (Cluny may have relied on
  internal necrology/obituary commemoration for its own abbots rather than
  circulating an external rotulus), which would explain the absence
  without implying anything is "missing" from Dufour specifically.
- Update: the pipeline has now finished the full Volume 1 corpus (136
  rolls) - neither Odilo nor Hugues appears anywhere in the completed
  extraction either. The absence is now confirmed against the whole corpus,
  not just a partial run.
- The single strongest next step: check Bernard & Bruel's *Recueil des
  chartes de l'abbaye de Cluny* and/or a specialist Cluniac-necrology study
  (e.g. work building on Lemaître's *Répertoire des documents
  nécrologiques français*) for any record of a rotulus for either abbot -
  this project could not access those directly.

## Remaining candidates - final list against the complete corpus, re-vetted

After re-vetting all matching passes against the *complete* 136-roll corpus
(see "Precision bugs fixed this round" below), **7 in-scope Delisle rolls
remain genuinely unmatched**:

- **n° 2** - Formule de bref mortuaire employée par les moines de Reichenau
  (early 9th c., "commencement du neuvième siècle ?" - Delisle himself marks
  the date uncertain with a question mark) - a formula/template like n° 6,
  not a datable individual death; low priority.
- **n° 6** - Formule de réponse aux brefs mortuaires (anonymous reply
  formula, 9th c., from the same manuscript as Éginhard's letters) - a
  formula/template, not a datable event; low priority.
- **n° 18** - "Fragment d'un rouleau anonyme" (anonymous fragment, first
  half of the 11th c., two titles copied onto a flyleaf of Saint-Victor ms.
  65 - the second possibly from a monastery dedicated to St. Benoît).
  Anonymous by Delisle's own description; hard to verify further.
- **n° 24** - Lanfranc, archbishop of Canterbury (d. 1089) - see above,
  the strongest candidate found (roll confirmed to have existed via Orderic
  Vitalis, quoted by Delisle, but no edition survives).
- **n° 35** - Odo/Eudes, bishop of Cambrai (d. 1113) - see above, new this
  round; a *published, surviving* encyclical text (Martène, Thesaurus
  anecdotorum V, 855), unlike Lanfranc's lost roll.
- **n° 45** - Encyclique sur la mort de Hervé, moine (Delisle says "de
  Bourgdieu"; the encyclical's own text calls him "Dolensis coenobii
  monachus" - discrepancy not resolved), "vers 1150". **Important caveat in
  Delisle's own words**: "Je la donne sans pouvoir cependant affirmer
  qu'elle ait jamais fait partie d'un rouleau mortuaire" ("I give it without
  being able to confirm it was ever part of a mortuary roll") - published by
  d'Achery, Pez, and Mabillon's continuators as a literary circular, not
  necessarily ever a touring rotulus. Weakest of the remaining candidates
  for exactly the reason Delisle himself flags.
- **n° 55** - Fragments of a roll for "un abbé nommé Henri" - Delisle
  explicitly says he doesn't know which monastery this abbot belonged to,
  and proposes **1180** only as an approximate date, derived indirectly by
  cross-referencing the abbatial succession at Tournus (one of the roll's 7
  surviving response-fragments; the others came from an abbey in the
  diocese of Liège Delisle calls "Flona" - possibly Floreffe or Florennes,
  not confirmed - and from Saint-Jean d'Amiens). Tournus's own abbot list
  (Letbald, 1171-1179, succeeded by Gérard II, 1179-1197) is consistent with
  a response written right around 1179-1180, i.e. genuinely right at this
  corpus's cutoff and not resolvable either way without finding Henri's home
  monastery. Note: `audit_rolls.py`'s automated out-of-scope filter
  currently *mis*-excludes this entry (it picks up "1848" - the year
  Delisle received the fragment from a correspondent - rather than the
  roll's own approximate date); this is a known false negative in the tool,
  corrected manually here.

**Formerly on this list, now resolved and removed:**
- **n° 65** (Raoul, moine de Saint-Germain-des-Prés) - **confirmed
  out-of-scope**: explicitly dated "Treizième siècle" (13th c.) in text a
  parser bug had been silently truncating away (see below). Not a gap.
- **n° 17** (Bernard, comte de Bésalu, d. 1020) - **ruled out**: same
  situation as Guifred de Cerdagne below - covered by Dufour's own 1977
  article "Les rouleaux et encycliques mortuaires de Catalogne (1008-1102)",
  *Cahiers de civilisation médiévale* 20 (1977), which explicitly discusses
  Bernard I de Besalú's encyclical as document #2 of 6. Confirmed via
  Persée abstract fetch.
- **n° 11, n° 12** (two more anonymous Saint-Martial-de-Limoges fragments)
  - now correctly title-matched to our roll 45 (shared "Martial, Limoges").
- **n° 56** (Bertrand de Baux) - **confirmed out-of-scope**: Delisle's own
  raw text states his death "est rapportée au 5 avril 1181 par les auteurs
  de l'Art de vérifier les dates" - i.e. 1181, one year past this corpus's
  1180 cutoff. The automated tool currently still misses this (the date
  appears past its 600-char capture window); corrected manually here.

## Precision bugs fixed this round (relevant to trusting the above list)

Round one (see git history / prior notes) fixed two parser bugs bringing the
list from 38 candidates down to a "final 7" - but that 7 turned out to still
contain both false positives and false negatives. A second pass on
`audit_rolls.py` found and fixed **six more distinct bugs**, several of which
directly flipped whether specific entries counted as real gaps:

1. **Title paragraph itself split by an extra blank line**: entry LXV's
   (Raoul) title broke mid-sentence across what looked like 2 paragraphs
   before even reaching the date paragraph, so the existing 2-paragraph cap
   silently dropped "Treizième siècle." Bumped to 3 paragraphs
   (`parse_delisle.py`) - this alone is what surfaced n° 65 as correctly
   out-of-scope.
2. **300-char title truncation cut off dates buried in later commentary**
   (e.g. Bertrand de Baux's real death date appears in a *later* sentence
   than Delisle's own garbled "vers 1181" estimate). Widened to 600 chars.
   Still not always enough (n° 56 above) - a known remaining limitation.
3. **OCR digit-gap and letter-substitution in years**: beyond the already-
   fixed "1"→"4" leading-digit confusion, this scan also (a) inserts a
   stray space *anywhere* inside a 4-digit year ("1305"→"4 305", "1181"→
   "11 81" - not always at the same position) and (b) substitutes a
   lowercase "l" for a leading "1" ("1398"→"l398"). Fixed by collapsing all
   whitespace between digits before matching, and accepting "l" as an
   alternate leading character.
4. **`_significant_words` didn't deduplicate**: a name appearing twice in a
   Delisle entry (once in the title, once in its own commentary) counted as
   two independent "hits" against a target that only contained it once -
   letting a single coincidental shared word (usually a common first name)
   clear the "2+ words" match threshold alone. This produced a confirmed
   false match: Delisle's Bernard-de-Marmoutier entry (n° 30) was matching
   correctly, but the *duplicate-count* bug let the word "Bernard" alone
   falsely satisfy the threshold for the unrelated Bernard-de-Bésalu entry
   (n° 17) too. Fixed via order-preserving dedup.
5. **Citation filter too loose**: `cited_work LIKE '%Delisle%'` also matches
   citations to Delisle's *other* books (he was prolific) - "Vital de
   Savigny" (an unrelated saint's biography), "Notes sur les poésies de
   Baudri de Bourgueil", "Rouleaux des largesses de France" (a different
   genre), etc. This caused a real false match on our headline finding:
   Lanfranc's entry (n° 24) was spuriously "matched" via the single shared
   word "Vital" (from "Orderic **Vital**" vs. an unrelated citation to
   Delisle's "**Vital** de Savigny"). Fixed by requiring cited_work to
   contain both "rouleau" and "mort" (every real variant does; no other
   cited Delisle work has both). Also independently confirmed this same
   weak single-word threshold in the fuzzy-match pass was too permissive in
   general - tightened to require 2+ distinct words there too.
6. **Generic bibliographic/citation-source words counted as "significant"**:
   words like "Bibliothèque", "manuscrit", "Saint-" (a hyphen-truncated
   fragment), and prolific editors' names like "Baluze" and "Martène"
   recur across dozens of unrelated entries and produced further confirmed
   false matches (e.g. n° 14 Abbon-de-Fleury spuriously matched an unrelated
   Mont-Saint-Michel monk-list roll via "Bibliothèque"+"Saint-"). Added to
   stopwords - but only words with a *confirmed* false match traced to them;
   an earlier attempt to also stopword "Gallia"/"christiana" (a standard
   reference-work name) was reverted after it broke a genuinely correct
   match (n° 43, Odouin abbé de Saint-Ghislain) with no confirmed false
   positive to justify it.

**Net effect**: several entries flipped classification in both directions.
n° 11, 12, 14, 17, 30, 43 moved from "gap" to "genuinely matched/covered."
n° 2, 18, 35, 45 moved from "matched" (falsely) to "genuine gap." n° 56, 65
moved from "gap" to "correctly out of scope." This is worth internalizing as
the core lesson of this whole exercise: **the true signal-to-noise ratio in
this kind of cross-reference is very low, and a "match" or "gap" from any
automated pass is a lead to manually verify, never a conclusion on its own**
- exactly as demonstrated by n° 14 (still shows as unmatched by the
automated tool due to an "Abbon"/"Abbéon" spelling variant, but was manually
confirmed via direct query to already be covered by our own roll 64).

**Ruled out**: Guifred, comte de Cerdagne (Delisle n° XIX) - roll is
extremely well documented externally (Stiennon, *Annales du Midi*, 1964;
Dufour's own earlier article "Les rouleaux et encycliques mortuaires de
Catalogne") - almost certainly included in Dufour's edition, just cited
under a different reference than Delisle's number. (Bernard de Bésalu,
n° 17, is now confirmed ruled out on the same basis - see above.)

## External literature leads (not yet fully accessed)

- Warren Pezé, "Des rouleaux des morts inédits du haut Moyen Âge évoquant
  notamment l'archevêque Hugues de Reims," *Archivum Latinitatis Medii
  Aevi* 76 (2018), 189-208. Presents a commented edition of several
  9th-10th century mortuary rolls "adding to the short list of early
  medieval mortuary rolls" - i.e. explicitly unpublished material,
  published 13 years after Dufour's Volume 1 (2005) cutoff, so temporally
  impossible for Dufour to have included. Full text paywalled (Persée +
  academia.edu both blocked automated access) - worth obtaining via
  institutional access; if it names specific manuscripts, cross-check
  those directly against our extracted corpus.
