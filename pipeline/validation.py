"""Shared validation for extracted roll numbers. Every processor (regex, local
LLM, local VLM, cloud) is subject to the same sanity check before its output
is accepted by the orchestrator - a hallucinated roll number from an LLM/VLM
processor is exactly as dangerous to the sequence-tracking state machine as
a regex mis-match, so it gets the same guard.
"""

# Known roll-number range per source PDF (Dufour T1, split into 4 files by
# page range). Derived from the legacy regex processor's original bounds.
PDF_ROLL_BOUNDS = {1: (1, 74), 2: (74, 105), 3: (106, 121), 4: (122, 200)}


def validate_roll_num(roll_num: int, pdf_idx: int, expected_next: int, slack: int = 10) -> bool:
    """True if roll_num is plausible given the PDF's known range and how far
    it is from the expected next roll in sequence."""
    min_r, max_r = PDF_ROLL_BOUNDS.get(pdf_idx, (1, 200))
    # The per-PDF bounds come from the legacy regex processor and mark
    # roughly where one source PDF's page range ends - but a roll's actual
    # header can legitimately fall a few pages into the next file (a roll
    # doesn't know about our arbitrary file split). A hard wall exactly at
    # the boundary wrongly rejects genuine rolls there; a small buffer lets
    # the sequential expected_next check (below) be the real arbiter near
    # the edges, while still catching wildly out-of-range hallucinations.
    boundary_buffer = 5
    if not (min_r - boundary_buffer <= roll_num <= max_r + boundary_buffer):
        return False
    if not (expected_next - 2 <= roll_num <= expected_next + slack):
        return False
    return True
