#!/usr/bin/env python3
"""Golf Log — personal golf tracking PWA + VD match scoring"""

import json, os, math, base64
from collections import defaultdict
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Golf flag icon (180×180 PNG — dark green background, white flag, PIL-generated)
ICON_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAIAAACyr5FlAAACxUlEQVR4nO3bsXFcNxRA"
    "UcrjKoQO5Jbk6lSTSkAfDqBAMnmpJbXc3f9xTviQILjzEgw+ff765Qle8teLUxAHrxEH"
    "SRwkcZDEQRIHSRwkcZDEQRIHSRwkcZDEQRIHSRwkcZDEQRIHSRwkcZDEQRIHSRwkcZDE"
    "QRIHSRwkcZD+fjqp+e37/ybj33/udJej2mhzzG/fnxfDKzaKY5HI5baLY5HIJTaNY5HI"
    "67aOY5FIEccPEnlOHL+QyM/E8QKJLOJIc/tExPEbc+NExHGRuWUi4niDuVki4nizuU0i"
    "4ninuUEf4ni/efYVIo4/Nc+biDiuY54xEXFc0zxXIuK4vnmWRMTxUebxExHHx5pHTkQc"
    "tzCPmYg4bmceLRFx3No8TiLiuI95hETEcU/zsRMRx/3NR01EHI9iPl4ip/1IfTjj8f55"
    "i+P+xuNlsYjjnsajZrGI4z7GY2exiOPWxhGyWMRxO+M4WSziuIVxtCwWcXysccwsFnF8"
    "lHHkLBZxXN84fhaLOK5pnCWLRRzXMc6VxSKOPzXOmMUijvcb581i8WT/TuPsZdgc7zE2"
    "yGIRxxuMbbJYxHGRsVkWizh+Y2yZxSKONDbOYhHHC2SxiOMXsviZOH6QxXPikEXaOg5Z"
    "vG7TOGRxie3ikMXlNopDFm/lVZYkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4"
    "SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMk"
    "DpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIgiYMkDpI4SOIg"
    "iYMkDpI4SOIgiYMkDpI4SOIgffr89UufsjWbgyQOkjhI4iCJgyQOkjhI4iCJgyQOkjhI"
    "4iCJgyQOkjhI4iCJgyQOkjhI4iCJgyQOkjhI4iCJgyQOkjhI4iCJgyQOkjhI4uCp/Afh"
    "r5mufl+wVgAAAABJRU5ErkJggg=="
)

PORT         = int(os.environ.get('PORT', 8052))
ROUNDS_FILE  = os.path.join(os.path.dirname(__file__), 'ghin_rounds.json')
COURSES_FILE = os.path.join(os.path.dirname(__file__), 'courses.json')
MATCHES_FILE = os.path.join(os.path.dirname(__file__), 'vd_matches.json')


# ---------------------------------------------------------------------------
# Date helper
# ---------------------------------------------------------------------------
def parse_date(s):
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return date.min


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def load_rounds():  return load_json(ROUNDS_FILE)
def load_courses(): return load_json(COURSES_FILE)
def load_matches(): return load_json(MATCHES_FILE)

def save_round(r):
    rounds = load_rounds()
    new_id = max((x['id'] for x in rounds), default=0) + 1
    r['id'] = new_id
    if r.get('rating') and r.get('slope') and r.get('adj_score') is not None:
        r['differential'] = round((r['adj_score'] - r['rating']) * 113 / r['slope'], 1)
    rounds.append(r)
    save_json(ROUNDS_FILE, rounds)
    return r

def save_course(c):
    courses = load_courses()
    courses.append(c)
    save_json(COURSES_FILE, courses)

def append_match(m):
    matches = load_matches()
    matches.append(m)
    save_json(MATCHES_FILE, matches)


# ---------------------------------------------------------------------------
# Handicap calculations
# ---------------------------------------------------------------------------
def get_handicap_data():
    rounds = load_rounds()
    posted = [r for r in rounds
              if r.get('include_ghin') and r.get('differential') is not None]
    posted.sort(key=lambda r: parse_date(r['date']))

    last_20 = posted[-20:]
    diffs   = [r['differential'] for r in last_20]
    n       = len(diffs)

    index = anti_idx = target_diff = None
    if n >= 8:
        sd        = sorted(diffs)
        index     = round(sum(sd[:8]) / 8, 1)
        anti_idx  = round(sum(sd[-8:]) / 8, 1)
        best_8    = sd[:8]
        oldest_d  = last_20[0]['differential']
        target_diff = oldest_d if oldest_d in best_8 else max(best_8)
    elif n >= 1:
        index = round(sum(diffs) / n, 1)

    # Rolling index series for chart
    series = []
    for i, r in enumerate(posted):
        w  = posted[max(0, i - 19):i + 1]
        wd = sorted(x['differential'] for x in w)
        idx_after = round(sum(wd[:8]) / 8, 1) if len(wd) >= 8 else round(sum(wd) / len(wd), 1)
        series.append({
            'date': r['date'], 'differential': r['differential'],
            'index_after': idx_after, 'course': r.get('course_name', ''),
        })

    # Yearly averages
    by_year = defaultdict(list)
    for r in posted:
        try:
            yr = str(parse_date(r['date']).year)
        except Exception:
            yr = r['date'][:4]
        by_year[yr].append(r['differential'])
    yearly_avgs = [{'year': y, 'avg': round(sum(d) / len(d), 1)}
                   for y, d in sorted(by_year.items())]

    # GHIN manual series
    ghin_series = [{'date': r['date'], 'ghin': r['ghin_manual']}
                   for r in posted if r.get('ghin_manual') is not None]

    last_20_avg = round(sum(diffs) / n, 1) if n else None
    cy = str(date.today().year)
    yr_diffs = [r['differential'] for r in posted
                if str(parse_date(r['date']).year) == cy]
    year_avg = round(sum(yr_diffs) / len(yr_diffs), 1) if yr_diffs else None

    # Budget: target_diff on most recent 18-hole posted course
    budget = target_course = None
    if target_diff is not None:
        for r in reversed(posted):
            if not r.get('nine_hole') and r.get('rating') and r.get('slope'):
                par    = r.get('par', 72)
                budget = math.floor(r['rating'] + target_diff * r['slope'] / 113) - par
                target_course = r.get('course_name', '')
                break

    return {
        'index': index, 'anti_index': anti_idx, 'target_diff': target_diff,
        'budget': budget, 'target_course': target_course,
        'last_20_avg': last_20_avg, 'year_avg': year_avg,
        'series': series, 'yearly_avgs': yearly_avgs, 'ghin_series': ghin_series,
        'n_posted': len(posted), 'n_last_20': n,
    }


MANIFEST_JSON = json.dumps({
    "name": "Golf Log",
    "short_name": "Golf Log",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#111827",
    "theme_color": "#111827",
    "icons": [
        {"src": "/icon.png", "sizes": "180x180", "type": "image/png"}
    ]
})

# ---------------------------------------------------------------------------
# Service Worker
# ---------------------------------------------------------------------------
SW_JS = """
const CACHE = 'golf-log-v4';
const CORE = ['/', '/icon.png', '/manifest.json'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)));
  self.skipWaiting();
});
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(
    keys.filter(k => k !== CACHE).map(k => caches.delete(k))
  )).then(() => clients.claim())
));
self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) return;
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
      if (resp.ok) caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
      return resp;
    }))
  );
});
"""

