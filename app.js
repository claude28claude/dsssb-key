/* ==========================================================================
   THE DSSSB KEY — app.js
   No framework, no build step at runtime. Each data-*.js file pushes one
   subject onto window.SUBJECTS; this file renders them.

   ROUTES (all in the hash, so the site works from any static folder):
     #/                     home: every subject and topic
     #/s/<subject>          one subject
     #/t/<subject>/<topic>  the questions of one topic   (?q=<id> jumps to one)
     #/p/<all|subject>      a practice set of 20 random questions
     #/mts/…                the same four routes for the separate MTS 2026
                            section (data-mts.js pushes window.MTS_SUBJECTS)
     #/as/…                 and for the separate Assistant Superintendent 2026
                            section (data-as.js pushes window.AS_SUBJECTS)

   ANSWERS are saved in localStorage as { questionId: chosenOptionIndex }.
   Nothing ever leaves the browser.
   ========================================================================== */
'use strict';

var SUBJECTS = window.SUBJECTS || [];
var MTS_SUBJECTS = window.MTS_SUBJECTS || [];
var AS_SUBJECTS = window.AS_SUBJECTS || [];
var PRAC_SUBJECTS = window.PRAC_SUBJECTS || [];
var bank = 'main';   // which section the current page belongs to: 'main', 'mts', 'as' or 'prac'
var main = document.getElementById('main');
var tabsEl = document.getElementById('tabs');
var qEl = document.getElementById('q');
var resEl = document.getElementById('results');
var brandsub = document.getElementById('brandsub');

var LETTERS = 'ABCD';
var SET_SIZE = 20;
var PAGE_SIZE = 25;   // questions per page of a topic, so a big topic is not one endless scroll

/* --------------------------------------------------------------------------
   HELPERS
   -------------------------------------------------------------------------- */
function esc(s){
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* Storage can be unavailable (private windows, blocked site data). The site
   still works; answers are simply not remembered in that case. */
function load(key, fallback){
  try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
  catch (e) { return fallback; }
}
function save(key, value){
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* not persisted */ }
}
function sload(key){
  try { var v = sessionStorage.getItem(key); return v ? JSON.parse(v) : null; } catch (e) { return null; }
}
function ssave(key, value){
  try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* not persisted */ }
}

var progress = load('dk-progress', {});
var filter = load('dk-filter', 'all');
var view = load('dk-view', 'all');
var shown = {};   // questions whose answer was revealed without answering (this visit only)
/* Questions the user marked to come back to. { questionId: time saved },
   so the newest sits at the top of the Saved tab. Kept in this browser only. */
var saved = load('dk-saved', {});
function isSaved(id){ return Object.prototype.hasOwnProperty.call(saved, id); }
function savedList(){
  return Object.keys(saved)
    .filter(function(id){ return BYID[id]; })        // a question dropped by a rebuild just goes
    .sort(function(a, b){ return saved[b] - saved[a]; })
    .map(function(id){ return BYID[id]; });
}
function savedCount(){ return savedList().length; }

/* Every question gets back-references to its subject and topic. */
var ALL = [], MTS_ALL = [], AS_ALL = [], PRAC_ALL = [], BYID = {};
function indexBank(subjects, into, name){
  subjects.forEach(function(s){
    s.topics.forEach(function(t){
      t.qs.forEach(function(q){ q.s = s; q.t = t; q.bank = name; into.push(q); BYID[q.id] = q; });
    });
  });
}
indexBank(SUBJECTS, ALL, 'main');
indexBank(MTS_SUBJECTS, MTS_ALL, 'mts');
indexBank(AS_SUBJECTS, AS_ALL, 'as');
indexBank(PRAC_SUBJECTS, PRAC_ALL, 'prac');

/* The separate exam sections, each kept apart from the main bank. */
var SECTIONS = {
  mts: { name: 'MTS 2026', subjects: MTS_SUBJECTS, all: MTS_ALL,
         heading: 'MTS 2026: General Awareness from every shift, by subject',
         exam: 'DSSSB’s MTS exam (24 Feb – 14 May 2026)',
         source: 'Answers come from the published answer key, which matched DSSSB’s own ticked papers on every question where both exist.' },
  as:  { name: 'AS 2026', subjects: AS_SUBJECTS, all: AS_ALL,
         heading: 'AS 2026: General Awareness from every shift, by subject',
         exam: 'DSSSB’s Assistant Superintendent exam (1 – 7 July 2026)',
         source: 'Answers come from a coaching institute’s compilation of the answer key, because DSSSB’s own ticked papers for these shifts are not available. Every answer was checked again; questions whose key looked wrong or unclear were left out.' },
  /* The one section that is NOT previous-year questions. Marked `written` so
     every page says so plainly and nobody mistakes these for a real paper. */
  prac:{ name: 'Extra Practice', subjects: PRAC_SUBJECTS, all: PRAC_ALL, written: true,
         heading: 'Extra practice: new questions in the DSSSB pattern',
         source: 'These questions were not asked by DSSSB. They were written fresh, in the same pattern and on the same syllabus, so that there is something left to practise on after a topic’s real questions have been used up. Each one carries a short explanation like the rest of the site, and none of them repeats a question from the other sections.' }
};
function subjectsNow(){ return bank === 'main' ? SUBJECTS : SECTIONS[bank].subjects; }
function allNow(){ return bank === 'main' ? ALL : SECTIONS[bank].all; }
/* A link inside the current section: link('/s/geo') is #/s/geo, #/mts/s/geo or #/as/s/geo. */
function link(path){ return (bank === 'main' ? '#' : '#/' + bank) + path; }
/* "MTS 2026 · " or "AS 2026 · " in front of a page name when inside a section. */
function sectionPrefix(){ return bank === 'main' ? '' : SECTIONS[bank].name + ' · '; }

var FILTERS = [
  ['all', 'All DSSSB papers'],
  ['aso', 'ASO 2025'],
  ['patwari', 'Patwari 2022'],
  ['clerical', 'Clerical exams'],
  ['other', 'Teaching & other posts']
];

