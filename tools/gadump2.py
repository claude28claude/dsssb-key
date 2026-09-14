"""Merge General Awareness questions from the newly read papers into the
existing question list WITHOUT changing any existing question id (so progress
saved in users' browsers stays attached to the same questions).

Inputs
  ga/ga-unique.json, ga/ga-readable.json   existing lists (ids q0001..q1624)
  papers2/json/*.json                      output of batch.py
  papers2/labels.json                      post name / dates per paper

Outputs
  ga/ga-readable.json      existing rows (sources extended) + new readable rows
  ga/ga-new-review.txt     compact list of the NEW rows, for review
  ga/ga-new.json           the new rows only
  papers2/gadump2-report.txt  per paper: GA found, kept, duplicates, problems
"""
import json, glob, os, re, collections, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GA = os.path.join(HERE, '..', 'ga')
P2 = os.path.join(HERE, '..', 'papers2')
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()


def norm(s):
    return re.sub(r'[^a-z0-9ऀ-ॿ]', '', (s or '').lower())


def key_of(stem, opts, a):
    return norm(stem)[:120] + '|' + (norm(opts[a]) if opts and a is not None else '?')


FAMILIES = [  # (label, pattern on subject / paper name / file name)
    ('ASO', r'assistant section officer|\baso\b'),
    ('Patwari', r'patwari'),
    ('Junior Assistant', r'junior assistant'),
    ('Stenographer', r'steno'),
    ('Head Clerk', r'head clerk'),
    ('Junior Secretariat Assistant', r'junior secretariat|\bjsa\b|\bldc\b|lower division'),
    ('Junior Clerk', r'junior clerk'),
    ('Assistant Superintendent', r'assistant superintendent'),
    ('MTS', r'\bmts\b|multi.?tasking'),
    ('PRT', r'assistant teacher.{0,3}primary|\bprt\b(?!.*special)'),
    ('Nursery Teacher', r'nursery'),
    ('Special Educator', r'special educat'),
    ('TGT', r'\btgt\b|drawing teacher|domestic science teacher'),
    ('PGT', r'\bpgt\b|evgc'),
]


def family(text):
    low = text.lower()
    for name, pat in FAMILIES:
        if re.search(pat, low):
            return name
    return None


def parse_date(lab, fname):
    # 1. the exam date printed on the answer sheet
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', lab.get('testdate') or '')
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    # 2. DSSSB's own file names carry the exam day ("17thOct21_S3"); the sheet's
    #    "Creation Date" is sometimes the following day, so the file name wins
    m = re.match(r'(\d{1,2})(?:st|nd|rd|th)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)i?(\d{2})[_i]',
                 fname.lower())
    if m:
        return 2000 + int(m.group(3)), MONTHS.index(m.group(2).title()) + 1, int(m.group(1))
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', lab.get('created') or '')
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    low = fname.lower()
    m = re.search(r'(\d{1,2})[-_ ](\d{2})[-_ ](20\d\d)', low)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    m = re.search(r'(\d{1,2})(?:st|nd|rd|th)?[-_ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ]?(?:20)?(\d{2})\b', low)
    if m:
        return 2000 + int(m.group(3)), MONTHS.index(m.group(2).title()) + 1, int(m.group(1))
    m = re.search(r'(\d{1,2})(?:st|nd|rd|th)?[-_ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*', low)
    y = re.search(r'(20[2]\d)', low)
    if m and y:
        return int(y.group(1)), MONTHS.index(m.group(2).title()) + 1, int(m.group(1))
    return None


def shift_of(fname):
    m = re.search(r'(?:shift|_i?s|-s)[-_ ]?([1-3])(?![0-9])', fname.lower())
    return f' S{m.group(1)}' if m else ''


