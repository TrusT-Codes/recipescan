"""Writes the merged model into a fresh SQLite database."""
import datetime
import os
import sqlite3

from . import config

SOURCE_NAMES = {
    'pfquest': 'pfQuest database', 'pfquest-octo': 'pfQuest-octo (OctoWow data)', 'atlas-cfm': 'Atlas-CFM',
    'atlasloot': 'AtlasLoot TW Edition', 'wh': 'Wowhead Classic (scraped)', 'ow': 'OctoWow DB (scraped)',
}


def write(m, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), encoding='utf-8') as f:
        db.executescript(f.read())
    q = db.execute

    q('INSERT INTO meta VALUES (?, ?)', ('built_at', datetime.datetime.now().isoformat(timespec='seconds')))
    q('INSERT INTO meta VALUES (?, ?)', ('atlas_server', config.ATLAS_SERVER))
    for sid, name in SOURCE_NAMES.items():
        info = m.manifest.get(sid, {})
        q('INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)',
          (sid, name, info.get('version'), info.get('commit'), info.get('date') or (m.manifest.get('extracted_at') if info else None), info.get('remote')))
    for pid, name, kind, _ in config.PROFESSIONS:
        q('INSERT INTO professions VALUES (?, ?, ?)', (pid, name, kind))
    for zid, z in m.zones.items():
        b = z['bounds'] or [None] * 4
        q('INSERT INTO zones VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (zid, z['name'], z['parent'], z['continent'], b[0], b[1], b[2], b[3]))
    for iid, it in m.items.items():
        q('INSERT INTO items VALUES (?, ?, ?, ?, ?, ?)', (iid, it['name'], it['quality'], it['item_level'], it['class'], it['quality_origin']))

    for r in sorted(m.recipes.values(), key=lambda r: r['id']):
        c = r.get('colors') or [None] * 4
        q('INSERT INTO recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            r['id'], r['prof'], r['spell'], r['name'], r['skill_req'], r['skill_origin'], c[0], c[1], c[2], c[3],
            r['crafted_item'], r['qty'][0], r['qty'][1], r['station'],
            r['rep'][0] if r['rep'] else None, r['rep'][1] if r['rep'] else None,
            ','.join(r['atlas_servers']) or None, None if r['atlas_visible'] is None else int(r['atlas_visible']),
            int(r['listed']), r['unlisted_reason'], ','.join(sorted(r['origins']))))
        for i in sorted(r['items']):
            q('INSERT INTO recipe_items VALUES (?, ?)', (i, r['id']))
        for i, n in r['reagents']:
            q('INSERT OR REPLACE INTO reagents VALUES (?, ?, ?)', (r['id'], i, n))
        for i in r['tools']:
            q('INSERT OR IGNORE INTO tools VALUES (?, ?)', (r['id'], i))
        for s in r['sources']:
            q('INSERT INTO recipe_sources (recipe_id, item_id, type, npc_id, object_id, quest_id, chance, stock, note, origin) '
              'VALUES (?,?,?,?,?,?,?,?,?,?)',
              (r['id'], s.get('item'), s['type'], s.get('npc'), s.get('object'), s.get('quest'), s.get('chance'),
               s.get('stock'), s.get('note'), s['origin']))

    for nid, n in m.npcs.items():
        q('INSERT INTO npcs VALUES (?, ?, ?, ?, ?, ?)', (nid, n['name'], n['faction'], n['level'], n['rank'], n['origin']))
        for z, x, y, origin in n['spawns']:
            q('INSERT INTO spawns VALUES (?, ?, ?, ?, ?, ?)', ('npc', nid, z, x, y, origin))
    for oid, o in m.objects.items():
        q('INSERT INTO objects VALUES (?, ?, ?)', (oid, o['name'], o['faction']))
        for z, x, y, origin in o['spawns']:
            q('INSERT INTO spawns VALUES (?, ?, ?, ?, ?, ?)', ('object', oid, z, x, y, origin))
    for qid, qu in m.quests.items():
        q('INSERT INTO quests VALUES (?, ?, ?, ?, ?, ?, ?)', (qid, qu['name'], qu['level'], qu['min_level'], qu['side'], qu['zone'], qu['origin']))
        for kind, x in qu['starters']:
            q('INSERT INTO quest_starters VALUES (?, ?, ?)', (qid, {'U': 'npc', 'O': 'object', 'I': 'item'}[kind], x))
    for d in m.disenchant:
        for mat in d['mats']:
            q('INSERT INTO disenchant_rules VALUES (?, ?, ?, ?, ?, ?, ?)',
              (d['quality'], d['kind'], d['ilvl_min'], d['ilvl_max'], mat['item'], mat['chance'], mat['qty']))
    db.commit()
    db.close()
