"""Turn the reviewed decisions into the site's data files.

Inputs (all in ../ga):
  ga-readable.json   every readable General Awareness question, with the
                     answer read from DSSSB's own tick mark
  dec-*.json         one decision per question id:
                       "CA" / "X"   dropped (current affairs / not usable)
                       [subject, topic, explanation, example, note,
                        stem_override?, options_override?]

The answer index is ALWAYS taken from ga-readable.json (the machine-read tick),
never from the decision files, so a typing slip while writing explanations can
never change an answer. The script stops with an error if any readable
question has no decision, or a decision names an unknown subject/topic."""
import json, glob, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
GA = os.path.join(HERE, 'ga')
OUT = sys.argv[1]

SUBJECTS = [
  ('static', 'Static GK', 'Static GK', 'Dances, music, festivals, monuments, books, sports, awards and firsts.', [
    ('dance', 'Dances'), ('music', 'Music and Instruments'), ('festivals', 'Fairs and Festivals'),
    ('art', 'Monuments, Art and Architecture'), ('books', 'Books and Authors'),
    ('sports', 'Sports'), ('misc', 'Awards, Firsts, Days and Organisations')]),
  ('hist', 'History', 'History', 'Ancient and medieval India, British India, and the freedom struggle.', [
    ('ancient', 'Ancient India'), ('medieval', 'Medieval India'),
    ('modern', 'Modern India (1757–1885)'), ('freedom', 'Freedom Struggle (1885–1947)')]),
  ('pol', 'Polity', 'Polity', 'The Constitution, rights, Parliament, courts, states and constitutional bodies.', [
    ('constitution', 'Making and Features of the Constitution'),
    ('rights', 'Citizenship, Rights, DPSP and Duties'),
    ('union', 'President, Prime Minister and Parliament'), ('judiciary', 'Judiciary'),
    ('states', 'States, Union Territories, Delhi and Local Bodies'),
    ('federal', 'Centre–State Relations and Emergency'),
    ('bodies', 'Constitutional Bodies, Acts and Elections')]),
  ('geo', 'Geography', 'Geography', 'Earth, physical geography, India, resources, population and the world.', [
    ('earth', 'Earth and the Solar System'), ('physical', 'Physical Geography'),
    ('india', 'India: Relief, Rivers and Climate'), ('resources', 'Resources, Agriculture and Industry'),
    ('people', 'Population and Census'), ('world', 'World and Neighbours')]),
  ('eco', 'Economy', 'Economy', 'Static economy only: concepts, banking, planning and long-running schemes.', [
    ('basics', 'Concepts and National Income'), ('money', 'Money, Banking and the RBI'),
    ('planning', 'Planning, Budget and Reforms'), ('schemes', 'Government Schemes and Policies')]),
  ('phy', 'Physics', 'Physics', 'Motion, heat and sound, light, electricity and magnetism.', [
    ('mechanics', 'Motion, Force, Units and Measurement'), ('heat', 'Heat, Sound and Thermodynamics'),
    ('light', 'Light and Optics'), ('electricity', 'Electricity and Magnetism')]),
  ('chem', 'Chemistry', 'Chemistry', 'Matter and solutions, reactions, and chemistry in daily life.', [
    ('matter', 'Matter, Atoms and Solutions'), ('reactions', 'Reactions, Acids and Bases'),
    ('everyday', 'Chemistry in Everyday Life')]),
  ('bio', 'Biology', 'Biology', 'Cells and genetics, the human body, health, plants and the living world.', [
    ('cell', 'Cell, Genetics and DNA'), ('human', 'Human Body'), ('health', 'Nutrition and Diseases'),
    ('plants', 'Plants'), ('living', 'Classification and Animals')]),
  ('env', 'Environment', 'Environment', 'Ecology, protected areas and biodiversity, pollution and climate.', [
    ('ecology', 'Ecology and Sustainability'), ('biodiversity', 'Parks, Forests and Biodiversity'),
    ('pollution', 'Pollution'), ('climate', 'Climate Change and Treaties')]),
]
VALID = {s[0]: {t[0] for t in s[4]} for s in SUBJECTS}

