"""Merges legacy scrapes and extracted addon data into one model (plain dicts).

Precedence (docs/roadmap.md):
- recipe identity: craft spell id. Wowhead's teach spell is the craft spell; OctoWow's teach spell is the
  learn spell (craft = teach + 1) or is resolved through the crafted item in Atlas-CFM.
- vendors: pfQuest-octo + OctoWow scrape; Wowhead only when both have none.
- drops / objects: pfQuest-octo; else OctoWow scrape; else Wowhead; else Atlas-CFM boss tables; else world-drop labels.
- quests, trainers, reputation: scrapes (pfQuest has no quest rewards or trainer lists).
- skill to learn: Wowhead > OctoWow > Atlas-CFM orange; difficulty colours, reagents, tools, station: Atlas-CFM.
"""
import re
from collections import defaultdict

from . import config
from .sources.legacy import UNMAPPED_ZONES, canon_zone


def _faction_from_react(react):
    if react is None:
        return None
    a, h = react
    fa = a == 1 or (a == 0 and h <= 0)
    fh = h == 1 or (h == 0 and a <= 0)
    return ('A' if fa else '') + ('H' if fh else '')


class Model:
    def __init__(self):
        self.recipes = {}          # id -> recipe dict
        self.item_recipe = {}      # recipe item id -> recipe id
        self.items = {}            # id -> {name, quality, item_level, class, quality_origin}
        self.npcs = {}             # id -> {name, faction, level, rank, origin, spawns: [(zone, x, y, origin)]}
        self.objects = {}
        self.quests = {}
        self.zones = {}
        self.disenchant = []
        self.notes = defaultdict(list)   # report sections -> lines


