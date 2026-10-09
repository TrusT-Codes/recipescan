# Handoff: export addon (phase 2) and website (phase 3)

Read this first, then `docs/roadmap.md` (decisions and plan) and `pipeline/README.md` (data rules).

## Goal
Players on **OctoWow** (vanilla 1.12.1, Turtle WoW-derived custom server) see which profession recipes their characters are **missing** and where to get them. Flow:
1. A small in-game **export addon** (`addon/RecipeScan/`) scans learned recipes.
2. The user imports the export into the **website** (`web/`).
3. The site lists missing recipes with their sources.

A full in-game addon is a later option. Keep data and code reusable for it: the pipeline can later emit a `Data.lua`.

## Decided (by the user, don't relitigate)
- Phase order: export addon + website first, full addon later.
- Website stack: **Vite + React + TypeScript, shadcn/ui (Radix + Tailwind, dark theme), TanStack Table + TanStack Virtual, cmdk command palette, Leaflet zone maps**.
- Data: SQLite is the source of truth (`pipeline/`). The site reads static JSON from `web/public/data/` (GitHub Pages, no backend). Characters are stored only in the browser (IndexedDB).
- **All addon work uses the `vanilla-wow-addon` skill** (`~/.claude/skills/vanilla-wow-addon/`; read SKILL.md + references before writing Lua). Key rules:
  - Lua 5.0 (no `#`, `%`, `...` expressions, `gmatch`).
  - Handlers use globals `this`/`event`/`arg1`.
  - Max 32 upvalues per function.
  - `/run` checks of 250 characters or fewer; never guess client behaviour.
  - Stage git files by exact path.

## State (end of phase 1)
- `pipeline/` (Python 3, stdlib only):
  - `py -3 pipeline/run.py extract` reads the git-ignored reference addons in the repo root (`pfQuest/`, `pfQuest-octo/`, `Atlas-CFM/`, `AtlasLoot/`) into committed `data/extracted/*.json`.
  - `py -3 pipeline/run.py build` writes `build/recipescan.sqlite` and `build/report.md` (both git-ignored) and `web/public/data/*.json` (committed, deterministic, `meta.json` `dataVersion` is a content hash).
- **1,451 listed recipes** in 9 professions: alchemy, blacksmithing, enchanting, engineering, jewelcrafting, leatherworking, tailoring, cooking, firstaid.
- The legacy prototype (`build.py` Python 2.7, `template.html`, `index.html`) is untouched and still the live GitHub Pages page. Move it to `legacy/` only when the new site replaces it.

## Website data contract (`web/public/data/`)
| File | Shape |
| --- | --- |
| `meta.json` | `schemaVersion`, `dataVersion`, `server`, `professions[{id,name,kind,recipes}]`, `sources[]` (addon versions), `disenchant[]` rules |
| `recipes.json` | array of `{id, profession, name, spell?, skill?, colors?[orange,yellow,green,grey], craftedItem?, craftedQty?, recipeItems?[], station?, reputation?{faction,level}, reagents?[[item,count]], tools?[], sources[]}` |
| `recipes.json` → `sources[]` | `{type: vendor\|reputation\|trainer\|quest\|drop\|object\|world, npc?, object?, quest?, chance?, stock?, note?, item?, origin}`; `world` = `{count, top[[npc,chance]]}` |
| `items.json` | `{id: {name, quality?, itemLevel?, class?}}` (recipe items, crafted items, reagents, tools) |
| `npcs.json` | `{id: {name, faction? (A/H/AH), level?, rank?, spawns[[zone,x,y]] or [[zone]]}}` |
| `objects.json`, `quests.json` | same idea; quests `{name, level?, minLevel?, side?, zone?, starters[[kind,id]]}` |
| `zones.json` | `{id: {name, parent?, continent?, bounds?[x_min,y_min,x_max,y_max]}}`. `bounds` are WorldMapArea world coordinates: zone map x/y percent maps onto them, which Leaflet needs |

Optional keys are omitted when empty. `id` is `s<craftSpellId>`, or `i<recipeItemId>` for 22 OctoWow recipes without a known craft spell.