# ---------------------------------------------------------------------------
# PWA HTML — filled in below
# ---------------------------------------------------------------------------
PWA_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Golf Log">
<title>Golf Log</title>
<link rel="apple-touch-icon" sizes="180x180" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{--green:#22c55e;--red:#ef4444;--blue:#60a5fa;--gold:#f59e0b;--saffron:#FF9933;--bg:#111827;--card:#1f2937;--border:#374151;--text:#f9fafb;--muted:#9ca3af}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--text);min-height:100svh}
/* tabs */
.tab{display:none;max-width:440px;margin:0 auto;padding-bottom:76px;overflow-y:auto}
.tab.active{display:block}
/* fullscreen overlays (hole entry, summary) */
.fullscreen{display:none;position:fixed;inset:0;background:var(--bg);z-index:40;overflow-y:auto;padding-bottom:76px;max-width:440px;margin:0 auto}
.fullscreen.open{display:block}
/* bottom tab nav */
.tabnav{position:fixed;bottom:0;left:0;right:0;z-index:50;background:var(--card);border-top:1px solid var(--border);display:flex;padding-bottom:env(safe-area-inset-bottom)}
.tnbtn{flex:1;padding:9px 4px 7px;background:none;border:none;color:var(--muted);font-size:10px;font-weight:600;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px;transition:color .15s;letter-spacing:.3px}
.tnbtn .ti{font-size:20px}
.tnbtn.active{color:var(--green)}
/* cards */
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;margin:10px 14px}
.card h3{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:10px}
/* top bar */
.topbar{background:var(--card);border-bottom:1px solid var(--border);padding:10px 16px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:20}
.topbar h1{font-size:18px;font-weight:800}
/* score bar */
.sbar{display:flex;align-items:center;justify-content:space-between;background:var(--card);border-bottom:1px solid var(--border);padding:10px 20px}
.sbar-player{text-align:center;min-width:64px}
.sbar-pts{font-size:28px;font-weight:800}
.sbar-label{font-size:11px;color:var(--muted);margin-top:1px}
.sbar-nine{font-size:12px;color:var(--muted);margin-top:3px;font-weight:600}
.sbar-mid{flex:1;text-align:center}
.sbar-lead{font-size:16px;font-weight:700;color:var(--gold)}
.sbar-hint{font-size:11px;color:var(--muted);margin-top:2px}
/* budget bar */
.budget-wrap{padding:8px 14px;background:var(--card);border-bottom:1px solid var(--border)}
.budget-lbl{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:5px}
.budget-track{background:#374151;border-radius:4px;height:7px;overflow:hidden}
.budget-fill{height:100%;border-radius:4px;transition:width .3s,background .3s;background:var(--green)}
/* nine picker buttons */
.nine-row{display:flex;gap:9px;margin-top:8px}
.nine-btn{flex:1;padding:13px 6px;border-radius:10px;border:2px solid var(--border);background:transparent;color:var(--text);font-size:15px;font-weight:700;cursor:pointer;transition:all .15s}
.nine-btn.sel{border-color:var(--green);background:rgba(34,197,94,.1);color:var(--green)}
/* course select */
select.course-sel{width:100%;padding:11px;background:#1e2a3a;border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;margin-top:4px}
/* toggle switch */
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:2px 0}
.toggle-lbl{font-size:15px;font-weight:600}
.tgl{position:relative;width:48px;height:28px;flex-shrink:0}
.tgl input{opacity:0;width:0;height:0}
.tgl-slider{position:absolute;inset:0;background:#374151;border-radius:14px;cursor:pointer;transition:.3s}
.tgl-slider:before{content:'';position:absolute;height:22px;width:22px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
.tgl input:checked+.tgl-slider{background:var(--green)}
.tgl input:checked+.tgl-slider:before{transform:translateX(20px)}
/* honor / offset */
.honor-row{display:flex;gap:10px;margin-top:6px}
.hbtn{flex:1;padding:12px;border-radius:10px;border:2px solid var(--border);background:transparent;color:var(--text);font-size:20px;font-weight:800;cursor:pointer;transition:all .15s}
.hbtn.sel{border-color:var(--gold);background:rgba(245,158,11,.1);color:var(--gold)}
/* score entry */
.entry{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px 16px;margin:6px 14px}
.entry-name{font-size:14px;font-weight:700;margin-bottom:10px}
.entry-row{display:flex;align-items:center;justify-content:center;gap:22px}
.sbtn{width:58px;height:58px;border-radius:50%;border:none;font-size:30px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform .1s}
.sbtn:active{transform:scale(.88)}
.sbtn.minus{background:#374151;color:var(--text)}
.sbtn.plus{background:var(--blue);color:#fff}
.snum{font-size:50px;font-weight:900;min-width:54px;text-align:center;line-height:1}
.slabel{font-size:13px;color:var(--muted);text-align:center;margin-top:3px}
/* buttons */
.btn{width:calc(100% - 28px);margin:7px 14px;padding:16px;border-radius:12px;border:none;font-size:16px;font-weight:700;cursor:pointer;transition:transform .1s}
.btn:active{transform:scale(.97)}
.btn-green{background:var(--green);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-red{background:transparent;border:1px solid var(--red);color:var(--red)}
/* hole info */
.hole-hdr{display:flex;justify-content:space-between;align-items:flex-start}
.hole-nine{font-size:12px;color:var(--blue);font-weight:600;margin-bottom:2px}
.hole-num{font-size:32px;font-weight:900}
.hole-meta{font-size:14px;color:var(--muted);margin-top:3px}
.badges{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
.badge{display:inline-flex;align-items:center;gap:5px;border-radius:20px;padding:5px 12px;font-size:12px;font-weight:600}
.badge-honor{background:rgba(245,158,11,.12);border:1px solid var(--gold);color:var(--gold)}
.badge-stroke{background:rgba(96,165,250,.12);border:1px solid var(--blue);color:var(--blue)}
/* result overlay */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;z-index:100;padding:20px}
.overlay-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:28px 22px;width:100%;max-width:360px;text-align:center}
.ov-hole{font-size:13px;color:var(--muted);margin-bottom:6px}
.ov-winner{font-size:34px;font-weight:900;margin-bottom:4px}
.ov-scores{font-size:14px;color:var(--muted);margin-bottom:6px}
.ov-match{font-size:20px;font-weight:700;color:var(--gold);margin-bottom:20px}
.ov-detail{font-size:12px;color:var(--muted);margin-bottom:14px}
/* summary */
.win-banner{font-size:26px;font-weight:900;text-align:center;padding:18px 16px 6px}
.stat-row{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--border);font-size:14px}
.stat-row:last-child{border-bottom:none}
.stat-lbl{color:var(--muted)}
.stat-val{font-weight:700}
/* hole table */
.htbl{width:100%;border-collapse:collapse;font-size:12px}
.htbl th{background:#0d1520;padding:6px 4px;text-align:center;color:var(--muted);font-size:10px;font-weight:700;position:sticky;top:0}
.htbl td{padding:6px 4px;text-align:center;border-bottom:1px solid #1e2a3a}
.htbl tr:last-child td{border-bottom:none}
.htbl .total-row td{font-weight:800;background:#0d1520}
.pv{color:var(--saffron);font-weight:700} .pd{color:var(--green);font-weight:700}
.stroke-mark{font-size:9px;color:var(--gold);vertical-align:super}
/* resume card */
.resume-card{margin:10px 14px;background:var(--card);border:2px solid var(--gold);border-radius:14px;padding:14px}
/* handicap stat cards */
.stat-cards{display:flex;gap:8px;padding:10px 14px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.stat-card{flex:0 0 auto;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;min-width:88px;text-align:center}
.sc-val{font-size:22px;font-weight:900;line-height:1.1}
.sc-lbl{font-size:9px;color:var(--muted);margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
/* chart */
.chart-wrap{height:180px;position:relative;margin-top:8px}
/* courses list */
.course-item{display:flex;justify-content:space-between;align-items:center;padding:11px 0;border-bottom:1px solid var(--border)}
.course-item:last-child{border-bottom:none}
.course-name{font-size:14px;font-weight:600}
.course-sub{font-size:12px;color:var(--muted);margin-top:2px}
/* input */
input[type=text],input[type=number]{width:100%;padding:11px;background:#1e2a3a;border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;margin-bottom:10px}
/* toast */
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;z-index:200;opacity:0;transition:opacity .3s;pointer-events:none;white-space:nowrap}
.toast.show{opacity:1}
</style>
</head>
<body>

<!-- ═══════════ SCORE TAB ═══════════ -->
<div id="tab-score" class="tab active">
  <div class="topbar"><h1>⛳ Golf Log</h1><div style="font-size:12px;color:var(--muted)" id="score-date"></div></div>

  <!-- Resume card -->
  <div id="resume-card" class="resume-card" style="display:none">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--gold);margin-bottom:8px">Round in Progress</div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <div id="rc-lead" style="font-size:20px;font-weight:900"></div>
      <div id="rc-holes" style="font-size:12px;color:var(--muted);text-align:right"></div>
    </div>
    <button class="btn btn-green" onclick="resumeRound()" style="margin:0 0 6px">Resume Round</button>
    <button class="btn btn-red" onclick="deleteRound()" style="margin:0;font-size:13px;padding:9px">Delete Round</button>
  </div>

  <!-- Governors Club nine picker -->
  <div class="card">
    <h3>Governors Club — Select Nines</h3>
    <div class="nine-row">
      <button id="nine-btn-0" class="nine-btn" onclick="toggleNineBtn(0)">Lakes</button>
      <button id="nine-btn-1" class="nine-btn" onclick="toggleNineBtn(1)">Foothills</button>
      <button id="nine-btn-2" class="nine-btn" onclick="toggleNineBtn(2)">Mountain</button>
    </div>
  </div>

  <!-- Other course -->
  <div class="card">
    <h3>Or Other Course</h3>
    <select class="course-sel" id="other-course-sel" onchange="selectOtherCourse()">
      <option value="">— pick a course —</option>
    </select>
  </div>

  <!-- VD Match toggle -->
  <div class="card">
    <div class="toggle-row">
      <span class="toggle-lbl">VD Match</span>
      <label class="tgl"><input type="checkbox" id="vd-toggle" onchange="toggleVD()"><span class="tgl-slider"></span></label>
    </div>
    <div id="vd-opts" style="display:none;margin-top:12px">
      <h3>Honor on Hole 1</h3>
      <div class="honor-row">
        <button class="hbtn sel" id="hbtn-V" onclick="setHonor('V')">V</button>
        <button class="hbtn" id="hbtn-D" onclick="setHonor('D')">D</button>
      </div>
      <h3 style="margin-top:14px">Starting Score</h3>
      <div style="display:flex;align-items:center;justify-content:center;gap:22px;padding:4px 0">
        <button class="sbtn minus" onclick="adjOffset(-1)">−</button>
        <div style="text-align:center">
          <div style="font-size:30px;font-weight:900" id="offset-display">D+1</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">carry-in pts</div>
        </div>
        <button class="sbtn plus" onclick="adjOffset(1)">+</button>
      </div>
    </div>
  </div>

  <button class="btn btn-green" onclick="startRound()">Start Round</button>
</div>

<!-- ═══════════ HANDICAP TAB ═══════════ -->
<div id="tab-handicap" class="tab">
  <div class="topbar"><h1>📊 Handicap</h1></div>
  <div class="stat-cards" id="hcp-stats">
    <div class="stat-card"><div class="sc-val" id="hcp-index">—</div><div class="sc-lbl">Index</div></div>
    <div class="stat-card"><div class="sc-val" id="hcp-target">—</div><div class="sc-lbl">Target Diff</div></div>
    <div class="stat-card"><div class="sc-val" id="hcp-anti">—</div><div class="sc-lbl">Anti-Index</div></div>
    <div class="stat-card"><div class="sc-val" id="hcp-l20avg">—</div><div class="sc-lbl">Last 20 Avg</div></div>
    <div class="stat-card"><div class="sc-val" id="hcp-yravg">—</div><div class="sc-lbl">Year Avg</div></div>
  </div>
  <div id="hcp-budget-info" class="card" style="display:none">
    <div style="font-size:13px;color:var(--muted)" id="hcp-budget-txt"></div>
  </div>
  <div class="card">
    <h3>Differential Per Round</h3>
    <div class="chart-wrap"><canvas id="chart-diff"></canvas></div>
  </div>
  <div class="card">
    <h3>Calculated Index Over Time</h3>
    <div class="chart-wrap"><canvas id="chart-index"></canvas></div>
  </div>
  <div class="card">
    <h3>GHIN Index (Manual)</h3>
    <div class="chart-wrap"><canvas id="chart-ghin"></canvas></div>
  </div>
  <div class="card">
    <h3>Yearly Average Differential</h3>
    <div class="chart-wrap"><canvas id="chart-yearly"></canvas></div>
  </div>
</div>

<!-- ═══════════ HISTORY TAB ═══════════ -->
<div id="tab-history" class="tab">
  <div class="topbar"><h1>📋 History</h1><a href="/history" style="font-size:12px;color:var(--muted);text-decoration:none">VD Full →</a></div>
  <div id="history-body" style="padding:0 0 8px"><div style="color:var(--muted);text-align:center;padding:40px">Loading…</div></div>
</div>

<!-- ═══════════ COURSES TAB ═══════════ -->
<div id="tab-courses" class="tab">
  <div class="topbar"><h1>🏌 Courses</h1></div>
  <div class="card" id="courses-list-card">
    <div style="color:var(--muted);text-align:center;padding:20px">Loading…</div>
  </div>
  <div class="card">
    <h3>Add Course</h3>
    <input type="text" id="new-course-name" placeholder="Course name">
    <div style="display:flex;gap:8px">
      <input type="number" id="new-course-rating" placeholder="Rating" step="0.1" style="flex:1">
      <input type="number" id="new-course-slope" placeholder="Slope" style="flex:1">
      <input type="number" id="new-course-par" placeholder="Par" style="flex:1;margin-bottom:10px">
    </div>
    <button class="btn btn-green" onclick="addCourse()" style="margin:0">Add Course</button>
  </div>
</div>

<!-- ═══════════ HOLE SCREEN (fullscreen overlay) ═══════════ -->
<div id="screen-hole" class="fullscreen">
  <!-- Score bar -->
  <div id="hole-sbar-vd" class="sbar">
    <div class="sbar-player">
      <div class="sbar-pts" id="sb-v" style="color:var(--saffron)">0</div>
      <div class="sbar-label" style="color:var(--saffron)">V</div>
      <div class="sbar-nine" id="sb-v-nine">–</div>
    </div>
    <div class="sbar-mid">
      <div class="sbar-lead" id="sb-lead">Even</div>
      <div class="sbar-hint" id="sb-hint"></div>
    </div>
    <div class="sbar-player">
      <div class="sbar-pts" id="sb-d" style="color:var(--green)">0</div>
      <div class="sbar-label" style="color:var(--green)">D</div>
      <div class="sbar-nine" id="sb-d-nine">–</div>
    </div>
  </div>
  <div id="hole-sbar-solo" class="sbar" style="display:none">
    <div class="sbar-mid" style="text-align:center;padding:4px 0">
      <div id="sb-solo-info" style="font-size:14px;color:var(--muted)"></div>
      <div id="sb-solo-vspar" style="font-size:22px;font-weight:900;margin-top:2px">E</div>
    </div>
  </div>

  <!-- Budget bar -->
  <div id="budget-bar-wrap" class="budget-wrap" style="display:none">
    <div class="budget-lbl">
      <span>Strokes over par remaining</span>
      <span id="budget-remaining" style="font-weight:700"></span>
    </div>
    <div class="budget-track"><div id="budget-fill" class="budget-fill" style="width:100%"></div></div>
  </div>

  <!-- Hole info -->
  <div class="card" style="margin-top:8px">
    <div class="hole-hdr">
      <div>
        <div class="hole-nine" id="hole-nine"></div>
        <div class="hole-num" id="hole-num">Hole 1</div>
        <div class="hole-meta" id="hole-meta">Par 4 · Hdcp 3</div>
      </div>
      <button id="edit-btn" onclick="showEditOverlay()" style="display:none;background:none;border:1px solid var(--border);border-radius:8px;padding:7px 10px;color:var(--muted);font-size:12px;cursor:pointer">↩ Edit</button>
    </div>
    <div class="badges">
      <span class="badge badge-honor" id="badge-honor" style="display:none"></span>
      <span class="badge badge-stroke" id="badge-stroke" style="display:none"></span>
    </div>
  </div>

  <!-- VD score entry -->
  <div id="entry-vd">
    <div class="entry">
      <div class="entry-name" style="color:var(--saffron)">V</div>
      <div class="entry-row">
        <button class="sbtn minus" onclick="adj('v',-1)">−</button>
        <div><div class="snum" id="v-num">4</div><div class="slabel" id="v-lbl">Par</div></div>
        <button class="sbtn plus" onclick="adj('v',1)">+</button>
      </div>
    </div>
    <div class="entry">
      <div class="entry-name" style="color:var(--green)">D (Me)</div>
      <div class="entry-row">
        <button class="sbtn minus" onclick="adj('d',-1)">−</button>
        <div><div class="snum" id="d-num">4</div><div class="slabel" id="d-lbl">Par</div></div>
        <button class="sbtn plus" onclick="adj('d',1)">+</button>
      </div>
    </div>
  </div>

  <!-- Solo score entry -->
  <div id="entry-solo" style="display:none">
    <div class="entry">
      <div class="entry-name">Me</div>
      <div class="entry-row">
        <button class="sbtn minus" onclick="adj('me',-1)">−</button>
        <div><div class="snum" id="me-num">4</div><div class="slabel" id="me-lbl">Par</div></div>
        <button class="sbtn plus" onclick="adj('me',1)">+</button>
      </div>
    </div>
  </div>

  <button class="btn btn-green" onclick="recordHole()">Record Hole</button>
  <button class="btn btn-ghost" onclick="endRoundEarly()" style="margin-bottom:14px">End Round</button>
</div>

<!-- ═══════════ SUMMARY SCREEN (fullscreen overlay) ═══════════ -->
<div id="screen-summary" class="fullscreen">
  <div class="topbar"><h1>Round Complete</h1><div style="font-size:12px;color:var(--muted)" id="sum-date"></div></div>
  <!-- VD result (shown for VD rounds) -->
  <div id="sum-vd-section" style="display:none">
    <div class="win-banner" id="win-banner"></div>
    <div class="card">
      <h3>Match Result</h3>
      <div class="stat-row"><span class="stat-lbl">V Points</span><span class="stat-val pv" id="sum-v">0</span></div>
      <div class="stat-row"><span class="stat-lbl">D Points</span><span class="stat-val pd" id="sum-d">0</span></div>
      <div class="stat-row"><span class="stat-lbl">Margin</span><span class="stat-val" id="sum-margin">Even</span></div>
    </div>
  </div>
  <!-- GHIN round stats -->
  <div class="card">
    <h3>Round Stats</h3>
    <div class="stat-row"><span class="stat-lbl">Course</span><span class="stat-val" id="sum-course" style="font-size:13px;text-align:right;max-width:200px"></span></div>
    <div class="stat-row"><span class="stat-lbl">Gross Score</span><span class="stat-val" id="sum-gross">—</span></div>
    <div class="stat-row"><span class="stat-lbl">Adj Score</span><span class="stat-val" id="sum-adj">—</span></div>
    <div class="stat-row"><span class="stat-lbl">Differential</span><span class="stat-val" id="sum-diff">—</span></div>
    <div class="stat-row"><span class="stat-lbl">Proj New Index</span><span class="stat-val" id="sum-proj-index">—</span></div>
  </div>
  <!-- Hole table (VD) -->
  <div id="sum-hole-card" class="card" style="overflow-x:auto;display:none">
    <h3>Hole by Hole <span style="font-weight:400;color:var(--muted)">(*= stroke)</span></h3>
    <table class="htbl" id="hole-tbl"></table>
  </div>
  <div class="card" style="padding:12px 16px">
    <div class="toggle-row">
      <span style="font-size:14px;color:var(--muted)">Include in GHIN handicap</span>
      <label class="tgl"><input type="checkbox" id="include-ghin-toggle" checked><span class="tgl-slider"></span></label>
    </div>
  </div>
  <button class="btn btn-green" id="save-round-btn" onclick="saveRound()">Save Round</button>
  <button class="btn btn-ghost" onclick="newRound()">New Round</button>
</div>

<!-- ═══════════ RESULT OVERLAY ═══════════ -->
<div class="overlay" id="overlay" style="display:none">
  <div class="overlay-card">
    <div class="ov-hole" id="ov-hole">Hole 1</div>
    <div class="ov-winner" id="ov-winner">Halved</div>
    <div class="ov-scores" id="ov-scores"></div>
    <div class="ov-detail" id="ov-detail"></div>
    <div id="ov-nine-sum" style="display:none"></div>
    <div class="ov-match" id="ov-match">Even</div>
    <button class="btn btn-green" onclick="nextHole()" id="ov-next" style="width:100%;margin:0">Next →</button>
  </div>
</div>

<!-- ═══════════ EDIT HOLES OVERLAY ═══════════ -->
<div class="overlay" id="edit-overlay" style="display:none">
  <div class="overlay-card" style="max-height:82vh;overflow-y:auto;padding:18px 14px">
    <div style="font-size:12px;color:var(--muted);margin-bottom:12px;font-weight:600">Tap hole to go back and re-enter</div>
    <div id="edit-hole-list"></div>
    <button class="btn btn-ghost" onclick="document.getElementById('edit-overlay').style.display='none'" style="width:100%;margin:10px 0 0">Cancel</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- ═══════════ BOTTOM NAV ═══════════ -->
<nav class="tabnav">
  <button class="tnbtn active" id="tn-score" onclick="showTab('score')"><span class="ti">⛳</span>Score</button>
  <button class="tnbtn" id="tn-handicap" onclick="showTab('handicap')"><span class="ti">📊</span>Hdcp</button>
  <button class="tnbtn" id="tn-history" onclick="showTab('history')"><span class="ti">📋</span>History</button>
  <button class="tnbtn" id="tn-courses" onclick="showTab('courses')"><span class="ti">🏌</span>Courses</button>
</nav>

<script>
// ═══════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════
const GOV_NINES = [
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
];

const NINE_COMBOS = {
  '0':  {id:'gov-lakes',             name:'Lakes (9)',               rating:69.6, slope:129, par:36},
  '1':  {id:'gov-foothills',         name:'Foothills (9)',           rating:70.2, slope:132, par:36},
  '2':  {id:'gov-mountain',          name:'Mountain (9)',            rating:null, slope:null, par:36},
  '01': {id:'gov-lakes-foothills',   name:'GC Lakes to Foothills',   rating:69.9, slope:131, par:72},
  '12': {id:'gov-foothills-mountain',name:'GC Foothills to Mountain', rating:69.3, slope:131, par:72},
  '02': {id:'gov-mountain-lakes',    name:'GC Mountain to Lakes',    rating:69.0, slope:130, par:72},
  '00': {id:'gov-lakes-lakes',       name:'GC Lakes, Lakes',         rating:69.6, slope:129, par:72},
  '11': {id:'gov-foothills-foothills',name:'GC Foothills, Foothills',rating:70.2, slope:132, par:72},
  '22': {id:'gov-mountain-mountain', name:'GC Mountain, Mountain',   rating:68.4, slope:130, par:72},
};

// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
let R = loadState() || freshR();
let HDCP = null;
let COURSES = [];
let _charts = {};

function freshR() {
  return {
    date: today(),
    selectedNines: [], isGovRun: false,
    course_id: null, course_name: '', rating: null, slope: null, par: 72,
    nine_hole: false, holes: [],
    course_hdcp: null, budget: null, index: null,
    vd_enabled: false, initialHonor: 'V', startOffset: -1,
    strokeMap: {}, strokesComputedAt: [],
    curV: 5, curD: 5, curMe: 5,
    results: [], inProgress: false,
  };
}
function today() { return new Date().toISOString().slice(0,10); }
function saveState() { localStorage.setItem('golf-log-round', JSON.stringify(R)); }
function loadState() {
  try { const s = localStorage.getItem('golf-log-round'); return s ? JSON.parse(s) : null; }
  catch(e) { return null; }
}

// ═══════════════════════════════════════════════════════════
// TAB MANAGEMENT
// ═══════════════════════════════════════════════════════════
function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tnbtn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('tn-' + name).classList.add('active');
  if (name === 'score')    initScoreTab();
  else if (name === 'handicap') loadHandicap();
  else if (name === 'history')  loadHistory();
  else if (name === 'courses')  loadCourses();
}

// ═══════════════════════════════════════════════════════════
// SCORE TAB
// ═══════════════════════════════════════════════════════════
function initScoreTab() {
  document.getElementById('score-date').textContent = today();
  // Resume card
  if (R.inProgress && R.results.length > 0) {
    document.getElementById('resume-card').style.display = 'block';
    if (R.vd_enabled) {
      const ms = matchScore(); const m = ms.v - ms.d;
      const leadEl = document.getElementById('rc-lead');
      if (m === 0) { leadEl.textContent = 'Even'; leadEl.style.color = '#9ca3af'; }
      else { const who=m>0?'V':'D', c=m>0?'var(--green)':'var(--blue)';
             leadEl.textContent=`${who} leads +${Math.abs(m)}`; leadEl.style.color=c; }
    } else {
      const gross = R.results.reduce((s,r)=>s+r.gross,0);
      const el = document.getElementById('rc-lead');
      el.textContent = `Score: ${gross}`; el.style.color = 'var(--text)';
    }
    document.getElementById('rc-holes').textContent = `${R.results.length} of ${R.holes.length} holes`;
  } else {
    document.getElementById('resume-card').style.display = 'none';
  }
  // Nine buttons
  for (let i=0; i<3; i++)
    document.getElementById('nine-btn-'+i).classList.toggle('sel', R.selectedNines.includes(i));
  // VD toggle
  document.getElementById('vd-toggle').checked = R.vd_enabled;
  document.getElementById('vd-opts').style.display = R.vd_enabled ? 'block' : 'none';
  setHonor(R.initialHonor);
  updateOffsetDisplay();
}

function toggleNineBtn(i) {
  document.getElementById('other-course-sel').value = '';
  R.isGovRun = true;
  const pos = R.selectedNines.indexOf(i);
  if (pos >= 0) R.selectedNines.splice(pos,1);
  else { R.selectedNines.push(i); R.selectedNines.sort((a,b)=>a-b); }
  for (let j=0; j<3; j++)
    document.getElementById('nine-btn-'+j).classList.toggle('sel', R.selectedNines.includes(j));
  updateCourseFromNines();
  saveState();
}

function updateCourseFromNines() {
  if (R.selectedNines.length === 0) {
    R.course_id=null; R.course_name=''; R.rating=null; R.slope=null; R.par=72;
    R.holes=[]; R.nine_hole=false; return;
  }
  const key = R.selectedNines.join('');
  const combo = NINE_COMBOS[key];
  if (combo) {
    R.course_id=combo.id; R.course_name=combo.name;
    R.rating=combo.rating; R.slope=combo.slope; R.par=combo.par;
    R.nine_hole = combo.par===36;
  }
  R.holes = [];
  R.selectedNines.forEach(ni => R.holes.push(...GOV_NINES[ni].holes));
}

function selectOtherCourse() {
  const id = document.getElementById('other-course-sel').value;
  if (!id) { R.isGovRun = false; return; }
  R.selectedNines = [];
  for (let i=0;i<3;i++) document.getElementById('nine-btn-'+i).classList.remove('sel');
  const c = COURSES.find(x=>x.id===id);
  if (c) {
    R.isGovRun=false; R.course_id=c.id; R.course_name=c.name;
    R.rating=c.rating; R.slope=c.slope; R.par=c.par||72;
    R.nine_hole=(c.par||72)<=36; R.holes=c.holes||[];
  }
  saveState();
}

function toggleVD() {
  R.vd_enabled = document.getElementById('vd-toggle').checked;
  document.getElementById('vd-opts').style.display = R.vd_enabled ? 'block' : 'none';
  saveState();
}

function setHonor(p) {
  R.initialHonor = p;
  document.getElementById('hbtn-V').classList.toggle('sel', p==='V');
  document.getElementById('hbtn-D').classList.toggle('sel', p==='D');
  saveState();
}

function adjOffset(d) {
  R.startOffset = (R.startOffset||0) + d;
  updateOffsetDisplay(); saveState();
}

function updateOffsetDisplay() {
  const off = R.startOffset||0;
  let s;
  if (off===0) s='Even';
  else if (off>0) s=`V+${off}`;
  else s=`D+${Math.abs(off)}`;
  document.getElementById('offset-display').textContent = s;
}

function startRound() {
  if (R.isGovRun) updateCourseFromNines();
  if (!R.course_id) { showToast('Select nines or a course'); return; }
  // Compute handicap info
  if (R.rating && R.slope && HDCP && HDCP.index !== null) {
    R.index = HDCP.index;
    R.course_hdcp = Math.round(HDCP.index * R.slope / 113 + (R.rating - R.par));
    if (HDCP.target_diff !== null && R.rating && R.slope)
      R.budget = Math.floor(R.rating + HDCP.target_diff * R.slope / 113) - R.par;
  }
  R.date = today(); R.results = []; R.strokeMap = {};
  R.strokesComputedAt = []; R.inProgress = true;
  saveState();
  openHoleScreen(); showHole(0);
}

function resumeRound() { openHoleScreen(); showHole(R.results.length); }

function deleteRound() {
  R = freshR(); saveState(); initScoreTab();
}

// ═══════════════════════════════════════════════════════════
// HOLE SCREEN
// ═══════════════════════════════════════════════════════════
function openHoleScreen() {
  document.getElementById('screen-hole').classList.add('open');
  const vd = R.vd_enabled;
  document.getElementById('entry-vd').style.display    = vd ? 'block' : 'none';
  document.getElementById('entry-solo').style.display  = vd ? 'none'  : 'block';
  document.getElementById('hole-sbar-vd').style.display  = vd ? 'flex' : 'none';
  document.getElementById('hole-sbar-solo').style.display = vd ? 'none' : 'flex';
}

function closeHoleScreen() {
  document.getElementById('screen-hole').classList.remove('open');
}

function showHole(idx) {
  const hole = R.holes[idx];
  if (!hole) { closeHoleScreen(); showSummary(); return; }

  if (R.vd_enabled) {
    if (isNineStart(idx) || (idx===0 && Math.abs(R.startOffset||0)>=5))
      computeStrokesForNine(idx);
    R.curV = hole.par+1; R.curD = hole.par+1;
  } else {
    R.curMe = hole.par+1;
  }

  const nine = nineForIdx(idx);
  document.getElementById('hole-nine').textContent = nine?.name || '';
  document.getElementById('hole-num').textContent = 'Hole '+hole.number;
  document.getElementById('hole-meta').textContent = 'Par '+hole.par+' · Hdcp '+(hole.handicap||'—');
  document.getElementById('edit-btn').style.display = idx>0 ? 'block' : 'none';

  const hb = document.getElementById('badge-honor');
  const sb = document.getElementById('badge-stroke');
  if (R.vd_enabled) {
    const strokes = R.strokeMap[idx]||{v:false,d:false};
    hb.textContent='🏌️ '+getHonor()+' has honor'; hb.style.display='inline-flex';
    if (strokes.v||strokes.d) {
      sb.textContent='+ '+(strokes.v?'V':'D')+' gets a stroke'; sb.style.display='inline-flex';
    } else { sb.style.display='none'; }
  } else { hb.style.display='none'; sb.style.display='none'; }

  updateScoreBar(); updateBudget(); renderScores(); saveState();
}

function adj(p,d) {
  if (p==='v') R.curV=Math.max(1,R.curV+d);
  else if (p==='d') R.curD=Math.max(1,R.curD+d);
  else R.curMe=Math.max(1,R.curMe+d);
  renderScores();
}

function renderScores() {
  const idx = R.results.length;
  const hole = R.holes[idx]; if (!hole) return;
  if (R.vd_enabled) {
    document.getElementById('v-num').textContent = R.curV;
    document.getElementById('d-num').textContent = R.curD;
    document.getElementById('v-lbl').textContent = scoreLabel(R.curV,hole.par);
    document.getElementById('d-lbl').textContent = scoreLabel(R.curD,hole.par);
  } else {
    document.getElementById('me-num').textContent = R.curMe;
    document.getElementById('me-lbl').textContent = scoreLabel(R.curMe,hole.par);
  }
}

function adjHoleScore(gross, par, holeHdcp, courseHdcp) {
  if (holeHdcp && courseHdcp !== null && courseHdcp !== undefined) {
    const base  = Math.floor(courseHdcp/18);
    const extra = holeHdcp <= (courseHdcp%18) ? 1 : 0;
    return Math.min(gross, par+2+base+extra);
  }
  return Math.min(gross, par+2);
}

function updateBudget() {
  const wrap = document.getElementById('budget-bar-wrap');
  if (!R.budget || R.nine_hole) { wrap.style.display='none'; return; }
  wrap.style.display='block';
  let used=0;
  R.results.forEach(r => used += r.adj - r.par);
  const rem = R.budget - used;
  const frac = R.budget>0 ? Math.max(0, rem/R.budget) : 0;
  document.getElementById('budget-remaining').textContent = rem+' of '+R.budget+' left';
  const fill = document.getElementById('budget-fill');
  fill.style.width = (frac*100)+'%';
  fill.style.background = rem>=4 ? 'var(--green)' : rem>=1 ? 'var(--gold)' : 'var(--red)';
}

function updateScoreBar() {
  if (R.vd_enabled) {
    let vG=0,dG=0,parT=0;
    R.results.forEach(r=>{if(r.vd){vG+=r.vd.vGross;dG+=r.vd.dGross;parT+=r.par;}});
    document.getElementById('sb-v').textContent=R.results.length?fmtVsPar(vG-parT):'E';
    document.getElementById('sb-d').textContent=R.results.length?fmtVsPar(dG-parT):'E';
    const m=margin();
    const lead=document.getElementById('sb-lead'); const hint=document.getElementById('sb-hint');
    if (m===0) { lead.textContent='Even'; lead.style.color='var(--muted)'; hint.textContent=''; }
    else {
      const who=m>0?'V':'D', c=m>0?'var(--saffron)':'var(--green)';
      lead.textContent=`${who} +${Math.abs(m)}`; lead.style.color=c;
      hint.textContent='';
    }
    const nine=getCurrentNineScore();
    document.getElementById('sb-v-nine').textContent = nine.count?fmtVsPar(nine.vVsPar):'–';
    document.getElementById('sb-d-nine').textContent = nine.count?fmtVsPar(nine.dVsPar):'–';
  } else {
    const gross = R.results.reduce((s,r)=>s+r.gross,0);
    const par   = R.results.reduce((s,r)=>s+r.par,0);
    const n = R.results.length, total = R.holes.length;
    document.getElementById('sb-solo-info').textContent = `Hole ${n+1} of ${total}`;
    const vp = document.getElementById('sb-solo-vspar');
    const d = gross-par;
    vp.textContent = n>0 ? (d>0?`+${d}`:d===0?'E':`${d}`) : 'E';
    vp.style.color = d<0?'var(--green)':d>0?'var(--red)':'var(--muted)';
  }
}

function recordHole() {
  const idx=R.results.length; const hole=R.holes[idx]; if (!hole) return;
  if (R.vd_enabled) {
    const strokes=R.strokeMap[idx]||{v:false,d:false};
    const calc=calcHole(hole,R.curV,R.curD,strokes.v,strokes.d);
    const honor=getHonor();
    const adjD=adjHoleScore(R.curD,hole.par,hole.handicap,R.course_hdcp);
    R.results.push({
      holeNumber:hole.number, par:hole.par, handicap:hole.handicap,
      gross:R.curD, adj:adjD, strokes_received:strokes.d?1:0,
      vd:{vGross:R.curV,dGross:R.curD,vStroke:strokes.v,dStroke:strokes.d,
          vNet:calc.vNet,dNet:calc.dNet,honor}
    });
    showOverlay(hole,calc);
  } else {
    const adjMe=adjHoleScore(R.curMe,hole.par,hole.handicap,R.course_hdcp);
    R.results.push({holeNumber:hole.number,par:hole.par,handicap:hole.handicap,
      gross:R.curMe,adj:adjMe,strokes_received:0,vd:null});
    saveState();
    if (R.results.length >= R.holes.length) { closeHoleScreen(); showSummary(); }
    else showHole(R.results.length);
    return;
  }
  saveState();
}

function endRoundEarly() {
  if (R.results.length===0) { showToast('No holes recorded'); return; }
  closeHoleScreen(); showSummary();
}

// ═══════════════════════════════════════════════════════════
// VD SCORING LOGIC (existing, adapted)
// ═══════════════════════════════════════════════════════════
function calcHole(hole,vGross,dGross,vStroke,dStroke) {
  const vNet=vGross-(vStroke?1:0), dNet=dGross-(dStroke?1:0);
  return {vNet,dNet};
}

function matchScore() {
  let vNet=0,dNet=0;
  R.results.forEach(r=>{ if(r.vd){vNet+=r.vd.vNet;dNet+=r.vd.dNet;} });
  return {vNet,dNet};
}
function margin() {
  const m=matchScore(); const off=R.startOffset||0;
  // positive = V ahead (V has lower net); startOffset>0 = V advantage
  return (m.dNet-m.vNet)+off;
}

function getHonor() {
  for (let i=R.results.length-1;i>=0;i--) {
    const r=R.results[i]; if(!r.vd) continue;
    if (r.vd.vGross<r.vd.dGross) return 'V';
    if (r.vd.dGross<r.vd.vGross) return 'D';
  }
  return R.initialHonor;
}

function isNineStart(idx) {
  if (idx===0||!R.isGovRun) return false;
  let c=0;
  for (const ni of R.selectedNines) {
    c+=GOV_NINES[ni].holes.length; if (idx===c) return true;
  }
  return false;
}

function nineForIdx(idx) {
  if (!R.isGovRun) return null;
  let c=0;
  for (const ni of R.selectedNines) {
    const nine=GOV_NINES[ni];
    if (idx<c+nine.holes.length) return nine;
    c+=nine.holes.length;
  }
  return null;
}

function computeStrokesForNine(nineStartIdx) {
  if (!R.vd_enabled||!R.isGovRun) return;
  if (R.strokesComputedAt.includes(nineStartIdx)) return;
  R.strokesComputedAt.push(nineStartIdx);
  const m=margin(); const strokes=Math.floor(Math.abs(m)/5);
  if (strokes===0) return;
  const trailV=m>0;
  const nine=nineForIdx(nineStartIdx); if (!nine) return;
  const sorted=[...nine.holes].sort((a,b)=>a.handicap-b.handicap);
  sorted.slice(0,strokes).forEach(h=>{
    const hi=R.holes.findIndex(hh=>hh.number===h.number);
    if (hi>=0) { if (!R.strokeMap[hi]) R.strokeMap[hi]={v:false,d:false};
      if (trailV) R.strokeMap[hi].d=true; else R.strokeMap[hi].v=true; }
  });
}

function getCurrentNineScore() {
  const nextIdx=R.results.length; let nineStart=0,c=0;
  for (const ni of R.selectedNines) {
    const len=GOV_NINES[ni].holes.length; nineStart=c; c+=len; if (nextIdx<c) break;
  }
  let vG=0,dG=0,par=0,count=0;
  for (let i=nineStart;i<nextIdx;i++) {
    const r=R.results[i]; if (!r||!r.vd) break;
    vG+=r.vd.vGross; dG+=r.vd.dGross; par+=R.holes[i].par; count++;
  }
  return {vGross:vG,dGross:dG,par,vVsPar:vG-par,dVsPar:dG-par,count};
}

function getNineSummary(endIdx) {
  let nineStart=0,nineName='',c=0;
  for (const ni of R.selectedNines) {
    const nine=GOV_NINES[ni];
    if (endIdx-1<c+nine.holes.length){nineStart=c;nineName=nine.name;break;}
    c+=nine.holes.length;
  }
  let vG=0,dG=0,par=0;
  for(let i=nineStart;i<endIdx;i++){vG+=R.results[i].vd.vGross;dG+=R.results[i].vd.dGross;par+=R.holes[i].par;}
  return {nineName,vGross:vG,dGross:dG,par,vVsPar:vG-par,dVsPar:dG-par};
}

function showOverlay(hole,calc) {
  const m=margin();
  document.getElementById('ov-hole').textContent='Hole '+hole.number;
  const w=document.getElementById('ov-winner');
  if (calc.vNet<calc.dNet){w.textContent='V wins hole';w.style.color='var(--saffron)';}
  else if (calc.dNet<calc.vNet){w.textContent='D wins hole';w.style.color='var(--green)';}
  else{w.textContent='Halved';w.style.color='var(--muted)';}
  const lr=R.results[R.results.length-1];
  const vDisp=lr.vd.vGross+(lr.vd.vStroke?'<span class="stroke-mark">*</span>':'');
  const dDisp=lr.vd.dGross+(lr.vd.dStroke?'<span class="stroke-mark">*</span>':'');
  document.getElementById('ov-scores').innerHTML=`<span style="color:var(--saffron)">V</span> ${vDisp} &nbsp;·&nbsp; <span style="color:var(--green)">D</span> ${dDisp}`;
  let det='';
  if (lr.vd.vStroke) det+=`V net ${lr.vd.vNet}  `;
  if (lr.vd.dStroke) det+=`D net ${lr.vd.dNet}`;
  document.getElementById('ov-detail').textContent=det.trim();
  const om=document.getElementById('ov-match');
  if (m===0){om.textContent='Even';om.style.color='var(--muted)';}
  else{const who=m>0?'V':'D';om.textContent=`${who} +${Math.abs(m)}`;om.style.color=m>0?'var(--saffron)':'var(--green)';}
  const nextIdx=R.results.length;
  document.getElementById('ov-next').textContent = nextIdx>=R.holes.length ? 'View Results →' : `Hole ${R.holes[nextIdx].number} →`;
  // Nine summary
  const nineSumEl=document.getElementById('ov-nine-sum');
  const nineJustDone=isNineStart(nextIdx)||(nextIdx>=R.holes.length&&nextIdx>0);
  if (nineJustDone&&nextIdx>0) {
    const sum=getNineSummary(nextIdx);
    const vC=sum.vVsPar<0?'var(--green)':sum.vVsPar>0?'var(--red)':'var(--muted)';
    const dC=sum.dVsPar<0?'var(--green)':sum.dVsPar>0?'var(--red)':'var(--muted)';
    let cumHtml=''; let nComp=0,cc=0;
    for(const ni of R.selectedNines){cc+=GOV_NINES[ni].holes.length;if(nextIdx>=cc)nComp++;}
    if (nComp>=2) {
      let cv=0,cd=0,cp=0;
      for(let i=0;i<nextIdx;i++){cv+=R.results[i].vd.vGross;cd+=R.results[i].vd.dGross;cp+=R.holes[i].par;}
      const cvC=(cv-cp)<0?'var(--green)':(cv-cp)>0?'var(--red)':'var(--muted)';
      const cdC=(cd-cp)<0?'var(--green)':(cd-cp)>0?'var(--red)':'var(--muted)';
      cumHtml=`<div style="border-top:1px solid #374151;margin:10px 0;padding-top:10px">
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;text-transform:uppercase">${nextIdx}-Hole Total</div>
        <div style="display:flex;justify-content:space-around">
          <div style="text-align:center"><div style="font-size:26px;font-weight:900;color:var(--saffron)">${cv}</div><div style="font-size:12px;color:var(--muted)">V <span style="color:${cvC};font-weight:700">${fmtVsPar(cv-cp)}</span></div></div>
          <div style="text-align:center"><div style="font-size:26px;font-weight:900;color:var(--green)">${cd}</div><div style="font-size:12px;color:var(--muted)">D <span style="color:${cdC};font-weight:700">${fmtVsPar(cd-cp)}</span></div></div>
        </div></div>`;
    }
    nineSumEl.innerHTML=`<div style="border-top:1px solid #374151;margin:12px 0;padding-top:12px">
      <div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;text-transform:uppercase">${sum.nineName} Complete</div>
      <div style="display:flex;justify-content:space-around">
        <div style="text-align:center"><div style="font-size:26px;font-weight:900;color:var(--saffron)">${sum.vGross}</div><div style="font-size:12px;color:var(--muted)">V <span style="color:${vC};font-weight:700">${fmtVsPar(sum.vVsPar)}</span></div></div>
        <div style="text-align:center"><div style="font-size:26px;font-weight:900;color:var(--green)">${sum.dGross}</div><div style="font-size:12px;color:var(--muted)">D <span style="color:${dC};font-weight:700">${fmtVsPar(sum.dVsPar)}</span></div></div>
      </div></div>${cumHtml}`;
    nineSumEl.style.display='block';
  } else { nineSumEl.style.display='none'; }
  document.getElementById('overlay').style.display='flex';
}

function nextHole() {
  document.getElementById('overlay').style.display='none';
  const idx=R.results.length;
  if (idx>=R.holes.length){closeHoleScreen();showSummary();}
  else showHole(idx);
}

function showEditOverlay() {
  document.getElementById('overlay').style.display='none';
  const list=document.getElementById('edit-hole-list'); list.innerHTML='';
  R.results.forEach((r,idx)=>{
    const vStr=r.vd?scoreLabel(r.vd.vGross,r.par):''; const dStr=r.vd?scoreLabel(r.vd.dGross,r.par):'';
    const btn=document.createElement('button');
    btn.style.cssText='width:100%;text-align:left;background:#111827;border:1px solid #374151;border-radius:10px;padding:11px 13px;margin-bottom:7px;cursor:pointer;color:#f9fafb;font-size:13px;';
    btn.innerHTML=r.vd
      ?`<b>Hole ${r.holeNumber}</b> <span style="color:#9ca3af">Par ${r.par}</span><span style="float:right"><span style="color:var(--saffron)">V ${r.vd.vGross}(${vStr})</span> · <span style="color:var(--green)">D ${r.vd.dGross}(${dStr})</span></span>`
      :`<b>Hole ${r.holeNumber}</b> <span style="color:#9ca3af">Par ${r.par}</span><span style="float:right">Score ${r.gross} (${scoreLabel(r.gross,r.par)})</span>`;
    btn.onclick=()=>goBackToHole(idx);
    list.appendChild(btn);
  });
  document.getElementById('edit-overlay').style.display='flex';
}

function goBackToHole(targetIdx) {
  R.strokesComputedAt=R.strokesComputedAt.filter(ns=>{
    if (ns>=targetIdx) {
      let c=0;
      for (const ni of R.selectedNines) {
        if (c===ns) { GOV_NINES[ni].holes.forEach(h=>{const hi=R.holes.findIndex(hh=>hh.number===h.number);if(hi>=0)delete R.strokeMap[hi];}); break; }
        c+=GOV_NINES[ni].holes.length;
      }
      return false;
    }
    return true;
  });
  R.results=R.results.slice(0,targetIdx);
  document.getElementById('edit-overlay').style.display='none';
  saveState(); showHole(targetIdx);
}

// ═══════════════════════════════════════════════════════════
// SUMMARY SCREEN
// ═══════════════════════════════════════════════════════════
function showSummary() {
  R.inProgress=false; saveState();
  document.getElementById('screen-summary').classList.add('open');
  document.getElementById('sum-date').textContent=R.date;
  document.getElementById('sum-course').textContent=R.course_name||'—';

  const grossTotal = R.results.reduce((s,r)=>s+r.gross,0);
  const adjTotal   = R.results.reduce((s,r)=>s+r.adj,0);
  const diff = (R.rating&&R.slope) ? ((adjTotal-R.rating)*113/R.slope).toFixed(1) : '—';
  document.getElementById('sum-gross').textContent=grossTotal;
  document.getElementById('sum-adj').textContent=adjTotal;
  document.getElementById('sum-diff').textContent=diff;

  // Projected index
  let projIdx='—';
  if (diff!=='—'&&HDCP&&HDCP.series) {
    const d20=HDCP.series.slice(-19).map(r=>r.differential);
    d20.push(parseFloat(diff));
    if (d20.length>=8) {
      const sd=[...d20].sort((a,b)=>a-b);
      projIdx=(sd.slice(0,8).reduce((s,x)=>s+x,0)/8).toFixed(1);
    }
  }
  document.getElementById('sum-proj-index').textContent=projIdx;

  if (R.vd_enabled) {
    document.getElementById('sum-vd-section').style.display='block';
    document.getElementById('sum-hole-card').style.display='block';
    const ms=matchScore(); const m=ms.v-ms.d;
    document.getElementById('sum-v').textContent=ms.v;
    document.getElementById('sum-d').textContent=ms.d;
    const banner=document.getElementById('win-banner');
    const marginEl=document.getElementById('sum-margin');
    if (m>0){banner.textContent=`🏆 V wins by ${m}!`;banner.style.color='var(--green)';marginEl.textContent=`V +${m}`;marginEl.style.color='var(--green)';}
    else if (m<0){banner.textContent=`🏆 D wins by ${Math.abs(m)}!`;banner.style.color='var(--blue)';marginEl.textContent=`D +${Math.abs(m)}`;marginEl.style.color='var(--blue)';}
    else{banner.textContent='All Square! 🤝';banner.style.color='var(--gold)';marginEl.textContent='Even';marginEl.style.color='var(--muted)';}
    // Hole table
    const tbl=document.getElementById('hole-tbl');
    tbl.innerHTML=`<tr><th>Hole</th><th>Par</th><th style="color:var(--green)">V</th><th style="color:var(--blue)">D</th><th style="color:var(--green)">V+</th><th style="color:var(--blue)">D+</th><th>Lead</th></tr>`;
    let vR=0,dR=0;
    R.results.forEach(r=>{
      if (!r.vd) return;
      vR+=r.vd.vPts; dR+=r.vd.dPts;
      const lead=vR-dR;
      const ls=lead>0?`<span class="pv">V${lead}</span>`:lead<0?`<span class="pd">D${Math.abs(lead)}</span>`:'–';
      const vs=r.vd.vGross+(r.vd.vStroke?'<span class="stroke-mark">*</span>':'');
      const ds=r.vd.dGross+(r.vd.dStroke?'<span class="stroke-mark">*</span>':'');
      tbl.innerHTML+=`<tr><td>${r.holeNumber}</td><td>${r.par}</td><td class="pv">${vs}</td><td class="pd">${ds}</td><td class="pv">${r.vd.vPts||'–'}</td><td class="pd">${r.vd.dPts||'–'}</td><td>${ls}</td></tr>`;
    });
    const totV=R.results.filter(r=>r.vd).reduce((s,r)=>s+r.vd.vGross,0);
    const totD=R.results.filter(r=>r.vd).reduce((s,r)=>s+r.vd.dGross,0);
    tbl.innerHTML+=`<tr class="total-row"><td colspan="2">Total</td><td class="pv">${totV}</td><td class="pd">${totD}</td><td class="pv">${ms.v}</td><td class="pd">${ms.d}</td><td></td></tr>`;
  } else {
    document.getElementById('sum-vd-section').style.display='none';
    document.getElementById('sum-hole-card').style.display='none';
  }
}

async function saveRound() {
  const adjTotal = R.results.reduce((s,r)=>s+r.adj,0);
  const grossTotal = R.results.reduce((s,r)=>s+r.gross,0);
  const nineHole = R.nine_hole || adjTotal < 60;
  const inclGhin = document.getElementById('include-ghin-toggle').checked;

  let vd_match = null;
  if (R.vd_enabled) {
    const ms=matchScore(); const m=ms.v-ms.d;
    const winner = m>0?'V':m<0?'D':'T';
    const honor_next = getHonorNext();
    const nines = R.selectedNines.map(i=>GOV_NINES[i].name);
    vd_match = {
      date:R.date, winner, margin:Math.abs(m),
      v_points:ms.v, d_points:ms.d,
      honor_next, nines, historical:false
    };
  }

  const body = {
    date:R.date, course_id:R.course_id, course_name:R.course_name,
    rating:R.rating, slope:R.slope, par:R.par,
    score:grossTotal, adj_score:adjTotal, course_hdcp:R.course_hdcp,
    include_ghin:inclGhin, nine_hole:nineHole,
    hole_results:R.results, vd_match,
  };

  document.getElementById('save-round-btn').textContent='Saving…';
  document.getElementById('save-round-btn').disabled=true;
  try {
    await fetch('/api/rounds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    showToast('Round saved!');
    R=freshR(); saveState();
    HDCP=null; // force refresh
    document.getElementById('screen-summary').classList.remove('open');
    initScoreTab();
  } catch(e) { showToast('Save failed'); }
  document.getElementById('save-round-btn').textContent='Save Round';
  document.getElementById('save-round-btn').disabled=false;
}

function getHonorNext() {
  for (let i=R.results.length-1;i>=0;i--) {
    const r=R.results[i]; if (!r.vd) continue;
    if (r.vd.vGross<r.vd.dGross) return 'D'; // V had low score → D has honor next
    if (r.vd.dGross<r.vd.vGross) return 'V';
  }
  return R.initialHonor==='V'?'D':'V';
}

function newRound() {
  R=freshR(); saveState();
  document.getElementById('screen-summary').classList.remove('open');
  initScoreTab();
}

// ═══════════════════════════════════════════════════════════
// HANDICAP TAB
// ═══════════════════════════════════════════════════════════
async function loadHandicap() {
  if (HDCP) { renderHandicap(HDCP); return; }
  try {
    HDCP = await fetch('/api/handicap').then(r=>r.json());
    renderHandicap(HDCP);
  } catch(e) { showToast('Could not load handicap data'); }
}

function renderHandicap(data) {
  const fmt = v => v !== null && v !== undefined ? v : '—';
  document.getElementById('hcp-index').textContent  = fmt(data.index);
  document.getElementById('hcp-target').textContent = fmt(data.target_diff);
  document.getElementById('hcp-anti').textContent   = fmt(data.anti_index);
  document.getElementById('hcp-l20avg').textContent = fmt(data.last_20_avg);
  document.getElementById('hcp-yravg').textContent  = fmt(data.year_avg);

  const bi = document.getElementById('hcp-budget-info');
  const bt = document.getElementById('hcp-budget-txt');
  if (data.target_diff !== null && data.budget !== null) {
    bi.style.display='block';
    bt.innerHTML=`Beat <b>${data.target_diff}</b> to lower your index · Budget: <b>${data.budget}</b> strokes over par at ${data.target_course||'last course'}`;
  } else { bi.style.display='none'; }

  const series = data.series||[];
  const YEAR_COLORS = {'2023':'rgba(96,165,250,.7)','2024':'rgba(34,197,94,.7)','2025':'rgba(245,158,11,.7)','2026':'rgba(239,68,68,.7)'};
  const defaultColor = 'rgba(156,163,175,.6)';

  function mkDate(s) {
    const p=s.split('/'); if(p.length===3&&p[0].length<=2) return `${p[2].length===2?'20'+p[2]:p[2]}-${p[0].padStart(2,'0')}-${p[1].padStart(2,'0')}`;
    return s;
  }
  const labels=series.map(r=>mkDate(r.date));
  const diffs=series.map(r=>r.differential);
  const indices=series.map(r=>r.index_after);
  const ptColors=series.map(r=>{const y=mkDate(r.date).slice(0,4);return YEAR_COLORS[y]||defaultColor;});

  function destroyChart(id) { if(_charts[id]){_charts[id].destroy();delete _charts[id];} }
  const SCALE_OPTS = {
    x:{ticks:{color:'#9ca3af',maxTicksLimit:8,maxRotation:45},grid:{color:'#1e2a3a'}},
    y:{ticks:{color:'#9ca3af'},grid:{color:'#1e2a3a'}}
  };
  const LEGEND_OPTS = {display:false};
  const PLUGIN_OPTS = {legend:LEGEND_OPTS};

  // 1. Differential per round
  destroyChart('diff');
  _charts['diff'] = new Chart(document.getElementById('chart-diff'),{
    type:'scatter',
    data:{datasets:[{data:series.map((r,i)=>({x:i,y:r.differential})),
      backgroundColor:ptColors,pointRadius:4,pointHoverRadius:6}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{...PLUGIN_OPTS,tooltip:{callbacks:{label:ctx=>`${labels[ctx.dataIndex]}: ${ctx.raw.y}`}}},
      scales:{x:{ticks:{color:'#9ca3af',maxTicksLimit:8,callback:(v)=>labels[v]||''},grid:{color:'#1e2a3a'}},y:SCALE_OPTS.y}}
  });

  // 2. Rolling index
  destroyChart('index');
  _charts['index'] = new Chart(document.getElementById('chart-index'),{
    type:'line',
    data:{labels,datasets:[{data:indices,borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.08)',
      borderWidth:2,pointRadius:0,tension:0.3,fill:true}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:PLUGIN_OPTS,scales:SCALE_OPTS}
  });

  // 3. GHIN manual
  destroyChart('ghin');
  const gs=data.ghin_series||[];
  _charts['ghin'] = new Chart(document.getElementById('chart-ghin'),{
    type:'line',
    data:{labels:gs.map(r=>mkDate(r.date)),datasets:[{data:gs.map(r=>r.ghin),
      borderColor:'#f59e0b',backgroundColor:'rgba(245,158,11,.08)',
      borderWidth:2,pointRadius:3,stepped:true,fill:true}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:PLUGIN_OPTS,scales:SCALE_OPTS}
  });

  // 4. Yearly average
  destroyChart('yearly');
  const ya=data.yearly_avgs||[];
  _charts['yearly'] = new Chart(document.getElementById('chart-yearly'),{
    type:'bar',
    data:{labels:ya.map(r=>r.year),datasets:[{data:ya.map(r=>r.avg),
      backgroundColor:'rgba(96,165,250,.6)',borderColor:'rgba(96,165,250,.9)',borderWidth:1}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:PLUGIN_OPTS,scales:SCALE_OPTS}
  });
}

// ═══════════════════════════════════════════════════════════
// HISTORY TAB
// ═══════════════════════════════════════════════════════════
async function loadHistory() {
  const body=document.getElementById('history-body');
  body.innerHTML='<div style="color:var(--muted);text-align:center;padding:40px">Loading…</div>';
  try {
    const [matches,rounds]=await Promise.all([
      fetch('/api/matches').then(r=>r.json()),
      fetch('/api/rounds').then(r=>r.json()),
    ]);
    renderHistory(matches, rounds);
  } catch(e) { body.innerHTML='<div style="color:var(--red);text-align:center;padding:40px">Load failed</div>'; }
}

function renderHistory(matches, rounds) {
  const body=document.getElementById('history-body');
  let html='';

  // VD Standing card
  if (matches.length) {
    let running=0;
    const standings=matches.map(m=>{
      if (m.historical) running=m.winner==='D'?m.margin:m.winner==='V'?-m.margin:0;
      else running+=m.winner==='D'?m.margin:m.winner==='V'?-m.margin:0;
      return running;
    });
    const cur=standings[standings.length-1];
    const curStr=cur>0?`D +${cur}`:cur<0?`V +${Math.abs(cur)}`:'Even';
    const curColor=cur>0?'var(--blue)':cur<0?'var(--green)':'var(--muted)';
    html+=`<div class="card" style="text-align:center">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin-bottom:6px">VD Standing</div>
      <div style="font-size:48px;font-weight:900;color:${curColor}">${curStr}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:6px">${matches.length} matches · <a href="/history" style="color:var(--muted)">Full history →</a></div>
    </div>`;
  }

  // Recent rounds
  const recent=[...rounds].reverse().slice(0,30);
  if (recent.length) {
    html+=`<div class="card"><h3>Recent Rounds</h3><div style="overflow-x:auto">
      <table class="htbl" style="font-size:12px">
        <tr><th>Date</th><th>Course</th><th>Score</th><th>Adj</th><th>Diff</th></tr>
        ${recent.map(r=>`<tr>
          <td style="color:var(--muted)">${r.date}</td>
          <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis">${r.course_name||'—'}</td>
          <td>${r.score??'—'}</td>
          <td>${r.adj_score??'—'}</td>
          <td style="color:${(r.differential||0)<(HDCP?.index||20)?'var(--green)':'var(--muted)'}">${r.differential??'—'}</td>
        </tr>`).join('')}
      </table>
    </div></div>`;
  }

  body.innerHTML = html || '<div style="color:var(--muted);text-align:center;padding:40px">No rounds yet</div>';
}

// ═══════════════════════════════════════════════════════════
// COURSES TAB
// ═══════════════════════════════════════════════════════════
async function loadCourses() {
  try { COURSES=await fetch('/api/courses').then(r=>r.json()); } catch(e){}
  // Populate other course dropdown
  const sel=document.getElementById('other-course-sel');
  const prev=sel.value;
  sel.innerHTML='<option value="">— pick a course —</option>';
  COURSES.filter(c=>!c.id.startsWith('gov-')).forEach(c=>{
    const o=document.createElement('option');
    o.value=c.id; o.textContent=c.name; sel.appendChild(o);
  });
  sel.value=prev;
  renderCoursesList();
}

function renderCoursesList() {
  const card=document.getElementById('courses-list-card');
  if (!COURSES.length) { card.innerHTML='<div style="color:var(--muted);text-align:center;padding:16px">No courses loaded</div>'; return; }
  card.innerHTML='<h3>All Courses</h3>'+COURSES.map(c=>`
    <div class="course-item">
      <div><div class="course-name">${c.name}</div>
        <div class="course-sub">${c.rating??'—'}/${c.slope??'—'} · Par ${c.par??'—'}${c.holes&&c.holes.length?' · hole data':''}
        </div></div>
    </div>`).join('');
}

async function addCourse() {
  const name=document.getElementById('new-course-name').value.trim();
  const rating=parseFloat(document.getElementById('new-course-rating').value)||null;
  const slope=parseInt(document.getElementById('new-course-slope').value)||null;
  const par=parseInt(document.getElementById('new-course-par').value)||72;
  if (!name) { showToast('Enter a course name'); return; }
  const id=name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  try {
    await fetch('/api/courses',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({id,name,rating,slope,par,holes:[],nines:[],aliases:[]})});
    document.getElementById('new-course-name').value='';
    document.getElementById('new-course-rating').value='';
    document.getElementById('new-course-slope').value='';
    document.getElementById('new-course-par').value='';
    COURSES=null; await loadCourses(); showToast('Course added!');
  } catch(e) { showToast('Save failed'); }
}

// ═══════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════
function scoreLabel(score,par) {
  const d=score-par;
  if (d<=-2) return 'Eagle'; if (d===-1) return 'Birdie';
  if (d===0) return 'Par'; if (d===1) return 'Bogey';
  if (d===2) return 'Double'; return `+${d}`;
}
function fmtVsPar(n) { return n>0?`+${n}`:n===0?'E':`${n}`; }

function showToast(msg) {
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2200);
}

// ═══════════════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════════════
async function boot() {
  // Register SW
  if ('serviceWorker' in navigator)
    navigator.serviceWorker.register('/sw.js').catch(()=>{});

  // Load courses + handicap data in parallel
  try {
    [COURSES] = await Promise.all([
      fetch('/api/courses').then(r=>r.json()),
    ]);
  } catch(e) {}

  // Populate other course dropdown
  const sel=document.getElementById('other-course-sel');
  COURSES.filter(c=>!c.id.startsWith('gov-')).forEach(c=>{
    const o=document.createElement('option'); o.value=c.id; o.textContent=c.name; sel.appendChild(o);
  });

  // Prefetch handicap silently
  fetch('/api/handicap').then(r=>r.json()).then(d=>{ HDCP=d; }).catch(()=>{});

  initScoreTab();
}

boot();
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# History HTML (VD match history page)
# ---------------------------------------------------------------------------
HISTORY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Golf Log — History</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#111827;color:#f9fafb;min-height:100vh}
.header{background:#1f2937;border-bottom:1px solid #374151;padding:20px 32px;display:flex;align-items:center;gap:16px}
.header h1{font-size:22px;font-weight:800}
.header a{color:#9ca3af;text-decoration:none;font-size:14px;margin-left:auto}
.wrap{max-width:960px;margin:0 auto;padding:24px 20px}
.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:20px;margin-bottom:20px}
.card h2{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#9ca3af;margin-bottom:16px}
.stats{display:flex;gap:0}
.stat{flex:1;text-align:center;padding:12px;border-right:1px solid #374151}
.stat:last-child{border-right:none}
.stat .num{font-size:40px;font-weight:900}
.stat .lbl{font-size:13px;color:#9ca3af;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#0d1520;padding:9px 10px;text-align:left;color:#9ca3af;font-size:11px;font-weight:700;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #1e2a3a;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:hover td{background:#161f2e}
.pv{color:#22c55e;font-weight:700} .pd{color:#60a5fa;font-weight:700}
.gold{color:#f59e0b;font-weight:700}
.dim{color:#9ca3af}
canvas{display:block}
.badge-hist{font-size:10px;color:#9ca3af;background:#1e2a3a;border-radius:4px;padding:1px 5px;vertical-align:middle;margin-left:4px}
</style>
</head>
<body>
<div class="header">
  <div>⛳</div>
  <h1>Golf Log — Match History</h1>
  <a href="/">← Scoring App</a>
</div>
<div class="wrap">
  <div id="content"><p style="color:#9ca3af;text-align:center;padding:60px">Loading…</p></div>
</div>
<script>
fetch('/api/matches').then(r=>r.json()).then(render).catch(()=>{
  document.getElementById('content').innerHTML='<p style="color:#ef4444;text-align:center;padding:60px">Could not load match data</p>';
});

function sma(arr, n, i) {
  if (i < n-1) return null;
  let s=0; for(let j=i-n+1;j<=i;j++) s+=arr[j]; return s/n;
}

function render(matches) {
  if (!matches.length) {
    document.getElementById('content').innerHTML='<p style="color:#9ca3af;text-align:center;padding:60px">No matches yet — play some golf!</p>';
    return;
  }

  let runningTotal = 0;
  const standings = matches.map(m => {
    if (m.historical) {
      runningTotal = m.winner==='D' ? m.margin : m.winner==='V' ? -m.margin : 0;
    } else {
      runningTotal += m.winner==='D' ? m.margin : m.winner==='V' ? -m.margin : 0;
    }
    return runningTotal;
  });

  let vW=0, dW=0, ties=0;
  for (let i=0; i<standings.length; i++) {
    const prev = i===0 ? 0 : standings[i-1];
    const delta = standings[i] - prev;
    if (delta > 0) dW++; else if (delta < 0) vW++; else ties++;
  }

  const sma5 = standings.map((_,i) => sma(standings,5,i));
  const chartLabels = matches.map((m,i) => m.date.startsWith('pre-2025') ? '#'+(i+1) : m.date);

  const cur = standings[standings.length-1];
  const curStr = cur>0 ? `D +${cur}` : cur<0 ? `V +${Math.abs(cur)}` : 'Even';
  const curColor = cur>0 ? '#60a5fa' : cur<0 ? '#22c55e' : '#9ca3af';

  const rows = [...matches].reverse().map((m, ri) => {
    const i = matches.length - 1 - ri;
    const standing = standings[i];
    const s5 = sma5[i];
    const standStr = standing>0
      ? `<span class="pd">D +${standing}</span>`
      : standing<0
      ? `<span class="pv">V +${Math.abs(standing)}</span>`
      : '<span class="dim">Even</span>';
    const honor = m.honor_next ? `<span class="${m.honor_next==='V'?'pv':'pd'}">${m.honor_next}</span>` : '<span class="dim">—</span>';
    const smaStr = s5 !== null
      ? `<span style="color:${s5>0?'#60a5fa':s5<0?'#22c55e':'#9ca3af'}">${s5>0?'+':''}${s5.toFixed(1)}</span>`
      : '<span class="dim">—</span>';
    const hist = m.historical ? '<span class="badge-hist">hist</span>' : '';
    const ninesStr = m.historical ? '<span class="dim">—</span>' : (m.nines||[]).join(', ') || '<span class="dim">—</span>';
    const ptsStr = m.historical
      ? '<span class="dim">—</span>'
      : `<span class="pv">${m.v_points}</span> / <span class="pd">${m.d_points}</span>`;
    return `<tr>
      <td class="dim">${m.date}${hist}</td>
      <td>${ninesStr}</td>
      <td>${ptsStr}</td>
      <td>${standStr}</td>
      <td>${smaStr}</td>
      <td>${honor}</td>
    </tr>`;
  }).join('');

  document.getElementById('content').innerHTML = `
  <div class="card" style="text-align:center;padding:24px 20px">
    <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#9ca3af;margin-bottom:8px">Current Standing</div>
    <div style="font-size:56px;font-weight:900;color:${curColor}">${curStr}</div>
    <div style="font-size:13px;color:#9ca3af;margin-top:8px">${matches.length} matches played</div>
  </div>

  <div class="card">
    <h2>Standing Over Time &nbsp;<span style="font-size:11px;font-weight:400;color:#9ca3af">(+ D leading / − V leading)</span></h2>
    <canvas id="chart" style="height:280px"></canvas>
  </div>

  <div class="card" style="overflow-x:auto">
    <h2>Match Log</h2>
    <table>
      <tr><th>Date</th><th>Nines</th><th>V / D Pts</th><th>Standing</th><th>5-SMA</th><th>Next Honor</th></tr>
      ${rows}
    </table>
  </div>`;

  const barColors = standings.map(v =>
    v > 0 ? 'rgba(96,165,250,.7)' : v < 0 ? 'rgba(34,197,94,.7)' : 'rgba(156,163,175,.5)'
  );

  new Chart(document.getElementById('chart'), {
    type: 'bar',
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: 'Standing',
          data: standings,
          backgroundColor: barColors,
          borderColor: barColors.map(c => c.replace('.7','.9').replace('.5','.8')),
          borderWidth: 1,
          order: 2,
        },
        {
          label: '5-SMA',
          data: sma5,
          type: 'line',
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          borderWidth: 2.5,
          borderDash: [5, 3],
          pointRadius: 0,
          tension: 0.4,
          spanGaps: false,
          order: 1,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#9ca3af', boxWidth: 14 } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.raw;
              if (ctx.datasetIndex === 0) {
                return v > 0 ? `D leads by ${v}` : v < 0 ? `V leads by ${Math.abs(v)}` : 'Even';
              }
              return v !== null ? `5-SMA: ${v > 0 ? '+' : ''}${v.toFixed(1)}` : '';
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#9ca3af', maxTicksLimit: 12, maxRotation: 45 }, grid: { color: '#1e2a3a' } },
        y: { ticks: { color: '#9ca3af' }, grid: { color: '#1e2a3a' },
             title: { display: true, text: '← V leading   |   D leading →', color: '#9ca3af', font: { size: 11 } } }
      }
    }
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
        elif self.path == '/icon.png':
            self._send(200, 'image/png', ICON_PNG)
        elif self.path == '/manifest.json':
            self._send(200, 'application/manifest+json', MANIFEST_JSON)
        elif self.path == '/history':
            self._send(200, 'text/html', HISTORY_HTML)
        elif self.path == '/api/matches':
            self._send(200, 'application/json', json.dumps(load_matches()))
        elif self.path == '/api/rounds':
            self._send(200, 'application/json', json.dumps(load_rounds()))
        elif self.path == '/api/courses':
            self._send(200, 'application/json', json.dumps(load_courses()))
        elif self.path == '/api/handicap':
            self._send(200, 'application/json', json.dumps(get_handicap_data()))
        else:
            self._send(404, 'text/plain', 'Not found')

    def do_POST(self):
        n    = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n))
        if self.path == '/api/rounds':
            result = save_round(body)
            if body.get('vd_match'):
                append_match(body['vd_match'])
            self._send(200, 'application/json',
                       json.dumps({'ok': True, 'id': result['id']}))
        elif self.path == '/api/courses':
            save_course(body)
            self._send(200, 'application/json', '{"ok":true}')
        elif self.path == '/api/match':  # legacy
            append_match(body)
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
    print(f'Golf Log → http://localhost:{PORT}')
    HTTPServer(('', PORT), Handler).serve_forever()
