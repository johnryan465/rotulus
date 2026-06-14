import os, re

RAW_TEXT_DIR = "/home/john/rolls/raw_text"

def scan_headers():
    files = sorted([f for f in os.listdir(RAW_TEXT_DIR) if f.endswith(".txt") and "_full" not in f], key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    
    expected = 1
    for fname in files:
        with open(os.path.join(RAW_TEXT_DIR, fname), "r") as f:
            for line in f:
                s = line.strip()
                # Pattern: N° 1 or standalone number or range
                m = re.search(r'^N[oO°\?]*\s*(\d+)', s)
                if m:
                    n = int(m.group(1))
                    if n == expected:
                        print(f"Found {n} in {fname}: {s[:50]}")
                        expected += 1
                elif s.isdigit() and int(s) == expected:
                    print(f"Found {expected} in {fname}: {s}")
                    expected += 1
                elif re.match(r'^(\d+)\s+', s):
                    n = int(re.match(r'^(\d+)', s).group(1))
                    if n == expected:
                        print(f"Found {n} in {fname}: {s[:50]}")
                        expected += 1

if __name__ == "__main__":
    scan_headers()
