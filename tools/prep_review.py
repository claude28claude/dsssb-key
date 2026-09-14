"""Turn ga/ga-new.json into review batches.

For every new question it adds
  * a SUGGESTED subject/topic (keyword rules; the reviewer confirms or changes it)
  * a 'likely current affairs' flag (recent years, 'recently', appointments, ...)
  * a priority: questions from clerical / ASO-level papers first, then teaching
    papers, then technical and senior posts
and writes ga/review/batch-NNN.txt, 120 questions each, in priority order.
Nothing here decides anything: decisions are still written by hand in dec-*.json."""
import json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
GA = os.path.join(HERE, '..', 'ga')
OUT = os.path.join(GA, 'review')
os.makedirs(OUT, exist_ok=True)

import glob
rows = json.load(open(os.path.join(GA, 'ga-new.json'), encoding='utf-8'))
decided = set()
for path in glob.glob(os.path.join(GA, 'dec-*.json')):
    decided.update(json.load(open(path, encoding='utf-8')).keys())
rows = [r for r in rows if r['id'] not in decided]   # only questions still to review

CLERICAL = r'^(ASO|Patwari|Junior Assistant|Stenographer|Head Clerk|Junior Secretariat Assistant|Junior Clerk|' \
           r'Assistant Superintendent|MTS|Store Keeper|Fire Operator|Ahlmad|Fee Collector|Personal Assistant|' \
           r'Jr\. Telephone Operator|Office Superintendent|Security Supervisor|Laboratory Attendant|Care Taker|Driver)'
TEACHING = r'^(PRT|TGT|PGT|Nursery Teacher|Special Educator|Physical Education Teacher|Librarian|Drawing Teacher)'


def priority(src):
    if any(re.match(CLERICAL, s, re.I) for s in src):
        return 0
    if any(re.match(TEACHING, s, re.I) for s in src):
        return 1
    return 2


CA = re.compile(r'\b(20(19|2[0-9]))\b|recently|newly|appointed|launched in|was named|has been named|won the .{0,30}20|'
                r'summit|theme of|report 20|index 20|ranked|visited|inaugurated|signed .{0,20}agreement|'
                r'championship|olympics? 20|world cup 20|budget 20', re.I)

