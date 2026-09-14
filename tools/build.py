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
# Round-1 questions (q0001-q1624) must all be decided. Round-2 questions are
# reviewed in stages: an undecided one is simply not published yet.
missing_old = [i for i in missing if int(i[1:]) <= 1624]
if missing_old:
    raise SystemExit(f'{len(missing_old)} round-1 questions have no decision: {missing_old[:20]}')
pending = len(missing)
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
    # MTS 2026 prints put the answer column's "Ans" label into the middle of
    # long questions ("which constitutional Ans principle"). Drop that word.
    s = re.sub(r'(?<=\S)\s+Ans\s+(?=\S)', ' ', s)
    s = s.replace('�', '’')
    s = unligature(s)
    return re.sub(r'\s+', ' ', s).strip()


# Words after which a ligature starts a NEW word ("The ﬁ rst", "a ﬁ rm", "for ﬁ shing").
LIG_BREAK = set('the a an of for is in on to and or by as at was are its his her their with from be been '
                'has have had not no most very more less than that this which who first'.split())


def unligature(s):
    """Printed ligatures come out of the PDFs as one glyph with a stray space on
    BOTH sides, whether the glyph is mid-word ("pro ﬁ t", "o ﬃ cially") or starts
    a word ("The ﬁ rst"). The space after it is always stray. The space before it
    is stray unless the fragment before is an ordinary short word. No English word
    starts with 'ff', so ﬀ ﬃ ﬄ always join on both sides."""
    def join(m):
        before, glyph = m.group(1), m.group(2)
        letters = {'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl'}[glyph]
        if before and glyph in 'ﬁﬂ' and before.lower() in LIG_BREAK:
            return before + ' ' + letters
        return (before or '') + letters
    return re.sub(r'([A-Za-z]+)? ?([ﬀﬁﬂﬃﬄ]) ?(?=[a-z])', join, s).replace('ﬁ', 'fi').replace('ﬂ', 'fl') \
        .replace('ﬀ', 'ff').replace('ﬃ', 'ffi').replace('ﬄ', 'ffl')


def clean_option(s):
    # An option that swallowed the NEXT question's stem: cut at the first "Q.n".
    s = re.split(r'\s+Q\s?\.\s?\d+\b', s or '')[0]
    # ...or the next section's heading ("1825 General Awareness2").
    s = re.sub(r'\s*General Awareness\s*\d*\s*$', '', s)
    return clean(s)


# Order of questions inside a topic: the user's own exams first, then the
# clerical and office posts closest to them in level, then teaching papers,
# then everything else (technical and senior posts) at rank 99.
EXAM_ORDER = ['ASO', 'Patwari',
              'Junior Assistant', 'Junior Clerk', 'Junior Secretariat Assistant', 'Head Clerk', 'Stenographer',
              'Personal Assistant', 'Assistant Superintendent', 'Office Superintendent', 'MTS', 'Store Keeper',
              'Fire Operator', 'Ahlmad', 'Fee Collector', 'Jr. Telephone Operator', 'Security Supervisor',
              'Laboratory Attendant', 'Care Taker', 'Accountant', 'Publication Assistant', 'Hindi Translator',
              'PRT', 'Nursery Teacher', 'TGT', 'Special Educator', 'PGT']


def exam_rank(src):
    for i, e in enumerate(EXAM_ORDER):
        if any(x.startswith(e) for x in src):
            return i
    return 99


def exam_family(label):
    """'Junior Clerk 11 Nov 2021 S1' -> 'Junior Clerk'; unknown posts -> text before the date."""
    for e in EXAM_ORDER:
        if label.startswith(e):
            return e
    return re.split(r' \d{1,2} [A-Z][a-z]{2} 20\d\d', label)[0]


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
print(dict(counts), 'written', total, '| not yet reviewed (left out):', pending)
src_count = collections.Counter(exam_family(x) for qs in bank.values() for q in qs for x in q['src'])
print('by exam:', dict(src_count.most_common()))
print('papers:', len({x for qs in bank.values() for q in qs for x in q['src']}))
