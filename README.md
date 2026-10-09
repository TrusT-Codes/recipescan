# recipescan
Website to scan all available Recipes on Octowow

Single-page report of vendor-sold recipes for Tailoring, Leatherworking, Enchanting, Alchemy, Blacksmithing, Engineering, Cooking and First Aid (OctoWow + Wowhead Classic), with faction filters, recipe/vendor links, likely disenchant mats and a route planner.

- `index.html` - generated page (open directly or serve via GitHub Pages)
- `template.html` - page UI and route planner
- `data/ow.txt`, `data/ow_crafting.txt` - OctoWow vendor/recipe data
- `data/wh.txt`, `data/wh_crafting.txt` - Wowhead Classic vendor/recipe data
- `data/items.txt`, `data/crafted.txt` - crafted item quality/item level and recipe -> crafted item links
- `data/disen_table.txt` - disenchant table by quality + item level (WoWWiki "Disenchanting tables")
- `build.py` - rebuilds `index.html` (Python 2.7: `python build.py`)
- `docs/handover-add-professions.md` - how the data was scraped
