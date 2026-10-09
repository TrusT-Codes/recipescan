"""Scraped prototype data in data/*.txt (Wowhead Classic = 'wh', OctoWow DB = 'ow').

Formats are documented in docs/handover-*.md. This module only parses; merging happens in build.py.
"""
import json
import os
import re

from .. import config

ZONE_ALIASES = {
    'Elwynn Forrest': 'Elwynn Forest', 'Silverpine Forrest': 'Silverpine Forest',
    'Ogrimmar': 'Orgrimmar', 'Hinterlands': 'The Hinterlands', 'Aszhara': 'Azshara',
    'Ungoro Crater': "Un'Goro Crater", 'Hilsbrad Foothills': 'Hillsbrad Foothills', 'Swamp O fSorrows': 'Swamp of Sorrows',
    'Dire Maul (Dungeon)': 'Dire Maul',
}
UNMAPPED_ZONES = ('Azeroth',)


def canon_zone(z):
    z = z.strip()
    return ZONE_ALIASES.get(z, z)


def _lines(name):
    p = os.path.join(config.DATA, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8') as f:
        return [l.rstrip('\n') for l in f if l.strip() and not l.startswith('#')]


def _react(s):
    v = [0 if x is None else int(x) for x in json.loads(s)] + [0, 0]   # [Alliance, Horde], may be short
    return v[0], v[1]


def _locs(s):
    out = []
    for part in [p.strip() for p in s.split(';') if p.strip()]:
        m = re.match(r'^(.*?) ([\d.]+),([\d.]+)$', part)
        if m:
            out.append((canon_zone(m.group(1)), float(m.group(2)), float(m.group(3))))
    return out


def _int(s):
    return int(s) if s not in (None, '', 'None') else None


def clean_recipe_name(n):
    if n and n[0].isdigit():  # ow_crafting.txt prefixes the item quality digit
        n = n[1:]
    return re.sub(config.RECIPE_PREFIX, '', n)


def load():
    """Returns a dict of normalized legacy records."""
    npcs = {}   # id -> {name, react, locs, zone_refs, src: set}

    def npc(src, nid, name, react=None, locs=None, zones=None):
        nid = int(nid)
        n = npcs.setdefault(nid, {'name': name, 'react': None, 'locs': [], 'zones': [], 'src': set()})
        n['src'].add(src)
        if not n['name']:
            n['name'] = name
        if react is not None and (n['react'] is None or src == 'ow'):
            n['react'] = react
        if locs and (not n['locs'] or src == 'ow'):
            n['locs'] = locs   # OctoWow locations win; Wowhead only fills gaps
        for z in zones or []:
            if z not in n['zones']:
                n['zones'].append(z)
        return nid

    # vendor lists: V = vendor, I = recipe item sold by vendors
    vendor_recipes = []   # {src, prof, item, name, skill, crafted, vendors}
    for src, files in (('ow', ('ow.txt', 'ow_crafting.txt')), ('wh', ('wh.txt', 'wh_crafting.txt', 'wh_npcs.txt'))):
        for fn in files:
            for line in _lines(fn):
                p = line.split('|')
                if p[0] == 'V':
                    npc(src, p[1], p[2], _react(p[3]), _locs(p[4]))
                elif p[0] == 'I':
                    if src == 'ow':
                        rec = {'prof': p[1], 'item': int(p[2]), 'name': clean_recipe_name(p[3]), 'skill': _int(p[4]),
                               'crafted': None, 'vendors': [int(v) for v in p[5].split(',') if v]}
                    else:
                        rec = {'prof': p[1], 'item': int(p[2]), 'name': clean_recipe_name(p[3]), 'skill': _int(p[4]),
                               'crafted': _int(p[5]), 'vendors': [int(v) for v in p[6].split(',') if v]}
                    rec['src'] = src
                    vendor_recipes.append(rec)

    # full recipe lists: R = recipe, S = one source of the R line above
    recipes = []   # {src, prof, key, item, spell (teach), name, skill, crafted, quality, rep, sources: [...]}
    quests = {}    # id -> {name, side, zones, src}
    for src, fn in (('wh', 'recipes_wh.txt'), ('ow', 'recipes_ow.txt')):
        cur = None
        for line in _lines(fn):
            p = line.split('|')
            if p[0] == 'R':
                key = p[2]
                cur = {'src': src, 'prof': p[1], 'key': key, 'item': int(key) if key.isdigit() else None,
                       'spell': int(key[1:]) if key.startswith('s') else _int(p[6]),
                       'teach': _int(p[6]), 'name': clean_recipe_name(p[4]), 'skill': _int(p[5]) or None,
                       'crafted': _int(p[7]), 'quality': _int(p[8]),
                       'rep': (p[9], p[10]) if len(p) > 10 and p[9] else None, 'sources': []}
                recipes.append(cur)
            elif p[0] == 'S' and cur is not None:
                kind = p[2]
                if kind == 'V':
                    nid = npc(src, p[3], p[4], _react(p[6]), zones=[z for z in p[5].split(',') if z])
                    cur['sources'].append({'type': 'vendor', 'npc': nid})
                elif kind == 'T':
                    cur['sources'].append({'type': 'trainer', 'npc': int(p[3])})
                elif kind == 'Q':
                    qid = int(p[3])
                    quests.setdefault(qid, {'name': p[4], 'side': _int(p[5]), 'zones': [z for z in p[6].split(',') if z], 'src': src})
                    cur['sources'].append({'type': 'quest', 'quest': qid})
                elif kind == 'D':
                    nid = npc(src, p[3], p[4], _react(p[6]), zones=[z for z in p[5].split(',') if z])
                    pct = float(p[7]) if len(p) > 7 and p[7] else None
                    cur['sources'].append({'type': 'drop', 'npc': nid, 'chance': pct})
                elif kind == 'X':
                    cur['sources'].append({'type': 'world', 'note': p[3]})

    items = {}
    for line in _lines('items.txt'):
        p = line.split('|')
        if len(p) >= 5:
            items[int(p[0])] = {'name': p[1], 'quality': int(p[2]), 'ilvl': int(p[3]), 'class': int(p[4])}
    crafted = {}
    for line in _lines('crafted.txt'):
        p = line.split('|')
        if len(p) >= 2:
            crafted[int(p[0])] = int(p[1])

    zones = {}
    for fn in ('zones.txt', 'zones_extra.txt'):
        for line in _lines(fn):
            p = line.split('|')
            if len(p) >= 2 and p[1]:
                zones[int(p[0])] = canon_zone(p[1])

    sod = {int(l.split('|')[0]) for l in _lines('sod_excluded.txt')}

    disenchant = []
    for line in _lines('disen_table.txt'):
        q, kind, lo, hi, mats = line.split('|')
        disenchant.append({'quality': int(q), 'kind': kind, 'ilvl_min': int(lo), 'ilvl_max': int(hi),
                           'mats': [{'item': m.split(':')[0], 'chance': float(m.split(':')[1]), 'qty': m.split(':')[2]}
                                    for m in mats.split(';')]})

    return {'npcs': npcs, 'vendor_recipes': vendor_recipes, 'recipes': recipes, 'quests': quests,
            'items': items, 'crafted': crafted, 'zones': zones, 'sod': sod, 'disenchant': disenchant}
