import re

def is_titulus_header(line):
    s = line.strip()
    # Format: [Ref] Num [Global] Date
    if re.match(r'^(?:\[\d+\]\s*)?(\d+)\s*\[\d+\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)', s): return True
    # Format: T. Location
    if re.match(r'^T[T]?\.\s+[A-Z]', s): return True
    # Format: Titulus ...
    if re.match(r'^TITULUS\b|^Trruzus\b|^TrruLus\b|^TITulus\b', s, re.IGNORECASE): return True
    return False

lines = [
    "[1047] 7 [5] S.d.- ~ S. Hilaire. Hilario de Carcassona. 7.S\"",
    "8 [6] S.d.- Lagrasse, N-D. (a) Maria virtutibus Crasse ",
    "28 [92] [7 juin 1047] Seu d'Urgell, catedral (S. Maria $. Ermengol)",
    "T. Sancte Marie Altifagensis ecclesie",
    "Trruzus SANCTI PETRI Podiensis monasterii.",
    "30 [78] 5 mai [1017] Rodes $ Pera"
]

for l in lines:
    print(f"'{l}' -> {is_titulus_header(l)}")

