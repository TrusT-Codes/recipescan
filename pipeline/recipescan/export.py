"""Exports the website data (web/public/data/*.json) from the SQLite database.

Only listed recipes and the entities they reference are exported. Drop sources with many creatures
are folded into one "world" source (count + the creatures with the best chance).
"""
import hashlib
import json
import os
import sqlite3
from collections import defaultdict

from . import config

SCHEMA_VERSION = 1
TOP_WORLD_DROPS = 5


def _write(name, data):
    os.makedirs(config.WEB_DATA, exist_ok=True)
    with open(os.path.join(config.WEB_DATA, name), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        f.write('\n')


def _clean(d):
    return {k: v for k, v in d.items() if v not in (None, [], '')}


def run(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = lambda sql, *a: db.execute(sql, a).fetchall()  # noqa: E731

    sources = defaultdict(list)
    for s in rows('SELECT * FROM recipe_sources ORDER BY id'):
        sources[s['recipe_id']].append(s)
    items_of = defaultdict(list)
    for ri in rows('SELECT * FROM recipe_items ORDER BY item_id'):
        items_of[ri['recipe_id']].append(ri['item_id'])
    reagents = defaultdict(list)
    for rg in rows('SELECT * FROM reagents ORDER BY rowid'):
        reagents[rg['recipe_id']].append([rg['item_id'], rg['count']])
    tools = defaultdict(list)
    for t in rows('SELECT * FROM tools ORDER BY rowid'):
        tools[t['recipe_id']].append(t['item_id'])

    used = {'npcs': set(), 'objects': set(), 'quests': set(), 'items': set()}
    recipes = []
    for r in rows('SELECT * FROM recipes WHERE listed = 1 ORDER BY profession_id, skill_req, name'):
        out_src = []
        drops = [s for s in sources[r['id']] if s['type'] == 'drop' and s['npc_id']]
        world = len({s['npc_id'] for s in drops}) > config.WORLD_DROP_MIN_UNITS
        if world:
            best = sorted(drops, key=lambda s: -(s['chance'] or 0))
            top, seen = [], set()
            for s in best:
                if s['npc_id'] not in seen:
                    seen.add(s['npc_id'])
                    top.append([s['npc_id'], s['chance']])
                if len(top) >= TOP_WORLD_DROPS:
                    break
            out_src.append({'type': 'world', 'count': len({s['npc_id'] for s in drops}), 'top': top,
                            'origin': drops[0]['origin']})
            used['npcs'] |= {n for n, _ in top}
        for s in sources[r['id']]:
            if world and s['type'] == 'drop' and s['npc_id']:
                continue
            e = _clean({'type': s['type'], 'npc': s['npc_id'], 'object': s['object_id'], 'quest': s['quest_id'],
                        'chance': s['chance'], 'stock': s['stock'] or None, 'note': s['note'], 'item': s['item_id'],
                        'origin': s['origin']})
            if e['type'] == 'vendor' and r['rep_faction']:
                e['type'] = 'reputation'
            out_src.append(e)
            for k, bucket in (('npc', 'npcs'), ('object', 'objects'), ('quest', 'quests')):
                if e.get(k):
                    used[bucket].add(e[k])
        rec = _clean({
            'id': r['id'], 'profession': r['profession_id'], 'name': r['name'], 'spell': r['spell_id'],
            'skill': r['skill_req'],
            'colors': [r['skill_orange'], r['skill_yellow'], r['skill_green'], r['skill_grey']] if r['skill_orange'] is not None else None,
            'craftedItem': r['crafted_item_id'],
            'craftedQty': [r['crafted_qty_min'], r['crafted_qty_max']] if r['crafted_qty_min'] else None,
            'recipeItems': items_of[r['id']], 'station': r['station'],
            'reputation': {'faction': r['rep_faction'], 'level': r['rep_level']} if r['rep_faction'] else None,
            'reagents': reagents[r['id']], 'tools': tools[r['id']], 'sources': out_src,
        })
        recipes.append(rec)
        used['items'] |= set(items_of[r['id']]) | {i for i, _ in reagents[r['id']]} | set(tools[r['id']])
        if r['crafted_item_id']:
            used['items'].add(r['crafted_item_id'])

    for qid in list(used['quests']):
        for st in rows('SELECT * FROM quest_starters WHERE quest_id = ?', qid):
            used['npcs' if st['kind'] == 'npc' else 'objects' if st['kind'] == 'object' else 'items'].add(st['ref_id'])

    def spawns(kind, ref):
        return [[s['zone_id'], s['x'], s['y']] if s['x'] is not None else [s['zone_id']]
                for s in rows('SELECT * FROM spawns WHERE kind = ? AND ref_id = ? ORDER BY rowid', kind, ref)]

    npcs = {}
    for n in rows('SELECT * FROM npcs ORDER BY id'):
        if n['id'] in used['npcs']:
            npcs[n['id']] = _clean({'name': n['name'], 'faction': n['faction'], 'level': n['level'], 'rank': n['rank'] or None,
                                    'spawns': spawns('npc', n['id'])})
    objects = {o['id']: _clean({'name': o['name'], 'faction': o['faction'], 'spawns': spawns('object', o['id'])})
               for o in rows('SELECT * FROM objects ORDER BY id') if o['id'] in used['objects']}
    quests = {}
    for q in rows('SELECT * FROM quests ORDER BY id'):
        if q['id'] in used['quests']:
            st = [[s['kind'], s['ref_id']] for s in rows('SELECT * FROM quest_starters WHERE quest_id = ?', q['id'])]
            quests[q['id']] = _clean({'name': q['name'], 'level': q['level'], 'minLevel': q['min_level'], 'side': q['side'],
                                      'zone': q['zone_id'], 'starters': st})
    items = {i['id']: _clean({'name': i['name'], 'quality': i['quality'], 'itemLevel': i['item_level'], 'class': i['class']})
             for i in rows('SELECT * FROM items ORDER BY id') if i['id'] in used['items']}
    zone_ids = {s[0] for e in list(npcs.values()) + list(objects.values()) for s in e.get('spawns', [])}
    zone_ids |= {q['zone'] for q in quests.values() if q.get('zone')}
    zones = {z['id']: _clean({'name': z['name'], 'parent': z['parent_id'], 'continent': z['continent_id'],
                              'bounds': [z['x_min'], z['y_min'], z['x_max'], z['y_max']] if z['x_min'] is not None else None})
             for z in rows('SELECT * FROM zones ORDER BY id') if z['id'] in zone_ids}

    disenchant = defaultdict(list)
    for d in rows('SELECT * FROM disenchant_rules ORDER BY rowid'):
        disenchant[(d['quality'], d['kind'], d['ilvl_min'], d['ilvl_max'])].append([d['material'], d['chance'], d['quantity']])

    counts = defaultdict(int)
    for r in recipes:
        counts[r['profession']] += 1
    files = {'recipes.json': recipes, 'items.json': items, 'npcs.json': npcs, 'objects.json': objects,
             'quests.json': quests, 'zones.json': zones}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]
    meta = {
        'schemaVersion': SCHEMA_VERSION,
        'dataVersion': digest,   # changes only when exported content changes
        'server': db.execute("SELECT value FROM meta WHERE key = 'atlas_server'").fetchone()[0],
        'professions': [_clean({'id': p['id'], 'name': p['name'], 'kind': p['kind'], 'recipes': counts[p['id']]})
                        for p in rows('SELECT * FROM professions ORDER BY kind, name')],
        'sources': [_clean(dict(s)) for s in rows('SELECT * FROM sources ORDER BY id')],
        'disenchant': [{'quality': k[0], 'kind': k[1], 'ilvlMin': k[2], 'ilvlMax': k[3], 'mats': v} for k, v in disenchant.items()],
    }
    _write('meta.json', meta)
    for name, data in files.items():
        _write(name, data)
    db.close()
    return {'recipes': len(recipes), 'items': len(items), 'npcs': len(npcs), 'objects': len(objects), 'quests': len(quests), 'zones': len(zones)}