# Patterns are written to match the SHAPE of a puzzle, not single words that
# also occur in GK ("Father of the Constitution", "What does ISRO stand for",
# "INSAT series", "a prominent figure").
REASONING = re.compile(
    r"(?:number|letter|alphabet(?:ical)?|given|following|word|figure)[- ](?:series|cluster)|series (?:is given|given below|with one term)|"
    r"code language|coded as|is written as|odd (?:one|word|figure|number|letter|pair)|"
    r"related (?:words|word|pair|number|numbers|letters|letter)|::|statements?.{0,120}conclusions?|assumptions? (?:is|are) implicit|"
    r"question figure|answer figure|given figure|following figure|figure (?:given|below|shown)|venn|mirror image|water image|"
    r"\bdice\b|paper is folded|punched|embedded|hidden in the|"
    r"sitting (?:in a row|around|in a circle)|seated (?:in a row|around)|facing (?:the )?(?:north|south|east|west|centre|center)|"
    r"live on .{0,20}floors|floors? (?:of a|of the same) building|"
    r"\b[A-Z]\b (?:is|was) (?:the )?(?:brother|sister|father|mother|son|daughter|husband|wife|uncle|aunt|grandfather|grandmother|nephew|niece)\b|"
    r"[‘'\"][^‘'\"]{1,3}[’'\"] (?:means|stands? for)|if [‘'\"]?[+×÷−-][’'\"]? means|mathematical (?:signs|operators)|interchanged? .{0,30}(?:signs|numbers)|"
    r"walks? \d+ ?(?:km|m)\b|turns? (?:to (?:the|his|her) )?(?:left|right)|in (?:a|the) dictionary|meaningful (?:sequence|order)|"
    r"how many .{0,40}(?:neither|but not)|how many .{0,30}\b(?:are|is) .{0,25}\bboth\b|"
    r"dictionary order|not necessarily in the same order|(?:height|weight|marks|ages?|salar(?:y|ies)) of \d+ .{0,40}(?:is|are) compared|"
    r"select the (?:option|correct alternative|related|number|word|pair|odd|figure|combination)|"
    r"missing (?:number|term|letter|figure)|(?:english )?alphabetical order", re.I)
MATHS = re.compile(
    r"\d\s*[+×x÷*/=^]\s*\d|simple interest|compound interest|\bprofit\b|\bloss\b|marked price|discount|"
    r"speed of (?:a|the) (?:boat|train|car|man)|km/h|km/hr|upstream|downstream|cistern|pipes? [A-Z]\b|"
    r"radius|\barea of (?:a|the) (?:circle|triangle|square|rectangle)|volume of (?:a|the) (?:cone|cube|sphere|cylinder)|"
    r"value of [a-z]\b|simplify|\blcm\b|\bhcf\b|divisible by|\bsum of\b.{0,30}\d|average of .{0,30}\d|"
    r"complete (?:a|the) (?:piece of )?work|in how many days|ratio of .{0,40}\d", re.I)
LANGUAGE = re.compile(
    r"synonym|antonym|\bidiom|one word substitut|spelling|misspelt|"
    r"fill in the blanks? with (?:the )?(?:most )?(?:appropriate|suitable|correct) (?:word|article|preposition|verb|option)(?!.{0,120}(?:dance|theatre|music|state|river|temple))|"
    r"from the (?:above|given) passage|parts? of (?:the )?sentence|select the sentence|grammatic|active voice|passive voice|narration|"
    r"correct preposition|no improvement|no error|highlighted words?|underlined (?:word|segment)", re.I)
GK_MARKERS = re.compile(
    r"census|literacy|poverty|constitution|\barticle \d|amendment|parliament|president|governor|chairman|"
    r"budget|scheme|yojana|rbi|reserve bank|gdp|inflation|acid|vinegar|element|compound|dance|theatre|"
    r"festival|temple|dynasty|emperor|river|national park|vitamin|disease|"
    r"written by|\bauthor|novel|economic profit|normal profit|periodic table|atomic radius|punched card|"
    r"father of (?:the )?(?:indian|modern|green|white|nation|constitution|economics|geography|history|medicine|surgery|computer|genetics|taxonomy|punched)", re.I)


def not_gk(stem, opts):
    """Reason string when a question is clearly reasoning, maths or English
    language (2021 papers mix these into the GK sections), else ''."""
    s = stem or ''
    if GK_MARKERS.search(s) and not re.search(r'(?:number|letter) series|code language|question figure', s, re.I):
        return ''
    if REASONING.search(s):
        return 'reasoning'
    if LANGUAGE.search(s):
        return 'language'
    if MATHS.search(s):
        return 'maths'
    return ''


