"""Read DSSSB's marked answers from an official CBT question paper by following
the ORDER in which the page is drawn, and prove every pairing.

Why: extract2.py counts option pictures four at a time over the whole paper, so
one odd question shifts every later answer; page heights reported by pypdf are
unreliable in the 2021 papers. The drawing order is not.

What the drawing order looks like
  2023-26 papers ("ion"):   [picture] "1. option text"  [picture] "2. ..."  ... "Question ID : 4410..."
  2021 papers ("digialm"):  "Question Number : 5 Question Id : 5406..." ... "1." [picture] "2." [picture] ...
So a picture belongs to the option label drawn right after it (ion) or right
before it (digialm). Pictures are told apart by COLOUR: green tick, red cross.
Tick-only papers (no crosses) work the same way.

Which picture a name refers to depends on the group ("form") being drawn, so
pictures are resolved by walking the page in exactly the order pypdf does and
pairing the n-th "draw picture" instruction of both walks.

Proof
  ion:     each block is closed by its own printed Question ID; the same IDs are
           read from pdftotext's text and must agree exactly, in order.
  digialm: some 2021 papers draw headers twice or out of order, so answers are
           collected per printed Question Id. A question gets an answer only if
           at least two complete copies (English and Hindi) exist and every
           complete copy agrees; otherwise it is left unanswered."""
import sys, re, json, hashlib, collections, os, subprocess
import pypdf
from pypdf.generic import ContentStream

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract2 as ex2
from extract3 import colour_class

LABEL = re.compile(r'^(?:Ans)?([1-4A-D])\.')


def lab(g):
    """Option label -> option number: '3' -> 3, 'C' -> 3."""
    return int(g) if g.isdigit() else ord(g) - 64


def resolve_draws(reader, page, cc):
    """Class of every 'Do' instruction on the page, depth-first in drawing order."""
    out = []

    def walk(obj, res, depth):
        xo = (res or {}).get('/XObject', {}) or {}
        for operands, op in ContentStream(obj, reader).operations:
            if op != b'Do' or not operands:
                continue
            name = operands[0]
            try:
                x = xo[name].get_object()
            except Exception:
                out.append((name, 'missing'))
                continue
            if x.get('/Subtype') == '/Form':
                out.append((name, 'form'))
                if depth < 8:
                    walk(x, x.get('/Resources') or res, depth + 1)
                continue
            w, h = int(x.get('/Width', 0)), int(x.get('/Height', 0))
            if w > 60 or h > 40:
                out.append((name, 'big'))
                continue
            hs = hashlib.md5(x.get_data()).hexdigest()[:8]
            if hs not in cc:
                cc[hs] = colour_class(x)
            out.append((name, cc[hs]))

    walk(page.get_contents(), page['/Resources'], 0)
    return out


def events(path):
    r = pypdf.PdfReader(path)
    cc, ev, misaligned = {}, [], 0
    for page in r.pages:
        draws = resolve_draws(r, page, cc)
        k = [0]

        def before(op, args, cm, tm):
            nonlocal misaligned
            if op != b'Do' or not args:
                return
            j = k[0]
            k[0] += 1
            if j >= len(draws) or draws[j][0] != args[0]:
                misaligned += 1
                ev.append(('M', '?'))
                return
            cls = draws[j][1]
            if cls in ('tick', 'cross'):
                ev.append(('M', cls))

        def vt(text, cm, tm, fd, fs):
            t = re.sub(r'\s+', '', text or '')
            if t:
                ev.append(('T', t))

        page.extract_text(visitor_operand_before=before, visitor_text=vt)
    return ev, cc, misaligned


def blocks_ion(ev):
    out, cur, pending, lead, in_opts = [], {}, None, '', False
    for i, (kind, val) in enumerate(ev):
        if kind == 'M':
            pending = val
            continue
        m = LABEL.match(val)
        if m and pending is not None:
            cur.setdefault(lab(m.group(1)), []).append(pending)
        if val.startswith('Ans') or m:
            in_opts = True
        elif not in_opts and not re.match(r'^(Option\dID:|\d{6,}$)', val) and len(lead) < 60:
            lead += val
        if val.startswith('QuestionID:'):
            qid = val[len('QuestionID:'):]
            if not re.search(r'\d{6,}', qid) and i + 1 < len(ev) and ev[i + 1][0] == 'T' \
                    and re.fullmatch(r'\d{6,}', ev[i + 1][1]):
                qid = ev[i + 1][1]
            out.append({'id': re.sub(r'\D', '', qid)[:13], 'opts': cur, 'lead': lead})
            cur, lead, in_opts = {}, '', False
        pending = None
    return out


QN = re.compile(r'^Q\.(\d+)')


