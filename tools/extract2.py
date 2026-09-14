"""Extract every question and DSSSB's marked answer from an official DSSSB CBT
question-paper PDF. Handles the two layouts DSSSB has used since 2021:

  ion      "Q.n ... 1. 2. 3. 4. ... Question ID :"       (2023-2026 papers)
  digialm  "Question Number : n ... Options : 1. 2. ..."  (2021 papers, each
           question printed twice: English then Hindi)

ANSWERS. Beside every option DSSSB draws a small picture. The correct option's
picture is a different image (a green tick). Pictures are collected page by
page, top to bottom; the tick is recognised by the md5 of its image bytes, not
its size. Refuses to write output when pictures and questions do not line up
four-to-one, so a misaligned paper can never produce wrong answers silently."""
import sys, re, json, subprocess, hashlib, collections
import pypdf
from pypdf.generic import ContentStream


def mul(a, b):
    return [a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3], a[2]*b[0]+a[3]*b[2],
            a[2]*b[1]+a[3]*b[3], a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5]]


def images_on(reader, page, cache):
    out = []

    def walk(obj, res, ctm):
        cs = ContentStream(obj, reader)
        stack, cur = [], ctm
        xo = res.get('/XObject', {}) if res else {}
        for operands, op in cs.operations:
            if op == b'q':
                stack.append(cur)
            elif op == b'Q':
                cur = stack.pop() if stack else cur
            elif op == b'cm':
                cur = mul([float(x) for x in operands], cur)
            elif op == b'Do':
                x = xo[operands[0]].get_object()
                if x['/Subtype'] == '/Form':
                    m = [float(v) for v in x.get('/Matrix', [1, 0, 0, 1, 0, 0])]
                    walk(x, x.get('/Resources', res), mul(m, cur))
                else:
                    w, h = int(x.get('/Width')), int(x.get('/Height'))
                    if w <= 40 and h <= 30 and cur[4] < 130 and abs(cur[3]) < 16:
                        ref = x.indirect_reference
                        key = (ref.idnum, ref.generation) if ref is not None else None
                        if key is not None and key in cache:
                            hs = cache[key]
                        else:
                            hs = hashlib.md5(x.get_data()).hexdigest()[:6]
                            if key is not None:
                                cache[key] = hs
                        out.append((hs, cur[4], cur[5]))

    walk(page.get_contents(), page['/Resources'], [1, 0, 0, 1, 0, 0])
    return out


def markers(path):
    r = pypdf.PdfReader(path)
    cache, seq = {}, []
    for p in r.pages:
        ims = images_on(r, p, cache)
        ims.sort(key=lambda t: -t[2])
        seq += [hs for hs, x, y in ims]
    return seq


def pdftext(path):
    return subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', path, '-'],
                          capture_output=True).stdout.decode('utf-8', 'replace')


KEYS = [('awareness', 'GA'), ('generalknowledge', 'GA'), ('reasoning', 'REA'),
        ('intelligence', 'REA'), ('numerical', 'NUM'), ('arithmet', 'NUM'),
        ('english', 'ENG'), ('hindi', 'HIN'), ('discipline', 'DISC'),
        ('teaching', 'TM'), ('methodology', 'TM'), ('pedagogy', 'TM')]


def sec_of(s):
    low = re.sub(r'\s+', '', s or '').lower()
    for k, v in KEYS:
        if k in low:
            return v
    return None


OPT = re.compile(r'^\s*(?:A\s*n?\s*s?\s*)?([1-4])\.\s*(.*)$')
JUNK = re.compile(r'^\s*(?:[A-Za-z0-9.]|Ans|Q\.?\s*\d*\.?)\s*$')


def tidy(lines):
    keep = [l for l in lines if l.strip() and not JUNK.match(l)]
    return re.sub(r'\s+', ' ', ' '.join(keep)).strip()