RULES = [  # (subject, topic, pattern) — first match wins
    ('pol', 'rights', r'fundamental (right|dut)|directive principle|dpsp|article (1[2-9]|2\d|3[0-5]|3[6-9]|4\d|5[01])\b|citizenship'),
    ('pol', 'judiciary', r'supreme court|high court|chief justice|judge|writ|judicial'),
    ('pol', 'union', r'president|vice.president|prime minister|parliament|lok sabha|rajya sabha|money bill|speaker|attorney general'),
    ('pol', 'states', r'governor|chief minister|legislative (assembly|council)|panchayat|municipal|union territor|article 24[3]'),
    ('pol', 'federal', r'emergency|article 35[2-9]|finance commission|inter-state|centre.state|schedule 7|seventh schedule'),
    ('pol', 'bodies', r'election commission|cag|comptroller|upsc|commission for|act,? (19|20)\d\d|amendment'),
    ('pol', 'constitution', r'constitution|preamble|constituent assembly|schedule'),
    ('hist', 'ancient', r'harappa|indus valley|vedic|maurya|ashoka|gupta|buddha|mahavira|jain|chola|pallava|chalukya|kushan|satavahana|sangam'),
    ('hist', 'medieval', r'sultanate|khilji|tughlaq|lodi|mughal|akbar|babur|humayun|aurangzeb|shivaji|maratha|vijayanagar|bahmani|sufi|bhakti'),
    ('hist', 'freedom', r'congress|gandhi|satyagraha|non.cooperation|quit india|swadeshi|partition of bengal|subhas|bhagat singh|1919|1920s|1930|1942|1947|jallianwala|muslim league'),
    ('hist', 'modern', r'east india company|governor.general|viceroy|1857|plassey|buxar|british|brahmo|arya samaj|reform movement|lord '),
    ('geo', 'earth', r'planet|solar system|earth\'?s (crust|core|mantle|rotation|revolution)|latitude|longitude|eclipse|galaxy'),
    ('geo', 'physical', r'volcan|earthquake|rock|ocean current|pressure belt|wind|cyclone|glacier|plateau|desert'),
    ('geo', 'people', r'census|literacy|sex ratio|population|density'),
    ('geo', 'resources', r'soil|crop|mineral|coal|iron ore|bauxite|industry|port|railway|irrigation|dam|multipurpose'),
    ('geo', 'world', r'country|continent|capital of|strait|world\'?s (largest|longest|highest)'),
    ('geo', 'india', r'river|lake|pass|hill|mountain|monsoon|himalaya|ghats|state of india|located in'),
    ('eco', 'money', r'rbi|reserve bank|repo|crr|slr|bank|inflation|monetary|currency|nabard|sebi'),
    ('eco', 'planning', r'five.year plan|niti aayog|planning commission|budget|fiscal|tax|gst|1991|liberali'),
    ('eco', 'schemes', r'yojana|scheme|mission|abhiyan|programme'),
    ('eco', 'basics', r'gdp|gnp|national income|economy|sector|demand|supply|unemployment|poverty'),
    ('static', 'dance', r'dance|natyam|kathak|kuchipudi|odissi|manipuri|bihu|garba'),
    ('static', 'music', r'music|raga|gharana|instrument|sitar|tabla|veena|singer|vocalist'),
    ('static', 'festivals', r'festival|fair|mela|celebrated'),
    ('static', 'art', r'temple|fort|monument|painting|architecture|stupa|cave|mosque|tomb|palace'),
    ('static', 'books', r'author|written by|book|novel|autobiography'),
    ('static', 'sports', r'cup|trophy|olympic|cricket|football|hockey|tennis|badminton|chess|athlet|player|stadium'),
    ('bio', 'health', r'vitamin|disease|deficiency|virus|bacteria|vaccine|nutrient|protein'),
    ('bio', 'human', r'blood|heart|kidney|liver|brain|hormone|gland|bone|human body|digest'),
    ('bio', 'plants', r'plant|photosynthesis|leaf|root|xylem|phloem|flower|seed'),
    ('bio', 'cell', r'cell|dna|rna|chromosome|gene|mitochondri'),
    ('bio', 'living', r'kingdom|phylum|species|animal|mammal|bird|insect|fish'),
    ('chem', 'reactions', r'acid|base|ph\b|oxidation|reduction|reaction|salt'),
    ('chem', 'everyday', r'soap|detergent|cement|glass|plastic|fertili[sz]er|baking|bleaching'),
    ('chem', 'matter', r'element|atom|molecule|isotope|periodic|metal|gas|compound|mixture'),
    ('phy', 'light', r'light|lens|mirror|refraction|reflection|colour|spectrum'),
    ('phy', 'electricity', r'electric|current|magnet|resistance|voltage|ohm|charge'),
    ('phy', 'heat', r'heat|temperature|sound|thermo|boil|melt'),
    ('phy', 'mechanics', r'force|motion|velocity|acceleration|gravity|unit of|newton|pressure|work|energy|power'),
    ('env', 'biodiversity', r'national park|sanctuary|biosphere|tiger reserve|wetland|ramsar|biodiversity|endangered'),
    ('env', 'pollution', r'pollution|pollutant|ozone|smog|acid rain'),
    ('env', 'climate', r'climate|global warming|greenhouse|paris agreement|kyoto|cop\d'),
    ('env', 'ecology', r'ecosystem|food chain|ecolog|sustainable'),
]


def suggest(stem):
    low = stem.lower()
    for s, t, pat in RULES:
        if re.search(pat, low):
            return f'{s}/{t}'
    return '?'


for r in rows:
    r['prio'] = priority(r['src'])
    r['hint'] = suggest(r['stem'] + ' ' + ' '.join(r['o']))
    r['ca'] = bool(CA.search(r['stem'] + ' ' + ' '.join(r['o'])))
rows.sort(key=lambda r: (r['prio'], int(r['id'][1:])))

for f in os.listdir(OUT):
    if f.startswith('batch-'):
        os.remove(os.path.join(OUT, f))
SIZE = 120
for b in range(0, len(rows), SIZE):
    with open(os.path.join(OUT, f'batch-{b // SIZE + 1:03d}.txt'), 'w', encoding='utf-8') as f:
        for r in rows[b:b + SIZE]:
            src = '; '.join(r['src'][:2]) + (f' +{len(r["src"]) - 2}' if len(r['src']) > 2 else '')
            flag = ' [CA?]' if r['ca'] else ''
            opts = ' | '.join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(r['o']))
            f.write(f"{r['id']} {{{r['hint']}}}{flag} [{src}] {r['stem']}\n   {opts}  => {'ABCD'[r['a']]}\n")
json.dump([{k: r[k] for k in ('id', 'prio', 'hint', 'ca')} for r in rows],
          open(os.path.join(OUT, 'order.json'), 'w', encoding='utf-8'), indent=0)
print('questions', len(rows), '| batches', (len(rows) + SIZE - 1) // SIZE,
      '| by priority', dict(collections.Counter(r['prio'] for r in rows)),
      '| flagged likely current affairs', sum(r['ca'] for r in rows),
      '| no subject suggestion', sum(1 for r in rows if r['hint'] == '?'))
