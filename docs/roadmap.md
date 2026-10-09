# Roadmap: export addon + website

Goal: players see which profession recipes their characters are **missing** on OctoWow, and where to get them.

Decisions (2026-10-09):
- Phase 1 is a small in-game **export addon** plus a rebuilt **website**. A full in-game addon stays a later option, so the data pipeline must be able to emit Lua tables as well as JSON.
- Website: Vite + React + TypeScript, shadcn/ui (Radix + Tailwind, dark), TanStack Table + TanStack Virtual, cmdk, Leaflet.
- Data: one SQLite database is the source of truth. The site gets static JSON (GitHub Pages, no backend). Characters live only in the browser (IndexedDB).
- Addon work follows the `vanilla-wow-addon` skill (modded 1.12.1 client: Turtle base + SuperWoW, nampower, ClassicAPI; Lua 5.0).

## Data sources

Reference addons sit in the repo root, git-ignored, read-only: `Atlas-CFM/`, `AtlasLoot/`, `pfQuest/`, `pfQuest-octo/`.

| Source | Gives us | Missing | Licence |
| --- | --- | --- | --- |
| **pfQuest + pfQuest-octo** | OctoWow-specific (`dburl = octowow.st`). 24.9k items with sources: vendor `V` (npc → stock limit), unit drop `U` (npc → %), object `O` (object → %), reference loot `R`. Units with coords `{x, y, zoneId, respawn}`, faction `fac`, level. Objects with coords. enUS names. Octo overlay merged per field (`"_"` deletes), see `pfQuest-octo/patchtable.lua`. | quest **rewards**, trainers, recipe → spell link, item quality, zone names (base pfQuest reads them from the client DBC; Octo ships only Turtle zones) | MIT |
| **Atlas-CFM** | 1,870 craft spells with all four skill colours; 1,969 spell entries with reagents + counts, tools, station (Anvil/Forge/Moonwell), crafted item; recipe item → crafted item (`container`); boss drop rates; faction reward tiers; trainers per tier; server tags (Turtle / Turtle 1.17.2 / Vanilla+ / Classic) | vendors, NPC coords, world drops, quests, names, quality | GPL v2 or later |
| **AtlasLoot TW** | item names + quality inline (`=q4=Name`) for listed loot and crafted sets | mostly redundant with Atlas-CFM | GPL |
| Wowhead Classic scrape (`data/recipes_wh.txt`) | recipe → spell, crafted item + quality, trainers, quest rewards, reputation requirement | OctoWow custom content | scraped |
| OctoWow scrape (`data/recipes_ow.txt`, `ow*.txt`) | custom recipes, Jewelcrafting, vendors with coords | completeness | scraped |

More findings from building the pipeline:
- OctoWow's recipe `teachSpellId` is the *learn* spell. The craft spell is next to it, usually +1 but sometimes -1, and is confirmed through the crafted item or the name. Wowhead's `teachSpellId` is already the craft spell.
- `pfQuest/toolbox/client-data.sql` has the client `AreaTable` and `WorldMapArea` tables for vanilla and Turtle. They give zone names, parent zones, continents and world bounds per zone map; Leaflet needs these to place pins.
- Only 18 of the 39 reference-loot tables that pfQuest items point to exist in pfQuest itself.

