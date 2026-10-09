"""Atlas-CFM addon data: craft spells (skill colours), spell details (reagents, tools, station, crafted item)
and recipe items found in loot / faction tables (recipe -> crafted item, drop rate, reputation standing).

Server-specific data is resolved for config.ATLAS_SERVER the way AtlasCFM.Server.IsVisible / GetDataField do.
"""
import glob
import os
import re

from .. import config
from ..lua import Expr, as_list, tables_assigned

STANDINGS = ('Neutral', 'Friendly', 'Honored', 'Revered', 'Exalted')


def _server_token(s):
    """AtlasCFM.Server.NOT_TURTLE -> '!Turtle WoW', STRICT_TURTLE1 -> '=Turtle WoW 1.17.2'."""
    if not isinstance(s, str):
        return None
    m = re.match(r'^AtlasCFM\.Server\.(NOT_|STRICT_)?([A-Z_0-9]+)$', s)
    if not m:
        return s
    name = config.ATLAS_SERVERS.get(m.group(2))
    if name is None:
        return None
    return {'NOT_': '!', 'STRICT_': '=', None: ''}[m.group(1)] + name


def server_list(entry):
    if not isinstance(entry, dict):
        return []
    servers = entry.get('servers') or entry.get('Servers')
    if not isinstance(servers, dict):
        return []
    return [t for t in (_server_token(v) for v in as_list(servers)) if t]


def visible(entry, active=config.ATLAS_SERVER):
    """Port of AtlasCFM.Server.IsVisible (list form)."""
    whitelist, allowed = False, False
    for s in server_list(entry):
        deny = s.startswith('!')
        target = s[1:] if deny else s
        strict = target.startswith('=')
        if strict:
            target = target[1:]
        if not deny:
            whitelist = True
        match = target == active or (not strict and active == config.ATLAS_SERVERS['TURTLE'] and target == config.ATLAS_SERVERS['TURTLE1'])
        if match:
            if deny:
                return False
            allowed = True
    return allowed if whitelist else True


def field(entry, name, active=config.ATLAS_SERVER):
    """Port of AtlasCFM.Server.GetDataField: server-suffixed overrides first."""
    suffix = {config.ATLAS_SERVERS['TURTLE']: '_TURTLE', config.ATLAS_SERVERS['TURTLE1']: '_TURTLE1',
              config.ATLAS_SERVERS['VANILLA_PLUS']: '_VANILLA_PLUS'}.get(active)
    if suffix and entry.get(name + suffix) is not None:
        return entry[name + suffix]
    if active == config.ATLAS_SERVERS['TURTLE'] and entry.get(name + '_TURTLE1') is not None:
        return entry[name + '_TURTLE1']
    return entry.get(name)


def _profession(table_name):
    if table_name in config.ATLAS_SKIP_TABLES:
        return None
    for pid, _, _, prefixes in config.PROFESSIONS:
        if any(table_name.startswith(p) for p in prefixes):
            return pid
    return None


def _ids(t):
    return [int(x) for x in as_list(t) if isinstance(x, (int, float))]


def _craft_spells(data_dir):
    tables = tables_assigned(os.path.join(data_dir, 'Tables', 'Crafting.lua'), r'craftingTable')
    crafting = next(iter(tables.values()))
    out = {}
    for tname, entries in crafting.items():
        prof = _profession(tname)
        if prof is None or not isinstance(entries, dict):
            continue
        for e in as_list(entries):
            if not isinstance(e, dict) or not isinstance(e.get('id'), int):
                continue
            sid = e['id']
            rec = out.setdefault(sid, {'prof': prof, 'tables': [], 'skill': None, 'servers': [], 'visible': False})
            rec['tables'].append(tname)
            vis = visible(e)
            rec['visible'] = rec['visible'] or vis
            for s in server_list(e):
                if s not in rec['servers']:
                    rec['servers'].append(s)
            skill = e.get('skill')
            if isinstance(skill, dict) and (rec['skill'] is None or (vis and tname.endswith(('Apprentice', 'Journeyman', 'Expert', 'Artisan')))):
                rec['skill'] = [int(x) for x in as_list(skill)]
            if rec['prof'] != prof:
                rec.setdefault('other_profs', []).append(prof)
    return out