def tidy_post(p):
    p = re.sub(r'\s+', ' ', p).strip()
    if p.isupper():
        p = p.title()
    return p.replace('Techer', 'Teacher').replace('Tire-I', 'Tier-I').replace('Tire ll', 'Tier-II')


labels = json.load(open(os.path.join(P2, 'labels.json'), encoding='utf-8'))
old_unique = json.load(open(os.path.join(GA, 'ga-unique.json'), encoding='utf-8'))
# Always merge onto the round-1 list, so running this script twice cannot add
# the same questions twice or hand out different ids.
BACKUP = os.path.join(GA, 'ga-readable.before-round2.json')
if not os.path.exists(BACKUP):
    shutil.copy(os.path.join(GA, 'ga-readable.json'), BACKUP)
old_readable = json.load(open(BACKUP, encoding='utf-8'))
readable_ids = {r['id'] for r in old_readable}
by_key = {}
for r in old_unique:
    by_key.setdefault(key_of(r['stem'], r['o'], r['a']), r['id'])
next_num = max(int(r['id'][1:]) for r in old_unique) + 1
# Permanent id register for NEW questions: a question keeps the id it was first
# given, even if later filter changes let other questions in earlier. Decisions
# in dec-*.json are keyed by id, so ids must never shift between runs.
REGISTRY = os.path.join(GA, 'id-registry.json')
registry = json.load(open(REGISTRY, encoding='utf-8')) if os.path.exists(REGISTRY) else {}
if registry:
    next_num = max(next_num, max(int(v[1:]) for v in registry.values()) + 1)


def new_id(k):
    global next_num
    if k not in registry:
        registry[k] = f'q{next_num:04d}'
        next_num += 1
    return registry[k]

report, seen_papers, dropped = [], {}, []
new_rows, new_by_key = [], {}
add_src = collections.defaultdict(set)
for path in sorted(glob.glob(os.path.join(P2, 'json', '*.json'))):
    d = json.load(open(path, encoding='utf-8'))
    qs, fname = d['questions'], d['file']
    lab = labels.get(fname, {})
    subject = re.sub(r'\s+', ' ', lab.get('subject') or '').strip()
    if re.match(r'(Section\s*:|\d{1,2}:\d{2})', subject):
        subject = ''          # an Adda247 print: this line is a section heading or a time, not the post
    ident = re.sub(r'[-_]+', ' ', ' '.join([subject, lab.get('paper', ''), os.path.basename(fname)]))
    fam = family(ident)
    date = parse_date(lab, os.path.basename(fname))
    if not date or date[0] < 2021:
        report.append(f'EXCLUDED (date {date}) {fname} | {subject}')
        continue
    post = tidy_post(re.sub(r'\s*Section [AB]$', '', subject) or re.sub(r'[-_]+', ' ', os.path.basename(fname))[:40])
    name = fam or post
    label = f'{name} {date[2]} {MONTHS[date[1] - 1]} {date[0]}{shift_of(os.path.basename(fname))}'
    fp = '|'.join(q.get('qid') or norm(q['stem'])[:30] for q in qs[:12])
    if fp in seen_papers:
        report.append(f'DUPLICATE of {seen_papers[fp]}: {fname}')
        continue
    seen_papers[fp] = fname
    # 2021 section labels are unreliable (a "General Ability" section mixing
    # reasoning and GK is left unlabelled, and labels carry over into the next
    # section), so take GA-labelled AND unlabelled English questions and drop
    # obvious reasoning / maths / English-language items by their wording.
    ga = [q for q in qs if q.get('sec') in ('GA', None)]
    # English copy only. The Hindi copy of a 2021 question can still contain
    # Latin code words (SOVIET, FARM) and pass the batch's language guess, so
    # also require (almost) no Devanagari in the question text.
    ga_en = [q for q in ga if q.get('lang') == 'en'
             and len(re.findall(r'[ऀ-ॿ]', q.get('stem') or '')) < 5]
    kept = dup_old = dup_new = unans = unread = notgk = 0
    for q in ga_en:
        why = not_gk(q['stem'], q['o'])
        if why:
            notgk += 1
            dropped.append(f'{why:10} | {q["stem"][:150]} || {" | ".join((o or "")[:30] for o in (q["o"] or []))}')
            continue
        if q['a'] is None:
            unans += 1
            continue
        if len(norm(q['stem'])) < 8 or not q['o'] or len(q['o']) != 4 or any(not o for o in q['o']):
            unread += 1
            continue
        k = key_of(q['stem'], q['o'], q['a'])
        if k in by_key:
            oid = by_key[k]
            if oid in readable_ids:
                add_src[oid].add(label)
            dup_old += 1
        elif k in new_by_key:
            new_by_key[k]['src'].add(label)
            dup_new += 1
        else:
            row = {'id': new_id(k), 'src': {label}, 'stem': q['stem'], 'o': q['o'], 'a': q['a'],
                   'pid': fname, 'n': q.get('n'), 'how': q.get('how')}
            new_by_key[k] = row
            new_rows.append(row)
            kept += 1
    flag = '' if len(ga_en) in (20, 25, 30, 40, 50) else '  <-- unusual GA count'
    report.append(f'{label:45} GA {len(ga)} en {len(ga_en)} new {kept} seen-before {dup_old + dup_new} '
                  f'unanswered {unans} unreadable {unread} [{d["fmt"]}] {fname}{flag}')

