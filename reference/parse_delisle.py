import re
import json

with open('reference/delisle_1866_raw.txt', encoding='utf-8') as f:
    text = f.read()

end_marker = text.find('TABLE.')
body = text[:end_marker] if end_marker != -1 else text
print('Body length:', len(body), 'of', len(text))

ROMAN_RE = re.compile(r'^([IVXLCDM]{1,8})\s*$')


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals.get(ch, 0)
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


lines = body.split('\n')
entries = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    m = ROMAN_RE.match(line)
    if m and line:
        num = roman_to_int(m.group(1))
        if 1 <= num <= 200:
            # Delisle's format is: number, blank line, title paragraph,
            # blank line, THEN a separate one-line date paragraph, blank
            # line, then commentary. Capture up to 3 blank-line-separated
            # paragraphs - 2 is not always enough: some titles themselves
            # get split across an extra blank line by the OCR/typesetting
            # (e.g. entry LXV's title breaks mid-sentence before "Raoul,
            # moine de..."), which pushes the real date paragraph ("Treizieme
            # siecle.") into a 3rd segment that a 2-paragraph cap would
            # silently drop - exactly the kind of loss that previously made
            # entry LXV look like an in-scope gap candidate when it is
            # actually explicitly 13th-century.
            j = i + 1
            paragraphs, current = [], []
            while j < len(lines) and len(paragraphs) < 3 and (j - i) < 20:
                l = lines[j].strip()
                if l:
                    current.append(l)
                elif current:
                    paragraphs.append(' '.join(current))
                    current = []
                j += 1
            if current:
                paragraphs.append(' '.join(current))
            title = ' '.join(paragraphs)
            entries.append({'num': num, 'roman': m.group(1), 'title': title[:600], 'line': i})
    i += 1

print('Found', len(entries), 'candidate entries')
with open('reference/delisle_entries_raw.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

for e in entries[:15]:
    print(e['num'], e['roman'], '|', e['title'][:90])
