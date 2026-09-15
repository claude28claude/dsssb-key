"""Group and prepare the Assistant Superintendent 2026 questions for review.

1. Exact repeats across the 17 shifts (same question, same answer text) become
   one item listing every shift. Ids a0001... in first-asked order ->
   as/as-items.json. Never renumber: decisions are keyed by id.
2. Review batches as/review/batch-NNN.txt, 100 per file, each question with
   a suggested subject/topic, a current-affairs hint, and the most similar
   question already kept in the main bank or the MTS 2026 section (to reuse
   facts and catch a disagreeing answer).
Nothing here decides a question."""
import glob, json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..')
raw = json.load(open(os.path.join(HERE, 'as-raw.json'), encoding='utf-8'))

src = open(os.path.join(T, 'prep_review.py'), encoding='utf-8').read()
chunk = src[src.index('CA = re.compile'):]
chunk = chunk[:chunk.index('\ndef ')] if '\ndef ' in chunk else chunk
ns = {'re': re}
exec(chunk, ns)
CA, RULES = ns['CA'], ns['RULES']


def norm(s):
    return re.sub(r'[\W_]+', '', s.lower())


# ---- 1. group repeats -------------------------------------------------------
groups = collections.OrderedDict()
for q in raw:
    k = (norm(q['stem']), norm(q['o'][q['a']]))
    if k in groups:
        if q['src'] not in groups[k]['src']:
            groups[k]['src'].append(q['src'])
    else:
        groups[k] = {'stem': q['stem'], 'o': q['o'], 'a': q['a'], 'src': [q['src']], 'part': q['part'], 'n': q['n']}
items = [dict(id=f'a{i:04d}', **g) for i, g in enumerate(groups.values(), 1)]
json.dump(items, open(os.path.join(HERE, 'as-items.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
bystem = collections.defaultdict(set)
for s, a in groups:
    bystem[s].add(a)
print(f'GA questions {len(raw)} -> distinct {len(items)}; same question with different answers: '
      f'{sum(len(a) > 1 for a in bystem.values())}')

# ---- 2. kept questions elsewhere on the site, for hints ----------------------
pool = {}   # id -> (stem, answer text, subject/topic, explanation)
rows = {r['id']: r for r in json.load(open(os.path.join(T, 'ga', 'ga-readable.json'), encoding='utf-8'))}
for p in sorted(glob.glob(os.path.join(T, 'ga', 'dec-*.json'))):
    for k, d in json.load(open(p, encoding='utf-8')).items():
        if isinstance(d, list):
            r = rows[k]
            opts = d[6] if len(d) > 6 and d[6] else r['o']
            pool[k] = (d[5] if len(d) > 5 and d[5] else r['stem'], opts[r['a']], f'{d[0]}/{d[1]}', d[2])
mts = {r['id']: r for r in json.load(open(os.path.join(T, 'mts', 'mts-items.json'), encoding='utf-8'))}
for p in sorted(glob.glob(os.path.join(T, 'mts', 'mdec-*.json'))):
    for k, d in json.load(open(p, encoding='utf-8')).items():
        if isinstance(d, list):
            r = mts[k]
            opts = d[6] if len(d) > 6 and d[6] else r['o']
            pool[k] = (d[5] if len(d) > 5 and d[5] else r['stem'], opts[r['a']], f'{d[0]}/{d[1]}', d[2])

STOP = set('''the of which following is in a an to and was were who what by for on at as are be from with its it this
that these those among given below known called name one has have had did does do or not correct statement statements
option options select india indian'''.split())


def toks(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP and len(w) > 1}


ptok = {k: toks(v[0]) for k, v in pool.items()}
inv = collections.defaultdict(set)
for k, t in ptok.items():
    for w in t:
        inv[w].add(k)


def best(t):
    cand = collections.Counter()
    for w in t:
        for k in inv.get(w, ()):
            cand[k] += 1
    top = None
    for k, _ in cand.most_common(40):
        j = len(t & ptok[k]) / len(t | ptok[k])
        if j >= 0.5 and (top is None or j > top[0]):
            top = (j, k)
    return top


os.makedirs(os.path.join(HERE, 'review'), exist_ok=True)
for old in glob.glob(os.path.join(HERE, 'review', 'batch-*.txt')):
    os.remove(old)
blocks = []
for q in items:
    text = (q['stem'] + ' ' + ' '.join(q['o'])).lower()
    sug = next((f'{s}/{tp}' for s, tp, pat in RULES if re.search(pat, text)), '?')
    flags = (['CA?'] if CA.search(q['stem']) else []) + ([f'x{len(q["src"])}'] if len(q['src']) > 1 else [])
    out = [f'{q["id"]} {{{sug}}} ' + ''.join(f'[{f}] ' for f in flags) + f'[{", ".join(q["src"])} GA{q["part"]} Q{q["n"]}] {q["stem"]}',
           '   ' + ' | '.join(f'{"ABCD"[k]}) {o}' for k, o in enumerate(q['o'])) + f'  => {"ABCD"[q["a"]]}']
    b = best(toks(q['stem']))
    if b:
        st, ans, where, x = pool[b[1]]
        out.append(f'   SIM {b[1]} {b[0]:.2f} {where} ans="{ans}" :: {x}')
    blocks.append('\n'.join(out))
n = 0
for i in range(0, len(blocks), 100):
    n += 1
    open(os.path.join(HERE, 'review', f'batch-{n:03d}.txt'), 'w', encoding='utf-8').write('\n'.join(blocks[i:i + 100]) + '\n')
print('batches', n, '| CA? flags', sum('[CA?]' in b for b in blocks), '| SIM hints', sum('   SIM ' in b for b in blocks))
