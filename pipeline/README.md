# Data pipeline

Builds the recipe database and the website data. Python 3.10+, standard library only.

```
py -3 pipeline/run.py extract   # reference addons -> data/extracted/*.json  (needs the git-ignored addon folders)
py -3 pipeline/run.py build     # data/*.txt + data/extracted -> build/recipescan.sqlite, web/public/data/*.json, build/report.md
py -3 pipeline/run.py all       # both
```

`build` only reads committed files, so it runs anywhere (CI included). Re-run `extract` when a reference addon is updated, then commit `data/extracted/`.

## Stages

| Stage | Reads | Writes |
| --- | --- | --- |
| `extract` | `pfQuest/`, `pfQuest-octo/`, `Atlas-CFM/`, `AtlasLoot/` (repo root, git-ignored) + `data/*.txt` (to know which ids matter) | `data/extracted/pfquest.json`, `atlas.json`, `atlasloot.json`, `manifest.json` (addon versions) |
| `build` | `data/*.txt`, `data/extracted/*.json`, `index.html` (prototype, for the diff) | `build/recipescan.sqlite`, `build/report.md` (git-ignored), `web/public/data/*.json` (committed) |

## Modules (`pipeline/recipescan/`)

| File | Job |
| --- | --- |
| `lua.py` | Reads Lua table literals from addon files (not an interpreter: `L["x"]` -> `"x"`, `a .. b` -> text) |
| `sources/legacy.py` | Parses the scraped `data/*.txt` (Wowhead `wh`, OctoWow `ow`) |
| `sources/pfquest.py` | pfQuest + Octo overlay (merged like `pfQuest-octo/patchtable.lua`), plus `toolbox/client-data.sql` (AreaTable, WorldMapArea) |
| `sources/atlas.py` | Atlas-CFM craft spells, spell details, recipe items in loot / faction tables, trainers; server visibility for `config.ATLAS_SERVER` |
| `sources/atlasloot.py` | AtlasLoot item quality (fallback) |
| `merge.py` | Resolves recipes and applies the source precedence (see its docstring) |
| `store.py`, `schema.sql` | SQLite output |
| `export.py` | Website JSON, read back from SQLite |
| `report.py` | `build/report.md`: diff against the prototype page, unresolved data, conflicts |

## Rules worth knowing

- **Recipe id** is `s<craft spell id>`; `i<recipe item id>` only when no craft spell could be found.
  - Wowhead's `teachSpellId` is the craft spell.
  - OctoWow's is the *learn* spell. The craft spell sits next to it (usually +1, sometimes -1) and is confirmed by the crafted item or the name in Atlas-CFM.
- **Matching learned recipes (addon export):** TradeSkill professions report the crafted item (`recipes.craftedItem` within the profession); Enchanting reports the craft spell (`recipes.spell`).
- **Sources:**
  - Vendors come from pfQuest-octo + the OctoWow scrape; Wowhead only fills in when both are empty.
  - Drops come from pfQuest-octo, then the OctoWow scrape, then Wowhead, then Atlas-CFM boss tables (only rows with a drop rate), then world-drop labels.
  - Quests and trainers come from the scrapes.
- **Listed** recipes have at least one source and are not hidden by Atlas-CFM for the server, unless pfQuest-octo has a source for them. Everything else stays in the DB with `listed = 0` and `unlisted_reason`.
- On the site, drops from more than `WORLD_DROP_MIN_UNITS` creatures become one `world` source (creature count + best five).
- `meta.json` `dataVersion` is a hash of the exported content, so it only changes when the data does.
