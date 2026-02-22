#!/usr/bin/env python3
"""
Build courses.json from known course data + CSV unique combos.
Run: python3 extract_courses.py
"""
import json, os

OUT_PATH = os.path.join(os.path.dirname(__file__), 'courses.json')

# Governor's Run nine hole data (from COURSE constant in server.py)
LAKES_HOLES = [
    {'number':1,'par':4,'handicap':3},{'number':2,'par':4,'handicap':4},
    {'number':3,'par':5,'handicap':9},{'number':4,'par':3,'handicap':7},
    {'number':5,'par':4,'handicap':2},{'number':6,'par':4,'handicap':6},
    {'number':7,'par':5,'handicap':8},{'number':8,'par':4,'handicap':1},
    {'number':9,'par':3,'handicap':5},
]
FOOTHILLS_HOLES = [
    {'number':10,'par':4,'handicap':2},{'number':11,'par':4,'handicap':1},
    {'number':12,'par':3,'handicap':6},{'number':13,'par':5,'handicap':8},
    {'number':14,'par':3,'handicap':7},{'number':15,'par':4,'handicap':9},
    {'number':16,'par':4,'handicap':3},{'number':17,'par':5,'handicap':5},
    {'number':18,'par':4,'handicap':4},
]
MOUNTAIN_HOLES = [
    {'number':19,'par':4,'handicap':9},{'number':20,'par':4,'handicap':2},
    {'number':21,'par':3,'handicap':8},{'number':22,'par':5,'handicap':6},
    {'number':23,'par':4,'handicap':4},{'number':24,'par':5,'handicap':7},
    {'number':25,'par':3,'handicap':5},{'number':26,'par':4,'handicap':1},
    {'number':27,'par':4,'handicap':3},
]

courses = [
    # ── Governor's Run 18-hole combos ──────────────────────────────────────
    {
        'id': 'gov-lakes-foothills',
        'name': 'Gov Lakes to Foothills',
        'aliases': ['Lakes to Foothills'],
        'rating': 69.9, 'slope': 131, 'par': 72,
        'nines': ['Lakes','Foothills'],
        'holes': LAKES_HOLES + FOOTHILLS_HOLES,
    },
    {
        'id': 'gov-mountain-lakes',
        'name': 'Gov Mountain to Lakes',
        'aliases': ['Mountain to Lakes'],
        'rating': 69.0, 'slope': 130, 'par': 72,
        'nines': ['Mountain','Lakes'],
        'holes': MOUNTAIN_HOLES + LAKES_HOLES,
    },
    {
        'id': 'gov-foothills-mountain',
        'name': 'Gov Foothills to Mountain',
        'aliases': ['Foothills to Mountain'],
        'rating': 69.3, 'slope': 131, 'par': 72,
        'nines': ['Foothills','Mountain'],
        'holes': FOOTHILLS_HOLES + MOUNTAIN_HOLES,
    },
    {
        'id': 'gov-mountain-mountain',
        'name': 'Gov Mountain Mountain',
        'aliases': [],
        'rating': 68.4, 'slope': 130, 'par': 72,
        'nines': ['Mountain','Mountain'],
        'holes': MOUNTAIN_HOLES + MOUNTAIN_HOLES,
    },
    {
        'id': 'gov-foothills-foothills',
        'name': 'Gov Foothills to Foothills',
        'aliases': [],
        'rating': 70.2, 'slope': 132, 'par': 72,
        'nines': ['Foothills','Foothills'],
        'holes': FOOTHILLS_HOLES + FOOTHILLS_HOLES,
    },
    {
        'id': 'gov-lakes-lakes',
        'name': 'Lakes, Lakes',
        'aliases': [],
        'rating': 69.6, 'slope': 129, 'par': 72,
        'nines': ['Lakes','Lakes'],
        'holes': LAKES_HOLES + LAKES_HOLES,
    },
    # ── Governor's Run Blue tee combos ─────────────────────────────────────
    {
        'id': 'gov-lakes-foothills-blue',
        'name': 'Lakes to Foothills Blue',
        'aliases': [],
        'rating': 71.9, 'slope': 135, 'par': 72,
        'nines': ['Lakes','Foothills'],
        'holes': LAKES_HOLES + FOOTHILLS_HOLES,
    },
    {
        'id': 'gov-foothills-mountain-blue',
        'name': 'Foothills to Mountain Blue',
        'aliases': ['Foothills to Mountain Blu'],
        'rating': 71.2, 'slope': 134, 'par': 72,
        'nines': ['Foothills','Mountain'],
        'holes': FOOTHILLS_HOLES + MOUNTAIN_HOLES,
    },
    # ── Governor's Run 9-hole ───────────────────────────────────────────────
    {
        'id': 'gov-lakes',
        'name': 'Lakes (9)',
        'aliases': ['Lakes'],
        'rating': 69.6, 'slope': 129, 'par': 36,
        'nines': ['Lakes'],
        'holes': LAKES_HOLES,
    },
    {
        'id': 'gov-foothills',
        'name': 'Foothills (9)',
        'aliases': ['Foothills'],
        'rating': 70.2, 'slope': 132, 'par': 36,
        'nines': ['Foothills'],
        'holes': FOOTHILLS_HOLES,
    },
    {
        'id': 'gov-mountain',
        'name': 'Mountain (9)',
        'aliases': ['Mountain', 'Mountain 9'],
        'rating': None, 'slope': None, 'par': 36,
        'nines': ['Mountain'],
        'holes': MOUNTAIN_HOLES,
    },
    # ── Outside courses ─────────────────────────────────────────────────────
    {
        'id': 'debordieu-iii',
        'name': 'Debordieu III',
        'aliases': [],
        'rating': 71.7, 'slope': 141, 'par': 72,
        'nines': [], 'holes': [],
    },
    {
        'id': 'holliday-farms-blue',
        'name': 'Holliday Farms Blue',
        'aliases': [],
        'rating': 71.0, 'slope': 143, 'par': 72,
        'nines': [], 'holes': [],
    },
    {
        'id': 'meadow-hills',
        'name': 'Meadow Hills',
        'aliases': [],
        'rating': 69.1, 'slope': 123, 'par': 72,
        'nines': [], 'holes': [],
    },
    {
        'id': 'raccoon-creek',
        'name': 'Raccoon Creek',
        'aliases': [],
        'rating': 69.7, 'slope': 129, 'par': 72,
        'nines': [], 'holes': [],
    },
    {
        'id': 'the-ridge',
        'name': 'The Ridge',
        'aliases': [],
        'rating': 68.9, 'slope': 130, 'par': 72,
        'nines': [], 'holes': [],
    },
    {
        'id': 'new-smyrna-golf-club',
        'name': 'New Smyrna Golf Club',
        'aliases': [],
        'rating': 69.6, 'slope': 123, 'par': 72,
        'nines': [], 'holes': [],
    },
]

with open(OUT_PATH, 'w') as f:
    json.dump(courses, f, indent=2)

print(f'Wrote {len(courses)} courses → {OUT_PATH}')
