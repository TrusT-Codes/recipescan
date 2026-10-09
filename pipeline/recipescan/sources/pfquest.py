"""pfQuest + pfQuest-octo (OctoWow) database: item sources, NPCs, objects, quests, zone names.

The Octo pack is merged onto the base tables the way pfQuest-octo/patchtable.lua does it:
items/units/objects/quests per field, locales per field, everything else per entry; "_" deletes.
"""
import os
import re

from .. import config
from ..lua import tables_assigned

FIELD_MERGE = ('items', 'units', 'objects', 'quests')


def _load(path, lhs=r'pfDB\[[^\n=]*?'):
    tables = tables_assigned(path, lhs)
    if len(tables) != 1:
        raise ValueError('%s: expected one table, found %d' % (path, len(tables)))
    return next(iter(tables.values()))


def _patch_entry(base, diff):
    for k, v in diff.items():
        if v == '_':
            base.pop(k, None)
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            for field, value in v.items():
                if value == '_':
                    base[k].pop(field, None)
                else:
                    base[k][field] = value
        else:
            base[k] = v


def _patch_table(base, diff):
    for k, v in diff.items():
        if v == '_':
            base.pop(k, None)
        else:
            base[k] = v


def load(base_dir=None, octo_dir=None):
    """Merged pfDB subset: {db: {'data': {...}, 'enUS': {...}}} for items, units, objects, quests, refloot, zones."""
    base_dir = base_dir or config.ADDONS['pfquest']
    octo_dir = octo_dir or config.ADDONS['pfquest-octo']
    db = {}
    for name in ('items', 'units', 'objects', 'quests', 'refloot'):
        data = _load(os.path.join(base_dir, 'db', name + '.lua'))
        octo = os.path.join(octo_dir, 'db', name + '-turtle.lua')
        if os.path.exists(octo):
            diff = _load(octo)
            (_patch_entry if name in FIELD_MERGE else _patch_table)(data, diff)
        loc = {}
        loc_path = os.path.join(base_dir, 'db', 'enUS', name + '.lua')
        if os.path.exists(loc_path):
            loc = _load(loc_path)
            octo_loc = os.path.join(octo_dir, 'db', 'enUS', name + '-turtle.lua')
            if os.path.exists(octo_loc):
                diff = _load(octo_loc)
                for k, v in diff.items():
                    if v == '_':
                        loc.pop(k, None)
                    elif isinstance(v, dict) and isinstance(loc.get(k), dict):
                        loc[k].update(v)
                    else:
                        loc[k] = v
        db[name] = {'data': data, 'enUS': loc}
    zone_names = _load(os.path.join(octo_dir, 'db', 'enUS', 'zones-turtle.lua'))
    db['zones'] = {'enUS': {k: v for k, v in zone_names.items() if v != '_'}}
    return db


def _coords(raw, limit=None):
    """pfQuest coords {i: {x, y, zone, respawn}} -> [[zone, x, y], ...] (deduplicated, rounded)."""
    out, seen = [], set()
    for c in (raw or {}).values():
        if not isinstance(c, dict) or len(c) < 3:
            continue
        x, y, zone = c[1], c[2], c[3]
        p = (int(zone), round(float(x), 1), round(float(y), 1))
        if p in seen:
            continue
        seen.add(p)
        out.append(list(p))
        if limit and len(out) >= limit:
            break
    return out


def _num_map(d):
    return {int(k): (round(v, 4) if isinstance(v, float) else v) for k, v in (d or {}).items()} if isinstance(d, dict) else {}


SQL_ROW = re.compile(r"^INSERT INTO `(\w+)` VALUES \((.*)\);$")
SQL_VALUE = re.compile(r'''\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^,]+)\s*(?:,|$)''')


