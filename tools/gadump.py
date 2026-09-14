"""Collect every General Awareness question from the extracted papers into one
list, merge the same question asked in several shifts, and write a compact
review file. GA is located by position, not by the section label (the 2021
papers label sections unreliably):

  200-question general papers (ASO, Stenographer)  -> questions 41-80
  2021 digialm papers (Junior Assistant)          -> Question Number 41-80, English copy
  teaching papers (PRT / TGT / PGT)               -> questions 21-40
"""
import json, glob, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PAPERS = os.path.join(HERE, '..', 'papers')
OUT = os.path.join(HERE, '..', 'ga')
os.makedirs(OUT, exist_ok=True)

EXAM = {'aso': 'ASO', 'ja': 'Junior Assistant', 'steno': 'Stenographer',
        'prt': 'PRT', 'tgt': 'TGT', 'pgt': 'PGT', 'pat': 'Patwari'}


def label(pid):
    m = re.match(r'([a-z]+)(?:-([a-z]+))?-(\d{4})-(\d{2})-(\d{2})(?:-(\w+))?', pid)
    kind, subj, y, mo, d, sh = m.groups()
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    name = EXAM[kind]
    shift = ''
    if sh and re.match(r's\d', sh):
        shift = ' S' + sh[1]
    return f'{name} {int(d)} {months[int(mo)-1]} {y}{shift}', int(y)


def norm(s):
    return re.sub(r'[^a-z0-9ऀ-ॿ]', '', (s or '').lower())


items = []
for path in sorted(glob.glob(os.path.join(PAPERS, '*.json'))):
    pid = os.path.basename(path)[:-5]
    if pid.startswith('manual'):
        continue
    qs = json.load(open(path, encoding='utf-8'))
    kind = pid.split('-')[0]
    if kind == 'ja':
        ga = [(q['n'], q) for q in qs if 41 <= q.get('n', 0) <= 80 and q['lang'] == 'en']
    elif kind in ('aso', 'steno'):
        ga = [(i + 1, q) for i, q in enumerate(qs) if 40 <= i < 80]
    else:
        ga = [(i + 1, q) for i, q in enumerate(qs) if 20 <= i < 40]
    for n, q in ga:
        items.append({'pid': pid, 'n': n, 'stem': q['stem'], 'o': q['o'],
                      'a': q['a'], 'ticks': q.get('ticks'), 'sec': q.get('sec')})

for path in glob.glob(os.path.join(PAPERS, 'manual-*.json')):
    data = json.load(open(path, encoding='utf-8'))
    if isinstance(data, list):
        data = {'pat-2022-09-17-s2': data}
    for pid, qs in data.items():
        for q in qs:
            items.append({'pid': pid, 'n': q['n'], 'stem': q['stem'], 'o': q['o'],
                          'a': q['a'], 'ticks': [q['a']], 'sec': 'GA'})

groups = collections.OrderedDict()
for it in items:
    key = norm(it['stem'])[:120] + '|' + (norm(it['o'][it['a']]) if it['o'] and it['a'] is not None else '?')
    groups.setdefault(key, []).append(it)

bad_sec = sum(1 for it in items if it['sec'] not in ('GA', None))
unreadable = [it for it in items if len(norm(it['stem'])) < 8 or not it['o'] or any(not o for o in it['o'])]
print('GA items', len(items), 'unique', len(groups), 'section-label disagreements', bad_sec,
      'unreadable', len(unreadable))
print('per exam:', dict(collections.Counter(it['pid'].split('-')[0] for it in items)))

rows = []
for i, (key, its) in enumerate(groups.items()):
    first = its[0]
    srcs = sorted({label(it['pid'])[0] for it in its})
    if first['ticks'] and len(first['ticks']) == 4:
        ans = 'ALL (dropped)'
    elif first['a'] is None:
        ans = '?'
    else:
        ans = 'ABCD'[first['a']]
    rows.append({'id': f'q{i+1:04d}', 'src': srcs, 'stem': first['stem'], 'o': first['o'],
                 'a': first['a'], 'ans': ans, 'pid': first['pid'], 'n': first['n']})

json.dump(rows, open(os.path.join(OUT, 'ga-unique.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
with open(os.path.join(OUT, 'ga-review.txt'), 'w', encoding='utf-8') as f:
    for r in rows:
        opts = ' | '.join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(r['o'] or []))
        f.write(f"{r['id']} [{'; '.join(r['src'])}] {r['stem']}\n    {opts}\n    => {r['ans']}\n")
print('wrote', len(rows), 'unique questions')
