#!/usr/bin/env python3
"""VD Golf Match — live scoring PWA + match history server"""

import json, os
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get('PORT', 8052))
DATA_FILE = os.path.join(os.path.dirname(__file__), 'matches.json')


def load_matches():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_match(match_data):
    matches = load_matches()
    matches.append(match_data)
    with open(DATA_FILE, 'w') as f:
        json.dump(matches, f, indent=2)


# ---------------------------------------------------------------------------
# Service Worker
# ---------------------------------------------------------------------------
SW_JS = """
const CACHE = 'vd-golf-v5';
const CORE = ['/'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)));
  self.skipWaiting();
});
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) return; // never cache API calls
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
      if (resp.ok) {
        caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
      }
      return resp;
    }))
  );
});
"""

# ---------------------------------------------------------------------------
# Scoring PWA HTML
# ---------------------------------------------------------------------------
PWA_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="VD Golf">
<title>VD Golf Match</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{
  --green:#22c55e;--red:#ef4444;--blue:#60a5fa;--gold:#f59e0b;
  --bg:#111827;--card:#1f2937;--border:#374151;--text:#f9fafb;--muted:#9ca3af;
}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100svh;padding-bottom:env(safe-area-inset-bottom)}
.screen{display:none;max-width:440px;margin:0 auto}
.screen.active{display:block}

/* ── top bar ── */
.topbar{background:var(--card);border-bottom:1px solid var(--border);padding:10px 16px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:20}
.topbar h1{font-size:18px;font-weight:800;letter-spacing:.5px}
.topbar .sub{font-size:12px;color:var(--muted);margin-top:1px}

/* ── score bar ── */
.sbar{display:flex;align-items:center;justify-content:space-between;background:var(--card);border-bottom:1px solid var(--border);padding:10px 20px;gap:8px}
.sbar-player{text-align:center;min-width:60px}
.sbar-pts{font-size:28px;font-weight:800}
.sbar-label{font-size:11px;color:var(--muted);margin-top:1px}
.sbar-nine{font-size:12px;color:var(--muted);margin-top:3px;font-weight:600}
.sbar-mid{flex:1;text-align:center}
.sbar-lead{font-size:16px;font-weight:700;color:var(--gold)}
.sbar-hint{font-size:11px;color:var(--muted);margin-top:2px}

/* ── cards ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;margin:12px 16px}
.card h3{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:12px}

/* ── hole header ── */
.hole-hdr{display:flex;justify-content:space-between;align-items:flex-start}
.hole-nine{font-size:12px;color:var(--blue);font-weight:600;margin-bottom:2px}
.hole-num{font-size:32px;font-weight:900}
.hole-meta{font-size:14px;color:var(--muted);margin-top:3px}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.badge{display:inline-flex;align-items:center;gap:5px;border-radius:20px;padding:6px 14px;font-size:13px;font-weight:600}
.badge-honor{background:rgba(245,158,11,.12);border:1px solid var(--gold);color:var(--gold)}
.badge-stroke{background:rgba(96,165,250,.12);border:1px solid var(--blue);color:var(--blue)}

/* ── score entry ── */
.entry{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin:8px 16px}
.entry-name{font-size:15px;font-weight:700;margin-bottom:12px}
.entry-row{display:flex;align-items:center;justify-content:center;gap:24px}
.sbtn{width:60px;height:60px;border-radius:50%;border:none;font-size:30px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform .1s}
.sbtn:active{transform:scale(.88)}
.sbtn.minus{background:#374151;color:var(--text)}
.sbtn.plus{background:var(--blue);color:#fff}
.snum{font-size:52px;font-weight:900;min-width:56px;text-align:center;line-height:1}
.slabel{font-size:13px;color:var(--muted);text-align:center;margin-top:4px}

/* ── buttons ── */
.btn{width:calc(100% - 32px);margin:8px 16px;padding:17px;border-radius:12px;border:none;font-size:17px;font-weight:700;cursor:pointer;transition:transform .1s}
.btn:active{transform:scale(.97)}
.btn-green{background:var(--green);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text)}

/* ── result overlay ── */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;z-index:100;padding:20px}
.overlay-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:32px 24px;width:100%;max-width:360px;text-align:center}
.ov-hole{font-size:13px;color:var(--muted);margin-bottom:6px}
.ov-winner{font-size:36px;font-weight:900;margin-bottom:4px}
.ov-scores{font-size:14px;color:var(--muted);margin-bottom:6px}
.ov-match{font-size:20px;font-weight:700;color:var(--gold);margin-bottom:24px}
.ov-detail{font-size:12px;color:var(--muted);margin-bottom:16px}

/* ── setup ── */
.nine-opt{display:flex;align-items:center;padding:14px;border-radius:10px;border:2px solid var(--border);margin:8px 0;cursor:pointer;transition:border-color .15s,background .15s;user-select:none}
.nine-opt.sel{border-color:var(--green);background:rgba(34,197,94,.07)}
.nine-info{flex:1}
.nine-name-lbl{font-size:16px;font-weight:600}
.nine-sublbl{font-size:13px;color:var(--muted);margin-top:2px}
.nine-check{font-size:20px;color:var(--green);opacity:0;transition:opacity .15s}
.nine-opt.sel .nine-check{opacity:1}
.honor-row{display:flex;gap:12px;margin-top:4px}
.hbtn{flex:1;padding:14px;border-radius:10px;border:2px solid var(--border);background:transparent;color:var(--text);font-size:20px;font-weight:800;cursor:pointer;transition:all .15s}
.hbtn.sel{border-color:var(--gold);background:rgba(245,158,11,.1);color:var(--gold)}

/* ── summary ── */
.win-banner{font-size:28px;font-weight:900;text-align:center;padding:20px 16px 8px}
.stat-row{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border);font-size:15px}
.stat-row:last-child{border-bottom:none}
.stat-lbl{color:var(--muted)}
.stat-val{font-weight:700}