/* Office and clerical posts: the papers closest in level to ASO and Patwari. */
var CLERICAL = /^(Junior Assistant|Junior Clerk|Junior Secretariat Assistant|Head Clerk|Stenographer|Personal Assistant|Assistant Superintendent|Office Superintendent|MTS|Store Keeper|Fire Operator|Ahlmad|Fee Collector|Jr\. Telephone Operator|Security Supervisor|Laboratory Attendant|Care Taker|Accountant|Publication Assistant|Hindi Translator)/;

function examsOf(q){
  var e = {};
  q.src.forEach(function(x){
    if (x.indexOf('ASO') === 0) e.aso = 1;
    else if (x.indexOf('Patwari') === 0) e.patwari = 1;
    else if (CLERICAL.test(x)) e.clerical = 1;
    else e.other = 1;
  });
  return e;
}
/* The exam filter belongs to the main bank; MTS and AS 2026 questions always pass. */
function passes(q){ return q.bank !== 'main' || filter === 'all' || !!examsOf(q)[filter]; }
function visible(list){ return list.filter(passes); }

function stat(list, everything){
  var n = 0, done = 0, right = 0;
  list.forEach(function(q){
    if (!everything && !passes(q)) return;
    n++;
    if (progress[q.id] !== undefined){ done++; if (progress[q.id] === q.a) right++; }
  });
  return { n: n, done: done, right: right };
}
function subjectQs(s){ var out = []; s.topics.forEach(function(t){ out = out.concat(t.qs); }); return out; }
function bar(st){
  var pct = st.n ? Math.round(st.done * 100 / st.n) : 0;
  return '<span class="bar" title="' + st.done + ' of ' + st.n + ' answered"><i style="width:' + pct + '%"></i></span>';
}
function subjectById(id){ var list = subjectsNow(); for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]; return null; }
function topicById(s, id){ if (!s) return null; for (var i = 0; i < s.topics.length; i++) if (s.topics[i].id === id) return s.topics[i]; return null; }

function filterChips(){
  if (bank !== 'main') return '';
  var h = ['<div class="chips" role="group" aria-label="Which exam papers"><span class="cl">Papers</span>'];
  FILTERS.forEach(function(f){
    h.push('<button type="button" class="chip" data-filter="' + f[0] + '" aria-pressed="' + (filter === f[0]) + '">' + esc(f[1]) + '</button>');
  });
  h.push('</div>');
  return h.join('');
}

function daysUntil(y, m, d){
  var now = new Date();
  var today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((Date.UTC(y, m - 1, d) - today) / 86400000);
}
function countdownText(start, end){
  var a = daysUntil(start[0], start[1], start[2]);
  var b = daysUntil(end[0], end[1], end[2]);
  if (a > 1) return a + ' days to go';
  if (a === 1) return 'Starts tomorrow';
  if (b >= 0) return 'Exam window is on now';
  return 'Exam window is over';
}

/* --------------------------------------------------------------------------
   A QUESTION CARD
   -------------------------------------------------------------------------- */
function shiftName(x){ return x.replace(/^(?:MTS|AS) (\d+ \w+) \d{4} S(\d)$/, '$1 · Shift $2'); }

function srcChips(q){
  if (q.bank === 'prac') return '<span class="src written">' + esc(q.src[0]) + '</span>';
  if (q.bank !== 'main'){
    var extra = q.src.length - 2;
    return q.src.slice(0, 2).map(function(x){ return '<span class="src home">' + esc(shiftName(x)) + '</span>'; }).join('') +
      (extra > 0 ? '<span class="src" title="Also asked: ' + esc(q.src.slice(2).map(shiftName).join(', ')) + '">+' +
                   extra + ' more shift' + (extra > 1 ? 's' : '') + '</span>' : '');
  }
  return q.src.map(function(x){
    var home = x.indexOf('ASO') === 0 || x.indexOf('Patwari') === 0;
    return '<span class="src' + (home ? ' home' : '') + '">' + esc(x) + '</span>';
  }).join('');
}

/* Where a question lives, whichever section it belongs to. */
function topicHref(q){
  return (q.bank === 'main' ? '#' : '#/' + q.bank) + '/t/' + q.s.id + '/' + q.t.id + '?q=' + q.id;
}

function cardHTML(q, num, withTopic){
  var chosen = progress[q.id];
  var answered = chosen !== undefined;
  var revealed = answered || shown[q.id];
  var h = [];
  h.push('<article class="card' + (answered ? ' done' : '') + '" id="q-' + q.id + '" data-id="' + q.id + '">');
  h.push('<div class="cmeta"><span class="qn">Q' + num + '</span>' + srcChips(q) +
         (withTopic ? '<a class="tlabel" href="' + topicHref(q) + '">' +
            (q.bank !== 'main' ? esc(SECTIONS[q.bank].name) + ' · ' : '') +
            esc(q.s.n) + ' · ' + esc(q.t.n) + '</a>' : '') + '</div>');
  h.push('<p class="qtext">' + esc(q.q) + '</p>');
  h.push('<div class="opts">');
  q.o.forEach(function(o, i){
    var cls = 'opt', mark = '';
    if (revealed && i === q.a){ cls += ' right'; mark = '✓'; }
    if (answered && i === chosen && chosen !== q.a){ cls += ' wrong'; mark = '✗'; }
    h.push('<button type="button" class="' + cls + '" data-i="' + i + '"' + (answered ? ' aria-disabled="true"' : '') + '>' +
           '<span class="L">' + LETTERS[i] + '</span><span class="T">' + esc(o) + '</span>' +
           (mark ? '<span class="M" aria-hidden="true">' + mark + '</span>' : '') + '</button>');
  });
  h.push('</div>');

  h.push('<div class="cfoot" aria-live="polite">');
  if (answered){
    h.push(chosen === q.a ? '<span class="verdict ok">Correct</span>'
                          : '<span class="verdict no">Not this one — the answer is (' + LETTERS[q.a] + ')</span>');
    h.push('<button type="button" class="linkbtn" data-act="retry">Try again</button>');
  } else if (shown[q.id]){
    h.push('<button type="button" class="linkbtn" data-act="hide">Hide answer</button>');
  } else {
    h.push('<button type="button" class="linkbtn" data-act="show">Show answer</button>');
  }
  h.push('<button type="button" class="linkbtn savebtn' + (isSaved(q.id) ? ' on' : '') + '" data-act="save"' +
         ' aria-pressed="' + isSaved(q.id) + '" title="' + (isSaved(q.id) ? 'Remove from Saved' : 'Keep this for revision') + '">' +
         (isSaved(q.id) ? '★ Saved' : '☆ Save') + '</button>');
  h.push('</div>');

  if (revealed){
    h.push('<div class="reveal">');
    h.push('<p class="ans"><span class="lbl">Answer</span><span class="v">(' + LETTERS[q.a] + ') ' + esc(q.o[q.a]) + '</span></p>');
    h.push('<p class="why">' + esc(q.x) + '</p>');
    if (q.e) h.push('<p class="ex"><span class="lbl">Remember</span>' + esc(q.e) + '</p>');
    if (q.k) h.push('<div class="keynote"><span class="lbl">About this key</span>' + esc(q.k) + '</div>');
    h.push('</div>');
  }
  h.push('</article>');
  return h.join('');
}