def client_data(base_dir=None):
    """AreaTable (zone id -> parent zone, name) and WorldMapArea (zone map bounds) from pfQuest's toolbox dump.

    Uses the Turtle tables when present (they extend the vanilla ones)."""
    path = os.path.join(base_dir or config.ADDONS['pfquest'], 'toolbox', 'client-data.sql')
    tables = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = SQL_ROW.match(line.strip())
            if not m or not m.group(1).startswith(('AreaTable_', 'WorldMapArea_')):
                continue
            vals = [v.strip()[1:-1] if v.strip()[:1] in '"\'' else v.strip() for v in SQL_VALUE.findall(m.group(2))]
            tables.setdefault(m.group(1), []).append(vals)
    areas, maps = {}, {}
    for flavor in ('vanilla', 'turtle'):
        for v in tables.get('AreaTable_' + flavor, []):
            areas[int(v[0])] = [int(v[1]), v[2]]
        for v in tables.get('WorldMapArea_' + flavor, []):
            maps[int(v[0])] = {'map': int(v[1]), 'area': int(v[2]), 'name': v[3],
                               'bounds': [round(float(x), 2) for x in v[4:8]]}
    return areas, maps


def extract(extra_item_ids=(), extra_unit_ids=(), extra_quest_ids=()):
    """Builds the committed extract: every item name, sources for recipe items, and the NPCs/objects/quests they use."""
    db = load()
    items, item_names = db['items']['data'], db['items']['enUS']
    prefix = re.compile(config.RECIPE_PREFIX)
    recipe_ids = {k for k, n in item_names.items() if isinstance(n, str) and prefix.match(n)}
    recipe_ids |= {int(i) for i in extra_item_ids}

    sources, refs, unit_ids, object_ids = {}, set(), set(int(u) for u in extra_unit_ids), set()
    for iid in sorted(recipe_ids):
        e = items.get(iid)
        if not isinstance(e, dict):
            continue
        s = {}
        for kind in ('U', 'O', 'V', 'R'):
            if isinstance(e.get(kind), dict) and e[kind]:
                s[kind] = _num_map(e[kind])
        if not s:
            continue
        sources[iid] = s
        unit_ids |= set(s.get('U', {})) | set(s.get('V', {}))
        object_ids |= set(s.get('O', {}))
        refs |= set(s.get('R', {}))

    refloot = {}
    for r in sorted(refs):
        e = db['refloot']['data'].get(r)
        if not isinstance(e, dict):
            continue
        refloot[r] = {k: sorted(int(x) for x in e[k]) for k in ('U', 'O') if isinstance(e.get(k), dict)}
        unit_ids |= set(refloot[r].get('U', []))
        object_ids |= set(refloot[r].get('O', []))

    quests = {}
    qdata, qloc = db['quests']['data'], db['quests']['enUS']
    for q in sorted(int(x) for x in extra_quest_ids):
        e, loc = qdata.get(q), qloc.get(q)
        if not isinstance(e, dict) and not isinstance(loc, dict):
            continue
        e = e if isinstance(e, dict) else {}
        rec = {'name': loc.get('T') if isinstance(loc, dict) else None}
        for f in ('lvl', 'min', 'race', 'class', 'skill'):
            if f in e and not isinstance(e[f], dict):
                rec[f] = e[f]
        for f in ('start', 'end'):
            if isinstance(e.get(f), dict):
                rec[f] = {k: sorted(set(int(x) for x in v.values())) for k, v in e[f].items() if isinstance(v, dict)}
                unit_ids |= set(rec[f].get('U', []))
                object_ids |= set(rec[f].get('O', []))
        quests[q] = rec

    units = {}
    udata, uloc = db['units']['data'], db['units']['enUS']
    for u in sorted(unit_ids):
        e = udata.get(u)
        if not isinstance(e, dict) and u not in uloc:
            continue
        e = e if isinstance(e, dict) else {}
        units[u] = {'name': uloc.get(u), 'fac': e.get('fac'), 'lvl': e.get('lvl'), 'rnk': e.get('rnk'),
                    'coords': _coords(e.get('coords'), config.MAX_SPAWNS)}

    objects = {}
    odata, oloc = db['objects']['data'], db['objects']['enUS']
    for o in sorted(object_ids):
        e = odata.get(o)
        e = e if isinstance(e, dict) else {}
        objects[o] = {'name': oloc.get(o), 'fac': e.get('fac'), 'coords': _coords(e.get('coords'), config.MAX_SPAWNS)}

    names = {k: v for k, v in item_names.items() if isinstance(v, str)}
    areas, map_areas = client_data()
    return {
        'areas': areas,
        'map_areas': map_areas,
        'item_names': names,
        'item_sources': sources,
        'refloot': refloot,
        'units': units,
        'objects': objects,
        'quests': quests,
        'zone_names': db['zones']['enUS'],
    }
