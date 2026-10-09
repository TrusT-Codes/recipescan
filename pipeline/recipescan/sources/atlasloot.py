"""AtlasLoot TW Edition: item quality from its `{ id, icon, "=qN=Name", ... }` loot rows (fallback only)."""
import glob
import os
import re

from .. import config

ROW = re.compile(r'\{\s*(\d+)\s*,\s*"[^"]*"\s*,\s*"=q([0-5])=([^"]*)"')


def extract(addon_dir=None):
    root = addon_dir or config.ADDONS['atlasloot']
    quality = {}
    for path in sorted(glob.glob(os.path.join(root, '**', '*.lua'), recursive=True)):
        with open(path, encoding='utf-8', errors='replace') as f:
            for m in ROW.finditer(f.read()):
                iid = int(m.group(1))
                if iid > 0:
                    quality.setdefault(iid, [int(m.group(2)), m.group(3).strip()])
    return {'items': quality}