function refreshCard(id){
  var node = document.getElementById('q-' + id);
  if (!node) return;
  var num = node.querySelector('.qn').textContent.replace('Q', '');
  var withTopic = !!node.querySelector('.tlabel');
  var fresh = document.createElement('div');
  fresh.innerHTML = cardHTML(BYID[id], num, withTopic);
  node.parentNode.replaceChild(fresh.firstElementChild, node);
  var st = document.getElementById('tstats');
  if (st && st.dataset.scope) st.innerHTML = statsLine(scopeList(st.dataset.scope), st.dataset.scope === 'saved');
}

function statsLine(list, everything){
  var s = stat(list, everything);
  var pct = s.done ? Math.round(s.right * 100 / s.done) : 0;
  return '<b>' + s.n + '</b> questions · <b>' + s.done + '</b> answered · <span class="ok">' + s.right + ' correct</span>' +
         (s.done ? ' (' + pct + '%)' : '');
}

/* The stats line on a page is re-counted after every answer; the scope string
   says which list it counts. */
function scopeList(scope){
  var p = scope.split(':');
  if (p[0] === 'topic'){ var s = subjectById(p[1]); var t = topicById(s, p[2]); return t ? t.qs : []; }
  if (p[0] === 'set'){ return (sload(p[1]) || []).map(function(id){ return BYID[id]; }).filter(Boolean); }
  if (p[0] === 'saved'){ return savedList(); }
  return [];
}

/* --------------------------------------------------------------------------
   PAGES
   -------------------------------------------------------------------------- */
/* The front door: two sites live at this address. The Key (this app) and the
   DUSIB Patwari Prep site in /patwari/, which is a separate page with its own
   offline cache and its own saved list. */
function pageStart(){
  var keyQ = visible(ALL).length + MTS_ALL.length + AS_ALL.length;
  var h = [];
  h.push('<section class="gate">');
  h.push('<h1>Which do you want to open?</h1>');
  h.push('<p class="lede">Two study sites live here. Pick one; you can switch at any time from the tab bar.</p>');
  h.push('<div class="gategrid">');
  h.push('<a class="gatecard" href="#/">' +
         '<span class="gk">Previous-year GK</span>' +
         '<b>The DSSSB Key</b>' +
         '<span class="gd">Static GK that DSSSB has actually asked since 2021, with answers and explanations. ASO, Patwari 2022, MTS 2026, AS 2026 and more.</span>' +
         '<span class="gs">' + keyQ + ' questions</span>' +
         '<span class="btn">Open the DSSSB Key →</span></a>');
  h.push('<a class="gatecard pat" href="patwari/">' +
         '<span class="gk">Subject paper · Post Code 14/26</span>' +
         '<b>DUSIB Patwari Prep</b>' +
         '<span class="gd">Every Delhi Act in the syllabus with section tables and traps (DUSIB 2010 + 2026 amendment, DD Act, Land Revenue, Land Reforms, LA 1894, RFCTLARR 2013, PLR 1887, NCT Special Provisions, Delhi administration), a full Delhi GK section, Delhi governance &amp; civic institutions and govt schemes, computer revision, a 100-question timed mock and a Revise list.</span>' +
         '<span class="gs">919 MCQs</span>' +
         '<span class="btn">Open Patwari Prep →</span></a>');
  h.push('</div></section>');
  brandsub.textContent = 'Choose a site';
  document.title = 'The DSSSB Key — choose: previous-year GK or DUSIB Patwari Prep';
  return h.join('');
}

function pageHome(){
  var shownQs = visible(ALL);
  var totalQ = shownQs.length;
  var papers = {};
  shownQs.forEach(function(q){ q.src.forEach(function(x){ papers[x] = 1; }); });
  var all = stat(ALL);
  var h = [];

  h.push('<section class="hero">');
  h.push('<h1>Static GK that DSSSB has actually asked, with answers</h1>');
  h.push('<p>General Awareness questions from DSSSB papers held since 2021, with current affairs removed and the rest sorted by subject. ' +
         'Tap an option to check yourself; the answer comes from the tick in DSSSB’s own paper, with a short explanation and a way to remember it.</p>');
  h.push('<div class="countdown">' +
         '<div><span class="k">ASO Tier-I</span><span class="v">21 Sep – 18 Oct 2026</span><span class="s">' + countdownText([2026, 9, 21], [2026, 10, 18]) + '</span></div>' +
         '<div><span class="k">Patwari</span><span class="v">21 – 23 Oct 2026</span><span class="s">' + countdownText([2026, 10, 21], [2026, 10, 23]) + '</span></div>' +
         '</div>');
  h.push('<div class="stats"><span><b>' + totalQ + '</b> questions</span><span><b>' + Object.keys(papers).length + '</b> papers</span>' +
         '<span><b>' + SUBJECTS.length + '</b> subjects</span><span>You: <b>' + all.done + '</b> answered, <b>' + all.right + '</b> correct</span></div>');
  h.push('<div class="btnrow"><a class="btn" href="#/p/all">Practise ' + SET_SIZE + ' at random</a>' +
         (filter !== 'aso' ? '<button type="button" class="btn ghost" data-filter="aso">Only ASO 2025 questions</button>' : '') +
         (filter !== 'patwari' ? '<button type="button" class="btn ghost" data-filter="patwari">Only Patwari 2022 questions</button>' : '') +
         (AS_ALL.length ? '<a class="btn ghost" href="#/as">AS 2026 shifts</a>' : '') +
         (MTS_ALL.length ? '<a class="btn ghost" href="#/mts">MTS 2026 shifts</a>' : '') +
         (PRAC_ALL.length ? '<a class="btn ghost" href="#/prac">Extra practice questions</a>' : '') +
         (savedCount() ? '<a class="btn ghost" href="#/saved">★ Saved (' + savedCount() + ')</a>' : '') +
         '</div>');
  h.push('</section>');

  h.push(filterChips());
  if (filter !== 'all') h.push('<p class="lede">Showing ' + totalQ + ' questions from ' + esc(FILTERS.filter(function(f){ return f[0] === filter; })[0][1]) + '.</p>');

  h.push(subjectGrid());

  brandsub.textContent = 'Previous-year GK';
  document.title = 'The DSSSB Key — previous-year static GK, answered';
  return h.join('');
}

