# Changelog

## Unreleased

### Added
- **Data pipeline** (`pipeline/`, Python 3, no dependencies): `extract` reads pfQuest + pfQuest-octo (OctoWow), Atlas-CFM and AtlasLoot into `data/extracted/`. `build` merges them with the scraped data into `build/recipescan.sqlite`, exports `web/public/data/*.json` for the new website and writes `build/report.md` (diff against this page, conflicts, unresolved data).
  - Recipes are keyed by craft spell, so the planned export addon can match learned recipes: crafted item for TradeSkill professions, spell for Enchanting.
  - New data: 1,451 listed recipes (prototype: 1,393). It adds 59 recipes, mostly Turtle/OctoWow content such as Timbermaw Hold, Emerald Sanctum, Centaur and Shen'dralar plans and belt buckles. No prototype recipe is lost; the two Warbear Harness patterns (drop and Timbermaw reputation) are now one recipe.
  - Atlas-CFM skill difficulty colours, reagents, tools and crafting station for every recipe. pfQuest-octo vendor stock, drop chances and NPC spawn points. Zone hierarchy and map bounds for the planned maps.
- Every recipe source, not only vendors: **Trainer**, **Quest** reward and **Drop** (single creatures, or one "World drop" line when many creatures drop it) join Vendor. All of Wowhead Classic's profession recipes are listed now, including trainer-taught ones, plus OctoWow-only recipes.
- **Reputation** source: vendor recipes whose item says "Requires <faction> - <level>" are typed Reputation instead of Vendor and only show while that source is ticked. New sortable **Reputation** column (faction, level).
- New sortable **Source** column between Faction and iLvl, and a multiple choice **Source** filter (Vendor, Reputation, Trainer, Quest, Drop). Rows with many sources show the first four with a "+N more" toggle.
- **Rarity** is shown for every recipe (crafted item quality, Poor to Legendary), not only for the disenchantable professions.
- Jewelcrafting grew from 7 to all recipes OctoWow knows an item source for.
- `scripts/scrape_wowhead.py` (re-runnable, cached) and `docs/handover-all-sources.md`.
- Disenchant mats column sorts by material value (dust < essence < shard, rising with item level) instead of alphabetically.
- Vendor name, location and faction are now three separate sortable columns; likely disenchant mats are split into sortable iLvl, Rarity and mats columns.
- Filters for vendor zone and disenchant material (dropdowns), plus a "Clear all filters" button. Filters live in a registry (`FILTERS` in `template.html`), so new entries are cleared automatically.
- Jewelcrafting tab with the 7 vendor-sold recipes (OctoWow only; Wowhead Classic has no Jewelcrafting).
- Enchanting: Formula: Enchanted Gemstone Oil (skill 275, 8 vendors).
- `data/sod_excluded.txt`: list of excluded Season of Discovery recipes.

### Changed
- Required skill now prefers Wowhead's value over OctoWow's when both exist (fixes Dark Iron Bracers, Heavy Scorpid Bracers, Corehound Boots; fills Fiery Chain Girdle/Shoulders).
- Jewelcrafting skill levels are filled in: OctoWow's "Requires <profession> (N)" or, when the recipe has none, the lowest value of the craft spell's skill breakdown (e.g. Pure Shining Moonstone starts yellow at 180). Only Small Pearl Ring and Shining Copper Cuffs have no breakdown and still show "?".
- Vendor recipes that need faction standing (90 recipes, e.g. Mantle of the Timbermaw) moved from Vendor to the Reputation source.
- The vendor column is now "Obtained from" and also lists trainers, quests and drops.

### Removed
- 95 recipes added in Season of Discovery (Wowhead patch 1.15.x) across all professions. Highest listed skill is now 300.