Coverage check (`scratch/atlas/pfcov.py`):
- pfQuest + Octo has **1,148** recipe-named items. Our current data has **1,089**.
- **910** of our recipes have a pfQuest source (vendor 372, drop 539, object 206, reference loot 210).
- The other 179 are quest rewards (84), world drops/containers (24), trainers and a few more, and 64 with no source at all. pfQuest doesn't cover these cases.
- **66** recipe items are in pfQuest but not in our data; 29 of them have a source (Timbermaw Hold, Shen'dralar, Centaur vendor plans, Turtle buckles, …). Atlas-CFM finds the same Turtle set.

### Precedence per field
1. pfQuest-octo (OctoWow-specific)
2. OctoWow scrape
3. Atlas-CFM
4. Wowhead (vanilla baseline)

Exceptions:
- Quest rewards come from Wowhead / OctoWow only.
- Skill colours, reagents and stations come from Atlas-CFM.

Every row stores its `source` so conflicts stay traceable.

## Database schema (SQLite, draft)

```sql
professions(id TEXT PK, name, kind)                     -- kind: primary|secondary
zones(id INT PK, name, map_id)
items(id INT PK, name, quality, item_level, class, subclass)
recipes(spell_id INT PK, profession_id, name,
        recipe_item_id NULL, crafted_item_id NULL, crafted_qty,
        skill_req, skill_orange, skill_yellow, skill_green, skill_grey,
        station NULL, rep_faction NULL, rep_level NULL, servers NULL)
reagents(spell_id, item_id, count)        tools(spell_id, item_id)
npcs(id INT PK, name, level, react_a, react_h)
objects(id INT PK, name)
spawns(kind TEXT, ref_id INT, zone_id, x, y)            -- kind: npc|object
recipe_sources(recipe_spell_id, type, ref_id NULL, chance NULL, stock NULL, note NULL, source)
                                                        -- type: vendor|reputation|trainer|quest|drop|object|world|container
quests(id INT PK, name, level, side, zone_id)
provenance(source TEXT PK, version, fetched_at)
```

`spell_id` is the key because recipe items don't exist for trainer recipes. The addon reports crafted item IDs (TradeSkill) or spell IDs (Enchanting/Craft), and both map onto `recipes`.

## Repo layout (target)

```
pipeline/      Python 3: importers -> build/recipescan.sqlite, exporters -> web/public/data/*.json (later addon Data.lua)
web/           Vite + React app
addon/RecipeScan/   export addon (.toc, Lua 5.0)
legacy/        current build.py / template.html / index.html until the new site replaces them
```

## Export addon (phase 1)

- Scans the open profession automatically. The TradeSkill frame gives crafted item IDs (`GetTradeSkillItemLink`); the Craft frame (Enchanting) gives `enchant:<spellId>` (`GetCraftItemLink`). Before scanning it expands headers and clears filters, and puts them back afterwards.
- Stores scans account-wide in `RecipeScanDB[realm][char] = { class, faction, professions = { [name] = { rank, max, ids, scannedAt } } }`, plus skill ranks from `GetSkillLineInfo`.
- `/recipescan export` opens a copyable multi-line edit box with a versioned string (`RS1;...`). The website also accepts the SavedVariables file dropped in directly.
- To check live first (skill rule: `/run` ≤ 250 chars, never guess):
  - TradeSkill filter and expand APIs on this client.
  - Whether the Turtle-only professions (Jewelcrafting, Survival, Gardening) use TradeSkill or Craft.
  - SuperWoW `ExportFile` as a direct file-export route.

## Website (phase 1)

- Import screen: paste the export string or drop the SavedVariables file. It parses in the browser and stores in IndexedDB.
- Character → profession view of missing recipes, with filters: learnable now (skill), source type, faction, zone. TanStack Table with virtual rows.
- Recipe detail: sources with Leaflet map pins, reagents, skill colours.
- A cmdk palette for recipes, items, NPCs and zones.

## Phases

1. **Done (2026-10-09).** `pipeline/`: SQLite schema, imports of `data/*.txt`, pfQuest(+octo), Atlas-CFM and AtlasLoot, JSON export and a diff report against the prototype. See `pipeline/README.md`.
   - Result: 1,451 listed recipes (prototype 1,393). 59 are added. Two prototype rows (Warbear Harness drop and reputation pattern) are now one recipe with two recipe items. Nothing is lost.
   - The Atlas-CFM fallback for drops ignores its "boss" rows that have no drop rate, because those are often vendors or quest chains (Lokhtos, the AQ opening chain).
   - Open data questions, listed in `build/report.md`:
     - 22 OctoWow recipes with no craft spell. They are custom ids that are in neither Atlas-CFM nor Wowhead.
     - 223 Atlas-CFM craft spells with no recipe data, probably taught by trainers on Turtle/OctoWow. Atlas-CFM trainer lists have names but no NPC ids.
     - 115 recipes where the scraped skill and the Atlas-CFM orange value differ. OctoWow Jewelcrafting recipe items usually require 20 more; the scrape wins.
     - 37 listed recipes with a missing field, mostly item quality of new Turtle items.
2. `addon/RecipeScan` export addon with live checks done.
3. `web/` scaffold, import flow, missing-recipes table.
4. Maps (zone images + coords), recipe detail, polish, then retire the legacy page.
5. Later: generate `Data.lua` and grow the addon into the in-game version (tooltips, vendor highlight, missing list).