/* One card per subject of the current section, each listing its topics. */
function subjectGrid(){
  var h = ['<div class="grid">'];
  subjectsNow().forEach(function(s){
    var st = stat(subjectQs(s));
    if (!st.n) return;
    h.push('<section class="scard">');
    h.push('<h2><a href="' + link('/s/' + s.id) + '">' + esc(s.n) + '</a></h2>');
    h.push('<p class="w">' + esc(s.w) + '</p>');
    h.push('<div class="meta"><span>' + st.n + ' questions</span><span>' + st.done + ' answered</span></div>' + bar(st));
    h.push('<ul class="tlist">');
    s.topics.forEach(function(t){
      var ts = stat(t.qs);
      if (!ts.n) return;
      h.push('<li><a href="' + link('/t/' + s.id + '/' + t.id) + '"><span class="t">' + esc(t.n) + '</span>' + bar(ts) +
             '<span class="c">' + ts.done + '/' + ts.n + '</span></a></li>');
    });
    h.push('</ul></section>');
  });
  h.push('</div>');
  return h.join('');
}

/* A separate exam section (MTS 2026, AS 2026): every shift's General
   Awareness, kept apart from the main bank and sorted by the same subjects
   and topics. */
function pageSectionHome(){
  var sec = SECTIONS[bank], shifts = {};
  sec.all.forEach(function(q){ q.src.forEach(function(x){ shifts[x] = 1; }); });
  var all = stat(sec.all);
  var h = [];
  h.push('<section class="hero">');
  h.push('<h1>' + esc(sec.heading) + '</h1>');
  if (sec.written){
    h.push('<p class="warnline"><b>Not from a DSSSB paper.</b> Everything else on this site is a question DSSSB has really asked. ' +
           'This section is the exception, and it is kept separate for that reason.</p>');
    h.push('<p>' + esc(sec.source) + '</p>');
    h.push('<div class="stats"><span><b>' + sec.all.length + '</b> questions</span>' +
           '<span><b>' + sec.subjects.length + '</b> subjects</span><span>You: <b>' + all.done + '</b> answered, <b>' + all.right + '</b> correct</span></div>');
  } else {
  h.push('<p>The static GK questions from all ' + Object.keys(shifts).length + ' shifts of ' + esc(sec.exam) + ', ' +
         'kept separate from the main bank. Current affairs are removed. A question asked in more than one shift appears once, with its shifts listed. ' +
         esc(sec.source) + '</p>');
  h.push('<div class="stats"><span><b>' + sec.all.length + '</b> questions</span><span><b>' + Object.keys(shifts).length + '</b> shifts</span>' +
         '<span><b>' + sec.subjects.length + '</b> subjects</span><span>You: <b>' + all.done + '</b> answered, <b>' + all.right + '</b> correct</span></div>');
  }
  h.push('<div class="btnrow"><a class="btn" href="' + link('/p/all') + '">Practise ' + SET_SIZE +
         (sec.written ? ' of these at random' : ' ' + esc(sec.name.split(' ')[0]) + ' questions at random') + '</a>' +
         '<a class="btn ghost" href="#/">Back to the main bank</a></div>');
  h.push('</section>');
  h.push(subjectGrid());
  brandsub.textContent = sec.name;
  document.title = sec.name + ' — The DSSSB Key';
  return h.join('');
}

function railFor(s, activeId){
  var h = ['<nav class="railnav" aria-label="Topics in ' + esc(s.n) + '"><span class="lbl">' + esc(s.n) + '</span><ol>'];
  s.topics.forEach(function(t){
    var n = visible(t.qs).length;
    if (!n) return;
    h.push('<li><a href="' + link('/t/' + s.id + '/' + t.id) + '"' + (t.id === activeId ? ' aria-current="true"' : '') + '>' +
           '<span>' + esc(t.n) + '</span><span class="c">' + n + '</span></a></li>');
  });
  h.push('</ol><div class="btnrow"><a class="btn ghost" href="' + link('/p/' + s.id) + '">Practise this subject</a></div></nav>');
  return h.join('');
}

function pageSubject(s){
  var h = [];
  var st = stat(subjectQs(s));
  h.push('<div class="pagehead"><p class="eyebrow">' + (bank !== 'main' ? '<a href="' + link('') + '" style="color:inherit">' + SECTIONS[bank].name + '</a> · Subject' : 'Subject') + '</p><h1>' + esc(s.n) + '</h1>' +
         '<p class="lede">' + esc(s.w) + '</p>' + filterChips() +
         '<p class="tstats">' + statsLine(subjectQs(s)) + '</p>' +
         '<div class="btnrow"><a class="btn" href="' + link('/p/' + s.id) + '">Practise ' + SET_SIZE + ' from ' + esc(s.n) + '</a></div></div>');
  h.push('<div class="rail">' + railFor(s, null) + '<div>');
  h.push('<ul class="tlist" style="max-width:780px">');
  s.topics.forEach(function(t){
    var ts = stat(t.qs);
    if (!ts.n) return;
    h.push('<li><a href="' + link('/t/' + s.id + '/' + t.id) + '" style="padding:12px 2px"><span class="t"><b>' + esc(t.n) + '</b></span>' +
           bar(ts) + '<span class="c">' + ts.done + '/' + ts.n + '</span></a></li>');
  });
  h.push('</ul>');
  if (!st.n) h.push('<div class="empty">No questions in this subject for the selected papers.</div>');
  h.push('</div></div>');
  brandsub.textContent = sectionPrefix() + s.n;
  document.title = s.n + (bank !== 'main' ? ' — ' + SECTIONS[bank].name : '') + ' — The DSSSB Key';
  return h.join('');
}

