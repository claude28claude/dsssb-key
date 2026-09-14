# The DSSSB Key

Static General Awareness questions from DSSSB computer-based tests held since
2021, sorted by subject, with the answer and a short explanation revealed when
you tap an option. Current affairs removed. Plain HTML/CSS/JS, no build step
to serve, works offline as an installable app.

## What is in it

996 questions from 60 official DSSSB papers:

| Exam | Papers | Questions kept |
|---|---|---|
| ASO (Grade II), Aug 2025 | 12 shifts | 334 |
| Patwari, Aug–Sep 2022 | 5 shifts | 61 |
| Junior Assistant, Aug 2021 | 7 shifts | 216 |
| Stenographer, Apr 2021 | 2 shifts | 57 |
| PRT 2026, TGT 2023–25, PGT 2025 (General Awareness section) | 34 | 329 |

Subjects: Static GK, History, Polity, Geography, Economy, Physics, Chemistry,
Biology, Environment.

## How the answers were obtained

Each official paper marks the correct option with a tick image.
`tools/extract2.py` reads that tick from the PDF by the image's fingerprint and
refuses to output anything for a paper whose ticks and questions do not line up
four-to-one. The Patwari 2022 papers are scans, so their questions were read by
eye (`tools/ga/manual-*.json`). Answers are never typed by hand: `build.py`
always takes the answer index from `ga-readable.json`.

Where DSSSB's key differs from standard textbooks, the question carries an
"About this key" note.

## Rebuilding the data files

```
python tools/build.py .
```

`tools/ga/dec-*.json` holds one decision per question: dropped (`"CA"` current
affairs, `"X"` unreadable or unreliable), or subject, topic, explanation,
memory hook, optional key note, and optional cleaned stem/options (used for
questions asked in Hindi or garbled in the PDF). The build stops if any
question lacks a decision.

The source PDFs are not in this repository.

## Run locally

```
npx http-server . -p 8140 -c-1
```
