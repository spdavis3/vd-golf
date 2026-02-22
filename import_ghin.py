#!/usr/bin/env python3
"""
Import GHIN CSV into ghin_rounds.json.
Run: python3 import_ghin.py
"""
import csv, json, os, re

CSV_PATH = os.path.expanduser('~/Downloads/Golf Handicap Calculator - GHIN.1.csv')
OUT_PATH  = os.path.join(os.path.dirname(__file__), 'ghin_rounds.json')

# Course name → canonical ID (normalize "Gov X" and "X" variants to same ID)
NAME_TO_ID = {
    'gov lakes to foothills':         'gov-lakes-foothills',
    'lakes to foothills':             'gov-lakes-foothills',
    'gov mountain to lakes':          'gov-mountain-lakes',
    'mountain to lakes':              'gov-mountain-lakes',
    'gov foothills to mountain':      'gov-foothills-mountain',
    'foothills to mountain':          'gov-foothills-mountain',
    'gov mountain mountain':          'gov-mountain-mountain',
    'gov foothills to foothills':     'gov-foothills-foothills',
    'lakes, lakes':                   'gov-lakes-lakes',
    'lakes to foothills blue':        'gov-lakes-foothills-blue',
    'foothills to mountain blu':      'gov-foothills-mountain-blue',
    'lakes':                          'gov-lakes',
    'foothills':                      'gov-foothills',
    'mountain':                       'gov-mountain',
    'mountain 9':                     'gov-mountain',
    'debordieu iii':                  'debordieu-iii',
    'holliday farms blue':            'holliday-farms-blue',
    'meadow hills':                   'meadow-hills',
    'raccoon creek':                  'raccoon-creek',
    'the ridge':                      'the-ridge',
    'new smyrna golf club':           'new-smyrna-golf-club',
    'gov foothills to foothills':     'gov-foothills-foothills',
}

SKIP_ROUNDS = {109}  # duplicate

def course_id(name):
    key = name.strip().lower()
    return NAME_TO_ID.get(key, re.sub(r'[^a-z0-9]+', '-', key).strip('-'))

def safe_float(s):
    try: return float(s)
    except: return None

def safe_int(s):
    try: return int(s)
    except: return None

rounds = []
rid = 0

with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        # skip rows where col 0 is not a positive integer (headers, summary rows)
        if not row or not row[0].strip().isdigit():
            continue
        round_num = int(row[0])
        if round_num in SKIP_ROUNDS:
            continue

        date       = row[1].strip() if len(row) > 1 else ''
        course_name = row[2].strip() if len(row) > 2 else ''
        rating     = safe_float(row[3]) if len(row) > 3 else None
        slope      = safe_int(row[4])   if len(row) > 4 else None
        # col 5: PCC (ignored)
        score      = safe_int(row[6])   if len(row) > 6 else None
        adj_score  = safe_int(row[7])   if len(row) > 7 else None
        course_hdcp = safe_int(row[8])  if len(row) > 8 else None
        # col 9: net score (ignored)
        diff       = safe_float(row[10]) if len(row) > 10 else None
        hdcp_index = safe_float(row[11]) if len(row) > 11 else None
        ghin_val   = safe_float(row[12]) if len(row) > 12 else None
        # col 13: GHIN Year (ignored)
        anti_index = safe_float(row[14]) if len(row) > 14 else None
        # col 15: Ave Diff 20 (ignored — we recompute)
        # col 16: VD (match column — handled by vd_matches.json)

        # Skip rounds with no adj score (incomplete rounds)
        if adj_score is None:
            continue

        nine_hole = adj_score < 60
        par = 36 if nine_hole else 72

        rid += 1
        rounds.append({
            'id':           rid,
            'date':         date,
            'course_id':    course_id(course_name),
            'course_name':  course_name,
            'rating':       rating,
            'slope':        slope,
            'par':          par,
            'score':        score,
            'adj_score':    adj_score,
            'course_hdcp':  course_hdcp,
            'differential': diff,
            'ghin_manual':  ghin_val,
            'include_ghin': True,
            'nine_hole':    nine_hole,
            'hole_results': [],
            'vd_match':     None,
        })

with open(OUT_PATH, 'w') as f:
    json.dump(rounds, f, indent=2)

print(f'Imported {len(rounds)} rounds → {OUT_PATH}')
