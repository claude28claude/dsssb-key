"""1. Trust check: for the 16 MTS shifts already read from DSSSB's own tick
   images (ga/ga-readable.json), the compilation's answer TEXT must match.
   Option order differs between the two prints, so match by text.
2. Group exact repeats across the 117 shifts (same question and same answer
   text) into one item that lists every shift it was asked in.
Writes mts/mts-items.json with stable ids m0001... in first-asked order."""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(HERE, 'mts-raw.json'), encoding='utf-8'))
old = json.load(open(os.path.join(HERE, '..', 'ga', 'ga-readable.json'), encoding='utf-8'))


def norm(s):
    s = s.lower().replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff').replace('ﬃ', 'ffi')
    s = re.sub(r'\bans\b', ' ', s)
    return re.sub(r'[\W_]+', '', s)


# ---- 1. answer check against tick-read papers ------------------------------
oldby = collections.defaultdict(list)
for r in old:
    for s in r['src']:
        if s.startswith('MTS ') and '2026' in s:
            oldby[s].append(r)
same = diff = unmatched = 0
diffs = []
for q in raw:
    cands = oldby.get(q['src'])
    if not cands:
        continue
    key = norm(q['stem'])
    hit = [r for r in cands if norm(r['stem']) == key or (len(key) > 30 and (key in norm(r['stem']) or norm(r['stem']) in key))]
    if not hit:
        unmatched += 1
        continue
    r = hit[0]
    q['old'] = r['id']
    if norm(r['o'][r['a']]) == norm(q['o'][q['a']]):
        same += 1
    else:
        diff += 1
        diffs.append((q['src'], q['stem'][:90], 'pdf:', q['o'][q['a']], 'tick:', r['o'][r['a']], r['id']))
print(f'answer check vs DSSSB tick prints: same {same}, different {diff}, not matched {unmatched}')
for d in diffs:
    print('  DIFF', d)

# ---- 2. group repeats --------------------------------------------------------
groups = collections.OrderedDict()
conflicts = []
for q in raw:
    k = (norm(q['stem']), norm(q['o'][q['a']]))
    if k in groups:
        g = groups[k]
        if q['src'] not in g['src']:
            g['src'].append(q['src'])
    else:
        groups[k] = {'stem': q['stem'], 'o': q['o'], 'a': q['a'], 'src': [q['src']], 'part': q['part'], 'page': q['page']}
    if q.get('old'):
        groups[k]['old'] = q['old']
# same question, different answer text between shifts
bystem = collections.defaultdict(set)
for (s, a) in groups:
    bystem[s].add(a)
conflicts = [s for s, a in bystem.items() if len(a) > 1]

items = []
for i, g in enumerate(groups.values(), 1):
    g = dict(id=f'm{i:04d}', **g)
    items.append(g)
json.dump(items, open(os.path.join(HERE, 'mts-items.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(f'GA questions {len(raw)} -> distinct {len(items)} (repeats merged {len(raw) - len(items)})')
print('same question with different answers across shifts:', len(conflicts))
for s in conflicts[:20]:
    print('  ', [ (g['src'], g['o'][g['a']]) for g in items if norm(g['stem']) == s ])
print('by part:', collections.Counter(g['part'] for g in items))