for r in new_rows:
    r['src'] = sorted(r['src'])
merged = []
for r in old_readable:
    r = dict(r)
    if r['id'] in add_src:
        r['src'] = sorted(set(r['src']) | add_src[r['id']])
    merged.append(r)
# Round-1 questions that were unreadable and have now been recovered from the
# page drawing (unreadable_fix.py): same ids as before, answer = round-1 tick.
recovered_path = os.path.join(GA, 'recovered.json')
have = {r['id'] for r in merged}
recovered = json.load(open(recovered_path, encoding='utf-8')) if os.path.exists(recovered_path) else []
for r in recovered:
    if r['id'] not in have:
        merged.append({'id': r['id'], 'src': r['src'], 'stem': r['stem'], 'o': r['o'], 'a': r['a'],
                       'ans': 'ABCD'[r['a']], 'pid': r['pid'], 'n': r['n'], 'recovered': True})
        have.add(r['id'])
merged += [{'id': r['id'], 'src': r['src'], 'stem': r['stem'], 'o': r['o'], 'a': r['a'],
            'ans': 'ABCD'[r['a']], 'pid': r['pid'], 'n': r['n']} for r in new_rows]
print('recovered round-1 questions added:', sum(1 for r in merged if r.get('recovered')))

if not os.path.exists(os.path.join(GA, 'ga-readable.before-round2.json')):
    shutil.copy(os.path.join(GA, 'ga-readable.json'), os.path.join(GA, 'ga-readable.before-round2.json'))
json.dump(merged, open(os.path.join(GA, 'ga-readable.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(new_rows, open(os.path.join(GA, 'ga-new.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(registry, open(REGISTRY, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open(os.path.join(GA, 'ga-new-review.txt'), 'w', encoding='utf-8') as f:
    for r in new_rows:
        opts = ' | '.join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(r['o']))
        f.write(f"{r['id']} [{'; '.join(r['src'][:3])}{' +' + str(len(r['src']) - 3) if len(r['src']) > 3 else ''}] "
                f"{r['stem']}\n    {opts}\n    => {'ABCD'[r['a']]}\n")
open(os.path.join(P2, 'gadump2-report.txt'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
# every question the wording filter threw out, so its mistakes can be checked by eye
open(os.path.join(P2, 'gadump2-dropped.txt'), 'w', encoding='utf-8').write('\n'.join(dropped) + '\n')
print('dropped as reasoning/maths/language:', len(dropped),
      dict(collections.Counter(line.split('|')[0].strip() for line in dropped)))
print('papers used', len(seen_papers), '| new unique readable GA questions', len(new_rows),
      '| existing questions that gained sources', len(add_src),
      '| readable total now', len(merged))