rows = {r['id']: r for r in json.load(open(os.path.join(GA, 'ga-readable.json'), encoding='utf-8'))}
dec = {}
for path in sorted(glob.glob(os.path.join(GA, 'dec-*.json'))):
    dec.update(json.load(open(path, encoding='utf-8')))

missing = [i for i in rows if i not in dec]
if missing:
    raise SystemExit(f'{len(missing)} readable questions have no decision: {missing[:20]}')
unknown = [i for i in dec if i not in rows]
if unknown:
    raise SystemExit(f'decisions for ids not in the readable set: {unknown[:20]}')


def clean(s):
    s = s or ''
    if 'cdn.digialm' in s:
        m = list(re.finditer(r'Q\.\s?\d+\s', s))
        if m:
            s = s[m[-1].end():]
    # A stem that swallowed the previous question's tail: keep only the text
    # after the last "Q.n" marker, which is where this question really starts.
    m = list(re.finditer(r'Q\.\s?\d+\s', s))
    if m:
        s = s[m[-1].end():]
    s = re.sub(r'^Q\s+', '', s)
    s = re.sub(r'\s\.\s', ' ', s)
    s = s.replace('�', '’').replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    return re.sub(r'\s+', ' ', s).strip()


def clean_option(s):
    # An option that swallowed the NEXT question's stem: cut at the first "Q.n".
    s = re.split(r'\s+Q\s?\.\s?\d+\b', s or '')[0]
    return clean(s)


EXAM_ORDER = ['ASO', 'Patwari', 'Junior Assistant', 'Stenographer', 'PRT', 'TGT', 'PGT']


def exam_rank(src):
    for i, e in enumerate(EXAM_ORDER):
        if any(x.startswith(e) for x in src):
            return i
    return 99


bank = collections.defaultdict(list)
counts = collections.Counter()
for qid, d in dec.items():
    if isinstance(d, str):
        counts['dropped ' + d] += 1
        continue
    s, t, x, e, note = d[0], d[1], d[2], d[3], d[4]
    if s not in VALID or t not in VALID[s]:
        raise SystemExit(f'{qid}: unknown subject/topic {s}/{t}')
    r = rows[qid]
    stem = d[5] if len(d) > 5 and d[5] else clean(r['stem'])
    opts = d[6] if len(d) > 6 and d[6] else [clean_option(o) for o in r['o']]
    if len(opts) != 4 or not all(opts) or r['a'] not in (0, 1, 2, 3):
        raise SystemExit(f'{qid}: bad options or answer')
    item = {'id': qid, 'q': stem, 'o': opts, 'a': r['a'], 'x': x, 'e': e, 'src': r['src']}
    if note:
        item['k'] = note
    bank[(s, t)].append(item)
    counts['kept'] += 1

os.makedirs(OUT, exist_ok=True)
total = 0
for sid, name, tab, blurb, topics in SUBJECTS:
    out_topics = []
    for tid, tname in topics:
        qs = sorted(bank[(sid, tid)], key=lambda q: (exam_rank(q['src']), q['id']))
        if not qs:
            continue
        out_topics.append({'id': tid, 'n': tname, 'qs': qs})
        total += len(qs)
    subj = {'id': sid, 'n': name, 'tab': tab, 'w': blurb, 'topics': out_topics}
    with open(os.path.join(OUT, f'data-{sid}.js'), 'w', encoding='utf-8') as f:
        f.write('/* Generated by tools/build.py from reviewed DSSSB papers. Do not edit by hand. */\n')
        f.write('window.SUBJECTS = window.SUBJECTS || [];\nwindow.SUBJECTS.push(')
        json.dump(subj, f, ensure_ascii=False, separators=(',', ':'))
        f.write(');\n')
    print(f'{sid:7} {sum(len(t["qs"]) for t in out_topics):4} questions  ' +
          ', '.join(f'{t["id"]}:{len(t["qs"])}' for t in out_topics))
print(dict(counts), 'written', total)
src_count = collections.Counter(x.split(' ')[0] if not x.startswith('Junior') else 'Junior Assistant'
                                for qs in bank.values() for q in qs for x in q['src'])
print('by exam:', dict(src_count))
