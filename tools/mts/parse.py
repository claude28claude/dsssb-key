"""Split the 2,661-page MTS 2026 answer-key compilation into shifts, sections and
questions, and keep only the two General Awareness sections.

Layout (checked by hand on shift 1): each shift = 10 blocks of 20 questions,
numbering restarts at Q.1 for every block. A block's label "Section : X" is
printed at the foot of the page where the block starts. Order is Reasoning,
Reasoning1, General Awareness, General Awareness1, Arithmetic, Arithmetic1,
English, English1, Hindi, Hindi1. Every question ends with
"Correct Answer: <letter>".

Writes mts/mts-raw.json and prints a check line per shift. Any shift whose
structure is not exactly as expected is reported, never silently accepted."""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
pages = json.load(open(os.path.join(HERE, 'pages.json'), encoding='utf-8'))

# ---- table of contents: date, start time, printed page number --------------
toc = ''
for i in range(1, 6):
    if re.search(r'(?m)^Q\.\d+ ', pages[i]):
        break
    toc += pages[i]
rows = re.findall(r'(\d{2})/(\d{2})/(\d{4})\((\d+):00 ([AP]M) - [^)]*\)\s*(\d+)', toc)
MON = {'02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May'}
SHIFT = {('9', 'AM'): 'S1', ('1', 'PM'): 'S2', ('5', 'PM'): 'S3'}

# Printed page 1 is PDF page 5 (index 4): offset found from shift 1 and 2.
OFF = 3
FIRST_Q = int(rows[0][5]) + OFF
assert re.search(r'(?m)^Q\.1 ', pages[FIRST_Q]), 'page offset is wrong'

QRE = re.compile(r'(?m)^Q\.(\d+) ')
SECRE = re.compile(r'Section : ([A-Za-z ]+?)(1?)\s*$', re.M)
OPTRE = re.compile(r'A\s*n\s*s\s*A\s*\)\s*\.\s*(.*?)\s*B\s*\)\s*\.\s*(.*?)\s*C\s*\)\s*\.\s*(.*?)\s*D\s*\)\s*\.\s*(.*?)\s*Correct Answer\s*:\s*([A-D])', re.S)

out, problems = [], []
for k, (dd, mm, yyyy, hh, ap, pno) in enumerate(rows):
    start = int(pno) + OFF
    end = int(rows[k + 1][5]) + OFF if k + 1 < len(rows) else len(pages)
    label = f'MTS {int(dd)} {MON[mm]} {yyyy} {SHIFT[(hh, ap)]}'
    text = '\n'.join(pages[start:end]).replace('Click to Join Telegram Channel', '')
    labels = [m.group(1).strip() for m in SECRE.finditer(text)]
    text = SECRE.sub('', text)
    parts = QRE.split(text)          # ['', n, body, n, body, ...]
    blocks, cur = [], None
    for j in range(1, len(parts), 2):
        n, body = int(parts[j]), parts[j + 1]
        # A new block starts whenever the numbering goes back (usually to 1; a
        # maths block whose Q.1 line was a picture restarts at 2).
        if cur is None or n <= cur[-1][0]:
            cur = []
            blocks.append(cur)
        cur.append((n, body))
    sizes = [len(b) for b in blocks]
    ga_idx = [i for i, l in enumerate(labels) if l == 'General Awareness']
    ga_ok = ga_idx == [2, 3] and len(blocks) > 3 and all([n for n, _ in blocks[i]] == list(range(1, 21)) for i in ga_idx)
    ok = ga_ok
    if not ok:
        problems.append(f'{label}: labels={labels} sizes={sizes}')
    for part, bi in enumerate(ga_idx):
        if bi >= len(blocks):
            continue
        for n, body in blocks[bi]:
            m = OPTRE.search(body)
            if not m:
                problems.append(f'{label} GA{part + 1} Q{n}: options not readable: {body[:120]!r}')
                continue
            stem = re.sub(r'\s+', ' ', body[:m.start()]).strip()
            opts = [re.sub(r'\s+', ' ', x).strip() for x in m.groups()[:4]]
            out.append({'src': label, 'part': part + 1, 'n': n, 'stem': stem, 'o': opts,
                        'a': 'ABCD'.index(m.group(5)), 'page': start + 1})
    print(f'{k + 1:3} {label:22} pages {start + 1}-{end} blocks {len(blocks)} sizes {sizes} GA at {ga_idx}')

json.dump(out, open(os.path.join(HERE, 'mts-raw.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('shifts', len(rows), 'GA questions read', len(out))
print('PROBLEMS', len(problems))
for p in problems:
    print('  ', p)