def _spells(data_dir):
    tables = tables_assigned(os.path.join(data_dir, 'Tables', 'Spells.lua'), r'AtlasCFM\.SpellDB')
    db = next(iter(tables.values()))
    out = {}
    for group, entries in db.items():
        for sid, e in entries.items():
            if not isinstance(e, dict) or not isinstance(sid, int):
                continue
            rec = {'group': group}
            if e.get('item'):
                rec['item'] = int(e['item'])
            qty = e.get('quantity')
            if isinstance(qty, dict):
                rec['qty'] = [int(x) for x in as_list(qty)]
            elif isinstance(qty, (int, float)):
                rec['qty'] = [int(qty)]
            if e.get('name'):
                rec['name'] = str(e['name'])
            req = field(e, 'requires')
            if req:
                rec['requires'] = str(req)
            tools = field(e, 'tools')
            if isinstance(tools, dict):
                rec['tools'] = _ids(tools)
            reagents = field(e, 'reagents')
            if isinstance(reagents, dict):
                rec['reagents'] = [[int(r[1]), int(r.get(2, 1))] for r in as_list(reagents) if isinstance(r, dict) and isinstance(r.get(1), (int, float))]
            out[sid] = rec
    return out


def _walk_loot(data_dir, recipe_ids):
    """Every recipe-item entry in loot, faction and event tables, with its context."""
    found = {}
    for path in sorted(glob.glob(os.path.join(data_dir, '**', '*.lua'), recursive=True)):
        rel = os.path.relpath(path, data_dir).replace('\\', '/')
        if rel.startswith(('Menu/', 'Info/')) or rel in ('Tables/Crafting.lua', 'Tables/Spells.lua', 'Tables/ProfessionTrainers.lua'):
            continue
        for lhs, root in tables_assigned(path, r'[A-Za-z_][\w.]*').items():
            ctx = {'file': rel, 'table': lhs.split('.')[-1]}
            _walk(root, ctx, True, None, recipe_ids, found)
    return found


def _walk(t, ctx, vis, default_rate, recipe_ids, found):
    if not isinstance(t, dict):
        return
    ctx = dict(ctx)
    if isinstance(t.get('Name'), str):
        ctx['instance'] = t['Name']
    if isinstance(t.get('name'), str) and isinstance(t.get('loot') or t.get('items'), dict):
        ctx['boss'] = t['name']
    vis = vis and visible(t)
    defaults = t.get('defaults')
    if isinstance(defaults, dict) and defaults.get('dropRate') is not None:
        default_rate = defaults['dropRate']
    standing = None
    for k, v in t.items():
        if isinstance(k, str) and k not in ('loot', 'items') and isinstance(v, dict) and not isinstance(k, int):
            _walk(v, dict(ctx, table=k if 'instance' not in ctx else ctx['table']), vis, default_rate, recipe_ids, found)
    for k in ('loot', 'items'):
        if isinstance(t.get(k), dict):
            _walk(t[k], ctx, vis, default_rate, recipe_ids, found)
    for e in as_list(t):
        if not isinstance(e, dict):
            continue
        if isinstance(e.get('name'), str) and e['name'] in STANDINGS and 'id' not in e:
            standing = e['name'] if visible(e) else standing
            continue
        iid = e.get('id')
        if isinstance(iid, int) and iid in recipe_ids:
            rate = e.get('dropRate', default_rate)
            found.setdefault(iid, []).append({
                'file': ctx['file'], 'table': ctx.get('table'), 'instance': ctx.get('instance'), 'boss': ctx.get('boss'),
                'standing': standing, 'drop_rate': str(rate) if rate is not None else None,
                'disc': e.get('disc') if isinstance(e.get('disc'), str) else None,
                'container': _ids(e.get('container')), 'visible': vis and visible(e), 'servers': server_list(e)})
        elif not isinstance(iid, int):
            _walk(e, ctx, vis, default_rate, recipe_ids, found)


def _trainers(data_dir):
    tables = tables_assigned(os.path.join(data_dir, 'Tables', 'ProfessionTrainers.lua'), r'ProfessionTrainers')
    root = next(iter(tables.values()))
    out = {}
    for prof_name, entries in root.items():
        key = prof_name.lower().replace(' ', '')
        pid = next((p[0] for p in config.PROFESSIONS if p[1].lower().replace(' ', '') == key), key)
        for e in as_list(entries):
            if isinstance(e, dict) and e.get('name') and visible(e):
                out.setdefault(pid, []).append({'name': str(e['name']), 'loc': str(e.get('loc') or ''),
                                                'faction': {'ALLIANCE': 'A', 'HORDE': 'H', 'NEUTRAL': 'AH'}.get(str(e.get('faction'))),
                                                'level': str(e.get('level') or '')})
    return out


def extract(recipe_ids, addon_dir=None):
    data_dir = os.path.join(addon_dir or config.ADDONS['atlas-cfm'], 'CFMLoot', 'Data')
    return {
        'server': config.ATLAS_SERVER,
        'craft_spells': _craft_spells(data_dir),
        'spells': _spells(data_dir),
        'recipe_items': _walk_loot(data_dir, set(recipe_ids)),
        'trainers': _trainers(data_dir),
    }
