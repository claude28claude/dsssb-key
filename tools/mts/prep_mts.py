"""Make review batches for the MTS 2026 questions (mts/mts-items.json).

* A question already decided in the main bank (linked by crosscheck.py as
  'old') copies that decision into mts/dec/mdec-00-auto.json when the old
  decision was kept or current affairs. An old "X" can mean "repeat of another
  main-bank question", which does not apply to this separate MTS section, so
  those go to review like everything else.
* Every other question goes to mts/review/batch-NNN.txt, 100 per file, with
  a suggested subject/topic, a current-affairs hint, a Hindi flag, and the most
  similar question already kept in the main bank (to reuse its facts) or
  earlier in the MTS set (a near-repeat).
Nothing here decides a question except the copied main-bank decisions."""
import glob, json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..')
items = json.load(open(os.path.join(HERE, 'mts-items.json'), encoding='utf-8'))

# Reuse the keyword rules and current-affairs pattern from the main review tool.
src = open(os.path.join(S, 'tools', 'prep_review.py'), encoding='utf-8').read()
chunk = src[src.index('CA = re.compile'):]
chunk = chunk[:chunk.index('\ndef ')] if '\ndef ' in chunk else chunk
ns = {'re': re}
exec(chunk, ns)
CA, RULES = ns['CA'], ns['RULES']

rows = {r['id']: r for r in json.load(open(os.path.join(S, 'ga', 'ga-readable.json'), encoding='utf-8'))}
dec = {}
for p in sorted(glob.glob(os.path.join(S, 'ga', 'dec-*.json'))):
    dec.update(json.load(open(p, encoding='utf-8')))
kept = {k: v for k, v in dec.items() if isinstance(v, list)}

os.makedirs(os.path.join(HERE, 'dec'), exist_ok=True)
os.makedirs(os.path.join(HERE, 'review'), exist_ok=True)

STOP = set('''the of which following is in a an to and was were who what by for on at as are be from with its it this
that these those among given below known called name one has have had did does do or not correct statement statements
option options select india indian'''.split())


def toks(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP and len(w) > 1}


def main_stem(qid):
    d = dec[qid]
    return d[5] if len(d) > 5 and d[5] else rows[qid]['stem']


# inverted index over kept main-bank questions
mtok = {k: toks(main_stem(k)) for k in kept}
inv = collections.defaultdict(set)
for k, t in mtok.items():
    for w in t:
        inv[w].add(k)


def best_match(t, pool_tok, pool_inv, before=None):
    cand = collections.Counter()
    for w in t:
        for k in pool_inv.get(w, ()):
            cand[k] += 1
    best = None
    for k, c in cand.most_common(40):
        if before is not None and k >= before:
            continue
        pt = pool_tok[k]
        j = len(t & pt) / len(t | pt)
        if j >= 0.5 and (best is None or j > best[0]):
            best = (j, k)
    return best


auto, todo = {}, []
mts_tok, mts_inv = {}, collections.defaultdict(set)
for q in items:
    old = q.get('old')
    if old and old in dec and (isinstance(dec[old], list) or dec[old] == 'CA'):
        auto[q['id']] = dec[old]
    else:
        todo.append(q)

lines_by_batch = []
for i, q in enumerate(todo):
    t = toks(q['stem'])
    text = (q['stem'] + ' ' + ' '.join(q['o'])).lower()
    sug = next((f'{s}/{tp}' for s, tp, pat in RULES if re.search(pat, text)), '?')
    flags = []
    if CA.search(q['stem']):
        flags.append('CA?')
    if len(re.findall(r'[ऀ-ॿ]', q['stem'])) > 5:
        flags.append('HI')
    if len(q['src']) > 1:
        flags.append(f'x{len(q["src"])}')
    out = [f'{q["id"]} {{{sug}}} ' + ''.join(f'[{f}] ' for f in flags) + f'[{", ".join(q["src"])}] {q["stem"]}',
           '   ' + ' | '.join(f'{"ABCD"[k]}) {o}' for k, o in enumerate(q['o'])) + f'  => {"ABCD"[q["a"]]}']
    if q.get('old'):
        out.append(f'   OLD {q["old"]} main-bank decision: {dec.get(q["old"])!r}')
    if t:
        b = best_match(t, mtok, inv)
        if b:
            k = b[1]
            d = kept[k]
            ro = rows[k]
            opts = d[6] if len(d) > 6 and d[6] else ro['o']
            out.append(f'   SIM {k} {b[0]:.2f} {d[0]}/{d[1]} ans="{opts[ro["a"]]}" :: {d[2]}')
        bm = best_match(t, mts_tok, mts_inv)
        if bm and bm[0] >= 0.7:
            out.append(f'   MTS-REPEAT? {bm[1]} {bm[0]:.2f}')
        mts_tok[q['id']] = t
        for w in t:
            mts_inv[w].add(q['id'])
    lines_by_batch.append('\n'.join(out))

json.dump(auto, open(os.path.join(HERE, 'dec', 'mdec-00-auto.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
for old in glob.glob(os.path.join(HERE, 'review', 'batch-*.txt')):
    os.remove(old)
n = 0
for b in range(0, len(lines_by_batch), 100):
    n += 1
    with open(os.path.join(HERE, 'review', f'batch-{n:03d}.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines_by_batch[b:b + 100]) + '\n')
print('items', len(items), '| decisions copied from main bank', len(auto),
      '| to review', len(todo), 'in', n, 'batches')
print('flags: CA?', sum('[CA?]' in l for l in lines_by_batch), ' HI', sum('[HI]' in l for l in lines_by_batch),
      ' MTS-REPEAT?', sum('MTS-REPEAT?' in l for l in lines_by_batch), ' SIM', sum('   SIM ' in l for l in lines_by_batch))
