"""Question text + DSSSB's marked answer, taken entirely from the page's
drawing order (pypdf), one block per printed "Question ID". Used where
pdftotext cannot help: Hindi-medium papers (pdftotext drops Devanagari) and
questions whose text pdftotext mangles.

Usage: python blocktext.py paper.pdf out.json [first_q last_q]
Prints each block as  n | answer | stem || 1) .. 2) .. 3) .. 4) ..
The answer comes from the same colour-and-order rule as extract4.py."""
import sys, os, re, json
import pypdf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract4 as ex4

LABEL = re.compile(r'^\s*(?:A\s*n\s*s\s*)?([1-4])\s*\.\s*')


def spaced_events(path):
    r = pypdf.PdfReader(path)
    cc, ev = {}, []
    for page in r.pages:
        draws = ex4.resolve_draws(r, page, cc)
        k = [0]

        def before(op, args, cm, tm):
            if op != b'Do' or not args:
                return
            j = k[0]
            k[0] += 1
            if j < len(draws) and draws[j][0] == args[0] and draws[j][1] in ('tick', 'cross'):
                ev.append(('M', draws[j][1]))

        def vt(text, cm, tm, fd, fs):
            if text and text.strip():
                ev.append(('T', text))

        page.extract_text(visitor_operand_before=before, visitor_text=vt)
    return ev


def blocks(path):
    ev = spaced_events(path)
    out, cur = [], {'stem': [], 'opts': {}, 'marks': {}}
    label, pending = None, None
    for kind, val in ev:
        if kind == 'M':
            pending = val
            continue
        tight = re.sub(r'\s+', '', val)
        if tight.startswith('QuestionID:'):
            a, how = ex4.decide({k: [v] for k, v in cur['marks'].items()})
            stem = re.sub(r'\s+', ' ', ' '.join(cur['stem'])).strip()
            stem = re.sub(r'^Q\s*\.\s*\d+\s*', '', stem)
            out.append({'stem': stem, 'o': [re.sub(r'\s+', ' ', ' '.join(cur['opts'].get(i, []))).strip()
                                           for i in (1, 2, 3, 4)], 'a': a, 'how': how})
            cur, label, pending = {'stem': [], 'opts': {}, 'marks': {}}, None, None
            continue
        if re.match(r'^(Option\dID:|\d{6,}$|Section:)', tight):
            pending = None
            continue
        m = LABEL.match(val)
        if m and (label is not None or pending is not None or tight.startswith('Ans')):
            label = int(m.group(1))
            if pending is not None:
                cur['marks'][label] = pending
            cur['opts'].setdefault(label, []).append(val[m.end():])
        elif tight == 'Ans':
            label = 0
        elif label:
            cur['opts'].setdefault(label, []).append(val)
        else:
            cur['stem'].append(val)
        pending = None
    return out


def unspace(line):
    """'Q . 7 I n  a  r o w' -> 'Q.7In a row' (letters spaced, words double-spaced)."""
    line = line.replace('\x00', '')
    line = re.sub(r'(?<=\S) (?=\S)', '', line)
    return re.sub(r'\s+', ' ', line).strip()


def blocks_pagedump(path):
    """Some prints make pypdf repeat each page as one long letter-spaced run.
    Text only (pictures are not interleaved there): the answer must come from
    elsewhere. Returns blocks in paper order with 'a' = None."""
    ev = spaced_events(path)
    big = [v for k, v in ev if k == 'T' and len(v) > 150 and 'QuestionID:' in re.sub(r'\s+', '', v)]
    out, stem, opts, label = [], [], {}, None
    for raw in '\n'.join(big).split('\n'):
        line = unspace(raw)
        tight = line.replace(' ', '')
        if not line:
            continue
        if tight.startswith('QuestionID:'):
            s = re.sub(r'^Q\.?\d+\s*', '', ' '.join(stem)).strip()
            out.append({'stem': s, 'o': [' '.join(opts.get(i, [])).strip() for i in (1, 2, 3, 4)],
                        'a': None, 'how': 'page text'})
            stem, opts, label = [], {}, None
            continue
        if re.match(r'^(Option\dID:|\d{6,}$|ParticipantID|ParticipantName|TestCenter|TestDate|TestTime|Subject|Section:)', tight):
            continue
        m = re.match(r'^(?:Ans)?\s*([1-4])\s*\.\s*(.*)$', line)
        if m and (label is not None or tight.startswith('Ans') or m.group(1) == '1'):
            label = int(m.group(1))
            opts.setdefault(label, []).append(m.group(2))
        elif tight == 'Ans':
            label = 0
        elif label:
            opts.setdefault(label, []).append(line)
        else:
            stem.append(line)
    return out


if __name__ == '__main__':
    bl = blocks(sys.argv[1])
    lo, hi = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1, len(bl))
    for i, b in enumerate(bl, 1):
        if lo <= i <= hi:
            ans = 'ABCD'[b['a']] if b['a'] is not None else '?'
            print(f"{i} | {ans} | {b['stem'][:300]} || " + ' '.join(f'{k+1}) {o[:80]}' for k, o in enumerate(b['o'])))
    if len(sys.argv) > 2 and sys.argv[2] != '-':
        json.dump(bl, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