/* `withReset` is off on the Saved page: "Clear my answers here" belongs to a
   topic, and Saved is not a topic. */
function viewChips(withReset){
  var opts = [['all', 'All'], ['todo', 'Not answered'], ['wrong', 'Got wrong']];
  var h = ['<div class="chips" role="group" aria-label="Which questions to show"><span class="cl">Show</span>'];
  opts.forEach(function(v){
    h.push('<button type="button" class="chip" data-view="' + v[0] + '" aria-pressed="' + (view === v[0]) + '">' + v[1] + '</button>');
  });
  if (withReset !== false) h.push('<button type="button" class="chip" data-act="reset-topic">Clear my answers here</button>');
  h.push('</div>');
  return h.join('');
}

/* --------------------------------------------------------------------------
   PAGING — a topic can hold 300+ questions, which is an unusable wall of
   scrolling on a phone. Topics are shown PAGE_SIZE at a time; the page number
   lives in the address (?p=2) so Back works and a page can be bookmarked.
   -------------------------------------------------------------------------- */
function pageStrip(base, pno, pages, where){
  if (pages < 2) return '';
  var h = ['<nav class="paging ' + where + '" aria-label="Pages of this topic">'];
  h.push(pno > 1 ? '<a class="pg step" href="' + base + '?p=' + (pno - 1) + '" rel="prev">‹ Back</a>'
                 : '<span class="pg step off">‹ Back</span>');

  /* First page, last page, and a short run around the one being read. */
  var want = {1: 1, 2: 1};
  want[pages] = 1; want[pages - 1] = 1;
  for (var d = -1; d <= 1; d++) if (pno + d >= 1 && pno + d <= pages) want[pno + d] = 1;
  var nums = Object.keys(want).map(Number).sort(function(a, b){ return a - b; });
  var last = 0;
  nums.forEach(function(n){
    if (n > last + 1) h.push('<span class="pg gap">…</span>');
    h.push(n === pno ? '<span class="pg here" aria-current="true">' + n + '</span>'
                     : '<a class="pg" href="' + base + '?p=' + n + '">' + n + '</a>');
    last = n;
  });

  h.push(pno < pages ? '<a class="pg step" href="' + base + '?p=' + (pno + 1) + '" rel="next">Next ›</a>'
                     : '<span class="pg step off">Next ›</span>');
  h.push('</nav>');
  return h.join('');
}

function pageTopic(s, t, query){
  var list = visible(t.qs).filter(function(q){
    if (view === 'todo') return progress[q.id] === undefined;
    if (view === 'wrong') return progress[q.id] !== undefined && progress[q.id] !== q.a;
    return true;
  });
  query = query || {};
  var base = link('/t/' + s.id + '/' + t.id);
  var pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));

  /* Arriving from search (?q=…) opens the page that question is actually on. */
  var pno = parseInt(query.p, 10) || 1;
  if (query.q){
    for (var qi = 0; qi < list.length; qi++){
      if (list[qi].id === query.q){ pno = Math.floor(qi / PAGE_SIZE) + 1; break; }
    }
  }
  pno = Math.min(pages, Math.max(1, pno));
  var from = (pno - 1) * PAGE_SIZE;
  var onPage = list.slice(from, from + PAGE_SIZE);

  var h = [];
  h.push('<div class="rail">' + railFor(s, t.id) + '<div>');
  h.push('<div class="pagehead"><p class="eyebrow">' + (bank !== 'main' ? '<a href="' + link('') + '" style="color:inherit">' + SECTIONS[bank].name + '</a> · ' : '') +
         '<a href="' + link('/s/' + s.id) + '" style="color:inherit">' + esc(s.n) + '</a></p>' +
         '<h1>' + esc(t.n) + '</h1>' + filterChips() + viewChips() +
         '<p class="tstats" id="tstats" data-scope="topic:' + s.id + ':' + t.id + '">' + statsLine(t.qs) + '</p>' +
         (pages > 1 ? '<p class="pagenote">Showing question ' + (from + 1) + '–' + (from + onPage.length) +
                      ' of ' + list.length + ' · page ' + pno + ' of ' + pages + '</p>' : '') + '</div>');
  h.push(pageStrip(base, pno, pages, 'top'));
  h.push('<div class="cards">');
  if (!list.length){
    h.push('<div class="empty">' + (view === 'all' ? 'No questions here for the selected papers.' :
           view === 'todo' ? 'You have answered every question shown here.' : 'Nothing answered wrongly here.') + '</div>');
  }
  onPage.forEach(function(q, i){ h.push(cardHTML(q, from + i + 1, false)); });
  h.push('</div>');
  h.push(pageStrip(base, pno, pages, 'bottom'));

  var i = s.topics.indexOf(t);
  var prev = s.topics[i - 1], next = s.topics[i + 1];
  h.push('<div class="pager">' +
    (prev ? '<a href="' + link('/t/' + s.id + '/' + prev.id) + '"><span class="k">Previous topic</span><span class="v">' + esc(prev.n) + '</span></a>'
          : '<span class="edge"><span class="k">Start of</span><span class="v">' + esc(s.n) + '</span></span>') +
    (next ? '<a href="' + link('/t/' + s.id + '/' + next.id) + '"><span class="k">Next topic</span><span class="v">' + esc(next.n) + '</span></a>'
          : '<span class="edge"><span class="k">End of</span><span class="v">' + esc(s.n) + '</span></span>') +
    '</div>');
  h.push('</div></div>');
  brandsub.textContent = sectionPrefix() + s.n;
  document.title = t.n + ' — ' + s.n + (bank !== 'main' ? ' — ' + SECTIONS[bank].name : '') + ' — The DSSSB Key';
  return h.join('');
}

