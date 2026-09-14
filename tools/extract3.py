"""Read DSSSB's marked answers from an official CBT question paper, question by
question, using where things sit on the page instead of counting pictures.

Why a second reader: extract2.py counts option pictures four at a time across
the whole paper, so one question with a missing or extra picture (a picture
question, a second tick design, a "tick only" paper) throws every later answer
off and the paper had to be skipped.

How this one works
  1. Every small picture beside an option is classified by its COLOUR: mostly
     green = tick, mostly red = cross. Size and count no longer matter.
  2. The question headings ("Q.12" or "Question Number : 12") are located on
     each page with their height, so each picture belongs to the heading above
     it. A picture can never leak into a neighbouring question.
  3. Inside one question: four pictures -> the answer is the position of the
     single tick; one picture only (tick-only papers) -> the tick is matched to
     the option label ("1." .. "4.") printed on the same line.
  4. Question text comes from pdftotext (extract2's parser). Headings and parsed
     questions are paired in order, and the first words of the stem are checked
     against the heading line; the paper is refused if too many disagree.
"""
import sys, re, json, hashlib, collections, os
import pypdf
from pypdf.generic import ContentStream

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract2 as ex2

mul = ex2.mul


def colour_class(x):
    try:
        im = x.decode_as_image().convert('RGB')
    except Exception:
        return 'other'
    px = list(im.getdata()) if not hasattr(im, 'get_flattened_data') else list(im.get_flattened_data())
    if px and not isinstance(px[0], tuple):
        px = [tuple(px[i:i + 3]) for i in range(0, len(px), 3)]
    green = sum(1 for p in px if p[1] > p[0] + 40 and p[1] > p[2] + 40)
    red = sum(1 for p in px if p[0] > p[1] + 60 and p[0] > p[2] + 60)
    if green >= 20 and green > red:
        return 'tick'
    if red >= 20 and red > green:
        return 'cross'
    return 'other'


def page_items(reader, pno, page, hcache, ccache):
    """Markers and text runs on one page, each with its height on the page."""
    marks, runs = [], []

    def walk(obj, res, ctm):
        xo = res.get('/XObject', {}) if res else {}
        stack, cur = [], ctm
        for operands, op in ContentStream(obj, reader).operations:
            if op == b'q':
                stack.append(cur)
            elif op == b'Q':
                cur = stack.pop() if stack else cur
            elif op == b'cm':
                cur = mul([float(v) for v in operands], cur)
            elif op == b'Do':
                x = xo[operands[0]].get_object()
                if x['/Subtype'] == '/Form':
                    m = [float(v) for v in x.get('/Matrix', [1, 0, 0, 1, 0, 0])]
                    walk(x, x.get('/Resources', res), mul(m, cur))
                    continue
                w, h = int(x.get('/Width')), int(x.get('/Height'))
                if w > 60 or h > 40 or cur[4] > 200 or abs(cur[3]) > 20:
                    continue
                ref = x.indirect_reference
                key = (ref.idnum, ref.generation) if ref is not None else None
                hs = hcache.get(key) if key else None
                if hs is None:
                    hs = hashlib.md5(x.get_data()).hexdigest()[:6]
                    if key:
                        hcache[key] = hs
                if hs not in ccache:
                    ccache[hs] = colour_class(x)
                if ccache[hs] in ('tick', 'cross'):
                    marks.append({'p': pno, 'y': cur[5], 'x': cur[4], 'h': abs(cur[3]), 'c': ccache[hs]})

    walk(page.get_contents(), page['/Resources'], [1, 0, 0, 1, 0, 0])

    def vt(text, cm, tm, fd, fs):
        if text and text.strip():
            m = mul(tm, cm)
            runs.append({'p': pno, 'y': m[5], 'x': m[4], 't': text})

    page.extract_text(visitor_text=vt)
    return marks, runs


ANCHOR = {'ion': re.compile(r'Question ID\s*:'),            # printed once, BELOW each question
          'digialm': re.compile(r'Question Number\s*:')}     # printed once, ABOVE each question
LABEL = re.compile(r'^\s*(?:Ans\s*)?([1-4])\.')


