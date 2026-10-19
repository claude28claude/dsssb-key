# The DSSSB Key

Static General Awareness questions from DSSSB computer-based tests held since
2021, sorted by subject, with the answer and a short explanation revealed when
you tap an option. Current affairs removed. Plain HTML/CSS/JS, no build step
to serve, works offline as an installable app.

The bare address opens a **front door** that asks which site to open: the Key
itself, or **DUSIB Patwari Prep** in `patwari/` (the subject paper for Post
Code 14/26: every Delhi Act in the syllabus with section tables, computer
revision, Delhi GK, Delhi governance and schemes, 1,333 MCQs, a timed 100-question mock and a Revise list). The Patwari
site is a separate page with its own service worker and its own saved list;
the Key's worker leaves `/patwari/` alone. `#/start` or the **⇄ Sites** tab
brings the front door back.

## Where the papers come from

- DSSSB's own "Question Bank Online Exam" pages on dsssb.delhi.gov.in
  (2021: 243 papers; 2022–23: 76 papers).
- Official DSSSB papers re-hosted by Adda247 and GovJobTracker (ASO 2025,
  Patwari 2022, MTS 2026, Assistant Superintendent 2024, PRT/TGT/PGT, JE, and others).

Round 1 (996 questions) used 60 papers. Round 2 reads about 500 more and is
being reviewed in stages: a new question appears on the site only after it has
been checked and given an explanation. The build prints how many are still
waiting.

## How the answers are read

Each official paper marks the correct option with a green tick picture.

- `tools/extract4.py` follows the order in which each page is drawn: the tick
  or cross picture sits next to its option label. Pictures are told apart by
  colour, not by size or count. Every question is tied to its printed Question ID
  (checked against the text), so an answer cannot slip onto a neighbouring
  question. Where a paper prints each question twice (English and Hindi), both
  copies must agree.
- `tools/extract2.py` is the round-1 reader (counts pictures four per question).
- `tools/blocktext.py` and `tools/unreadable_fix.py` recovered round-1 questions
  that pdftotext could not read (mostly Hindi-medium PRT papers); a recovered
  answer is kept only if it equals the round-1 tick.
- `tools/batch.py` runs the reader over every paper; `tools/gadump2.py` picks
  out General Awareness, removes reasoning/maths/language items by their wording,
  merges repeats, and hands out permanent question ids (`tools/ga/id-registry.json`)
  so saved progress stays attached to the same question.
- Answers are never typed by hand: `build.py` always takes the answer index
  from `ga-readable.json`.

Where DSSSB's key differs from standard textbooks the question carries an
"About this key" note; where the key is plainly wrong the question is left out.

## Rebuilding the data files

```
python tools/build.py .
```

`tools/ga/dec-*.json` holds one decision per question: dropped (`"CA"` current
affairs, `"X"` unreadable, wrong key, duplicate or not GK), or subject, topic,
explanation, memory hook, optional key note, and optional English stem/options
(used for questions asked in Hindi or garbled in the PDF). Round-1 questions
must all have a decision; round-2 questions without one are left out.

The source PDFs are not in this repository.

## Run locally

```
npx http-server . -p 8140 -c-1
```