/* --------------------------------------------------------------------------
   SAVED — the questions the user ticked to come back to, from every section
   of the site in one list, newest first.
   -------------------------------------------------------------------------- */
function pageSaved(query){
  query = query || {};
  var all = savedList();
  var list = all.filter(function(q){
    if (view === 'todo') return progress[q.id] === undefined;
    if (view === 'wrong') return progress[q.id] !== undefined && progress[q.id] !== q.a;
    return true;
  });
  var pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  var pno = Math.min(pages, Math.max(1, parseInt(query.p, 10) || 1));
  var from = (pno - 1) * PAGE_SIZE;
  var onPage = list.slice(from, from + PAGE_SIZE);

  /* Where the saved questions came from, so the page says something useful. */
  var where = {};
  all.forEach(function(q){ where[q.bank === 'main' ? 'the main bank' : SECTIONS[q.bank].name] = 1; });

  var h = [];
  h.push('<div class="pagehead"><p class="eyebrow">Your list</p><h1>Saved questions</h1>');
  if (!all.length){
    h.push('<p class="lede">Nothing saved yet. Tap <b>☆ Save</b> under any question and it lands here, ' +
           'so you can revise just those again later. Saved questions stay in this browser.</p></div>');
    h.push('<div class="empty">No saved questions yet.</div>');
    brandsub.textContent = 'Saved';
    document.title = 'Saved — The DSSSB Key';
    return h.join('');
  }
  h.push('<p class="lede">Everything you marked with ★, newest first — from ' +
         esc(Object.keys(where).join(', ')) + '. Tap ★ Saved on a card to drop it from this list.</p>');
  h.push(viewChips(false));
  h.push('<p class="tstats" id="tstats" data-scope="saved">' + statsLine(all, true) + '</p>');
  if (pages > 1){
    h.push('<p class="pagenote">Showing question ' + (from + 1) + '–' + (from + onPage.length) +
           ' of ' + list.length + ' · page ' + pno + ' of ' + pages + '</p>');
  }
  h.push('<div class="btnrow"><a class="btn" href="#/saved/p">Practise ' + Math.min(SET_SIZE, all.length) + ' saved at random</a>' +
         '<button type="button" class="btn ghost" data-act="clear-saved">Empty the list</button></div></div>');

  h.push(pageStrip('#/saved', pno, pages, 'top'));
  h.push('<div class="cards">');
  if (!list.length){
    h.push('<div class="empty">' + (view === 'todo' ? 'You have answered every saved question.'
                                                    : 'None of your saved questions was answered wrongly.') + '</div>');
  }
  onPage.forEach(function(q, i){ h.push(cardHTML(q, from + i + 1, true)); });
  h.push('</div>');
  h.push(pageStrip('#/saved', pno, pages, 'bottom'));

  brandsub.textContent = 'Saved';
  document.title = 'Saved (' + all.length + ') — The DSSSB Key';
  return h.join('');
}

/* A practice set prefers questions not yet answered, so repeated sets move
   through the bank instead of showing the same easy ones again. The set is
   kept for the browser session so a reload does not reshuffle it. */
