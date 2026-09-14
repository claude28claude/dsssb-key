"""Download a list of PDF URLs (one per line) into a folder, keeping a
URL -> file map. Skips files already present; rejects anything that is not a PDF."""
import sys, os, json, time, urllib.request, urllib.parse

src, dest = sys.argv[1], sys.argv[2]
os.makedirs(dest, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'}
mpath = os.path.join(dest, '_map.json')
m = json.load(open(mpath, encoding='utf-8')) if os.path.exists(mpath) else {}

urls = [u.strip() for u in open(src, encoding='utf-8') if u.strip().startswith('http')]
ok = bad = 0
for u in urls:
    parts = urllib.parse.urlparse(u).path.split('/')
    folder = parts[-2]
    name = (folder + '-' if folder.isdigit() else '') + urllib.parse.unquote(parts[-1])
    out = os.path.join(dest, name)
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        m[u] = name
        ok += 1
        continue
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
            break
        except Exception as e:
            data, err = None, e
            time.sleep(3)
    if not data or not data.startswith(b'%PDF'):
        print('FAIL', u, err if not data else 'not a PDF')
        bad += 1
        continue
    open(out, 'wb').write(data)
    m[u] = name
    ok += 1
json.dump(m, open(mpath, 'w', encoding='utf-8'), indent=1)
print(f'ok {ok} failed {bad}')