def build(legacy, pf, at, al, manifest):
    m = Model()
    profs = set(config.PROFESSION_IDS)
    prefix = re.compile(config.RECIPE_PREFIX)

    craft = {sid: c for sid, c in at['craft_spells'].items() if c['prof'] in profs}
    spells = at['spells']
    by_item = defaultdict(list)
    for sid, c in craft.items():
        s = spells.get(sid)
        if s and s.get('item'):
            by_item[s['item']].append(sid)

    item_names = pf['item_names']
    sod = legacy['sod']

    def is_sod(item):
        return item is not None and (item in sod or item >= config.SOD_MIN_ITEM_ID)

    def craft_name(sid):
        s = spells.get(sid, {})
        return s.get('name') or item_names.get(s.get('item'))

    def spell_via_crafted(crafted, prof):
        cands = [s for s in by_item.get(crafted, []) if craft[s]['prof'] == prof]
        return cands[0] if len(cands) == 1 else None

    def recipe(rid, prof, spell=None):
        r = m.recipes.get(rid)
        if r is None:
            r = m.recipes[rid] = {
                'id': rid, 'prof': prof, 'spell': spell, 'names': {}, 'skill': {}, 'crafted': {}, 'quality': {},
                'rep': None, 'items': set(), 'sources': [], 'origins': set(), 'legacy_keys': set()}
        elif r['prof'] != prof:
            m.notes['profession conflicts'].append('%s: %s vs %s' % (rid, r['prof'], prof))
        return r

    def attach_item(r, item):
        if item is None:
            return
        old = m.item_recipe.get(item)
        if old and old != r['id']:
            m.notes['recipe item mapped twice'].append('item %d: %s and %s (kept %s)' % (item, old, r['id'], old))
            return
        m.item_recipe[item] = r['id']
        r['items'].add(item)

    # ---- 1. legacy recipe lines (R/S)
    unresolved_ow = []
    for lr in legacy['recipes']:
        if lr['prof'] not in profs or is_sod(lr['item']):
            continue
        spell = None
        if lr['src'] == 'wh':
            spell = lr['spell']
        else:
            # OctoWow lists the learn spell; the craft spell is usually next to it (+1, sometimes -1)
            t = lr['teach']
            cands = [s for s in ((t + 1, t, t - 1) if t else ()) if s in craft and craft[s]['prof'] == lr['prof']]
            by_crafted = [s for s in cands if lr['crafted'] and spells.get(s, {}).get('item') == lr['crafted']]
            by_name = [s for s in cands if craft_name(s) and craft_name(s).lower() == lr['name'].lower()]
            if by_crafted:
                spell = by_crafted[0]
            elif by_name:
                spell = by_name[0]
            elif lr['crafted'] and spell_via_crafted(lr['crafted'], lr['prof']):
                spell = spell_via_crafted(lr['crafted'], lr['prof'])
            elif cands and cands[0] != t - 1:
                spell = cands[0]
                m.notes['OctoWow craft spell picked without confirmation'].append(
                    '%s %s "%s": teach %s -> s%d "%s"' % (lr['prof'], lr['key'], lr['name'], t, spell, craft_name(spell)))
            if spell is None:
                unresolved_ow.append(lr)
        if spell is None and lr['item'] is None:
            continue
        rid = 's%d' % spell if spell else 'i%d' % lr['item']
        if spell is None and lr['item'] in m.item_recipe:
            rid = m.item_recipe[lr['item']]
        r = recipe(rid, lr['prof'], spell)
        attach_item(r, lr['item'])
        r['origins'].add(lr['src'])
        r['legacy_keys'].add((lr['prof'], lr['key']))
        r['names'].setdefault(lr['src'], lr['name'])
        if lr['skill']:
            r['skill'].setdefault(lr['src'], lr['skill'])
        if lr['crafted']:
            r['crafted'].setdefault(lr['src'], lr['crafted'])
        if lr['quality'] is not None:
            r['quality'].setdefault(lr['src'], lr['quality'])
        if lr['rep'] and not r['rep']:
            r['rep'] = (lr['rep'][0], lr['rep'][1], lr['src'])
        for s in lr['sources']:
            r['sources'].append(dict(s, item=lr['item'], origin=lr['src']))
    for lr in unresolved_ow:
        m.notes['OctoWow recipes without a craft spell'].append(
            '%s %s "%s" (teach spell %s, crafted item %s)' % (lr['prof'], lr['key'], lr['name'], lr['teach'], lr['crafted']))

    # ---- 2. legacy vendor lists (I lines): recipes sold by vendors
    for vr in legacy['vendor_recipes']:
        if vr['prof'] not in profs or is_sod(vr['item']):
            continue
        rid = m.item_recipe.get(vr['item'])
        if rid is None:
            crafted = vr['crafted'] or legacy['crafted'].get(vr['item'])
            spell = spell_via_crafted(crafted, vr['prof']) if crafted else None
            rid = 's%d' % spell if spell else 'i%d' % vr['item']
            r = recipe(rid, vr['prof'], spell)
            attach_item(r, vr['item'])
            if crafted:
                r['crafted'].setdefault(vr['src'], crafted)
        r = m.recipes[rid]
        r['origins'].add(vr['src'])
        r['legacy_keys'].add((vr['prof'], str(vr['item'])))
        r['names'].setdefault(vr['src'], vr['name'])
        if vr['skill']:
            r['skill'].setdefault(vr['src'], vr['skill'])
        for v in vr['vendors']:
            r['sources'].append({'type': 'vendor', 'npc': v, 'item': vr['item'], 'origin': vr['src']})

    # ---- 3. recipe items only the addons know (Atlas-CFM container -> crafted item, or name match)
    craft_by_name = defaultdict(list)
    for sid, c in craft.items():
        s = spells.get(sid, {})
        n = s.get('name') or item_names.get(s.get('item'))
        if n:
            craft_by_name[(c['prof'], n.lower())].append(sid)
    candidates = set(at['recipe_items']) | {i for i in pf['item_sources'] if i in item_names and prefix.match(item_names[i])}
    for item in sorted(candidates):
        if item in m.item_recipe or is_sod(item):
            continue
        entries = at['recipe_items'].get(item, [])
        spell, how = None, None
        crafted = sorted({c for e in entries for c in e['container']})
        cands = sorted({s for c in crafted for s in by_item.get(c, [])})
        if len(cands) == 1:
            spell, how = cands[0], 'Atlas-CFM container'
        elif not cands and item in item_names and prefix.match(item_names[item]):
            stripped = prefix.sub('', item_names[item]).lower()
            hits = sorted({s for p in profs for s in craft_by_name.get((p, stripped), [])})
            if len(hits) == 1:
                spell, how = hits[0], 'name match'
        if spell is None:
            if item_names.get(item, '') and prefix.match(item_names.get(item, '')):
                m.notes['addon recipe items without a craft spell'].append(
                    '%d "%s" (Atlas crafted items %s)' % (item, item_names.get(item), crafted or '-'))
            continue
        r = recipe('s%d' % spell, craft[spell]['prof'], spell)
        attach_item(r, item)
        r['origins'].add('atlas' if how == 'Atlas-CFM container' else 'pfquest')
        if not r['legacy_keys']:
            m.notes['recipes new from addon data'].append('%s %s via %s (item %d "%s")' % (r['prof'], r['id'], how, item, item_names.get(item)))

    # ---- 4. per-recipe fields
    for r in m.recipes.values():
        spell = r['spell']
        c = craft.get(spell) if spell else None
        s = spells.get(spell, {}) if spell else {}
        if c:
            r['origins'].add('atlas')
            r['atlas_visible'] = c['visible']
            r['atlas_servers'] = c['servers']
            if c['skill']:
                r['colors'] = (c['skill'] + [None] * 4)[:4]
        else:
            r['atlas_visible'] = None
            r['atlas_servers'] = []
        # name: scrape names are the recipe names players know
        recipe_item_name = next((prefix.sub('', item_names[i]) for i in sorted(r['items']) if i in item_names), None)
        crafted_name = item_names.get(s.get('item')) if s.get('item') else None
        r['name'] = r['names'].get('wh') or r['names'].get('ow') or s.get('name') or recipe_item_name or crafted_name or r['id']
        # skill to learn
        orange = r.get('colors', [None])[0]
        for origin in ('wh', 'ow'):
            if r['skill'].get(origin):
                r['skill_req'], r['skill_origin'] = r['skill'][origin], origin
                break
        else:
            r['skill_req'], r['skill_origin'] = (orange, 'atlas') if orange else (None, None)
        if orange and r['skill_origin'] in ('wh', 'ow') and orange != r['skill_req'] and orange > 1:
            m.notes['skill: scrape vs Atlas-CFM orange'].append('%s %s "%s": %s %d, Atlas %d' % (
                r['prof'], r['id'], r['name'], r['skill_origin'], r['skill_req'], orange))
        # crafted item
        r['crafted_item'] = s.get('item') or r['crafted'].get('wh') or r['crafted'].get('ow')
        for i in sorted(r['items']):
            if not r['crafted_item'] and i in legacy['crafted']:
                r['crafted_item'] = legacy['crafted'][i]
        if s.get('item') and r['crafted'] and s['item'] not in r['crafted'].values():
            m.notes['crafted item: scrape vs Atlas-CFM'].append('%s "%s": scrape %s, Atlas %s' % (r['id'], r['name'], sorted(set(r['crafted'].values())), s['item']))
        qty = s.get('qty')
        r['qty'] = (qty[0], qty[-1]) if qty else (None, None)
        r['station'] = s.get('requires')
        r['reagents'] = s.get('reagents', [])
        r['tools'] = s.get('tools', [])

    # ---- 5. sources
    item_sources = pf['item_sources']
    refloot = pf['refloot']
    for r in m.recipes.values():
        legacy_src = r['sources']
        out = []
        recipe_items = sorted(r['items']) + [None]   # None: sources tied to the spell (trainers, s-key quests)
        for item in recipe_items:
            mine = [s for s in legacy_src if s.get('item') == item]
            pfs = item_sources.get(item, {}) if item else {}
            # vendors
            vend = [{'type': 'vendor', 'npc': n, 'stock': stock, 'origin': 'pfquest'} for n, stock in sorted(pfs.get('V', {}).items())]
            seen = {v['npc'] for v in vend}
            for s in mine:
                if s['type'] == 'vendor' and s['origin'] == 'ow' and s['npc'] not in seen:
                    vend.append({'type': 'vendor', 'npc': s['npc'], 'origin': 'ow'})
                    seen.add(s['npc'])
            if not vend:
                for s in mine:
                    if s['type'] == 'vendor' and s['npc'] not in seen:
                        vend.append({'type': 'vendor', 'npc': s['npc'], 'origin': s['origin']})
                        seen.add(s['npc'])
            # drops / objects
            drops = []
            for n, ch in sorted(pfs.get('U', {}).items()):
                drops.append({'type': 'drop', 'npc': n, 'chance': ch, 'origin': 'pfquest'})
            for o, ch in sorted(pfs.get('O', {}).items()):
                drops.append({'type': 'object', 'object': o, 'chance': ch, 'origin': 'pfquest'})
            for ref, ch in sorted(pfs.get('R', {}).items()):
                rl = refloot.get(ref, {})
                for n in rl.get('U', []):
                    drops.append({'type': 'drop', 'npc': n, 'chance': ch or None, 'origin': 'pfquest'})
                for o in rl.get('O', []):
                    drops.append({'type': 'object', 'object': o, 'chance': ch or None, 'origin': 'pfquest'})
            for origin in ('ow', 'wh'):
                if drops:
                    break
                drops = [{'type': 'drop', 'npc': s['npc'], 'chance': s.get('chance'), 'origin': origin}
                         for s in mine if s['type'] == 'drop' and s['origin'] == origin]
            if not drops and item:
                for e in at['recipe_items'].get(item, []):
                    rate = _rate(e['drop_rate'])
                    # Atlas also lists vendors and quest chains as "bosses"; only rows with a drop rate are drops
                    if e['visible'] and e['boss'] and rate and e['disc'] not in ('Vendor', 'Quest Reward'):
                        drops.append({'type': 'drop', 'chance': rate, 'origin': 'atlas',
                                      'note': '%s (%s)' % (e['boss'].strip(), e['instance']) if e['instance'] else e['boss'].strip()})
            if not drops:
                drops = [{'type': 'world', 'note': s['note'], 'origin': s['origin']} for s in mine if s['type'] == 'world'][:1]
            quests = []
            qseen = set()
            for s in mine:
                if s['type'] == 'quest' and s['quest'] not in qseen:
                    quests.append({'type': 'quest', 'quest': s['quest'], 'origin': s['origin']})
                    qseen.add(s['quest'])
            trainers = []
            tseen = set()
            for s in mine:
                if s['type'] == 'trainer' and s['npc'] not in tseen:
                    trainers.append({'type': 'trainer', 'npc': s['npc'], 'origin': s['origin']})
                    tseen.add(s['npc'])
            for s in vend + drops + quests + trainers:
                s['item'] = item
                out.append(s)
                r['origins'].add(s['origin'])
        r['sources'] = out

    # ---- 6. listing rules
    for r in m.recipes.values():
        reason = None
        if '[DEPRECATED]' in r['name'] or any('[DEPRECATED]' in item_names.get(i, '') for i in r['items']):
            reason = 'deprecated item'
        elif not r['sources']:
            reason = 'no known source'
        elif r['atlas_visible'] is False and not any(s['origin'] == 'pfquest' for s in r['sources']):
            reason = 'Atlas-CFM: not on %s (%s)' % (config.ATLAS_SERVER, ', '.join(r['atlas_servers']))
        r['listed'], r['unlisted_reason'] = (reason is None), reason

    # Atlas craft spells that no recipe uses (trainer-taught or unknown source)
    used = {r['spell'] for r in m.recipes.values() if r['spell']}
    for sid, c in sorted(craft.items()):
        if sid not in used and c['visible']:
            m.notes['Atlas-CFM craft spells without recipe data (likely trainer-taught)'].append(
                '%s s%d "%s" skill %s' % (c['prof'], sid, spells.get(sid, {}).get('name') or item_names.get(spells.get(sid, {}).get('item'), '?'),
                                         (c['skill'] or ['?'])[0]))

    _entities(m, legacy, pf, al, item_names)
    m.disenchant = legacy['disenchant']
    m.manifest = manifest
    return m