/* ── hole table ── */
.htbl{width:100%;border-collapse:collapse;font-size:13px}
.htbl th{background:#0d1520;padding:7px 5px;text-align:center;color:var(--muted);font-size:11px;font-weight:700;position:sticky;top:0}
.htbl td{padding:7px 5px;text-align:center;border-bottom:1px solid #1e2a3a}
.htbl tr:last-child td{border-bottom:none}
.htbl .total-row td{font-weight:800;background:#0d1520}
.pv{color:var(--green);font-weight:700}
.pd{color:var(--blue);font-weight:700}
.stroke-mark{font-size:10px;color:var(--gold);vertical-align:super}

/* ── toast ── */
.toast{position:fixed;bottom:40px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:11px 22px;border-radius:20px;font-size:14px;z-index:200;opacity:0;transition:opacity .3s;pointer-events:none;white-space:nowrap}
.toast.show{opacity:1}
</style>
</head>
<body>

<!-- ═══════════════ SETUP SCREEN ═══════════════ -->
<div id="screen-setup" class="screen">
  <div class="topbar">
    <div><div style="font-size:20px;font-weight:900">⛳ VD Golf</div><div class="sub" id="setup-date"></div></div>
  </div>

  <!-- Current match status card (shown when match is in progress) -->
  <div id="match-status-card" style="display:none;margin:12px 16px;background:#1f2937;border:2px solid #f59e0b;border-radius:14px;padding:16px">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#f59e0b;margin-bottom:10px">Match in Progress</div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div id="ms-lead" style="font-size:22px;font-weight:900"></div>
      <div id="ms-holes" style="font-size:13px;color:#9ca3af;text-align:right"></div>
    </div>
    <div style="display:flex;justify-content:space-around;margin-bottom:14px">
      <div style="text-align:center">
        <div style="font-size:28px;font-weight:900;color:#22c55e" id="ms-v-pts">0</div>
        <div style="font-size:11px;color:#9ca3af">V pts</div>
        <div style="font-size:12px;font-weight:600;color:#9ca3af;margin-top:2px" id="ms-v-nine"></div>
      </div>
      <div style="text-align:center">
        <div style="font-size:28px;font-weight:900;color:#60a5fa" id="ms-d-pts">0</div>
        <div style="font-size:11px;color:#9ca3af">D pts</div>
        <div style="font-size:12px;font-weight:600;color:#9ca3af;margin-top:2px" id="ms-d-nine"></div>
      </div>
    </div>
    <button class="btn btn-green" onclick="resumeMatch()" style="margin:0 0 8px">Resume Match</button>
    <button class="btn btn-ghost" onclick="deleteMatch()" style="margin:0;font-size:14px;padding:10px;color:#ef4444;border-color:#ef4444">Delete Match</button>
  </div>
  <div class="card">
    <h3>Select Nines (in play order)</h3>
    <div id="nine-opts"></div>
  </div>
  <div class="card">
    <h3>Honor on Hole 1</h3>
    <div class="honor-row">
      <button class="hbtn sel" id="hbtn-V" onclick="setHonor('V')">V</button>
      <button class="hbtn" id="hbtn-D" onclick="setHonor('D')">D</button>
    </div>
  </div>
  <div class="card">
    <h3>Starting Score</h3>
    <div style="display:flex;align-items:center;justify-content:center;gap:24px;padding:4px 0">
      <button class="sbtn minus" onclick="adjOffset(-1)">−</button>
      <div style="text-align:center">
        <div style="font-size:32px;font-weight:900" id="offset-display">D+1</div>
        <div style="font-size:12px;color:var(--muted);margin-top:2px">carry-in pts</div>
      </div>
      <button class="sbtn plus" onclick="adjOffset(1)">+</button>
    </div>
  </div>
  <button class="btn btn-green" onclick="startMatch()">Start Match</button>
  <button class="btn btn-ghost" onclick="showHistory()" style="margin-top:4px">View History</button>
</div>

<!-- ═══════════════ HOLE SCREEN ═══════════════ -->
<div id="screen-hole" class="screen">
  <!-- Score bar -->
  <div class="sbar">
    <div class="sbar-player">
      <div class="sbar-pts" id="sb-v" style="color:var(--green)">0</div>
      <div class="sbar-label" style="color:var(--green)">V pts</div>
      <div class="sbar-nine" id="sb-v-nine">–</div>
    </div>
    <div class="sbar-mid">
      <div class="sbar-lead" id="sb-lead">Even</div>
      <div class="sbar-hint" id="sb-hint"></div>
    </div>
    <div class="sbar-player">
      <div class="sbar-pts" id="sb-d" style="color:var(--blue)">0</div>
      <div class="sbar-label" style="color:var(--blue)">D pts</div>
      <div class="sbar-nine" id="sb-d-nine">–</div>
    </div>
  </div>

  <!-- Hole info -->
  <div class="card" style="margin-top:12px">
    <div class="hole-hdr">
      <div>
        <div class="hole-nine" id="hole-nine"></div>
        <div class="hole-num" id="hole-num">Hole 1</div>
        <div class="hole-meta" id="hole-meta">Par 4 · Hdcp 3</div>
      </div>
    </div>
    <div class="badges">
      <span class="badge badge-honor" id="badge-honor">🏌️ V has honor</span>
      <span class="badge badge-stroke" id="badge-stroke" style="display:none"></span>
    </div>
  </div>

  <!-- Score entry V -->
  <div class="entry">
    <div class="entry-name" style="color:var(--green)">V</div>
    <div class="entry-row">
      <button class="sbtn minus" onclick="adj('v',-1)">−</button>
      <div><div class="snum" id="v-num">4</div><div class="slabel" id="v-lbl">Par</div></div>
      <button class="sbtn plus" onclick="adj('v',1)">+</button>
    </div>
  </div>

  <!-- Score entry D -->
  <div class="entry">
    <div class="entry-name" style="color:var(--blue)">D</div>
    <div class="entry-row">
      <button class="sbtn minus" onclick="adj('d',-1)">−</button>
      <div><div class="snum" id="d-num">4</div><div class="slabel" id="d-lbl">Par</div></div>
      <button class="sbtn plus" onclick="adj('d',1)">+</button>
    </div>
  </div>

  <button class="btn btn-green" onclick="recordHole()">Record Hole</button>
  <button class="btn btn-ghost" id="edit-btn" onclick="showEditOverlay()" style="display:none">↩ Edit Previous Holes</button>
  <button class="btn btn-ghost" onclick="endMatchEarly()" style="margin-bottom:16px">End Match</button>
</div>

<!-- ═══════════════ EDIT HOLES OVERLAY ═══════════════ -->
<div class="overlay" id="edit-overlay" style="display:none">
  <div class="overlay-card" style="max-height:80vh;overflow-y:auto;padding:20px 16px">
    <div style="font-size:13px;color:var(--muted);margin-bottom:14px;font-weight:600">Tap a hole to go back and re-enter it</div>
    <div id="edit-hole-list"></div>
    <button class="btn btn-ghost" onclick="document.getElementById('edit-overlay').style.display='none'" style="width:100%;margin:12px 0 0">Cancel</button>
  </div>
</div>

<!-- ═══════════════ RESULT OVERLAY ═══════════════ -->
<div class="overlay" id="overlay" style="display:none">
  <div class="overlay-card">
    <div class="ov-hole" id="ov-hole">Hole 1</div>
    <div class="ov-winner" id="ov-winner">Halved</div>
    <div class="ov-scores" id="ov-scores">V 4 · D 4</div>
    <div class="ov-detail" id="ov-detail"></div>
    <div id="ov-nine-sum" style="display:none"></div>
    <div class="ov-match" id="ov-match">Even</div>
    <button class="btn btn-green" onclick="nextHole()" id="ov-next" style="width:100%;margin:0">Next →</button>
  </div>
</div>

<!-- ═══════════════ SUMMARY SCREEN ═══════════════ -->
<div id="screen-summary" class="screen">
  <div class="topbar"><div><div style="font-size:18px;font-weight:900">Match Complete</div><div class="sub" id="sum-date"></div></div></div>
  <div class="win-banner" id="win-banner"></div>
  <div class="card">
    <h3>Final Score</h3>
    <div class="stat-row"><span class="stat-lbl">V Total Points</span><span class="stat-val pv" id="sum-v">0</span></div>
    <div class="stat-row"><span class="stat-lbl">D Total Points</span><span class="stat-val pd" id="sum-d">0</span></div>
    <div class="stat-row"><span class="stat-lbl">Margin</span><span class="stat-val" id="sum-margin">Even</span></div>
  </div>
  <div class="card" style="overflow-x:auto">
    <h3>Hole by Hole <span style="font-weight:400;color:var(--muted)">(*= stroke given)</span></h3>
    <table class="htbl" id="hole-tbl"></table>
  </div>
  <button class="btn btn-green" id="save-btn" onclick="saveMatch()">Save to History</button>
  <button class="btn btn-ghost" onclick="newMatch()">New Match</button>
</div>

<!-- ═══════════════ HISTORY SCREEN ═══════════════ -->
<div id="screen-history" class="screen">
  <div class="topbar">
    <div style="font-size:18px;font-weight:900">Match History</div>
    <button onclick="showScreen('screen-setup')" style="background:none;border:none;color:var(--muted);font-size:14px;cursor:pointer">← Back</button>
  </div>
  <div style="padding:16px" id="history-body"><div style="color:var(--muted);text-align:center;padding:40px">Loading…</div></div>
</div>

<div class="toast" id="toast"></div>

<script>
// ═══════════════════════════════════════════
// COURSE DATA
// ═══════════════════════════════════════════
const COURSE = {
  nines: [
    { name:'Lakes', holes:[
      {number:1,par:4,handicap:3},{number:2,par:4,handicap:4},{number:3,par:5,handicap:9},
      {number:4,par:3,handicap:7},{number:5,par:4,handicap:2},{number:6,par:4,handicap:6},
      {number:7,par:5,handicap:8},{number:8,par:4,handicap:1},{number:9,par:3,handicap:5}
    ]},
    { name:'Foothills', holes:[
      {number:10,par:4,handicap:2},{number:11,par:4,handicap:1},{number:12,par:3,handicap:6},
      {number:13,par:5,handicap:8},{number:14,par:3,handicap:7},{number:15,par:4,handicap:9},
      {number:16,par:4,handicap:3},{number:17,par:5,handicap:5},{number:18,par:4,handicap:4}
    ]},
    { name:'Mountain', holes:[
      {number:19,par:4,handicap:9},{number:20,par:4,handicap:2},{number:21,par:3,handicap:8},
      {number:22,par:5,handicap:6},{number:23,par:4,handicap:4},{number:24,par:5,handicap:7},
      {number:25,par:3,handicap:5},{number:26,par:4,handicap:1},{number:27,par:4,handicap:3}
    ]}
  ]
};

// ═══════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════
let S = loadState() || freshState();

function freshState() {
  return {
    date: today(),
    selectedNines: [],
    holes: [],
    initialHonor: 'V',
    startOffset: -1,     // D+1 default (negative=D leads, positive=V leads)
    results: [],
    strokeMap: {},
    strokesComputedAt: [],
    curV: 4,
    curD: 4,
    inProgress: false,
  };
}

// ═══════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════
function today() { return new Date().toISOString().slice(0,10); }

function matchScore() {
  let v=0, d=0;
  S.results.forEach(r => { v+=r.vPts; d+=r.dPts; });
  const off = S.startOffset || 0;
  if (off > 0) v += off; else d += Math.abs(off);
  return {v, d};
}
function margin() { const m=matchScore(); return m.v - m.d; } // pos=V winning

function getHonor() {
  // Look back through gross scores; first non-tie determines honor
  for (let i=S.results.length-1; i>=0; i--) {
    const r=S.results[i];
    if (r.vGross < r.dGross) return 'V';
    if (r.dGross < r.vGross) return 'D';
  }
  return S.initialHonor;
}

function scoreLabel(score, par) {
  const d = score-par;
  if (d<=-2) return 'Eagle';
  if (d===-1) return 'Birdie';
  if (d===0)  return 'Par';
  if (d===1)  return 'Bogey';
  if (d===2)  return 'Double';
  return `+${d}`;
}

function isNineStart(idx) {
  if (idx===0) return false;
  let c=0;
  for (const ni of S.selectedNines) {
    c += COURSE.nines[ni].holes.length;
    if (idx===c) return true;
  }
  return false;
}

function nineForIdx(idx) {
  let c=0;
  for (const ni of S.selectedNines) {
    const nine = COURSE.nines[ni];
    if (idx < c + nine.holes.length) return nine;
    c += nine.holes.length;
  }
  return null;
}

// ═══════════════════════════════════════════
// STROKE ADVANTAGE
// ═══════════════════════════════════════════
function computeStrokesForNine(nineStartIdx) {
  // Only called once per nine transition
  if (S.strokesComputedAt.includes(nineStartIdx)) return;
  S.strokesComputedAt.push(nineStartIdx);

  const m = margin();
  const strokes = Math.floor(Math.abs(m) / 5);
  if (strokes === 0) return;

  // Trailing player
  const trailV = m > 0; // V leading → D trails → D gets strokes
  const nine = nineForIdx(nineStartIdx);
  if (!nine) return;

  // Holes sorted by handicap ascending (hcp 1 = hardest = gets stroke first)
  const sorted = [...nine.holes].sort((a,b) => a.handicap - b.handicap);
  const strokeHoles = sorted.slice(0, strokes).map(h => h.number);

  strokeHoles.forEach(num => {
    const hi = S.holes.findIndex(h => h.number === num);
    if (hi >= 0) {
      if (!S.strokeMap[hi]) S.strokeMap[hi] = {v:false, d:false};
      if (trailV) S.strokeMap[hi].d = true; else S.strokeMap[hi].v = true;
    }
  });
}

// ═══════════════════════════════════════════
// GAME LOGIC
// ═══════════════════════════════════════════
function calcHole(hole, vGross, dGross, vStroke, dStroke) {
  const par = hole.par;
  const cap = par + 2;

  // Net scores after applying strokes
  const vNet = vGross - (vStroke ? 1 : 0);
  const dNet = dGross - (dStroke ? 1 : 0);

  // Cap at double bogey
  const vCap = Math.min(vNet, cap);
  const dCap = Math.min(dNet, cap);

  let vPts=0, dPts=0;
  if (vCap < dCap && vNet <= par+1) vPts = dCap - vCap;
  else if (dCap < vCap && dNet <= par+1) dPts = vCap - dCap;

  return {vPts, dPts, vNet, dNet, vCap, dCap};
}

// ═══════════════════════════════════════════
// SETUP SCREEN
// ═══════════════════════════════════════════
function initSetup() {
  document.getElementById('setup-date').textContent = today();

  // Show/update match status card
  const card = document.getElementById('match-status-card');
  if (S.inProgress && S.holes.length > 0 && S.results.length > 0) {
    card.style.display = 'block';
    const ms = matchScore();
    const m = ms.v - ms.d;
    const leadEl = document.getElementById('ms-lead');
    if (m === 0) { leadEl.textContent = 'Even'; leadEl.style.color = '#9ca3af'; }
    else { const who=m>0?'V':'D', color=m>0?'#22c55e':'#60a5fa'; leadEl.textContent=`${who} leads +${Math.abs(m)}`; leadEl.style.color=color; }
    document.getElementById('ms-v-pts').textContent = ms.v;
    document.getElementById('ms-d-pts').textContent = ms.d;
    const nines = S.selectedNines.map(i => COURSE.nines[i].name).join(' + ');
    const holesLeft = S.holes.length - S.results.length;
    document.getElementById('ms-holes').innerHTML = `${nines}<br>${S.results.length} of ${S.holes.length} holes played`;
    // Running nine score
    const nine = getCurrentNineScore();
    document.getElementById('ms-v-nine').textContent = nine.count > 0 ? `Nine: ${fmtVsPar(nine.vVsPar)}` : '';
    document.getElementById('ms-d-nine').textContent = nine.count > 0 ? `Nine: ${fmtVsPar(nine.dVsPar)}` : '';
  } else {
    card.style.display = 'none';
  }

  const el = document.getElementById('nine-opts');
  el.innerHTML = '';
  COURSE.nines.forEach((nine, idx) => {
    const d = document.createElement('div');
    d.className = 'nine-opt' + (S.selectedNines.includes(idx) ? ' sel' : '');
    d.onclick = () => toggleNine(idx);
    d.id = `nine-opt-${idx}`;
    const hn = nine.holes;
    d.innerHTML = `<div class="nine-info">
      <div class="nine-name-lbl">${nine.name}</div>
      <div class="nine-sublbl">Holes ${hn[0].number}–${hn[hn.length-1].number} &nbsp;·&nbsp; Par ${hn.reduce((s,h)=>s+h.par,0)}</div>
    </div><div class="nine-check">✓</div>`;
    el.appendChild(d);
  });
  setHonor(S.initialHonor);
  updateOffsetDisplay();
}

function toggleNine(idx) {
  const pos = S.selectedNines.indexOf(idx);
  if (pos >= 0) S.selectedNines.splice(pos,1);
  else { S.selectedNines.push(idx); S.selectedNines.sort((a,b)=>a-b); }
  initSetup();
}

function setHonor(p) {
  S.initialHonor = p;
  document.getElementById('hbtn-V').classList.toggle('sel', p==='V');
  document.getElementById('hbtn-D').classList.toggle('sel', p==='D');
}

function startMatch() {
  if (S.selectedNines.length === 0) { showToast('Select at least one nine'); return; }
  // Preserve settings from setup UI before resetting
  const savedOffset = S.startOffset || 0;
  const savedHonor = S.initialHonor;
  S = freshState();
  S.startOffset = savedOffset;
  S.initialHonor = savedHonor;
  S.selectedNines = [];
  document.querySelectorAll('.nine-opt.sel').forEach(el => {
    S.selectedNines.push(parseInt(el.id.split('-')[2]));
  });
  S.selectedNines.sort((a,b)=>a-b);
  if (S.selectedNines.length === 0) { showToast('Select at least one nine'); return; }
  S.initialHonor = document.querySelector('.hbtn.sel').id === 'hbtn-V' ? 'V' : 'D';
  S.holes = [];
  S.selectedNines.forEach(ni => S.holes.push(...COURSE.nines[ni].holes));
  S.inProgress = true;
  saveState();
  showHole(0);
  showScreen('screen-hole');
}

// ═══════════════════════════════════════════
// HOLE SCREEN
// ═══════════════════════════════════════════
function showHole(idx) {
  const hole = S.holes[idx];
  if (!hole) { showSummary(); return; }

  // Compute strokes if entering a new nine
  if (isNineStart(idx)) computeStrokesForNine(idx);

  const strokes = S.strokeMap[idx] || {v:false, d:false};

  // Default scores to bogey
  S.curV = hole.par + 1;
  S.curD = hole.par + 1;

  // Hole info
  document.getElementById('hole-nine').textContent = nineForIdx(idx)?.name || '';
  document.getElementById('hole-num').textContent = `Hole ${hole.number}`;
  document.getElementById('hole-meta').textContent = `Par ${hole.par} · Hdcp ${hole.handicap}`;

  // Honor badge
  document.getElementById('badge-honor').textContent = `🏌️ ${getHonor()} has honor`;

  // Stroke badge
  const sb = document.getElementById('badge-stroke');
  if (strokes.v || strokes.d) {
    sb.textContent = `+ ${strokes.v ? 'V' : 'D'} gets a stroke`;
    sb.style.display = 'inline-flex';
  } else {
    sb.style.display = 'none';
  }

  // Edit button (shown after at least 1 hole recorded)
  document.getElementById('edit-btn').style.display = idx > 0 ? 'block' : 'none';

  updateScoreBar();
  renderScores();
  saveState();
}

function adj(p, d) {
  if (p==='v') S.curV = Math.max(1, S.curV+d);
  else S.curD = Math.max(1, S.curD+d);
  renderScores();
}

function renderScores() {
  const idx = S.results.length;
  const hole = S.holes[idx];
  if (!hole) return;
  document.getElementById('v-num').textContent = S.curV;
  document.getElementById('d-num').textContent = S.curD;
  document.getElementById('v-lbl').textContent = scoreLabel(S.curV, hole.par);
  document.getElementById('d-lbl').textContent = scoreLabel(S.curD, hole.par);
}

function getCurrentNineScore() {
  // Returns running gross vs par for the nine currently being played
  const nextHoleIdx = S.results.length;
  let nineStart = 0, c = 0;
  for (const ni of S.selectedNines) {
    const nineLen = COURSE.nines[ni].holes.length;
    nineStart = c;
    c += nineLen;
    if (nextHoleIdx < c) break;
  }
  let vGross=0, dGross=0, par=0, count=0;
  for (let i=nineStart; i<nextHoleIdx; i++) {
    const r=S.results[i];
    if (!r) break;
    vGross+=r.vGross; dGross+=r.dGross; par+=S.holes[i].par; count++;
  }
  return {vGross, dGross, par, vVsPar:vGross-par, dVsPar:dGross-par, count};
}

function getNineSummary(endIdx) {
  // Find the nine that contains hole endIdx-1 (the nine just completed)
  let nineStart=0, nineName='', c=0;
  for (const ni of S.selectedNines) {
    const nine=COURSE.nines[ni];
    if (endIdx-1 < c+nine.holes.length) { nineStart=c; nineName=nine.name; break; }
    c+=nine.holes.length;
  }
  let vGross=0, dGross=0, par=0;
  for (let i=nineStart; i<endIdx; i++) {
    vGross+=S.results[i].vGross; dGross+=S.results[i].dGross; par+=S.holes[i].par;
  }
  return {nineName, vGross, dGross, par, vVsPar:vGross-par, dVsPar:dGross-par};
}

function fmtVsPar(n) {
  return n>0?`+${n}`:n===0?'E':`${n}`;
}

function updateScoreBar() {
  const ms = matchScore();
  document.getElementById('sb-v').textContent = ms.v;
  document.getElementById('sb-d').textContent = ms.d;
  const m = ms.v - ms.d;
  const lead = document.getElementById('sb-lead');
  const hint = document.getElementById('sb-hint');
  if (m===0) {
    lead.textContent='Even'; lead.style.color='var(--muted)';
    hint.textContent='';
  } else {
    const who = m>0?'V':'D', color = m>0?'var(--green)':'var(--blue)';
    lead.textContent=`${who} +${Math.abs(m)}`; lead.style.color=color;
    const strokes = Math.floor(Math.abs(m)/5);
    const trail = m>0?'D':'V';
    if (strokes>0) hint.textContent=`${trail} gets ${strokes} stroke${strokes>1?'s':''} next 9`;
    else hint.textContent=`${5-(Math.abs(m)%5)} to next stroke`;
  }
  // Running nine score
  const nine = getCurrentNineScore();
  const vNineEl = document.getElementById('sb-v-nine');
  const dNineEl = document.getElementById('sb-d-nine');
  if (nine.count === 0) {
    vNineEl.textContent='–'; dNineEl.textContent='–';
  } else {
    vNineEl.textContent=fmtVsPar(nine.vVsPar);
    dNineEl.textContent=fmtVsPar(nine.dVsPar);
  }
}

function recordHole() {
  const idx = S.results.length;
  const hole = S.holes[idx];
  if (!hole) return;
  const strokes = S.strokeMap[idx] || {v:false, d:false};
  const calc = calcHole(hole, S.curV, S.curD, strokes.v, strokes.d);
  const honor = getHonor();

  S.results.push({
    holeNumber: hole.number,
    par: hole.par,
    vGross: S.curV,
    dGross: S.curD,
    vStroke: strokes.v,
    dStroke: strokes.d,
    vNet: calc.vNet,
    dNet: calc.dNet,
    vPts: calc.vPts,
    dPts: calc.dPts,
    honor,
  });

  showOverlay(hole, calc);
  saveState();
}

function showOverlay(hole, calc) {
  const ms = matchScore();
  const m = ms.v - ms.d;
  document.getElementById('ov-hole').textContent = `Hole ${hole.number}`;

  const w = document.getElementById('ov-winner');
  if (calc.vPts > 0) { w.textContent=`V +${calc.vPts}`; w.style.color='var(--green)'; }
  else if (calc.dPts > 0) { w.textContent=`D +${calc.dPts}`; w.style.color='var(--blue)'; }
  else { w.textContent='Halved'; w.style.color='var(--muted)'; }

  // Scores with net in parens if stroke given
  const vStr = S.results[S.results.length-1];
  let vDisp = vStr.vGross + (vStr.vStroke ? `<span class="stroke-mark">*</span>` : '');
  let dDisp = vStr.dGross + (vStr.dStroke ? `<span class="stroke-mark">*</span>` : '');
  document.getElementById('ov-scores').innerHTML = `V ${vDisp} &nbsp;·&nbsp; D ${dDisp}`;

  // Net detail if stroke applied
  let det = '';
  if (vStr.vStroke) det += `V net ${vStr.vNet}  `;
  if (vStr.dStroke) det += `D net ${vStr.dNet}`;
  document.getElementById('ov-detail').textContent = det.trim();

  const match = document.getElementById('ov-match');
  if (m===0) { match.textContent='Even'; match.style.color='var(--muted)'; }
  else { const who=m>0?'V':'D'; match.textContent=`${who} leads ${Math.abs(m)}`; match.style.color=m>0?'var(--green)':'var(--blue)'; }

  const nextIdx = S.results.length;
  const nextBtn = document.getElementById('ov-next');
  if (nextIdx >= S.holes.length) nextBtn.textContent='View Results →';
  else nextBtn.textContent=`Hole ${S.holes[nextIdx].number} →`;

  // Nine summary — show when we just finished a nine
  const nineSumEl = document.getElementById('ov-nine-sum');
  const nineJustDone = isNineStart(nextIdx) || nextIdx >= S.holes.length;
  if (nineJustDone && nextIdx > 0) {
    const sum = getNineSummary(nextIdx);
    const vStr = fmtVsPar(sum.vVsPar), dStr = fmtVsPar(sum.dVsPar);
    const vColor = sum.vVsPar<0?'var(--green)':sum.vVsPar>0?'var(--red)':'var(--muted)';
    const dColor = sum.dVsPar<0?'var(--green)':sum.dVsPar>0?'var(--red)':'var(--muted)';

    // Count how many nines have been completed
    let ninesCompleted = 0, c = 0;
    for (const ni of S.selectedNines) {
      c += COURSE.nines[ni].holes.length;
      if (nextIdx >= c) ninesCompleted++;
    }

    // Cumulative totals (all holes played so far)
    let cumV=0, cumD=0, cumPar=0;
    for (let i=0; i<nextIdx; i++) {
      cumV+=S.results[i].vGross; cumD+=S.results[i].dGross; cumPar+=S.holes[i].par;
    }
    const cvStr=fmtVsPar(cumV-cumPar), cdStr=fmtVsPar(cumD-cumPar);
    const cvColor=(cumV-cumPar)<0?'var(--green)':(cumV-cumPar)>0?'var(--red)':'var(--muted)';
    const cdColor=(cumD-cumPar)<0?'var(--green)':(cumD-cumPar)>0?'var(--red)':'var(--muted)';
    const cumLabel = nextIdx===18?'18-Hole Total':nextIdx===27?'27-Hole Total':`${nextIdx}-Hole Total`;

    let cumHtml = '';
    if (ninesCompleted >= 2) {
      cumHtml = `
        <div style="border-top:1px solid #374151;margin:12px 0;padding-top:12px">
          <div style="font-size:12px;color:var(--muted);margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">${cumLabel}</div>
          <div style="display:flex;justify-content:space-around">
            <div style="text-align:center">
              <div style="font-size:28px;font-weight:900;color:var(--green)">${cumV}</div>
              <div style="font-size:13px;color:var(--muted)">V &nbsp;<span style="color:${cvColor};font-weight:700">${cvStr}</span></div>
            </div>
            <div style="text-align:center">
              <div style="font-size:28px;font-weight:900;color:var(--blue)">${cumD}</div>
              <div style="font-size:13px;color:var(--muted)">D &nbsp;<span style="color:${cdColor};font-weight:700">${cdStr}</span></div>
            </div>
          </div>
        </div>`;
    }

    nineSumEl.innerHTML = `
      <div style="border-top:1px solid #374151;margin:14px 0;padding-top:14px">
        <div style="font-size:12px;color:var(--muted);margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">${sum.nineName} Complete</div>
        <div style="display:flex;justify-content:space-around">
          <div style="text-align:center">
            <div style="font-size:28px;font-weight:900;color:var(--green)">${sum.vGross}</div>
            <div style="font-size:13px;color:var(--muted)">V &nbsp;<span style="color:${vColor};font-weight:700">${vStr}</span></div>
          </div>
          <div style="text-align:center">
            <div style="font-size:28px;font-weight:900;color:var(--blue)">${sum.dGross}</div>
            <div style="font-size:13px;color:var(--muted)">D &nbsp;<span style="color:${dColor};font-weight:700">${dStr}</span></div>
          </div>
        </div>
      </div>${cumHtml}`;
    nineSumEl.style.display='block';
  } else {
    nineSumEl.style.display='none';
  }

  document.getElementById('overlay').style.display='flex';
}

function nextHole() {
  document.getElementById('overlay').style.display='none';
  const idx = S.results.length;
  if (idx >= S.holes.length) { showSummary(); return; }
  showHole(idx);
}

function showEditOverlay() {
  document.getElementById('overlay').style.display='none';
  const list = document.getElementById('edit-hole-list');
  list.innerHTML = '';
  S.results.forEach((r, idx) => {
    const vStr = scoreLabel(r.vGross, r.par);
    const dStr = scoreLabel(r.dGross, r.par);
    const btn = document.createElement('button');
    btn.style.cssText='width:100%;text-align:left;background:#111827;border:1px solid #374151;border-radius:10px;padding:12px 14px;margin-bottom:8px;cursor:pointer;color:#f9fafb;font-size:14px;';
    btn.innerHTML=`<span style="font-weight:700">Hole ${r.holeNumber}</span> <span style="color:#9ca3af">Par ${r.par}</span>
      <span style="float:right"><span style="color:#22c55e">V ${r.vGross} (${vStr})</span> &nbsp;·&nbsp; <span style="color:#60a5fa">D ${r.dGross} (${dStr})</span></span>`;
    btn.onclick = () => goBackToHole(idx);
    list.appendChild(btn);
  });
  document.getElementById('edit-overlay').style.display='flex';
}

function goBackToHole(targetIdx) {
  // Clear stroke data for any nine that starts at or after targetIdx
  S.strokesComputedAt = S.strokesComputedAt.filter(nineStart => {
    if (nineStart >= targetIdx) {
      // Clear stroke map entries for this nine
      let c=0;
      for (const ni of S.selectedNines) {
        if (c===nineStart) {
          COURSE.nines[ni].holes.forEach(h => {
            const hi=S.holes.findIndex(hh=>hh.number===h.number);
            if (hi>=0) delete S.strokeMap[hi];
          });
          break;
        }
        c+=COURSE.nines[ni].holes.length;
      }
      return false;
    }
    return true;
  });
  S.results = S.results.slice(0, targetIdx);
  document.getElementById('edit-overlay').style.display='none';
  saveState();
  showHole(targetIdx);
}

function endMatchEarly() {
  if (S.results.length===0) { showToast('No holes recorded yet'); return; }
  document.getElementById('overlay').style.display='none';
  showSummary();
}

// ═══════════════════════════════════════════
// SUMMARY SCREEN
// ═══════════════════════════════════════════
function showSummary() {
  S.inProgress = false;
  saveState();
  showScreen('screen-summary');

  const ms = matchScore();
  const m = ms.v - ms.d;
  document.getElementById('sum-date').textContent = S.date;
  document.getElementById('sum-v').textContent = ms.v;
  document.getElementById('sum-d').textContent = ms.d;

  const banner = document.getElementById('win-banner');
  const marginEl = document.getElementById('sum-margin');
  if (m>0) {
    banner.textContent=`🏆 V wins by ${m}!`; banner.style.color='var(--green)';
    marginEl.textContent=`V +${m}`; marginEl.style.color='var(--green)';
  } else if (m<0) {
    banner.textContent=`🏆 D wins by ${Math.abs(m)}!`; banner.style.color='var(--blue)';
    marginEl.textContent=`D +${Math.abs(m)}`; marginEl.style.color='var(--blue)';
  } else {
    banner.textContent='All Square! 🤝'; banner.style.color='var(--gold)';
    marginEl.textContent='Even'; marginEl.style.color='var(--muted)';
  }

  // Build table
  const tbl = document.getElementById('hole-tbl');
  tbl.innerHTML = `<tr><th>Hole</th><th>Par</th><th style="color:var(--green)">V</th><th style="color:var(--blue)">D</th><th style="color:var(--green)">V+</th><th style="color:var(--blue)">D+</th><th>Lead</th></tr>`;
  let vRun=0, dRun=0;
  S.results.forEach(r => {
    vRun+=r.vPts; dRun+=r.dPts;
    const lead = vRun-dRun;
    const leadStr = lead>0?`<span class="pv">V${lead}</span>`:lead<0?`<span class="pd">D${Math.abs(lead)}</span>`:'–';
    const vs = r.vGross + (r.vStroke?'<sup style="color:var(--gold);font-size:9px">*</sup>':'');
    const ds = r.dGross + (r.dStroke?'<sup style="color:var(--gold);font-size:9px">*</sup>':'');
    const vp = r.vPts>0?`<span class="pv">+${r.vPts}</span>`:'–';
    const dp = r.dPts>0?`<span class="pd">+${r.dPts}</span>`:'–';
    tbl.innerHTML += `<tr><td>${r.holeNumber}</td><td>${r.par}</td><td>${vs}</td><td>${ds}</td><td>${vp}</td><td>${dp}</td><td>${leadStr}</td></tr>`;
  });
  tbl.innerHTML += `<tr class="total-row"><td colspan="4">Total</td><td class="pv">${ms.v}</td><td class="pd">${ms.d}</td><td></td></tr>`;

  document.getElementById('save-btn').textContent = 'Save to History';
  document.getElementById('save-btn').disabled = false;
}

async function saveMatch() {
  const ms = matchScore();
  const m = ms.v - ms.d;
  const payload = {
    date: S.date,
    nines: S.selectedNines.map(i => COURSE.nines[i].name),
    holes_played: S.holes.length,
    v_points: ms.v,
    d_points: ms.d,
    margin: m,
    winner: m>0?'V':m<0?'D':'Tie',
    hole_results: S.results,
  };
  try {
    const r = await fetch('/api/match', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if (r.ok) {
      document.getElementById('save-btn').textContent='✓ Saved!';
      document.getElementById('save-btn').disabled=true;
      localStorage.removeItem('vd-golf-state');
      showToast('Saved to history!');
    } else showToast('Save failed');
  } catch { showToast('No connection — save when online'); }
}

function resumeMatch() {
  const idx = S.results.length;
  if (idx < S.holes.length) { showScreen('screen-hole'); showHole(idx); }
  else showSummary();
}

function adjOffset(d) {
  S.startOffset = (S.startOffset || 0) + d;
  updateOffsetDisplay();
  saveState();
}

function updateOffsetDisplay() {
  const o = S.startOffset || 0;
  const el = document.getElementById('offset-display');
  if (!el) return;
  if (o === 0) { el.textContent='Even'; el.style.color='var(--muted)'; }
  else if (o > 0) { el.textContent=`V+${o}`; el.style.color='var(--green)'; }
  else { el.textContent=`D+${Math.abs(o)}`; el.style.color='var(--blue)'; }
}

function deleteMatch() {
  S = freshState();
  saveState();
  initSetup();
}

function abandonMatch() {
  S = freshState();
  saveState();
  initSetup();
}

function newMatch() {
  S = freshState();
  saveState();
  initSetup();
  showScreen('screen-setup');
}

// ═══════════════════════════════════════════
// HISTORY SCREEN
// ═══════════════════════════════════════════
async function showHistory() {
  showScreen('screen-history');
  const body = document.getElementById('history-body');
  body.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px">Loading…</div>';
  try {
    const r = await fetch('/api/matches');
    const matches = await r.json();
    renderHistory(matches);
  } catch {
    body.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px">Could not load — check connection</div>';
  }
}

function renderHistory(matches) {
  const body = document.getElementById('history-body');
  if (!matches.length) { body.innerHTML='<div style="color:var(--muted);text-align:center;padding:40px">No matches yet</div>'; return; }

  let vW=0,dW=0,ties=0;
  matches.forEach(m => { if(m.winner==='V')vW++; else if(m.winner==='D')dW++; else ties++; });

  let html = `<div class="card"><h3>Head to Head</h3>
    <div style="display:flex;justify-content:space-around;text-align:center;padding:8px 0">
      <div><div style="font-size:32px;font-weight:900;color:var(--green)">${vW}</div><div style="color:var(--muted);font-size:13px">V Wins</div></div>
      <div><div style="font-size:32px;font-weight:900;color:var(--muted)">${ties}</div><div style="color:var(--muted);font-size:13px">Ties</div></div>
      <div><div style="font-size:32px;font-weight:900;color:var(--blue)">${dW}</div><div style="color:var(--muted);font-size:13px">D Wins</div></div>
    </div></div>
  <div class="card" style="overflow-x:auto"><h3>Matches</h3>
  <table class="htbl"><tr><th>Date</th><th>Nines</th><th style="color:var(--green)">V</th><th style="color:var(--blue)">D</th><th>Result</th></tr>`;

  [...matches].reverse().forEach(m => {
    const res = m.winner==='V'?`<span class="pv">V +${m.margin}</span>`:m.winner==='D'?`<span class="pd">D +${Math.abs(m.margin)}</span>`:'Tie';
    html += `<tr><td>${m.date}</td><td style="font-size:11px">${(m.nines||[]).join(', ')}</td><td>${m.v_points}</td><td>${m.d_points}</td><td>${res}</td></tr>`;
  });
  html += '</table></div>';
  body.innerHTML = html;
}

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0,0);
}

function showToast(msg) {
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}

function saveState() { localStorage.setItem('vd-golf',JSON.stringify(S)); }
function loadState() { try { const s=localStorage.getItem('vd-golf'); return s?JSON.parse(s):null; } catch{return null;} }

// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════
// Always land on setup screen — match status card shows if a match is in progress
if (!S.inProgress) S = freshState();
showScreen('screen-setup');
initSetup();

if ('serviceWorker' in navigator) {
  // Unregister old SW versions, then register fresh
  navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(r => r.unregister());
  }).finally(() => {
    navigator.serviceWorker.register('/sw.js').catch(()=>{});
  });
}
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# History page (desktop-friendly, served at /history)
# ---------------------------------------------------------------------------
HISTORY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VD Golf — History</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#111827;color:#f9fafb;min-height:100vh}
.header{background:#1f2937;border-bottom:1px solid #374151;padding:20px 32px;display:flex;align-items:center;gap:16px}
.header h1{font-size:22px;font-weight:800}
.header a{color:#9ca3af;text-decoration:none;font-size:14px;margin-left:auto}
.wrap{max-width:900px;margin:0 auto;padding:24px 20px}
.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:20px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#9ca3af;margin-bottom:16px}
.stats{display:flex;gap:0}
.stat{flex:1;text-align:center;padding:12px;border-right:1px solid #374151}
.stat:last-child{border-right:none}
.stat .num{font-size:40px;font-weight:900}
.stat .lbl{font-size:13px;color:#9ca3af;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{background:#0d1520;padding:10px 12px;text-align:left;color:#9ca3af;font-size:12px;font-weight:700}
td{padding:10px 12px;border-bottom:1px solid #1e2a3a}
tr:last-child td{border-bottom:none}
.pv{color:#22c55e;font-weight:700} .pd{color:#60a5fa;font-weight:700}
canvas{max-height:220px}
</style>
</head>
<body>
<div class="header">
  <div>⛳</div>
  <h1>VD Golf — Match History</h1>
  <a href="/">← Scoring App</a>
</div>
<div class="wrap">
  <div id="content"><p style="color:#9ca3af;text-align:center;padding:60px">Loading…</p></div>
</div>
<script>
fetch('/api/matches').then(r=>r.json()).then(render).catch(()=>{
  document.getElementById('content').innerHTML='<p style="color:#ef4444;text-align:center;padding:60px">Could not load match data</p>';
});

function render(matches) {
  if (!matches.length) {
    document.getElementById('content').innerHTML='<p style="color:#9ca3af;text-align:center;padding:60px">No matches yet — play some golf!</p>';
    return;
  }
  let vW=0,dW=0,ties=0,vPtsTotal=0,dPtsTotal=0;
  const labels=[], vCum=[], dCum=[];
  let vRun=0,dRun=0;
  matches.forEach(m=>{
    if(m.winner==='V')vW++; else if(m.winner==='D')dW++; else ties++;
    vPtsTotal+=m.v_points; dPtsTotal+=m.d_points;
    vRun+=m.v_points; dRun+=m.d_points;
    labels.push(m.date);
    vCum.push(vRun); dCum.push(dRun);
  });
  const avgMargin = matches.reduce((s,m)=>s+Math.abs(m.margin),0)/matches.length;

  document.getElementById('content').innerHTML = `
  <div class="card">
    <h2>Head to Head</h2>
    <div class="stats">
      <div class="stat"><div class="num pv">${vW}</div><div class="lbl">V Wins</div></div>
      <div class="stat"><div class="num" style="color:#9ca3af">${ties}</div><div class="lbl">Ties</div></div>
      <div class="stat"><div class="num pd">${dW}</div><div class="lbl">D Wins</div></div>
      <div class="stat"><div class="num" style="color:#f59e0b">${matches.length}</div><div class="lbl">Matches</div></div>
      <div class="stat"><div class="num" style="font-size:28px">${avgMargin.toFixed(1)}</div><div class="lbl">Avg Margin</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Cumulative Points</h2>
    <canvas id="chart"></canvas>
  </div>

  <div class="card">
    <h2>Match Log</h2>
    <table>
      <tr><th>Date</th><th>Nines</th><th>Holes</th><th>V Pts</th><th>D Pts</th><th>Result</th></tr>
      ${[...matches].reverse().map(m=>{
        const res=m.winner==='V'?`<span class="pv">V +${m.margin}</span>`:m.winner==='D'?`<span class="pd">D +${Math.abs(m.margin)}</span>`:'Tie';
        return `<tr><td>${m.date}</td><td>${(m.nines||[]).join(', ')}</td><td>${m.holes_played}</td><td class="pv">${m.v_points}</td><td class="pd">${m.d_points}</td><td>${res}</td></tr>`;
      }).join('')}
    </table>
  </div>`;

  new Chart(document.getElementById('chart'), {
    type:'line',
    data:{
      labels,
      datasets:[
        {label:'V',data:vCum,borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.1)',tension:.3,fill:false,pointRadius:4},
        {label:'D',data:dCum,borderColor:'#60a5fa',backgroundColor:'rgba(96,165,250,.1)',tension:.3,fill:false,pointRadius:4}
      ]
    },
    options:{responsive:true,plugins:{legend:{labels:{color:'#9ca3af'}}},scales:{x:{ticks:{color:'#9ca3af'},grid:{color:'#1e2a3a'}},y:{ticks:{color:'#9ca3af'},grid:{color:'#1e2a3a'}}}}
  });
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._send(200, 'text/html', PWA_HTML)
        elif self.path == '/sw.js':
            self._send(200, 'application/javascript', SW_JS)
        elif self.path == '/history':
            self._send(200, 'text/html', HISTORY_HTML)
        elif self.path == '/api/matches':
            self._send(200, 'application/json', json.dumps(load_matches()))
        else:
            self._send(404, 'text/plain', 'Not found')

    def do_POST(self):
        if self.path == '/api/match':
            n = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(n))
            save_match(body)
            self._send(200, 'application/json', '{"ok":true}')
        else:
            self._send(404, 'text/plain', 'Not found')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _send(self, code, ctype, body):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(data))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a): pass


if __name__ == '__main__':
    print(f'VD Golf Match server → http://localhost:{PORT}')
    HTTPServer(('', PORT), Handler).serve_forever()