def blocks_qhead(ev):
    """Papers with no "Question ID" lines (e.g. MTS 2026 answer-key prints):
    a block runs from one "Q.n" heading to the next; the picture before an
    option label belongs to that label, as in the ion layout."""
    out, cur, pending = [], None, None
    for kind, val in ev:
        if kind == 'M':
            pending = val
            continue
        m = QN.match(val)
        if m:
            cur = {'n': int(m.group(1)), 'opts': {}}
            out.append(cur)
        elif cur is not None:
            lm = LABEL.match(val)
            if lm and pending is not None:
                cur['opts'].setdefault(lab(lm.group(1)), []).append(pending)
        pending = None
    return out


def parse_qhead(text):
    """Questions from pdftotext text split on "Q.n" lines."""
    secs = [(m.start(), ex2.sec_of(m.group(1))) for m in re.finditer(r'Section\s*:\s*(.+)', text)]
    starts = list(re.finditer(r'(?m)^\s*Q\.\s?(\d+)\s', text))
    qs = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[m.start():end]
        sec = None
        for pos, name in secs:
            if pos < m.start() and name:
                sec = name
        lines = [l for l in block.split('\n') if not re.search(r'Section\s*:', l)]
        got = ex2.pick_options(lines)
        if got is None:
            qs.append({'sec': sec, 'n': int(m.group(1)), 'stem': ex2.tidy(lines)[-300:], 'o': None})
            continue
        stem, opts = got
        qs.append({'sec': sec, 'n': int(m.group(1)), 'stem': ex2.clean_stem(stem), 'o': opts})
    return qs


def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def lead_check(qs, bl):
    """When a paper prints no ID numbers: compare the opening letters of every
    question as drawn with the same question as read by pdftotext."""
    checked = bad = 0
    for q, b in zip(qs, bl):
        a = norm(re.sub(r'^Q\.?\d+', '', b['lead']))[:10]
        t = norm(q['stem'])[:10]
        if len(a) >= 6 and len(t) >= 6:
            checked += 1
            bad += a != t
    return checked, bad


def blocks_digialm(ev):
    # 2022 prints draw "Question Number : 1" and "Question Id : 9277..." as two
    # separate pieces of text; 2021 prints draw them as one. Join the pair.
    joined = []
    for kind, val in ev:
        if kind == 'T' and joined and joined[-1][0] == 'T' \
                and re.fullmatch(r'QuestionNumber:\d+', joined[-1][1]) and val.startswith('QuestionId:'):
            joined[-1] = ('T', joined[-1][1] + val)
            continue
        joined.append((kind, val))
    ev = joined
    out, cur, last_label = [], None, None
    for kind, val in ev:
        if kind == 'T':
            m = re.search(r'QuestionNumber:(\d+)QuestionId:(\d+)', val)
            if m:
                cur = {'n': int(m.group(1)), 'id': m.group(2), 'opts': {}}
                out.append(cur)
                last_label = None
                continue
            lm = LABEL.match(val)
            last_label = lab(lm.group(1)) if (lm and cur is not None) else None
        elif last_label is not None and cur is not None:
            cur['opts'].setdefault(last_label, []).append(val)
            last_label = None
    return out


def decide(opts):
    """(answer index or None, how)."""
    marks = {k: v for k, v in opts.items() if v}
    if any(len(v) > 1 for v in marks.values()) or any('?' in v for v in marks.values()):
        return None, 'confused'
    ticks = [k for k, v in marks.items() if v == ['tick']]
    crosses = [k for k, v in marks.items() if v == ['cross']]
    if len(ticks) == 1 and len(crosses) == 3:
        return ticks[0] - 1, 'four'
    if len(ticks) == 1 and not crosses:
        return ticks[0] - 1, 'tick-only'
    if len(ticks) == 4:
        return None, 'all-ticked'
    return None, f'unclear t{len(ticks)} c{len(crosses)}'


def rawtext(path):
    return subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', path, '-'],
                          capture_output=True).stdout.decode('utf-8', 'replace')


