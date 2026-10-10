"""Build data-prac.js: the separate "Extra Practice" section of the site.

These questions are NOT previous-year DSSSB questions. They are written in the
same pattern as the DSSSB papers, on the same syllabus, so that there is
something left to practise on once a topic's real questions have been used up.
The site labels every one of them as a practice question, so they can never be
mistaken for something DSSSB actually asked.

Input:
  ./prac/prac-*.json   a list of question objects:
                         {"id","s","t","q","o":[4 options],"a":0-3,"x","e"}
                       "a" is the index of the correct option.

The script refuses to write anything if an id repeats, a subject or topic is
unknown, a question does not have exactly four distinct non-empty options, the
answer index is out of range, or a question duplicates one already in the
site's real question banks.

  python tools/build_prac.py <site folder>"""
import glob, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PRAC = os.path.join(HERE, 'prac')
OUT = sys.argv[1]
LABEL = 'Practice question'

# Subjects, topics and text clean-up are shared with the main bank's build.py.
src = open(os.path.join(HERE, 'build.py'), encoding='utf-8').read()
shared = src[src.index('SUBJECTS = ['):src.index('rows = {')]
ns = {'re': re, 'collections': collections}
exec(shared, ns)
SUBJECTS, VALID = ns['SUBJECTS'], ns['VALID']

# ---------------------------------------------------------------- read input
items, seen = [], {}
for path in sorted(glob.glob(os.path.join(PRAC, 'prac-*.json'))):
    for q in json.load(open(path, encoding='utf-8')):
        name = os.path.basename(path)
        qid = q.get('id')
        if not qid or not re.match(r'^p\d{4}$', qid):
            raise SystemExit(f'{name}: id must look like p0001, got {qid!r}')
        if qid in seen:
            raise SystemExit(f'{qid} appears twice ({seen[qid]} and {name})')
        seen[qid] = name
        items.append(q)

# ------------------------------------------------------------------- checks
def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', str(s).lower())).strip()

stems = {}
for q in items:
    qid = q['id']
    if q['s'] not in VALID or q['t'] not in VALID[q['s']]:
        raise SystemExit(f'{qid}: unknown subject/topic {q["s"]}/{q["t"]}')
    if not q.get('q', '').strip() or not q.get('x', '').strip():
        raise SystemExit(f'{qid}: needs both a question and an explanation')
    opts = q.get('o') or []
    if len(opts) != 4 or not all(str(o).strip() for o in opts):
        raise SystemExit(f'{qid}: needs exactly four non-empty options')
    if len({norm(o) for o in opts}) != 4:
        raise SystemExit(f'{qid}: two options are the same')
    if q.get('a') not in (0, 1, 2, 3):
        raise SystemExit(f'{qid}: answer index must be 0-3, got {q.get("a")!r}')
    if re.search(r'[ऀ-ॿ]', q['q'] + ''.join(map(str, opts)) + q['x'] + q.get('e', '')):
        raise SystemExit(f'{qid}: Hindi text must be written in English')
    key = norm(q['q'])
    if key in stems:
        raise SystemExit(f'{qid} repeats the question of {stems[key]}')
    stems[key] = qid

# The answer must not always sit in the same place, or the set teaches nothing.
spread = collections.Counter(q['a'] for q in items)
if max(spread.values()) > len(items) * 0.4:
    raise SystemExit(f'answers are lopsided across the options: {dict(spread)}')

# ------------------------- must not repeat a question the real banks already have
existing = {}
for data in ['data-static.js', 'data-hist.js', 'data-pol.js', 'data-geo.js',
             'data-eco.js', 'data-phy.js', 'data-chem.js', 'data-bio.js',
             'data-env.js', 'data-mts.js', 'data-as.js']:
    path = os.path.join(OUT, data)
    if not os.path.exists(path):
        continue
    text = open(path, encoding='utf-8').read()
    if '.push(' in text:                       # one subject: …SUBJECTS.push({…});
        body = text[text.index('.push(') + 6:text.rindex(');')]
        subs = [json.loads(body)]
    else:                                      # a whole section: …SUBJECTS = […];
        body = text[text.index('= ') + 2:text.rindex(';')]
        subs = json.loads(body)
    for sub in subs:
        for t in sub['topics']:
            for q in t['qs']:
                existing[norm(q['q'])] = q['id']
print(f'checked against {len(existing)} questions already on the site')

clash = [(q['id'], existing[norm(q['q'])]) for q in items if norm(q['q']) in existing]
if clash:
    raise SystemExit('these practice questions repeat real ones: ' +
                     ', '.join(f'{a} = {b}' for a, b in clash[:20]))

# -------------------------------------------------------------------- write
bank = collections.defaultdict(list)
for q in items:
    bank[(q['s'], q['t'])].append({'id': q['id'], 'q': q['q'].strip(),
                                   'o': [str(o).strip() for o in q['o']], 'a': q['a'],
                                   'x': q['x'].strip(), 'e': q.get('e', '').strip(),
                                   'src': [LABEL]})

os.makedirs(OUT, exist_ok=True)
subjects, total = [], 0
for sid, name, tab, blurb, topics in SUBJECTS:
    out_topics = []
    for tid, tname in topics:
        qs = sorted(bank[(sid, tid)], key=lambda q: q['id'])
        if qs:
            out_topics.append({'id': tid, 'n': tname, 'qs': qs})
            total += len(qs)
    if out_topics:
        subjects.append({'id': sid, 'n': name, 'tab': tab, 'w': blurb, 'topics': out_topics})
        print(f'{sid:7} {sum(len(t["qs"]) for t in out_topics):4} questions  ' +
              ', '.join(f'{t["id"]}:{len(t["qs"])}' for t in out_topics))

with open(os.path.join(OUT, 'data-prac.js'), 'w', encoding='utf-8') as f:
    f.write('/* Generated by tools/build_prac.py. Newly written practice questions, NOT DSSSB papers. Do not edit by hand. */\n')
    f.write('window.PRAC_SUBJECTS = ')
    json.dump(subjects, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';\n')
print(f'written {total} practice questions across {len(subjects)} subjects; '
      f'answer spread A/B/C/D = {[spread[i] for i in range(4)]}')
