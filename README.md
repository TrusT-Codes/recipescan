# recipescan
Website to scan all available Recipes on Octowow

Single-page report of every Classic profession recipe and where to get it, for Tailoring, Leatherworking, Enchanting, Alchemy, Blacksmithing, Engineering, Cooking, First Aid and Jewelcrafting (OctoWow + Wowhead Classic; Jewelcrafting is OctoWow only). Sources per recipe: vendor, reputation vendor, trainer, quest reward and drop, with faction, source and zone filters, recipe/NPC links, reputation requirement, rarity, likely disenchant mats and a route planner.

- `index.html` - generated page (open directly or serve via GitHub Pages)
- `template.html` - page UI and route planner
- `data/ow.txt`, `data/ow_crafting.txt` - OctoWow vendor/recipe data
- `data/wh.txt`, `data/wh_crafting.txt` - Wowhead Classic vendor/recipe data
- `data/recipes_wh.txt`, `data/recipes_ow.txt`, `data/wh_npcs.txt`, `data/zones.txt`, `data/zones_extra.txt` - all recipes with skill, crafted item, reputation and every source (trainer, quest, drop, vendor)
- `data/items.txt`, `data/crafted.txt` - crafted item quality/item level and recipe -> crafted item links
- `data/disen_table.txt` - disenchant table by quality + item level (WoWWiki "Disenchanting tables")
- `data/sod_excluded.txt` - recipes added in Season of Discovery (Wowhead patch 1.15.x); build.py skips them
- `build.py` - rebuilds `index.html` (Python 2.7: `python build.py`)
- `scripts/scrape_wowhead.py` - Wowhead Classic scraper for `data/recipes_wh.txt` (Python 3, see the docstring)
- `docs/handover-add-professions.md` - how the vendor data was scraped
- `docs/handover-all-sources.md` - how trainer/quest/drop/reputation data and skill levels were scraped
