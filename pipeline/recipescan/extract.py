"""Stage 1: read the reference addons (git-ignored) into committed data/extracted/*.json."""
import datetime
import os
import re
import subprocess

from . import config, jsonio
from .sources import atlas, atlasloot, legacy, pfquest


def _addon_version(path):
    info = {}
    try:
        out = subprocess.run(['git', '-C', path, 'log', '-1', '--format=%H %cs'], capture_output=True, text=True, check=True).stdout.split()
        top = subprocess.run(['git', '-C', path, 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
        if os.path.normcase(os.path.abspath(top)) == os.path.normcase(os.path.abspath(path)):
            info['commit'], info['date'] = out[0], out[1]
            info['remote'] = subprocess.run(['git', '-C', path, 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError, IndexError):
        pass
    for toc in sorted(os.listdir(path)):
        if toc.endswith('.toc'):
            with open(os.path.join(path, toc), encoding='utf-8-sig', errors='replace') as f:
                m = re.search(r'^## Version:\s*(.+)$', f.read(), re.M)
            if m:
                info['version'] = m.group(1).strip()
    return info


def run():
    for name, path in config.ADDONS.items():
        if not os.path.isdir(path):
            raise SystemExit('missing reference addon %s at %s' % (name, path))
    old = legacy.load()
    item_ids = {r['item'] for r in old['recipes'] if r['item']} | {r['item'] for r in old['vendor_recipes']}
    quest_ids = set(old['quests'])

    print('pfQuest ...')
    pf = pfquest.extract(extra_item_ids=item_ids, extra_unit_ids=old['npcs'], extra_quest_ids=quest_ids)
    prefix = re.compile(config.RECIPE_PREFIX)
    recipe_ids = item_ids | {k for k, n in pf['item_names'].items() if prefix.match(n)}
    print('Atlas-CFM ...')
    at = atlas.extract(recipe_ids)
    print('AtlasLoot ...')
    al = atlasloot.extract()

    os.makedirs(config.EXTRACTED, exist_ok=True)
    jsonio.write_sections(os.path.join(config.EXTRACTED, 'pfquest.json'), pf)
    jsonio.write_sections(os.path.join(config.EXTRACTED, 'atlas.json'), at)
    jsonio.write_sections(os.path.join(config.EXTRACTED, 'atlasloot.json'), al)
    manifest = {name: _addon_version(path) for name, path in config.ADDONS.items()}
    manifest['extracted_at'] = datetime.date.today().isoformat()
    jsonio.write_sections(os.path.join(config.EXTRACTED, 'manifest.json'), manifest)
    for fn in ('pfquest.json', 'atlas.json', 'atlasloot.json'):
        p = os.path.join(config.EXTRACTED, fn)
        print('  %-15s %7.0f KB' % (fn, os.path.getsize(p) / 1024))
    print('  pfQuest: %d item names, %d recipe items with sources, %d units, %d objects, %d quests'
          % (len(pf['item_names']), len(pf['item_sources']), len(pf['units']), len(pf['objects']), len(pf['quests'])))
    print('  Atlas: %d craft spells, %d spells, %d recipe items in loot tables'
          % (len(at['craft_spells']), len(at['spells']), len(at['recipe_items'])))
