# -*- coding: utf-8 -*-
# Builds index.html from data/*.txt + template.html
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'index.html')

def read(name):
    p = os.path.join(HERE, 'data', name)
    return [l for l in open(p).read().splitlines() if not l.startswith('#')] if os.path.exists(p) else []

ALIASES = {
    'Elwynn Forrest': 'Elwynn Forest', 'Silverpine Forrest': 'Silverpine Forest',
    'Ogrimmar': 'Orgrimmar', 'Hinterlands': 'The Hinterlands', 'Aszhara': 'Azshara',
    'Ungoro Crater': "Un'Goro Crater", 'Hilsbrad Foothills': 'Hillsbrad Foothills', 'Swamp O fSorrows': 'Swamp of Sorrows',
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
    return re.sub(r'^(Pattern|Formula|Plans|Schematic|Recipe|Manual|Technique): ', '', n)

vendors = {}     # id -> dict
wh_ids = set()
wh_recipes = set()   # (prof, rid) present on Wowhead
crafted = {}     # recipe id -> crafted item id
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

def add_recipe(prof, rid, name, skill, vids, authoritative=False):
    r = recipes.get((prof, rid))
    if r is None:
        r = {'rid': rid, 'prof': prof, 'name': clean_name(name), 'skill': int(skill), 'vendors': []}
        recipes[(prof, rid)] = r
    elif int(skill) > 0 and (r['skill'] <= 0 or authoritative):
        r['skill'] = int(skill)   # Wowhead 'learnedat' wins over OctoWow, which is sometimes missing or off
    for v in vids.split(','):
        if v and v not in r['vendors']:
            r['vendors'].append(v)

for line in read('ow.txt') + read('ow_crafting.txt'):
    p = line.split('|')
    if p[0] == 'V': add_vendor('ow', p[1], p[2], p[3], p[4])
    elif p[0] == 'I': add_recipe(p[1], p[2], p[3], p[4], p[5])
for line in read('wh.txt') + read('wh_crafting.txt') + read('wh_npcs.txt'):
    p = line.split('|')
    if p[0] == 'V': add_vendor('wh', p[1], p[2], p[3], p[4])
    elif p[0] == 'I':
        add_recipe(p[1], p[2], p[3], p[4], p[6], True)
        wh_recipes.add((p[1], p[2]))
        if p[5] != 'None': crafted[p[2]] = p[5]

# crafted-item info (data/items.txt) and extra recipe -> crafted links (data/crafted.txt)
items = {}   # item id -> (name, quality, ilvl, class)
for line in read('items.txt'):
    p = line.split('|')
    if len(p) >= 5: items[p[0]] = (p[1], int(p[2]), int(p[3]), int(p[4]))
for line in read('crafted.txt'):
    p = line.split('|')
    if len(p) >= 2 and p[0] not in crafted: crafted[p[0]] = p[1]

PROFS = ['tailoring', 'leatherworking', 'enchanting', 'alchemy', 'blacksmithing', 'engineering', 'cooking', 'firstaid', 'jewelcrafting']
ROWS_PROFS = set(PROFS)

# ---- recipes outside the vendor lists: trainers, quests, drops, reputation (data/recipes_*.txt, data/zones.txt)
zones = {}   # zone id -> name
for line in read('zones.txt') + read('zones_extra.txt'):
    p = line.split('|')
    if len(p) >= 2: zones[p[0]] = canon(p[1])

def zone_list(s):
    """'12,3' or 'Zone Name' -> list of zone names (ids resolved through zones.txt)."""
    out = []
    for z in [x.strip() for x in s.split(',') if x.strip()]:
        if re.match(r'^-?\d+$', z):
            n = zones.get(z)         # negative ids are quest categories, unknown ids have no name
        else:
            n = canon(z)
        if n and n not in out: out.append(n)
    return out

SRC_ORDER = 'VRTQD'
entries = {}     # (prof, key) -> [(entity id, type)]
extra = {}       # (prof, key) -> {'rep': [name, level], 'q': quality, 'craft': item id, 'src': 'wh'/'ow', 'sp': spell id, 'link': url}
ents = {}        # non-vendor entities: id -> record for the page
labels = {}      # world drop label -> entity id

def add_entry(k, eid, t):
    lst = entries.setdefault(k, [])
    if (eid, t) not in lst: lst.append((eid, t))

def mob_record(src, nid, name, zs, pct):
    n = name if pct == '' else '%s (%s%%)' % (name, pct)
    url = ('https://www.wowhead.com/classic/npc=' if src == 'wh' else 'https://octowow.st/db/?npc=') + nid
    return {'n': n, 'u': url, 'src': src, 'loc': '; '.join(zone_list(zs)) or 'No location listed', 'pos': None,
            'fac': 'Any', 'A': True, 'H': True}

def side_label(side):
    return {'1': 'Alliance', '2': 'Horde'}.get(side, 'Both')

cur = None
for fname in ('recipes_wh.txt', 'recipes_ow.txt'):
    for line in read(fname):
        p = line.split('|')
        if p[0] == 'R':
            prof, key, src = p[1], p[2], p[3]
            cur = None
            if prof not in ROWS_PROFS: continue
            k = (prof, key)
            if k not in recipes:
                if not p[6]: continue          # no spell behind the item: nothing to craft, skip unless already listed
                recipes[k] = {'rid': key, 'prof': prof, 'name': clean_name(p[4]), 'skill': 0, 'vendors': []}
            r = recipes[k]
            skill = int(p[5] or 0)
            if skill > 0 and (r['skill'] <= 0 or src == 'wh'): r['skill'] = skill
            if src == 'wh' and not key.startswith('s'): wh_recipes.add(k)
            if key.startswith('s'): wh_recipes.add(k)
            ex = extra.setdefault(k, {})
            ex['src'] = src
            if p[7]: ex['craft'] = p[7]; crafted.setdefault(key, p[7])
            if p[8]: ex['q'] = int(p[8])
            if p[9]: ex['rep'] = [p[9], p[10]]
            cur = k
        elif p[0] == 'S' and cur is not None:
            kind = p[2]
            src = extra[cur]['src']
            if kind == 'V':
                vid = p[3]
                if vid not in vendors:
                    vendors[vid] = {'id': vid, 'name': p[4], 'react': parse_react(p[6]), 'locs': [], 'zn': zone_list(p[5])}
                    if src == 'wh': wh_ids.add(vid)
                add_entry(cur, vid, 'V')
            elif kind == 'T':
                add_entry(cur, p[3], 'T')
            elif kind == 'Q':
                eid = 'q' + p[3]
                ents[eid] = {'n': p[4], 'u': ('https://www.wowhead.com/classic/quest=' if src == 'wh' else 'https://octowow.st/db/?quest=') + p[3],
                             'src': src, 'loc': '; '.join(zone_list(p[6])) or 'No location listed', 'pos': None,
                             'fac': side_label(p[5]), 'A': p[5] != '2', 'H': p[5] != '1'}
                add_entry(cur, eid, 'Q')
            elif kind == 'D':
                eid = 'm%s' % p[3]
                pct = p[7] if len(p) > 7 else ''
                eid = 'm%s_%s' % (p[3], pct.replace('.', '_'))
                ents[eid] = mob_record(src, p[3], p[4], p[5], pct)
                add_entry(cur, eid, 'D')
            elif kind == 'X':
                eid = labels.setdefault(p[3], 'x%d' % len(labels))
                ents[eid] = {'n': p[3], 'u': '', 'src': src, 'loc': 'Various', 'pos': None, 'fac': 'Any', 'A': True, 'H': True}
                add_entry(cur, eid, 'D')

# disenchant table: (quality, kind, min, max, [(mat, prob, qty)])
DE_RULES = []
for line in read('disen_table.txt'):
    if not line or line.startswith('#'): continue
    q, kind, lo, hi, mats = line.split('|')
    DE_RULES.append((int(q), kind, int(lo), int(hi), [(m.split(':')[0], float(m.split(':')[1]), m.split(':')[2]) for m in mats.split(';')]))
QNAME = {2: 'Uncommon', 3: 'Rare', 4: 'Epic'}

def disenchant(rid):
    iid = crafted.get(rid)
    it = items.get(iid)
    if not it: return None
    name, q, ilvl, cls = it
    if q < 2 or cls not in (2, 4): return {'l': 'Not disenchantable', 'm': []}
    kind = 'W' if cls == 2 else 'A'
    for rq, rk, lo, hi, mats in DE_RULES:
        if rq == q and rk in ('*', kind) and lo <= ilvl <= hi:
            return {'l': 'ilvl %d %s %s' % (ilvl, QNAME[q], 'weapon' if kind == 'W' else 'armor'),
                    'm': [[m, (('%.1f' % p).rstrip('0').rstrip('.')), qty] for m, p, qty in mats]}
    return {'l': 'ilvl %d %s: not in table' % (ilvl, QNAME.get(q, '?')), 'm': []}

# vendor / trainer records for the page (NPCs with a map position are used by the route planner)
VEND = {}
for vid, v in vendors.items():
    a, h = v['react']
    locs = [l for l in v['locs']]
    disp = '; '.join('%s %s, %s' % (z, ('%.1f' % x).rstrip('0').rstrip('.'), ('%.1f' % y).rstrip('0').rstrip('.')) for z, x, y in locs) \
        or '; '.join(v.get('zn', [])) or 'No location listed'
    pos = None
    if locs and locs[0][0] not in UNMAPPED:
        pos = [locs[0][0], locs[0][1], locs[0][2]]
    url = ('https://www.wowhead.com/classic/npc=' + vid) if vid in wh_ids else ('https://octowow.st/db/?npc=' + vid)
    VEND[vid] = {
        'n': v['name'], 'u': url, 'src': 'wh' if vid in wh_ids else 'ow',
        'loc': disp, 'pos': pos, 'fac': faction_label(a, h),
        'A': allowed_a(a, h), 'H': allowed_h(a, h),
    }
VEND.update(ents)

DE_PROFS = ('tailoring', 'leatherworking', 'blacksmithing', 'engineering')
ROWS = dict((p, []) for p in PROFS)
# recipes added in Season of Discovery (Wowhead "Added in patch 1.15.x"), not part of this report
SOD = set(l.split('|')[0] for l in read('sod_excluded.txt') if l)
for (prof, rid), r in recipes.items():
    if rid in SOD or prof not in ROWS:
        continue
    k = (prof, rid)
    ex = extra.get(k, {})
    ent = [(v, 'V') for v in r['vendors']]
    for e in entries.get(k, []):
        if e not in ent: ent.append(e)
    ent = [(eid, t) for eid, t in ent if eid in VEND]
    if not ent:
        continue
    rep = ex.get('rep')
    # a vendor that sells a recipe needing faction standing is a reputation vendor, not a plain vendor
    types = {}
    for eid, t in ent:
        types[eid] = 'R' if (t == 'V' and rep) else t
    ent.sort(key=lambda e: SRC_ORDER.index(types[e[0]]))
    # crafted item: rarity for every recipe, item level for the disenchant columns
    it = items.get(ex.get('craft') or crafted.get(rid))
    q = it[1] if it else ex.get('q')
    is_item = rid.isdigit()
    row = {
        'id': rid, 's': r['skill'], 'n': r['name'], 'v': [eid for eid, t in ent], 'st': types,
        'u': (('https://www.wowhead.com/classic/item=' if k in wh_recipes else 'https://octowow.st/db/?item=') + rid) if is_item
             else 'https://www.wowhead.com/classic/spell=' + rid[1:],
        'w': 'wh' if k in wh_recipes else 'ow',
        'd': disenchant(rid) if prof in DE_PROFS else None,
    }
    if q is not None: row['q'] = q
    if rep: row['rep'] = rep
    if prof in DE_PROFS and it: row['i'] = it[2]
    ROWS[prof].append(row)
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

