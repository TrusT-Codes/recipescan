# recipescan
Website to scan all available Recipes on Octowow

Single-page report of vendor-sold Tailoring, Leatherworking and Enchanting recipes (OctoWow + Wowhead Classic), with faction filters and a route planner.

- `index.html` - generated page (open directly or serve via GitHub Pages)
- `template.html` - page UI and route planner
- `data/` - scraped vendor/recipe data (`ow.txt`, `wh.txt`, `disen.txt`)
- `build.py` - rebuilds `index.html` (Python 2.7: `python build.py`)
