"""Run the answer reader over every downloaded paper.

For each PDF writes papers2/json/<file>.json  = {"file", "fmt", "header", "questions"}
and appends one line per paper to papers2/batch.log.

Second opinion: extract2 (counting pictures four at a time) is also run. Its
answers are used ONLY to fill questions extract4 left unanswered, and only when
extract2 agrees with extract4 on every question both answered (at least 50)."""
import sys, os, json, glob, time, collections, traceback, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract2 as ex2
import extract4 as ex4

ROOT = os.path.join(HERE, '..', 'papers2')
OUT = os.path.join(ROOT, 'json')
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(ROOT, 'batch.log')

files = sorted(glob.glob(os.path.join(ROOT, 'official2021', '*.pdf'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'official', '*.pdf'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'raw', '*.pdf')))
if len(sys.argv) > 1:
    files = [f for f in files if any(s in f for s in sys.argv[1:])]


def log(line):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


for path in files:
    base = os.path.basename(path)
    folder = os.path.basename(os.path.dirname(path))
    dest = os.path.join(OUT, f'{folder}__{base[:-4]}.json')
    if os.path.exists(dest):
        continue
    t0 = time.time()
    try:
        fmt, qs, mis = ex4.run(path)
    except SystemExit as e:
        log(f'SKIP {folder}/{base}: {str(e)[:220]}')
        continue
    except Exception as e:
        log(f'ERROR {folder}/{base}: {type(e).__name__} {str(e)[:160]}')
        continue
    filled = 0
    note = ''
    if any(q['a'] is None for q in qs) and fmt in ('digialm', 'ion'):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                _, old = ex2.run(path)
            if len(old) == len(qs):
                both = [(q['a'], o['a']) for q, o in zip(qs, old) if q['a'] is not None and o['a'] is not None]
                dis = sum(1 for a, b in both if a != b)
                if dis == 0 and len(both) >= 50:
                    for q, o in zip(qs, old):
                        if q['a'] is None and o['a'] is not None:
                            q['a'], q['how'], q['ticks'] = o['a'], 'counted (second reader, confirmed)', [o['a']]
                            filled += 1
                note = f' second-reader overlap {len(both)} disagree {dis}'
        except SystemExit as e:
            note = ' second-reader refused'
        except Exception as e:
            note = f' second-reader error {type(e).__name__}'
    header = ex2.pdftext(path)[:2500]
    json.dump({'file': f'{folder}/{base}', 'fmt': fmt, 'header': header, 'questions': qs},
              open(dest, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    ans = sum(1 for q in qs if q['a'] is not None)
    log(f'OK {folder}/{base} [{fmt}] q {len(qs)} answered {ans} filled {filled}{note} '
        f'misaligned {mis} {time.time() - t0:.0f}s')