def run(path):
    name = os.path.basename(path)
    text = ex2.pdftext(path)
    if 'Question Number :' in text:
        fmt = 'digialm'
    elif re.search(r'Question ID\s*:', text):
        fmt = 'ion'
    elif re.search(r'(?m)^\s*Q\.\s?\d+\s', text):
        fmt = 'qhead'
    else:
        raise SystemExit(f'SKIP {name}: no readable question layout (scanned or unsupported script)')
    ev, cc, misaligned = events(path)
    if fmt == 'qhead':
        qs = parse_qhead(text)
        bl = blocks_qhead(ev)
        tn, dn = [q['n'] for q in qs], [b['n'] for b in bl]
        if not bl or tn != dn:
            first = next((i for i, (a, b) in enumerate(zip(tn, dn)) if a != b), None)
            raise SystemExit(f'SKIP {name} [qhead]: text {len(tn)} q, drawing {len(dn)}; first number mismatch at {first}')
        for q, b in zip(qs, bl):
            q['a'], q['how'] = decide(b['opts'])
        qs[0]['proof'] = 'question numbers'
        for q in qs:
            q['ticks'] = None if q['a'] is None else [q['a']]
            q['lang'] = 'en' if len(re.findall(r'[A-Za-z]{3,}', q['stem'])) >= 3 else 'other'
        return fmt, qs, misaligned
    qs = ex2.parse_digialm(text) if fmt == 'digialm' else ex2.parse_ion(text)
    if fmt == 'ion':
        bl = blocks_ion(ev)
        if not bl:
            raise SystemExit(f'SKIP {name} [ion]: no questions found in drawing (scanned?)')
        ids = [re.sub(r'\D', '', x)[:13] for x in re.findall(r'Question ID\s*:\s*(\d{6,})', text)]
        if len(ids) != len(bl):
            ids = [re.sub(r'\D', '', x)[:13] for x in re.findall(r'Question ID\s*:\s*(\d{6,})', rawtext(path))]
        page_ids = [b['id'] for b in bl]
        if len(qs) != len(bl):
            raise SystemExit(f'SKIP {name} [ion]: text {len(qs)} q, drawing {len(bl)} blocks')
        proof = 'ids'
        if not ids and not any(page_ids):
            # this paper prints "Question ID :" with no number at all
            checked, bad = lead_check(qs, bl)
            if checked < len(qs) * 0.6 or bad > max(2, checked * 0.03):
                raise SystemExit(f'SKIP {name} [ion]: no printed IDs and opening words agree only '
                                 f'{checked - bad}/{checked}')
            proof = f'opening words {checked - bad}/{checked}'
        elif page_ids != ids:
            first = next((i for i, (a, b) in enumerate(zip(page_ids, ids)) if a != b), None)
            raise SystemExit(f'SKIP {name} [ion]: text {len(ids)} ids, drawing {len(bl)} blocks; '
                             f'first id mismatch at {first}')
        for q, b in zip(qs, bl):
            q['a'], q['how'] = decide(b['opts'])
            q['qid'] = b['id']
        qs[0]['proof'] = proof
    else:
        bl = blocks_digialm(ev)
        if not bl:
            raise SystemExit(f'SKIP {name} [digialm]: no questions found in drawing')
        # A header redrawn in the middle of a question splits its options in two
        # ({1,2} then {3,4}): join neighbouring pieces of the same question whose
        # option labels do not overlap.
        merged = []
        for b in bl:
            p = merged[-1] if merged else None
            if p and p['id'] == b['id'] and not (set(p['opts']) & set(b['opts'])) \
                    and len(set(p['opts']) | set(b['opts'])) <= 4:
                p['opts'].update(b['opts'])
            else:
                merged.append({'n': b['n'], 'id': b['id'], 'opts': dict(b['opts'])})
        votes = collections.defaultdict(list)
        for b in merged:
            a, how = decide(b['opts'])
            if how in ('four', 'tick-only'):
                votes[b['id']].append(a)
            elif how in ('confused', 'all-ticked'):
                votes[b['id']].append('bad')
        ids = re.findall(r'Question Number\s*:\s*(\d+)\s+Question Id\s*:\s*(\d+)', text)
        if len(ids) != len(qs):
            raise SystemExit(f'SKIP {name} [digialm]: text {len(qs)} q but {len(ids)} ids')
        for q, (n, qid) in zip(qs, ids):
            if int(n) != q.get('n'):
                raise SystemExit(f'SKIP {name} [digialm]: number mismatch {n} vs {q.get("n")}')
            v = votes.get(qid, [])
            good = [x for x in v if x != 'bad']
            # every complete copy must agree; a complete copy on its own is accepted
            if good and len(set(good)) == 1 and 'bad' not in v:
                q['a'], q['how'] = good[0], f'agreed x{len(good)}'
            else:
                q['a'], q['how'] = None, f'votes {v}'
            q['qid'] = qid
    for q in qs:
        q['ticks'] = None if q['a'] is None else [q['a']]
        q['lang'] = 'en' if len(re.findall(r'[A-Za-z]{3,}', q['stem'])) >= 3 else 'other'
    return fmt, qs, misaligned


if __name__ == '__main__':
    fmt, qs, mis = run(sys.argv[1])
    how = collections.Counter(q['how'] if not q['how'].startswith('votes') else 'unanswered' for q in qs)
    print(f"OK {os.path.basename(sys.argv[1])} [{fmt}] questions {len(qs)} answered "
          f"{sum(1 for q in qs if q['a'] is not None)} {dict(how)} draw-misaligned {mis}")
    if len(sys.argv) > 2:
        json.dump(qs, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
