# -*- coding: utf-8 -*-
"""Scrape every Wowhead Classic profession recipe and where to get it (Python 3).

Usage: py -3 scripts/scrape_wowhead.py <stage> [<stage> ...]
Stages, in order (each one is cached, so it is safe to re-run):
  lists     profession spell lists, recipe item lists and crafted item lists      (~20 requests)
  items     one page per recipe item: teaches-spell, vendors, drops, quests, rep    (~800 requests)
  trainers  trainer NPCs per profession and the spells each one teaches
  quests    quest pages for recipe quest rewards (zone of the quest giver)
  npcs      NPC pages (name, zones, coordinates) for every vendor / trainer / quest giver not yet in data/
  emit      write data/recipes_wh.txt, data/wh_npcs.txt, data/zones.txt and extend data/items.txt
Intermediate JSON goes to scratch/ (git-ignored).
"""
import json
import os
import re
import sys

from wh_lib import *

SCRATCH = os.path.join(ROOT, 'scratch')
PROFS = ['tailoring', 'leatherworking', 'enchanting', 'alchemy', 'blacksmithing', 'engineering', 'cooking', 'firstaid']
SPELL_PATH = {
    'tailoring': 'spells/professions/tailoring', 'leatherworking': 'spells/professions/leatherworking',
    'enchanting': 'spells/professions/enchanting', 'alchemy': 'spells/professions/alchemy',
    'blacksmithing': 'spells/professions/blacksmithing', 'engineering': 'spells/professions/engineering',
    'cooking': 'spells/secondary-skills/cooking', 'firstaid': 'spells/secondary-skills/first-aid',
}
ITEM_SLUG = {'tailoring': 'tailoring', 'leatherworking': 'leatherworking', 'enchanting': 'enchanting', 'alchemy': 'alchemy',
             'blacksmithing': 'blacksmithing', 'engineering': 'engineering', 'cooking': 'cooking', 'firstaid': 'first-aid'}
SKILL_ID = {'tailoring': 197, 'leatherworking': 165, 'enchanting': 333, 'alchemy': 171, 'blacksmithing': 164,
            'engineering': 202, 'cooking': 185, 'firstaid': 129}
# "crafted items" filter id per profession (items?filter=86;<id>;0); only needed where disenchanting applies
CRAFTED_FILTER = {'tailoring': 10, 'leatherworking': 8, 'blacksmithing': 2, 'engineering': 5}
DE_PROFS = tuple(CRAFTED_FILTER)
# Season of Discovery recipe items have ids >= 200000 (1.15.x); the older ones are listed in data/sod_excluded.txt
SOD_ID_MIN = 200000
SOD_SPELL_MIN = 400000   # Season of Discovery spells
RANK_SPELLS = ('Tailoring', 'Leatherworking', 'Enchanting', 'Alchemy', 'Blacksmithing', 'Engineering', 'Cooking', 'First Aid')


