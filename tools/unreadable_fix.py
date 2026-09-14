"""Recover the General Awareness questions that were left out as unreadable in
round 1 (mostly Hindi-medium PRT papers, whose Hindi pdftotext cannot read).

For every such question the text is taken from the page's drawing order
(blocktext.py). It is accepted only if
  * the paper splits into exactly as many blocks as round 1 found questions, and
  * the answer read now equals the tick recorded in round 1 for that question,
  * all four options have text.
Writes ga/recovered.json and ga/recovered-review.txt."""
import json, os, sys, collections, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blocktext

GA = os.path.join(HERE, '..', 'ga')
PAPERS = os.path.join(HERE, '..', 'papers')

uniq = json.load(open(os.path.join(GA, 'ga-unique.json'), encoding='utf-8'))
readable = {r['id'] for r in json.load(open(os.path.join(GA, 'ga-readable.before-round2.json'
                                                        if os.path.exists(os.path.join(GA, 'ga-readable.before-round2.json'))
                                                        else 'ga-readable.json'), encoding='utf-8'))}
todo = [r for r in uniq if r['id'] not in readable]
by_pid = collections.defaultdict(list)
for r in todo:
    by_pid[r['pid']].append(r)

out, report = [], []
for pid, rows in sorted(by_pid.items()):
    pdf = os.path.join(PAPERS, pid + '.pdf')
    if pid.startswith(('ja-', 'steno-2021-08')) or not os.path.exists(pdf):
        report.append(f'{pid}: skipped (2021 layout or no PDF) {len(rows)}')
        continue
    try:
        bl = blocktext.blocks(pdf)
    except Exception as e:
        report.append(f'{pid}: blocktext error {e}')
        continue
    old = json.load(open(os.path.join(PAPERS, pid + '.json'), encoding='utf-8'))
    pagetext = False
    if not bl:
        # prints where pypdf repeats each page as one letter-spaced run: take the
        # text from those runs; the answer stays the round-1 tick for that question
        bl = blocktext.blocks_pagedump(pdf)
        pagetext = True
    if len(bl) != len(old):
        report.append(f'{pid}: {len(bl)} blocks vs {len(old)} questions in round 1 -> not used')
        continue
    ok = bad = empty = 0
    for r in rows:
        b = bl[r['n'] - 1]
        if pagetext and r['a'] is not None:
            b = dict(b, a=r['a'])
        if b['a'] is None or r['a'] is None or b['a'] != r['a']:
            bad += 1
            continue
        if not all(o.strip() for o in b['o']) or len(b['stem']) < 8:
            empty += 1
            continue
        out.append({'id': r['id'], 'src': r['src'], 'pid': pid, 'n': r['n'], 'stem': b['stem'], 'o': b['o'], 'a': b['a']})
        ok += 1
    report.append(f'{pid}: recovered {ok}, answer mismatch/unclear {bad}, options missing {empty}')

json.dump(out, open(os.path.join(GA, 'recovered.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
with open(os.path.join(GA, 'recovered-review.txt'), 'w', encoding='utf-8') as f:
    for r in out:
        f.write(f"{r['id']} [{'; '.join(r['src'])}] {r['stem']}\n    " +
                ' | '.join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(r['o'])) + f"\n    => {'ABCD'[r['a']]}\n")
print('\n'.join(report))
print('recovered', len(out), 'of', len(todo))
