"""Stage 2: data/*.txt + data/extracted/*.json -> build/recipescan.sqlite, web/public/data/*.json, build/report.md."""
import os

from . import config, export, jsonio, merge, report, store
from .sources import legacy


def _ints(d):
    """JSON object keys back to ints, one level deep for the given sections."""
    return {int(k) if isinstance(k, str) and k.lstrip('-').isdigit() else k: v for k, v in d.items()}


def load_extracted():
    def read(name):
        path = os.path.join(config.EXTRACTED, name)
        if not os.path.exists(path):
            raise SystemExit('missing %s - run `py -3 pipeline/run.py extract` first' % path)
        return jsonio.read(path)

    pf = {k: _ints(v) if isinstance(v, dict) else v for k, v in read('pfquest.json').items()}
    pf['item_sources'] = {i: {k: _ints(v) for k, v in s.items()} for i, s in pf['item_sources'].items()}
    at = read('atlas.json')
    at['craft_spells'] = _ints(at['craft_spells'])
    at['spells'] = _ints(at['spells'])
    at['recipe_items'] = _ints(at['recipe_items'])
    al = {'items': _ints(read('atlasloot.json')['items'])}
    return pf, at, al, read('manifest.json')


def run():
    old = legacy.load()
    pf, at, al, manifest = load_extracted()
    m = merge.build(old, pf, at, al, manifest)
    db_path = os.path.join(config.BUILD, 'recipescan.sqlite')
    store.write(m, db_path)
    counts = export.run(db_path)
    diff = report.write(m, os.path.join(config.BUILD, 'report.md'), counts)
    listed = sum(1 for r in m.recipes.values() if r['listed'])
    print('recipes: %d in DB, %d listed' % (len(m.recipes), listed))
    print('exported: ' + ', '.join('%d %s' % (n, k) for k, n in counts.items()))
    print('vs prototype (added/dropped): ' + ', '.join('%s +%d/-%d' % (p, a, d) for p, (a, d) in diff.items()))
    print('wrote %s, %s, %s' % (os.path.relpath(db_path, config.ROOT), os.path.relpath(config.WEB_DATA, config.ROOT),
                                os.path.relpath(os.path.join(config.BUILD, 'report.md'), config.ROOT)))