def read_key(path, fmt):
    r = pypdf.PdfReader(path)
    hcache, ccache = {}, {}
    heads, marks, labels = [], [], []
    for pno, page in enumerate(r.pages):
        mk, runs = page_items(r, pno, page, hcache, ccache)
        marks += mk
        seen = set()
        width = float(page.mediabox.width)
        for t in runs:
            # some papers space every letter out ("Q u e s tio n  ID"): match without spaces
            flat = re.sub(r'\s+', ' ', t['t']).strip()
            tight = flat.replace(' ', '')
            # pypdf sometimes reports the same text twice (bold/shadow drawing): keep one
            sig = (round(t['y']), tight[:20])
            if sig in seen:
                continue
            seen.add(sig)
            if ANCHOR[fmt].search(tight):
                heads.append({'p': pno, 'y': t['y']})
            lm = LABEL.match(tight)
            if lm and t['x'] < width * 0.35:
                labels.append({'p': pno, 'y': t['y'], 'k': int(lm.group(1))})
        scale.append(float(page.mediabox.height) / 1008.0)
    order = lambda o: (o['p'], -o['y'])
    heads.sort(key=order)
    marks.sort(key=order)
    labels.sort(key=order)
    # drop anchors that are the same label split across two runs on one line
    uniq = []
    for h in heads:
        if uniq and uniq[-1]['p'] == h['p'] and abs(uniq[-1]['y'] - h['y']) < 3:
            continue
        uniq.append(h)
    heads = uniq

    def between(items, a, b):
        return [o for o in items if (a is None or order(a) < order(o)) and (b is None or order(o) < order(b))]

    keys = []
    for i, hd in enumerate(heads):
        if fmt == 'ion':        # block = after previous "Question ID", up to this one
            start, nxt = (heads[i - 1] if i else None), hd
        else:                   # block = from this "Question Number", up to the next
            start, nxt = hd, (heads[i + 1] if i + 1 < len(heads) else None)
        ms = between(marks, start, nxt)
        ticks = [j for j, m in enumerate(ms) if m['c'] == 'tick']
        ans, how = None, None
        if len(ms) == 4 and len(ticks) == 1:
            ans, how = ticks[0], 'four'
        elif len(ms) == 4 and len(ticks) == 4:
            ans, how = None, 'all-ticked'
        elif len([m for m in ms if m['c'] == 'tick']) == 1:
            t = [m for m in ms if m['c'] == 'tick'][0]
            ls = [l for l in between(labels, start, nxt) if l['p'] == t['p']]
            near = sorted(ls, key=lambda l: abs(l['y'] - t['y']))
            if near and abs(near[0]['y'] - t['y']) <= 9 and \
                    (len(near) == 1 or abs(near[1]['y'] - t['y']) > abs(near[0]['y'] - t['y']) + 2):
                ans, how = near[0]['k'] - 1, 'label'
        keys.append({'a': ans, 'how': how, 'marks': len(ms)})
    return keys, ccache


def run(path):
    text = ex2.pdftext(path)
    fmt = 'digialm' if 'Question Number :' in text else 'ion'
    qs = ex2.parse_digialm(text) if fmt == 'digialm' else ex2.parse_ion(text)
    keys, ccache = read_key(path, fmt)
    if not keys:
        raise SystemExit(f'SKIP {path} [{fmt}]: no question headings found (scanned paper?)')
    if len(keys) != len(qs):
        raise SystemExit(f'SKIP {path} [{fmt}]: {len(qs)} questions in text but {len(keys)} headings')
    # The text parser also splits on "Question ID :" / "Question Number :", so the
    # two lists must be the same length; any difference means something was lost.
    for q, k in zip(qs, keys):
        q['a'] = k['a']
        q['how'] = k['how']
        q['marks'] = k['marks']
        q['ticks'] = None if k['a'] is None else [k['a']]
        q['lang'] = 'en' if len(re.findall(r'[A-Za-z]{3,}', q['stem'])) >= 3 else 'other'
    return fmt, qs, {'colours': ccache}


if __name__ == '__main__':
    fmt, qs, info = run(sys.argv[1])
    how = collections.Counter(q['how'] for q in qs)
    print(f"OK {os.path.basename(sys.argv[1])} [{fmt}] questions {len(qs)} answered "
          f"{sum(1 for q in qs if q['a'] is not None)} how {dict(how)}")
    if len(sys.argv) > 2:
        json.dump(qs, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
