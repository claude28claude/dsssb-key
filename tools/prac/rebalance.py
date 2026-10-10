"""Spread the correct answer evenly over positions A, B, C and D.

Writing questions by hand leaves the right answer sitting in the first or
second slot far too often, which lets a guesser score well without knowing
anything. This rewrites prac-*.json in place, moving each correct option to a
planned position and keeping the other three in their original order.

Nothing about the questions changes except the order of the four options, and
"a" is updated to follow the correct option, so the answer stays the answer.
Run once after adding new questions:

  python tools/prac/rebalance.py
"""
import glob, io, json, os, random, collections

HERE = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(os.path.join(HERE, 'prac-*.json')))
data = {f: json.load(io.open(f, encoding='utf-8')) for f in files}
items = [q for f in files for q in data[f]]

# A fixed seed, so running this twice gives the same site both times.
rng = random.Random(20261010)
targets = [i % 4 for i in range(len(items))]
rng.shuffle(targets)

for q, want in zip(items, targets):
    opts, a = list(q['o']), q['a']
    right = opts.pop(a)                 # take the correct option out…
    opts.insert(want, right)            # …and put it back where we want it
    q['o'], q['a'] = opts, want

for f in files:
    out = ['[']
    rows = data[f]
    for i, q in enumerate(rows):
        out.append(json.dumps(q, ensure_ascii=False, separators=(',', ':')) +
                   (',' if i < len(rows) - 1 else ''))
    out.append(']')
    io.open(f, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')

spread = collections.Counter(q['a'] for q in items)
print(f'{len(items)} questions rewritten across {len(files)} files')
print('answer now sits at A/B/C/D:', [spread[i] for i in range(4)])
