# -*- coding: utf-8 -*-
# Builds recipes-vendor-report.html from ow.txt + wh.txt + disen.txt + template.html
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'index.html')

def read(name):
    p = os.path.join(HERE, 'data', name)
    return open(p).read().splitlines() if os.path.exists(p) else []

ALIASES = {
    'Elwynn Forrest': 'Elwynn Forest', 'Silverpine Forrest': 'Silverpine Forest',
    'Ogrimmar': 'Orgrimmar', 'Hinterlands': 'The Hinterlands', 'Aszhara': 'Azshara',
    'Ungoro Crater': "Un'Goro Crater", 'Swamp O fSorrows': 'Swamp of Sorrows',
}
UNMAPPED = ('Azeroth',)

def canon(z):
    return ALIASES.get(z, z)

def parse_locs(s):
    locs = []
    for part in [p.strip() for p in s.split(';') if p.strip()]:
        m = re.match(r'^(.*?) ([\d.]+),([\d.]+)$', part)
        if m:
            locs.append((canon(m.group(1)), float(m.group(2)), float(m.group(3))))
    return locs

def parse_react(s):
    return [0 if x is None else int(x) for x in json.loads(s)]  # [Alliance, Horde]

def faction_label(a, h):
    if a == 1 and h == 1: return 'Both friendly'
    if a == 1: return 'Alliance'
    if h == 1: return 'Horde'
    if a == -1 and h == -1: return 'Hostile to both'
    return 'Neutral'

def allowed_a(a, h): return a == 1 or (a == 0 and h <= 0)
def allowed_h(a, h): return h == 1 or (h == 0 and a <= 0)

def clean_name(n):
    if n and n[0].isdigit():
        n = n[1:]
    return re.sub(r'^(Pattern|Formula): ', '', n)

vendors = {}     # id -> dict
wh_ids = set()
recipes = {}     # (prof, rid) -> dict

def add_vendor(src, vid, name, react_s, zones_s):
    locs = parse_locs(zones_s)
    if src == 'wh':
        wh_ids.add(vid)
    v = vendors.get(vid)
    if v is None:
        vendors[vid] = {'id': vid, 'name': name, 'react': parse_react(react_s), 'locs': locs}
    elif not v['locs'] and locs:
        v['locs'] = locs   # OctoWow locations/reactions win; Wowhead only fills gaps

def add_recipe(prof, rid, name, skill, vids):
    r = recipes.get((prof, rid))
    if r is None:
        r = {'rid': rid, 'prof': prof, 'name': clean_name(name), 'skill': int(skill), 'vendors': []}
        recipes[(prof, rid)] = r
    for v in vids.split(','):
        if v and v not in r['vendors']:
            r['vendors'].append(v)

for line in read('ow.txt'):
    p = line.split('|')
    if p[0] == 'V': add_vendor('ow', p[1], p[2], p[3], p[4])
    elif p[0] == 'I': add_recipe(p[1], p[2], p[3], p[4], p[5])
for line in read('wh.txt'):
    p = line.split('|')
    if p[0] == 'V': add_vendor('wh', p[1], p[2], p[3], p[4])
    elif p[0] == 'I': add_recipe(p[1], p[2], p[3], p[4], p[6])

disen = {}
for line in read('disen.txt'):
    if '|' in line:
        k, m = line.split('|', 1)
        disen[k.strip()] = m.strip()

# vendor records for the page
VEND = {}
for vid, v in vendors.items():
    a, h = v['react']
    locs = [l for l in v['locs']]
    disp = '; '.join('%s %s, %s' % (z, ('%.1f' % x).rstrip('0').rstrip('.'), ('%.1f' % y).rstrip('0').rstrip('.')) for z, x, y in locs) or 'No location listed'
    pos = None
    if locs and locs[0][0] not in UNMAPPED:
        pos = [locs[0][0], locs[0][1], locs[0][2]]
    url = ('https://www.wowhead.com/classic/npc=' + vid) if vid in wh_ids else ('https://octowow.st/db/?npc=' + vid)
    VEND[vid] = {
        'n': v['name'], 'u': url, 'src': 'wh' if vid in wh_ids else 'ow',
        'loc': disp, 'pos': pos, 'fac': faction_label(a, h),
        'A': allowed_a(a, h), 'H': allowed_h(a, h),
    }

ROWS = {'tailoring': [], 'leatherworking': [], 'enchanting': []}
for (prof, rid), r in recipes.items():
    vs = [v for v in r['vendors'] if v in VEND]
    if not vs or prof not in ROWS:
        continue
    ROWS[prof].append({
        'id': rid, 's': r['skill'], 'n': r['name'], 'v': vs,
        'd': disen.get(rid, '-') if prof == 'tailoring' else '',
    })
for p in ROWS:
    ROWS[p].sort(key=lambda x: (x['s'], x['n']))

used = set()
for p in ROWS:
    for r in ROWS[p]:
        used.update(r['v'])
VEND = dict((k, v) for k, v in VEND.items() if k in used)

data = {'rows': ROWS, 'vendors': VEND}
tpl = open(os.path.join(HERE, 'template.html')).read()
page = tpl.replace('/*DATA*/null', json.dumps(data, separators=(',', ':')))
open(OUT, 'w').write(page)
print(dict((k, len(v)) for k, v in ROWS.items()), len(VEND), 'vendors')