def _rate(s):
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        nums = re.findall(r'\d*\.?\d+', s)   # ".2-10" -> lower bound
        return float(nums[0]) if nums else None


def _entities(m, legacy, pf, al, item_names):
    # zones: client AreaTable (pfQuest toolbox) > Wowhead ids + OctoWow extras > pfQuest-octo Turtle zone names
    zones = {zid: v[1].strip() for zid, v in pf['areas'].items() if v[1].strip()}
    for zid, name in list(legacy['zones'].items()) + list(pf['zone_names'].items()):
        zones.setdefault(zid, name)
    bounds = {}
    for wma in pf['map_areas'].values():
        if wma['area']:
            bounds[wma['area']] = wma
    zone_by_name = {}
    for zid, name in sorted(zones.items()):
        zone_by_name.setdefault(name.lower(), zid)

    listed = [r for r in m.recipes.values()]
    npc_ids, object_ids, quest_ids, item_ids = set(), set(), set(), set()
    for r in listed:
        for s in r['sources']:
            if s.get('npc'):
                npc_ids.add(s['npc'])
            if s.get('object'):
                object_ids.add(s['object'])
            if s.get('quest'):
                quest_ids.add(s['quest'])
        item_ids |= r['items'] | {i for i, _ in r['reagents']} | set(r['tools'])
        if r['crafted_item']:
            item_ids.add(r['crafted_item'])

    # quests (scrape) + pfQuest level and starters
    for q in sorted(quest_ids):
        lq = legacy['quests'].get(q, {})
        pq = pf['quests'].get(q, {})
        zone = None
        for z in lq.get('zones', []):
            if z.lstrip('-').isdigit():
                if int(z) > 0 and int(z) in zones:
                    zone = int(z)
                    break
            elif canon_zone(z).lower() in zone_by_name:
                zone = zone_by_name[canon_zone(z).lower()]
                break
        side = {1: 'A', 2: 'H', 3: 'AH'}.get(lq.get('side'))
        m.quests[q] = {'name': pq.get('name') or lq.get('name'), 'level': pq.get('lvl'), 'min_level': pq.get('min'),
                       'side': side, 'zone': zone, 'origin': 'pfquest' if pq else lq.get('src', 'wh'),
                       'starters': [(k, x) for k, xs in (pq.get('start') or {}).items() for x in xs]}
        for kind, x in m.quests[q]['starters']:
            if kind == 'U':
                npc_ids.add(x)
            elif kind == 'O':
                object_ids.add(x)

    for n in sorted(npc_ids):
        pu = pf['units'].get(n)
        ln = legacy['npcs'].get(n)
        rec = {'name': (pu or {}).get('name') or (ln or {}).get('name'), 'level': (pu or {}).get('lvl'),
               'rank': int(pu['rnk']) if pu and pu.get('rnk') not in (None, '') else None,
               'faction': (pu or {}).get('fac') or _faction_from_react((ln or {}).get('react')),
               'origin': 'pfquest' if pu else ','.join(sorted((ln or {}).get('src', {'?'}))), 'spawns': []}
        if pu and pu['coords']:
            rec['spawns'] = [(z, x, y, 'pfquest') for z, x, y in pu['coords']]
        elif ln:
            for zname, x, y in ln['locs']:
                if zname in UNMAPPED_ZONES:
                    continue
                zid = zone_by_name.get(zname.lower())
                if zid is None:
                    m.notes['zone names without id'].append(zname)
                    continue
                rec['spawns'].append((zid, x, y, 'ow' if 'ow' in ln['src'] else 'wh'))
            if not rec['spawns']:
                for z in ln['zones']:
                    if z.lstrip('-').isdigit() and int(z) in zones:
                        rec['spawns'].append((int(z), None, None, 'ow' if 'ow' in ln['src'] else 'wh'))
        m.npcs[n] = rec

    for o in sorted(object_ids):
        po = pf['objects'].get(o, {})
        m.objects[o] = {'name': po.get('name'), 'faction': po.get('fac'),
                        'spawns': [(z, x, y, 'pfquest') for z, x, y in po.get('coords', [])]}

    used_zones = {s[0] for e in list(m.npcs.values()) + list(m.objects.values()) for s in e['spawns']}
    used_zones |= {q['zone'] for q in m.quests.values() if q['zone']}
    m.zones = {z: {'name': zones[z], 'parent': (pf['areas'].get(z) or [0])[0] or None,
                   'continent': bounds[z]['map'] if z in bounds else None,
                   'bounds': bounds[z]['bounds'] if z in bounds else None}
               for z in sorted(used_zones) if z in zones}
    for z in sorted(used_zones - set(zones)):
        m.notes['zone ids without name'].append(str(z))

    for i in sorted(item_ids):
        li = legacy['items'].get(i)
        rec = {'name': item_names.get(i) or (li or {}).get('name'), 'quality': None, 'item_level': None, 'class': None, 'quality_origin': None}
        if li:
            rec.update(quality=li['quality'], item_level=li['ilvl'], **{'class': li['class']})
            rec['quality_origin'] = 'wh'
        m.items[i] = rec
    for r in m.recipes.values():
        ci = r['crafted_item']
        if ci and m.items[ci]['quality'] is None:
            for origin in ('wh', 'ow'):
                if r['quality'].get(origin) is not None:
                    m.items[ci]['quality'], m.items[ci]['quality_origin'] = r['quality'][origin], origin
                    break
    for i, rec in m.items.items():
        if rec['quality'] is None and i in al['items']:
            rec['quality'], rec['quality_origin'] = al['items'][i][0], 'atlasloot'
