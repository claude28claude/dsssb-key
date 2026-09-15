"""Read the General Awareness questions of the 17 Assistant Superintendent 2026
shifts (1-7 July 2026) from the Grow Academy compilation PDF.

Layout (checked by hand on shift 1): every shift has 10 sections of 20
questions, each opened by "Section : X" (the second half carries a "1"):
Reasoning, Reasoning1, General Awareness, General Awareness1, Arithmetic, ...
Every question is followed by "(DSSSB: Assistant Superintendent dd/mm/yyyy
time) Ans: (n)". Every page has a "Join Telegram | Join WhatsApp ..." footer
(the institute's), which is thrown away.

Two independent readings:
  pypdf   text in DRAWING ORDER: stem, 1., 2., 3., 4., label, Ans. Wrapped
          option lines stay with their option. Stems, options and answers
          come from here.
  layout  pdftotext -layout: every "Ans: (n)" sits on its question's label
          line. Used only as a check: the same 20 answers, in the same order,
          and the same question numbers, for every section.
Anything that does not match is reported, never silently accepted.

  python tools/as/parse.py <pdf>     ->  tools/as/as-raw.json"""
import json, os, re, subprocess, sys
import pypdf

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = sys.argv[1]

reader = pypdf.PdfReader(PDF)
page_text = [p.extract_text() for p in reader.pages]
plain = '\n'.join(page_text)
layout = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-layout', PDF, '-'], capture_output=True, check=True).stdout.decode('utf-8')

SEC = re.compile(r'(?m)^\s*Section : ([A-Za-z ]+?)(1?)\s*$')
LABEL = re.compile(r'\(DSSSB: Assistant Superintendent (\d\d)/(\d\d)/(\d{4}) (\d+):00 ([AP]M) - [^)]*\)')
MON = {'07': 'Jul'}
SHIFT = {('9', 'AM'): 'S1', ('1', 'PM'): 'S2', ('5', 'PM'): 'S3'}
JUNK = re.compile(r'(?m)^.*Join Telegram.*\n?|^\s*\d+\. \(DSSSB:[^)]*\)\s*$\n?')
# "Q.18" can sit alone on its line or be glued to the stem ("Q.9The Seventh ...").
QRE = re.compile(r'(?m)^[ \t]*Q\.(\d+)(?:\s+|(?=[A-Z"\'(]))')
ENDRE = re.compile(r'\(DSSSB:[^)]*\)\s*Ans\s*:\s*\((\d)\)')
# Option markers are "1." to "4." not followed by a digit; the print often
# glues them to the end of the previous option ("Act, 19192. Government ...").
OPT = re.compile(r'1\.(?!\d)\s*(.*?)2\.(?!\d)\s*(.*?)3\.(?!\d)\s*(.*?)4\.(?!\d)\s*(.*)', re.S)


def sections(t):
    heads = list(SEC.finditer(t))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(t)
        yield m.group(1).strip(), m.group(2), t[m.end():end]


def label_of(body):
    dd, mm, yyyy, hh, ap = LABEL.search(body).groups()
    return f'AS {int(dd)} {MON[mm]} {yyyy} {SHIFT[(hh, ap)]}'


def flat(s):
    s = re.sub(r'-\n(?=\S)', '-', s)          # "(-\nOH)" -> "(-OH)"
    return re.sub(r'\s+', ' ', s).strip()


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


P = [s for s in sections(plain) if s[0] == 'General Awareness']
L = [s for s in sections(layout) if s[0] == 'General Awareness']
problems, out = [], []
if len(P) != 34 or len(L) != 34:
    problems.append(f'expected 34 GA sections, pypdf {len(P)} layout {len(L)}')

for (_, half, pb), (_, half2, lb) in zip(P, L):
    src = label_of(pb)
    part = 2 if half else 1
    if label_of(lb) != src or half != half2:
        problems.append(f'{src}: the two readings disagree on the shift or section')
        continue
    check = [int(a) for a in re.findall(r'Ans: \((\d)\)', lb)]
    lnums = [int(n) for n in re.findall(r'(?m)^\s*Q\.(\d+)', lb)]   # \s also skips page breaks
    pq = QRE.split(JUNK.sub('', pb))
    pnums = [int(n) for n in pq[1::2]]
    if pnums != list(range(1, 21)) or lnums != pnums:
        problems.append(f'{src} GA{part}: question numbers pypdf {pnums} layout {lnums}')
        continue
    answers = []
    for n, body in zip(pnums, pq[2::2]):
        end = ENDRE.search(body)
        if not end:
            problems.append(f'{src} GA{part} Q{n}: no "Ans" after the question')
            answers.append(None)
            continue
        a = int(end.group(1))
        answers.append(a)
        body = body[:end.start()]
        # options: the LAST "1. " from which 2., 3., 4. follow in order
        m = None
        for st in reversed([x.start() for x in re.finditer(r'1\.(?!\d)', body)]):
            m = OPT.fullmatch(body, st)
            if m:
                break
        if not m:
            problems.append(f'{src} GA{part} Q{n}: options not readable: {flat(body)[:160]!r}')
            continue
        stem = flat(body[:m.start()])
        opts = [flat(x) for x in m.groups()]
        if not stem or not all(opts) or not 1 <= a <= 4:
            problems.append(f'{src} GA{part} Q{n}: empty stem/option or bad answer')
            continue
        out.append({'src': src, 'part': part, 'n': n, 'stem': stem, 'o': opts, 'a': a - 1})
    if answers != check:
        problems.append(f'{src} GA{part}: answers differ between readings: pypdf {answers} layout {check}')

json.dump(out, open(os.path.join(HERE, 'as-raw.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('GA sections', len(P), '| questions read', len(out), '| shifts', len({q['src'] for q in out}))
print('PROBLEMS', len(problems))
for p in problems:
    print('  ', p)