def pick_options(lines):
    """(stem_lines, [opt1..opt4]) from the LAST 1-2-3-4 run in the block, so a
    stem listing numbered statements is not mistaken for the options."""
    hits = [(i, int(m.group(1))) for i, l in enumerate(lines) for m in [OPT.match(l)] if m]
    want, pos, chosen = 4, len(lines), {}
    for i, n in reversed(hits):
        if n == want and i < pos:
            chosen[n] = i
            pos = i
            want -= 1
            if want == 0:
                break
    if want != 0:
        return None
    idx = [chosen[k] for k in (1, 2, 3, 4)] + [len(lines)]
    opts = []
    for k in range(4):
        first = OPT.match(lines[idx[k]]).group(2)
        opts.append(tidy([first] + lines[idx[k] + 1:idx[k + 1]]))
    return lines[:idx[0]], opts


def clean_stem(lines):
    s = tidy(lines)
    s = re.sub(r'^Q\s*\.?\s*\d+\s*\.?\s*', '', s)
    s = re.sub(r'(?<=[?.:)\]_’”"])\s?\d{3,5}$', '', s)
    return s.strip()


def parse_ion(text):
    secs = [(m.start(), sec_of(m.group(1))) for m in re.finditer(r'Section\s*:\s*(.+)', text)]
    qs, prev = [], 0
    for m in re.finditer(r'Question ID\s*:', text):
        block = text[prev:m.start()]
        prev = m.end()
        sec = None
        for pos, name in secs:
            if pos < m.start() and name:
                sec = name
        lines = [l for l in block.split('\n')
                 if not re.search(r'Option\s*\d\s*ID|Section\s*:|^\s*\d{8,}\s*$', l)]
        got = pick_options(lines)
        if got is None:
            qs.append({'sec': sec, 'stem': tidy(lines)[-300:], 'o': None})
            continue
        stem, opts = got
        qs.append({'sec': sec, 'stem': clean_stem(stem[-40:]), 'o': opts})
    return qs


def parse_digialm(text):
    secs = []
    for m in re.finditer(r'Section Id\s*:', text):
        back = [l for l in text[max(0, m.start() - 400):m.start()].split('\n') if l.strip()]
        name = sec_of(back[-1]) if back else None
        if name:
            secs.append((m.start(), name))
    starts = list(re.finditer(r'Question Number\s*:\s*(\d+)', text))
    qs = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[m.start():end]
        block = re.split(r'\n[^\n]*(?:Section Id|Sub-Section Number|Group Number)\s*:', block)[0]
        sec = None
        for pos, name in secs:
            if pos < m.start():
                sec = name
        wm = re.search(r'Wrong Marks\s*:\s*[\d.]+', block)
        om = re.search(r'Options\s*:', block)
        if not (wm and om):
            qs.append({'sec': sec, 'n': int(m.group(1)), 'stem': '', 'o': None})
            continue
        got = pick_options(block[om.end():].split('\n'))
        qs.append({'sec': sec, 'n': int(m.group(1)),
                   'stem': clean_stem(block[wm.end():om.start()].split('\n')),
                   'o': got[1] if got else None})
    return qs


def run(path):
    text = pdftext(path)
    fmt = 'digialm' if 'Question Number :' in text else 'ion'
    qs = parse_digialm(text) if fmt == 'digialm' else parse_ion(text)
    raw = markers(path)
    c = collections.Counter(raw)
    top = [h for h, _ in c.most_common(2)]
    mk = [h for h in raw if h in top]
    if len(mk) != 4 * len(qs):
        raise SystemExit(f'SKIP {path} [{fmt}]: {len(qs)} questions but {len(mk)} option pictures {dict(c.most_common(4))}')
    n = len(qs)
    tick = min(top, key=lambda h: abs(mk.count(h) - n))
    for i, q in enumerate(qs):
        grp = mk[4 * i:4 * i + 4]
        q['ticks'] = [j for j, h in enumerate(grp) if h == tick]
        q['a'] = q['ticks'][0] if len(q['ticks']) == 1 else None
        q['lang'] = 'en' if len(re.findall(r'[A-Za-z]{3,}', q['stem'])) >= 3 else 'other'
    return fmt, qs


if __name__ == '__main__':
    fmt, qs = run(sys.argv[1])
    ga = [q for q in qs if q['sec'] == 'GA' and q['lang'] == 'en']
    noopt = sum(1 for q in qs if not q['o'])
    multi = sum(1 for q in qs if q['a'] is None)
    print(f"OK {sys.argv[1]} [{fmt}] questions {len(qs)} GA-en {len(ga)} no-options {noopt} not-single-tick {multi}")
    json.dump(qs, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