function newSet(scopeId){
  if (scopeId === 'saved'){
    var kept = savedList();
    shuffle(kept);
    return kept.slice(0, SET_SIZE).map(function(q){ return q.id; });
  }
  var pool = scopeId === 'all' ? allNow() : subjectQs(subjectById(scopeId) || { topics: [] });
  pool = visible(pool);
  var fresh = pool.filter(function(q){ return progress[q.id] === undefined; });
  var used = pool.filter(function(q){ return progress[q.id] !== undefined; });
  shuffle(fresh); shuffle(used);
  return fresh.concat(used).slice(0, SET_SIZE).map(function(q){ return q.id; });
}
function shuffle(a){
  for (var i = a.length - 1; i > 0; i--){ var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
  return a;
}

function pagePractice(scopeId){
  var fromSaved = scopeId === 'saved';
  if (fromSaved && !savedCount()) return pageSaved({});
  var s = (scopeId === 'all' || fromSaved) ? null : subjectById(scopeId);
  if (!fromSaved && scopeId !== 'all' && !s) return bank !== 'main' ? pageSectionHome() : pageHome();
  var key = fromSaved ? 'dk-set-saved' : 'dk-set-' + (bank !== 'main' ? bank + '-' : '') + scopeId + '-' + filter;
  var ids = sload(key);
  var stale = !ids || !ids.length || ids.some(function(id){
    return !BYID[id] || (fromSaved ? !isSaved(id) : BYID[id].bank !== bank);
  });
  if (stale){ ids = newSet(scopeId); ssave(key, ids); }
  var list = ids.map(function(id){ return BYID[id]; });
  var name = fromSaved ? 'Saved questions' : (s ? s.n : 'All subjects') + (bank !== 'main' ? ' · ' + SECTIONS[bank].name : '');

  var h = [];
  h.push('<div class="pagehead"><p class="eyebrow">Practice set</p><h1>' + list.length + ' random question' + (list.length === 1 ? '' : 's') + ' · ' + esc(name) + '</h1>' +
         '<p class="lede">' + (fromSaved
            ? 'Drawn only from the questions you saved. Your answers count towards your progress everywhere on the site.'
            : 'Unanswered questions are picked first. Your answers count towards your progress everywhere on the site.') + '</p>' +
         (fromSaved ? '' : filterChips()) +
         '<p class="tstats" id="tstats" data-scope="set:' + key + '">' + statsLine(list, fromSaved) + '</p>' +
         '<div class="btnrow"><button type="button" class="btn" data-act="newset" data-key="' + key + '" data-scope="' + scopeId + '">New set</button>' +
         (fromSaved ? '<a class="btn ghost" href="#/saved">Back to Saved</a>'
            : s ? '<a class="btn ghost" href="' + link('/s/' + s.id) + '">Back to ' + esc(s.n) + '</a>'
            : '<a class="btn ghost" href="' + link('/') + '">' + (bank !== 'main' ? 'Back to ' + SECTIONS[bank].name : 'Back home') + '</a>') + '</div></div>');
  h.push('<div class="cards">');
  if (!list.length) h.push('<div class="empty">No questions available for the selected papers.</div>');
  list.forEach(function(q, i){ h.push(cardHTML(q, i + 1, true)); });
  h.push('</div>');
  brandsub.textContent = 'Practice';
  document.title = 'Practice — ' + name + ' — The DSSSB Key';
  return h.join('');
}

/* --------------------------------------------------------------------------
   ROUTER AND TABS
   -------------------------------------------------------------------------- */
function parseHash(){
  var raw = location.hash.replace(/^#/, '') || '/';
  var query = {};
  var qi = raw.indexOf('?');
  if (qi > -1){
    raw.slice(qi + 1).split('&').forEach(function(pair){
      var kv = pair.split('=');
      query[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
    });
    raw = raw.slice(0, qi);
  }
  return { parts: raw.split('/').filter(Boolean), query: query };
}

function route(keepScroll){
  var r = parseHash(), p = r.parts, html, s, t;
  /* The front door: arriving at the bare address (or #/start) asks which site
     to open. Every link inside the Key says #/ explicitly, so it never lands here. */
  var bare = !location.hash || location.hash === '#';
  if (bare || (p[0] === 'start' && p.length === 1)){
    bank = 'main';
    main.innerHTML = pageStart();
    syncTabs(['start']);
    window.scrollTo(0, 0);
    return;
  }
  bank = SECTIONS.hasOwnProperty(p[0]) && SECTIONS[p[0]].all.length ? p[0] : 'main';
  if (bank !== 'main') p = p.slice(1);
  /* Saved spans every section, so it is not a section of its own. */
  if (p[0] === 'saved') html = p[1] === 'p' ? pagePractice('saved') : pageSaved(r.query);
  else if (p[0] === 't' && (s = subjectById(p[1])) && (t = topicById(s, p[2]))) html = pageTopic(s, t, r.query);
  else if (p[0] === 's' && (s = subjectById(p[1]))) html = pageSubject(s);
  else if (p[0] === 'p' && p[1]) html = pagePractice(p[1]);
  else html = bank !== 'main' ? pageSectionHome() : pageHome();

  var y = window.scrollY;
  main.innerHTML = html;
  syncTabs(p);
  if (keepScroll === true) window.scrollTo(0, y);
  else window.scrollTo(0, 0);

  if (r.query.q){
    var node = document.getElementById('q-' + r.query.q);
    if (node){ node.scrollIntoView({ block: 'center' }); node.classList.add('flash'); }
  }
}

function savedTabLabel(){
  var c = savedCount();
  return '★ Saved' + (c ? ' (' + c + ')' : '');
}
/* The count in the tab changes as the user saves, without a full redraw. */
function updateSavedTab(){
  var a = tabsEl.querySelector('[data-tab="saved"]');
  if (a) a.textContent = savedTabLabel();
}

function buildTabs(){
  var h = ['<a href="#/start" data-tab="start" class="starttab">⇄ Sites</a>', '<a href="#/" data-tab="home">Home</a>'];
  h.push('<a href="patwari/" data-tab="patwari" class="pattab">Patwari Prep</a>');
  h.push('<a href="#/saved" data-tab="saved" class="savedtab">' + savedTabLabel() + '</a>');
  if (AS_ALL.length) h.push('<a href="#/as" data-tab="as">AS 2026</a>');
  if (MTS_ALL.length) h.push('<a href="#/mts" data-tab="mts">MTS 2026</a>');
  if (PRAC_ALL.length) h.push('<a href="#/prac" data-tab="prac">Extra Practice</a>');
  SUBJECTS.forEach(function(s){ h.push('<a href="#/s/' + s.id + '" data-tab="' + s.id + '">' + esc(s.tab || s.n) + '</a>'); });
  h.push('<a href="#/p/all" data-tab="practice">Practise 20</a>');
  tabsEl.innerHTML = h.join('');
}
function syncTabs(p){
  var active = p[0] === 'start' ? 'start' : p[0] === 'saved' ? 'saved' : bank !== 'main' ? bank : !p.length ? 'home' :
               p[0] === 'p' ? (p[1] === 'all' ? 'practice' : p[1]) : (p[0] === 's' || p[0] === 't') ? p[1] : 'home';
  /* An address that names no real subject falls back to the home page, so light Home. */
  var known = Array.prototype.some.call(tabsEl.children, function(a){ return a.dataset.tab === active; });
  if (!known) active = 'home';
  Array.prototype.forEach.call(tabsEl.children, function(a){
    if (a.dataset.tab === active) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
  });
}

/* --------------------------------------------------------------------------
   CLICKS ON THE PAGE
   -------------------------------------------------------------------------- */
main.addEventListener('click', function(e){
  var f = e.target.closest('[data-filter]');
  if (f){ filter = f.dataset.filter; save('dk-filter', filter); route(true); return; }

  var v = e.target.closest('[data-view]');
  if (v){ view = v.dataset.view; save('dk-view', view); route(true); return; }

  var act = e.target.closest('[data-act]');
  var card = e.target.closest('.card');

  if (act && act.dataset.act === 'reset-topic'){
    var r = parseHash().parts;
    if (SECTIONS.hasOwnProperty(r[0])) r = r.slice(1);
    var s = subjectById(r[1]), t = topicById(s, r[2]);
    if (t && window.confirm('Clear your saved answers for “' + t.n + '”?')){
      t.qs.forEach(function(q){ delete progress[q.id]; });
      save('dk-progress', progress);
      route(true);
    }
    return;
  }
  if (act && act.dataset.act === 'clear-saved'){
    var howMany = savedCount();
    if (howMany && window.confirm('Remove all ' + howMany + ' questions from your Saved list? Your answers are not touched.')){
      saved = {};
      save('dk-saved', saved);
      updateSavedTab();
      route(false);
    }
    return;
  }
  if (act && act.dataset.act === 'newset'){
    ssave(act.dataset.key, newSet(act.dataset.scope));
    route(false);
    return;
  }
  if (!card) return;
  var id = card.dataset.id, q = BYID[id];

  if (act){
    if (act.dataset.act === 'show') shown[id] = true;
    if (act.dataset.act === 'hide') delete shown[id];
    if (act.dataset.act === 'retry'){ delete progress[id]; delete shown[id]; save('dk-progress', progress); }
    if (act.dataset.act === 'save'){
      if (isSaved(id)) delete saved[id]; else saved[id] = Date.now();
      save('dk-saved', saved);
      updateSavedTab();
    }
    refreshCard(id);
    return;
  }

  if (e.target.closest('.tlabel')) return;
  var opt = e.target.closest('.opt');
  if (opt && progress[id] === undefined){
    progress[id] = Number(opt.dataset.i);
    save('dk-progress', progress);
    refreshCard(id);
  }
});

/* --------------------------------------------------------------------------
   SEARCH — over question text, options and explanations. Results never show
   the answer, so searching cannot spoil a question.
   -------------------------------------------------------------------------- */
/* Search covers the main bank and the MTS 2026 and AS 2026 sections. */
var EVERY = ALL.concat(AS_ALL, MTS_ALL, PRAC_ALL);
EVERY.forEach(function(q){
  q.hay = (q.q + ' ' + q.o.join(' ') + ' ' + q.x + ' ' + (q.e || '') + ' ' + q.t.n + ' ' + q.s.n).toLowerCase();
});

function search(term){
  var needle = term.trim().toLowerCase();
  if (needle.length < 2) return [];
  var words = needle.split(/\s+/);
  var hits = [];
  EVERY.forEach(function(q){
    for (var i = 0; i < words.length; i++) if (q.hay.indexOf(words[i]) === -1) return;
    var stem = q.q.toLowerCase();
    hits.push({ q: q, score: stem.indexOf(needle) > -1 ? 0 : words.every(function(w){ return stem.indexOf(w) > -1; }) ? 1 : 2 });
  });
  hits.sort(function(a, b){ return a.score - b.score; });
  return hits.slice(0, 60).map(function(h){ return h.q; });
}

function markText(text, term){
  var out = esc(text);
  term.trim().split(/\s+/).filter(function(w){ return w.length > 1; }).forEach(function(w){
    out = out.replace(new RegExp('(' + esc(w).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
  });
  return out;
}

function renderResults(term){
  if (term.trim().length < 2){ closeResults(); return; }
  var hits = search(term);
  resEl.hidden = false;
  qEl.setAttribute('aria-expanded', 'true');
  if (!hits.length){
    resEl.innerHTML = '<div class="empty">Nothing for “' + esc(term) + '”. Try one word — a name, an Article number, a place.</div>';
    return;
  }
  resEl.innerHTML = hits.map(function(q, i){
    var sec = q.bank !== 'main' ? SECTIONS[q.bank] : null;
    var srcs = sec ? q.src.slice(0, 3).map(shiftName).join(' · ') + (q.src.length > 3 ? ' · +' + (q.src.length - 3) + ' more' : '')
                   : q.src.join(' · ');
    return '<a class="rrow' + (i === 0 ? ' sel' : '') + '" href="' + (sec ? '#/' + q.bank : '#') + '/t/' + q.s.id + '/' + q.t.id + '?q=' + q.id + '">' +
      '<div class="rk">' + (sec ? esc(sec.name) + ' · ' : '') + esc(q.s.n) + ' · ' + esc(q.t.n) + '</div>' +
      '<div class="rt">' + markText(q.q, term) + '</div>' +
      '<div class="rs">' + esc(srcs) + '</div></a>';
  }).join('');
}
function closeResults(){ resEl.hidden = true; qEl.setAttribute('aria-expanded', 'false'); }

var timer = null;
qEl.addEventListener('input', function(){
  clearTimeout(timer);
  var v = qEl.value;
  timer = setTimeout(function(){ renderResults(v); }, 90);
});
qEl.addEventListener('focus', function(){ if (qEl.value.trim().length > 1) renderResults(qEl.value); });

/* Going to a search result: if the question is filtered out or hidden by the
   "Show" choice, reset those so the question is actually on the page. */
resEl.addEventListener('click', function(e){
  var a = e.target.closest('a.rrow');
  if (!a) return;
  var id = a.getAttribute('href').split('?q=')[1];
  if (BYID[id] && !passes(BYID[id])){ filter = 'all'; save('dk-filter', filter); }
  if (view !== 'all'){ view = 'all'; save('dk-view', view); }
  closeResults(); qEl.blur();
  if (location.hash === a.getAttribute('href')){ e.preventDefault(); route(); }
});

document.addEventListener('keydown', function(e){
  if (e.key === '/' && document.activeElement !== qEl && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)){
    e.preventDefault(); qEl.focus(); qEl.select(); return;
  }
  if (e.key === 'Escape' && !resEl.hidden){ closeResults(); qEl.blur(); return; }
  if (resEl.hidden) return;
  var rows = Array.prototype.slice.call(resEl.querySelectorAll('.rrow'));
  if (!rows.length) return;
  var cur = rows.findIndex(function(r){ return r.classList.contains('sel'); });
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp'){
    e.preventDefault();
    if (cur > -1) rows[cur].classList.remove('sel');
    var nx = rows[Math.max(0, Math.min(rows.length - 1, cur + (e.key === 'ArrowDown' ? 1 : -1)))];
    nx.classList.add('sel'); nx.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter' && cur > -1){
    e.preventDefault(); rows[cur].click(); location.hash = rows[cur].getAttribute('href');
  }
});
document.addEventListener('click', function(e){
  if (!resEl.hidden && !resEl.contains(e.target) && e.target !== qEl) closeResults();
});

window.addEventListener('hashchange', function(){ route(); });

/* --------------------------------------------------------------------------
   INSTALL AND OFFLINE
   -------------------------------------------------------------------------- */
var deferredPrompt = null;
var installBtn = document.getElementById('install');
window.addEventListener('beforeinstallprompt', function(e){ e.preventDefault(); deferredPrompt = e; installBtn.hidden = false; });
installBtn.addEventListener('click', function(){
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(function(){ deferredPrompt = null; installBtn.hidden = true; });
});
window.addEventListener('appinstalled', function(){ installBtn.hidden = true; });

if ('serviceWorker' in navigator && location.protocol !== 'file:'){
  window.addEventListener('load', function(){
    navigator.serviceWorker.register('sw.js').catch(function(err){ console.warn('Offline mode unavailable:', err); });
  });
}

buildTabs();
route();
