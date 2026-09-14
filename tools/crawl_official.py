"""List every question paper DSSSB itself publishes on its "Question Bank Online
Exam" pages (dsssb.delhi.gov.in). Writes web/official-list.json."""
import re, json, html, time, urllib.request, os

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, '..', 'web')
BASE = 'https://dsssb.delhi.gov.in'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'}


def get(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
        except Exception as e:
            err = e
            time.sleep(3)
    raise SystemExit(f'could not fetch {url}: {err}')


start = get(BASE + '/doit/tab-content/question-bank')
tabs = sorted(set(re.findall(r'href="(/doit/tab-content/question-bank[^"?#]*)"', start)))
print('tabs:', tabs)

out = []
for tab in tabs:
    page = 0
    while True:
        s = get(f'{BASE}{tab}?page={page}')
        rows = re.findall(r'<tr.*?</tr>', s, re.S)
        got = 0
        for r in rows:
            links = re.findall(r'href="([^"]+\.pdf)"', r, re.I)
            if not links:
                continue
            cells = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
                     for c in re.findall(r'<td.*?</td>', r, re.S)]
            title = max(cells, key=len) if cells else ''
            url = links[0] if links[0].startswith('http') else BASE + links[0]
            out.append({'tab': tab.rsplit('/', 1)[-1], 'title': title, 'url': url})
            got += 1
        print(f'{tab} page {page}: {got} papers')
        if got == 0 or f'?page={page + 1}' not in s:
            break
        page += 1

seen, uniq = set(), []
for o in out:
    if o['url'] not in seen:
        seen.add(o['url'])
        uniq.append(o)
json.dump(uniq, open(os.path.join(WEB, 'official-list.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('total unique papers', len(uniq))