def jload(name, default=None):
    p = os.path.join(SCRATCH, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def jsave(name, obj):
    json.dump(obj, open(os.path.join(SCRATCH, name), 'w', encoding='utf-8'))


def sod_ids():
    return set(int(l.split('|')[0]) for l in read_lines('sod_excluded.txt'))


# ---------------------------------------------------------------- stage: lists
def stage_lists():
    out = {}
    for prof in PROFS:
        sp = var_array(fetch(SPELL_PATH[prof]), 'var listviewspells = ')
        it = var_array(fetch('items/recipes/' + ITEM_SLUG[prof]), 'var listviewitems = ')
        crafted = []
        if prof in CRAFTED_FILTER:
            crafted = var_array(fetch('items?filter=86;%d;0' % CRAFTED_FILTER[prof]), 'var listviewitems = ')
        out[prof] = {'spells': sp, 'items': it, 'crafted': crafted}
        print(prof, len(sp), 'spells', len(it), 'recipe items', len(crafted), 'crafted items', flush=True)
    jsave('lists.json', out)


def recipe_ids(lists):
    sod = sod_ids()
    seen, ids = set(), []
    for prof in PROFS:
        for i in lists[prof]['items']:
            if i['id'] < SOD_ID_MIN and i['id'] not in sod and i['id'] not in seen:
                seen.add(i['id'])
                ids.append(i['id'])
    return ids


# ---------------------------------------------------------------- stage: items
def stage_items():
    lists = jload('lists.json')
    ids = recipe_ids(lists)
    print(len(ids), 'recipe items', flush=True)
    for n, iid in enumerate(ids):
        fetch('item=%d' % iid)
        if n % 50 == 0:
            print(n, flush=True)


def parse_item(iid):
    h = fetch('item=%d' % iid)
    r = {'id': iid}
    m = re.search(r'g_items\[%d\]\.tooltip_enus = "(.*?)";\n' % iid, h)
    tt = m.group(1).replace(BS + '/', '/').replace(BS + '"', '"') if m else ''
    rep = re.search(r'Requires <a href="/classic/faction=(\d+)/[^"]*" class="q\d?">([^<]+)</a> - (\w+)', tt)
    r['rep'] = [rep.group(2), rep.group(3)] if rep else None
    name = re.search(r'<b class="q\d?">([^<]+)</b>', tt)
    r['name'] = name.group(1) if name else None
    r['teach'] = listview(h, 'teaches-recipe') or []
    r['sold'] = listview(h, 'sold-by') or []
    r['drop'] = (listview(h, 'dropped-by') or []) + (listview(h, 'pick-pocketed-from') or [])
    r['quest'] = listview(h, 'reward-from-q') or []
    r['cont'] = (listview(h, 'contained-in-item') or []) + (listview(h, 'contained-in-object') or []) + (listview(h, 'fished-in') or [])
    return r


# ---------------------------------------------------------------- stage: trainers
def trainer_spells(lists, taught):
    """Spells learned from a trainer (source 6) that no recipe item teaches."""
    out = {}
    for prof in PROFS:
        for s in lists[prof]['spells']:
            if 6 in s.get('source', []) and s['id'] not in taught:
                out[s['id']] = prof
    return out


def taught_spells(lists):
    taught = {}
    for iid in recipe_ids(lists):
        for t in parse_item(iid)['teach']:
            taught.setdefault(t['id'], []).append(iid)
    return taught


def stage_trainers():
    lists = jload('lists.json')
    taught = taught_spells(lists)
    ts = trainer_spells(lists, set())          # all trainer-learned spells (an item may also teach them)
    print(len(ts), 'trainer spells', flush=True)
    npcs = jload('trainers.json', {})            # npc id -> {name, react, zones, tag, spells:[...]}
    # seed trainer NPCs from a spread of spells per profession (cheap), then read each NPC's full teach list
    by_prof = {}
    for sid, prof in ts.items():
        by_prof.setdefault(prof, []).append(sid)
    spell_info = {s['id']: s for p in PROFS for s in lists[p]['spells']}
    seeds = []
    for prof, sids in by_prof.items():
        sids.sort(key=lambda x: spell_info[x].get('learnedat', 0))
        step = max(1, len(sids) // 10)
        seeds += sids[::step] + sids[-2:]
    found = {}

    def add_from_spell(sid):
        h = fetch('spell=%d' % sid)
        for n in listview(h, 'taught-by-npc') or []:
            found[n['id']] = {'name': n['name'], 'react': n.get('react', [0, 0]), 'zones': n.get('location', []), 'tag': n.get('tag', '')}
    for sid in dict.fromkeys(seeds):
        add_from_spell(sid)
    print(len(found), 'trainer NPCs found from seeds', flush=True)
    for nid, info in found.items():
        h = fetch('npc=%d' % nid)
        sp = listview(h, 'teaches-recipe') or []
        info['spells'] = [s['id'] for s in sp]
        npcs[str(nid)] = info
    # trainer spells nobody covers yet: ask the spell page directly
    covered = set(s for n in npcs.values() for s in n['spells'])
    missing = [s for s in ts if s not in covered]
    print(len(missing), 'trainer spells not covered by the seeded trainers', flush=True)
    for sid in missing:
        add_from_spell(sid)
    for nid, info in found.items():
        if str(nid) not in npcs:
            h = fetch('npc=%d' % nid)
            info['spells'] = [s['id'] for s in (listview(h, 'teaches-recipe') or [])]
            npcs[str(nid)] = info
    covered = set(s for n in npcs.values() for s in n['spells'])
    print(len([s for s in ts if s not in covered]), 'trainer spells still without a trainer', flush=True)
    jsave('trainers.json', npcs)



# ---------------------------------------------------------------- helpers shared by quests / npcs / emit
def parse_npc(nid):
    """Name and per-zone first coordinate of an NPC page."""
    h = fetch('npc=%d' % nid)
    title = re.search(r'<title>([^<]*) - NPC', h)
    zones = {}
    for coords, zone in re.findall(r'"coords":(\[\[[\d.,\[\]]*?\]\]),"uiMapId":\d+,"uiMapName":"([^"]+)"', h):
        if zone not in zones:
            x, y = json.loads(coords)[0]
            zones[zone] = (x, y)
    return {'name': title.group(1) if title else str(nid), 'zones': zones}


def fmt_num(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


def npc_line(nid, name, react, zones):
    loc = '; '.join('%s %s,%s' % (z, fmt_num(x), fmt_num(y)) for z, (x, y) in zones.items())
    return 'V|%d|%s|%s|%s' % (nid, name, json.dumps(react).replace(' ', '').replace('None', 'null'), loc)


def known_npc_ids():
    ids = set()
    for f in ('ow.txt', 'wh.txt'):
        for l in read_lines(f):
            if l.startswith('V|'):
                ids.add(int(l.split('|')[1]))
    return ids


def all_items():
    lists = jload('lists.json')
    return lists, [parse_item(i) for i in recipe_ids(lists)]


# ---------------------------------------------------------------- stage: quests
def quest_start(qid):
    h = fetch('quest=%d' % qid)
    m = re.search(r'Start: \[url=\\/classic\\/npc=(\d+)', h)
    return int(m.group(1)) if m else None


def stage_quests():
    lists, items = all_items()
    qs = {}
    for it in items:
        for q in it['quest']:
            qs[q['id']] = q
    print(len(qs), 'reward quests', flush=True)
    out = jload('quests.json', {})
    for qid, q in qs.items():
        if str(qid) in out:
            continue
        npc = quest_start(qid)
        zone = None
        if npc:
            zs = list(parse_npc(npc)['zones'])
            zone = zs[0] if zs else None
        out[str(qid)] = {'npc': npc, 'zone': zone}
        jsave('quests.json', out)


# ---------------------------------------------------------------- stage: npcs
def wanted_npcs(items, trainers):
    ids = {}
    for it in items:
        for n in it['sold']:
            ids.setdefault(n['id'], n.get('react', [0, 0]))
    for nid, info in trainers.items():
        ids.setdefault(int(nid), info['react'])
    return ids


def stage_npcs():
    lists, items = all_items()
    trainers = jload('trainers.json', {})
    known = known_npc_ids()
    todo = [n for n in wanted_npcs(items, trainers) if n not in known]
    print(len(todo), 'NPCs to read', flush=True)
    for n in todo:
        parse_npc(n)


# ---------------------------------------------------------------- stage: zones
def zone_names():
    """Zone id -> name (Wowhead zone index plus single zone pages for the few ids missing from it)."""
    h = fetch('zones')
    names = {}
    for cat, zid, nm in re.findall(r'\{"category":(-?\d+),[^{}]*?"id":(\d+),[^{}]*?"name":"([^"]+)"', h):
        names[int(zid)] = nm
    extra = jload('zones_extra.json', {})
    names.update((int(k), v) for k, v in extra.items())
    return names, extra


def resolve_zone(names, extra, zid):
    if zid in names:
        return names[zid]
    h = fetch('zone=%d' % zid)
    t = re.search(r'<title>([^<]*) - Zone', h)
    extra[str(zid)] = t.group(1) if t else ''
    names[zid] = extra[str(zid)]
    jsave('zones_extra.json', extra)
    return names[zid]


# ---------------------------------------------------------------- stage: emit
MAX_DROPPERS = 12      # more creatures than this = a world drop, shown as one line


def clean(s):
    return (s or '').replace('|', ' ').replace('&#039;', "'")


def drop_pct(n):
    if n.get('outof') and n.get('count', 0) > 0:
        return round(100.0 * n['count'] / n['outof'], 2)
    return None


def stage_emit():
    lists, items = all_items()
    trainers = jload('trainers.json', {})
    quests = jload('quests.json', {})
    names, extra = zone_names()
    used_zones = set()
    spells, item_prof = {}, {}
    for prof in PROFS:
        for s in lists[prof]['spells']:
            spells[s['id']] = s
        for i in lists[prof]['items']:
            item_prof.setdefault(i['id'], prof)
    spell_prof = {s['id']: prof for prof in PROFS for s in lists[prof]['spells']}
    trainers_of = {}          # spell id -> [npc id]
    for nid, info in trainers.items():
        for sid in info['spells']:
            trainers_of.setdefault(sid, []).append(int(nid))
    taught = {}               # spell id -> [recipe item id]
    for it in items:
        for tch in it['teach']:
            taught.setdefault(tch['id'], []).append(it['id'])

    out, npc_ids, crafted_ids = [], {}, set()

    def zones_str(ids):
        for z in ids or []:
            used_zones.add(z)
        return ','.join(str(z) for z in ids or [])

    def react_str(r):
        return json.dumps([0 if x is None else x for x in (r or [0, 0])]).replace(' ', '')

    def skill_of(sp, fallback):
        if sp.get('learnedat'):
            return sp['learnedat']
        cols = [c for c in sp.get('colors', []) if c]
        return min(cols) if cols else fallback

    def trainer_lines(key, sid):
        for nid in sorted(trainers_of.get(sid, [])):
            out.append('S|%s|T|%d' % (key, nid))
            npc_ids[nid] = trainers[str(nid)]['react']

    for it in items:
        if not it['teach'] or re.search(r'UNUSED| OLD$|DEPRECATED', it['name'] or ''):
            continue
        sp = it['teach'][0]
        prof = item_prof[it['id']]
        craft = (sp.get('creates') or [None])[0]
        if craft:
            crafted_ids.add(craft)
        rep = it['rep'] or ['', '']
        out.append('|'.join(['R', prof, str(it['id']), 'wh', clean(it['name']), str(skill_of(sp, 0)), str(sp['id']),
                             str(craft or ''), str(sp.get('quality', '')) if craft else '', rep[0], rep[1]]))
        for n in it['sold']:
            out.append('S|%d|V|%d|%s|%s|%s' % (it['id'], n['id'], clean(n['name']), zones_str(n.get('location')), react_str(n.get('react'))))
            npc_ids.setdefault(n['id'], n.get('react', [0, 0]))
        # creatures that only exist in Season of Discovery zones (ids >= 10000) are not part of Classic
        droppers = [n for n in it['drop'] if not (n.get('location') and all(z >= 10000 for z in n['location']))]
        if len(droppers) > MAX_DROPPERS:
            out.append('S|%d|X|World drop (%d%s creatures)' % (it['id'], len(droppers), '+' if len(droppers) >= 200 else ''))
        else:
            for n in sorted(droppers, key=lambda n: -(drop_pct(n) or 0)):
                pct = drop_pct(n)
                out.append('S|%d|D|%d|%s|%s|%s|%s' % (it['id'], n['id'], clean(n['name']), zones_str(n.get('location')),
                                                      react_str(n.get('react')), '' if pct is None else pct))
        if not droppers and it['cont']:
            first = clean(it['cont'][0].get('name', 'container'))
            out.append('S|%d|X|Loot from %s%s' % (it['id'], first, ' and %d more' % (len(it['cont']) - 1) if len(it['cont']) > 1 else ''))
        for q in it['quest']:
            if 'UNUSED' in q['name']:
                continue
            qi = quests.get(str(q['id']), {})
            zone = qi.get('zone') or (q['category'] if q.get('category', 0) > 0 else '')
            if isinstance(zone, int):
                used_zones.add(zone)
            out.append('S|%d|Q|%d|%s|%d|%s' % (it['id'], q['id'], clean(q['name']), q.get('side', 3), zone))
        trainer_lines(str(it['id']), sp['id'])

    # trainer-only recipes: no recipe item teaches the spell
    for sid, prof in sorted(spell_prof.items()):
        sp = spells[sid]
        if 6 not in sp.get('source', []) or sid in taught or sid >= SOD_SPELL_MIN:
            continue
        craft = (sp.get('creates') or [None])[0]
        if sp['name'] in RANK_SPELLS or (not craft and prof != 'enchanting'):
            continue          # profession rank spells ("Tailoring" learned at 50, 125, 200)
        if craft:
            crafted_ids.add(craft)
        out.append('|'.join(['R', prof, 's%d' % sid, 'wh', clean(sp['name']), str(skill_of(sp, 0)), str(sid),
                             str(craft or ''), str(sp.get('quality', '')) if craft else '', '', '']))
        trainer_lines('s%d' % sid, sid)

    # NPC lines (coordinates) for trainers and for vendors missing from ow.txt / wh.txt
    known = known_npc_ids()
    npc_out = []
    for nid, react in sorted(npc_ids.items()):
        if nid in known:
            continue
        info = parse_npc(nid)
        npc_out.append(npc_line(nid, clean(info['name']), [0 if x is None else x for x in react], info['zones']))

    # the OctoWow file uses the same (WoW area) zone ids
    for l in read_lines('recipes_ow.txt'):
        p = l.split('|')
        if p[0] != 'S':
            continue
        ids = p[5].split(',') if p[2] in ('V', 'D') else p[6:7] if p[2] == 'Q' else []
        used_zones.update(int(z) for z in ids if z.strip().isdigit() and int(z) > 0)

    # zone names for the ids used above
    zl = []
    for z in sorted(used_zones):
        zl.append('%d|%s' % (z, resolve_zone(names, extra, z)))

    # crafted items for iLvl / class (disenchant table); keep the ones this report references
    have = set(int(l.split('|')[0]) for l in read_lines('items.txt'))
    add = []
    for prof in DE_PROFS:
        for c in lists[prof]['crafted']:
            if c['id'] in crafted_ids and c['id'] not in have and c.get('level') is not None:
                add.append('%d|%s|%d|%d|%d' % (c['id'], clean(c['name']), c.get('quality', 1), c['level'], c.get('classs', 0)))
                have.add(c['id'])

    def write(name, header, lines):
        with open(os.path.join(DATA, name), 'w', encoding='utf-8', newline='\n') as f:
            f.write(header + '\n' + '\n'.join(lines) + '\n')
    write('recipes_wh.txt', '# R|profession|key|source|name|skill|teachSpellId|craftedItemId|craftedQuality|repFaction|repLevel   (key = recipe item id, or sSPELLID for trainer-only recipes)\n'
          '# S|key|V|npcId|name|zoneIds|react   vendor      S|key|T|npcId   trainer      S|key|Q|questId|name|side|zone   quest reward\n'
          '# S|key|D|npcId|name|zoneIds|react|pct   drop      S|key|X|label   world drop / container loot\n'
          '# Generated by scripts/scrape_wowhead.py (Wowhead Classic)', out)
    write('wh_npcs.txt', '# Trainers and vendors that are not in wh.txt/ow.txt: V|npcId|name|[allianceReact,hordeReact]|Zone x,y; ...', npc_out)
    write('zones.txt', '# zone id|name (Wowhead Classic)', zl)
    if add:
        with open(os.path.join(DATA, 'items.txt'), 'a', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(add) + '\n')
    print(len(out), 'lines;', len(npc_out), 'NPCs;', len(zl), 'zones;', len(add), 'crafted items added', flush=True)


if __name__ == '__main__':
    for st in sys.argv[1:]:
        globals()['stage_' + st]()