## Matching learned recipes (addon → site)
- **TradeSkill professions** (all but Enchanting): the addon reports **crafted item IDs** from `GetTradeSkillItemLink(i)`. Match on `recipes.craftedItem` within the profession. A few crafted items are made by more than one spell; fall back to the name if needed.
- **Enchanting** (Craft API): the addon reports **craft spell IDs** from `GetCraftItemLink(i)` (`enchant:<id>`). Match on `recipes.spell`.
- `i<item>` recipes without a spell: match on the crafted item where it is known, otherwise by name.
- Also export skill rank and max rank per profession (`GetSkillLineInfo`) for a "learnable now" filter (`recipes.skill`).

## Phase 2: export addon. First step: live checks
`docs/addon-live-checks.md` holds checks C1 to C8 (TradeSkill item links, expanding headers, filter reset, Craft spell links, the Jewelcrafting window type, events, skill ranks, SuperWoW `ExportFile`). The user runs them in game.
- **Do not write scan code until the results are recorded in that file.**
- Copy confirmed facts into the skill's `references/client-facts.md` section 4.

Planned design (adjust it to the check results):
- Folder `addon/RecipeScan/`. Use `RecipeScan.toc` with `## Interface: 11200` and `## SavedVariables: RecipeScanDB` (account-wide, all alts).
- Global `RecipeScan`, local alias `RS`. Login gate `RS.loginDone`.
- Scan when TRADE_SKILL_SHOW/UPDATE or CRAFT_SHOW/UPDATE fire (debounce with ClassicAPI `C_Timer.After`, no OnUpdate polling). The scan:
  1. remembers the collapsed headers and filters;
  2. expands all and clears the filters;
  3. reads the IDs;
  4. restores the headers and filters.
- Store `RecipeScanDB.chars["Realm-Name"] = {class, race, faction, scannedAt, professions = {[name] = {rank, max, ids = {...}, kind = "item"|"spell"}}}`.
- `/recipescan export` opens a copyable multi-line EditBox with a versioned string, e.g. `RS1;realm;name;faction;class;prof:rank:max:kind:id,id,...;...`. Plain text so the site can parse it; no base64 needed.
- The site also accepts a dropped `WTF/Account/<ACC>/SavedVariables/RecipeScan.lua`. It needs a tiny Lua-table parser in TS; the Python one in `pipeline/recipescan/lua.py` shows the subset.
- Use the template `~/.claude/skills/vanilla-wow-addon/templates/CLAUDE.md` for `addon/RecipeScan/CLAUDE.md`.

## Phase 3: website
- Scaffold `web/` (Vite React TS, Tailwind + shadcn/ui dark, TanStack Table + Virtual, cmdk). Leaflet comes in phase 4. Keep `web/public/data/` as is; the pipeline owns it.
- First screens:
  1. **Import** (paste the export string or drop the SavedVariables file → IndexedDB).
  2. **Character → profession missing-recipes table**: filters for source type, faction (`npcs.faction`), learnable-now, zone; sort by skill.
  3. **Recipe detail drawer**: sources, reagents, skill colours.
- Generate TS types from the data contract above. Load data lazily and cache it by `dataVersion`.
- Deploy to GitHub Pages. The legacy `index.html` currently lives at the repo root, so decide the new site path with the user before switching.

## Open data questions (see `build/report.md` after a build)
- 22 OctoWow recipes have no craft spell, and 223 Atlas-CFM craft spells have no recipe data (probably trainer-taught on Turtle/OctoWow). Atlas trainer lists have names only.
- 115 recipes have a different skill in the scrape and in Atlas-CFM. The scrape wins; OctoWow Jewelcrafting recipe items require about 20 more than Atlas's orange.
- 37 listed recipes miss a field, mostly item quality for new Turtle items.
- The site's "learnable now" filter needs the skill to **learn**, not the orange value. Both are exported.

## Useful facts
- OctoWow `teachSpellId` (scrape) is the learn spell. The craft spell is ±1 and the pipeline confirms it by crafted item or name. Wowhead's is the craft spell.
- pfQuest-octo is OctoWow-specific (`dburl = octowow.st`). It merges onto pfQuest per field; `"_"` deletes.
- Atlas-CFM server profile for OctoWow is `Turtle WoW` (`pipeline/recipescan/config.py` `ATLAS_SERVER`). Atlas lists vendors and quest chains as "bosses"; only rows with a `dropRate` are drops.
- `pfQuest/toolbox/client-data.sql` has the client AreaTable and WorldMapArea tables (zone names, parents, map bounds).
