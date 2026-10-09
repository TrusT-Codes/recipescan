# Handoff: export addon (phase 2) and website (phase 3)

Read this first, then `docs/roadmap.md` (decisions and plan), `pipeline/README.md` (data rules) and `docs/addon-live-checks.md` (live client results).

**Where things stand (2026-10-09):**
- Branch `feature/find-learned-ingame-recipes`, PR https://github.com/TrusT-Codes/recipescan/pull/5 (open; pipeline + docs).
- Phase 1 is done. The phase 2 live checks are answered except C12/C15 (profession rank source for Jewelcrafting).
- **Next:** build `addon/RecipeScan/` (phase 2), then scaffold `web/` (phase 3). Ask the user whether to continue on this branch after PR #5 merges or to start a new branch from `main`.

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
- **TradeSkill professions** (every profession except Enchanting, Jewelcrafting included): the addon reports **crafted item IDs** from `GetTradeSkillItemLink(i)` → `item:<id>`. Live example: 10050 Mageweave Bag. Match on `recipes.craftedItem` within the profession. A few crafted items are made by more than one spell; fall back to the name if needed.
- **Enchanting** (Craft API): the addon reports **craft spell IDs** from `GetCraftItemLink(i)` → `enchant:<id>`. Live example: 57146 = recipe `s57146` Enchant Bracer - Vampirism. Match on `recipes.spell`.
- `i<item>` recipes without a spell: match on the crafted item where it is known, otherwise by name.
- Export the skill rank and max rank per profession too, for a "learnable now" filter against `recipes.skill`.

## Phase 2: export addon. All design-critical checks are done
`docs/addon-live-checks.md` has every check (C1–C15) with its live result. Confirmed facts are also in the skill's `references/client-facts.md` section 4.15. Don't re-derive them.

**Confirmed on the user's client (2026-10-09):**
| Topic | Fact |
| --- | --- |
| APIs | TradeSkill API for every profession except Enchanting (Turtle Jewelcrafting included). Craft API for Enchanting. `GetTradeSkillLine()` / `GetCraftDisplaySkillLine()` return the English name. |
| Link parse | `string.find(link, "H(%a+):(%d+)")` → `"item", id` (TradeSkill) or `"enchant", spellId` (Craft). |
| Row info | `GetTradeSkillInfo(i)` → `name, type, numAvailable, isExpanded`; type is `header` or a difficulty (`optimal`/`medium`/`easy`/`trivial`). `GetCraftInfo(i)` → `name, subName, type, numAvailable, isExpanded, trainingPointCost, requiredLevel`. |
| Hidden rows | Collapsed headers **and** the subclass filter both hide recipes, independently: with all headers collapsed the count was `0`. A full scan needs `SetTradeSkillSubClassFilter(0,1,1)`, `SetTradeSkillInvSlotFilter(0,1,1)` and `ExpandTradeSkillSubClass(0)`. `GetTradeSkillSubClasses()` lists the subclass names. |
| Events | `TRADE_SKILL_UPDATE` fires **before** `TRADE_SKILL_SHOW` (same for `CRAFT_*`). `*_UPDATE` repeats 1–2× per craft. These events carry no args; `arg1` is stale. |
| Skill ranks | `GetSkillLineInfo(i)` → `name, isHeader, isExpanded, rank, temp, modifier, maxRank`. |
| File export | SuperWoW 1.5: `ExportFile(name, text)` writes `<WoW>\Imports\<name>.txt` (user: `F:\Octo_WoW\Imports\`). It **overwrites**, keeps `\n` as line breaks and handled 60,000 characters. `ImportFile(name)` returns the content as a string. |

**Still open (ask the user; not blocking):**
- **C12/C15:** does Jewelcrafting appear in `GetSkillLineInfo`? It was missing from the user's list. Does `GetTradeSkillLine()` return `name, rank, maxRank`? C15 in the checks doc has the two `/run` lines. Until answered, take rank from `GetTradeSkillLine()` / `GetCraftDisplaySkillLine()` if they return it, otherwise from `GetSkillLineInfo`; Jewelcrafting rank may then be unknown.
- Does the native window have its own search box or a have-materials filter with Atlas-CFM disabled? Atlas-CFM's filters only change its own display (`TSF.BuildList`).

**Design (follows from the facts above):**
- **Folder** `addon/RecipeScan/`:
  - `RecipeScan.toc` with `## Interface: 11200` and `## SavedVariables: RecipeScanDB` (account-wide, all alts).
  - Global `RecipeScan`, local alias `RS`, login gate `RS.loginDone`.
  - Copy `~/.claude/skills/vanilla-wow-addon/templates/CLAUDE.md` to `addon/RecipeScan/CLAUDE.md` and fill it in.
- **When to scan:** on `TRADE_SKILL_SHOW` / `CRAFT_SHOW`. Then rescan after `*_UPDATE` with a debounce (ClassicAPI `C_Timer.After(0.5, ...)`, cancel and restart on every update; no OnUpdate polling). That catches newly learned recipes while the window is open.
- **Scan steps (TradeSkill):**
  1. Save state: `GetTradeSkillSubClassFilter`/`GetTradeSkillInvSlotFilter` per index, and the names of the collapsed headers.
  2. Reset the filters `(0,1,1)` and call `ExpandTradeSkillSubClass(0)`.
  3. Read every non-header row's link ID.
  4. Restore: collapse the saved headers by name, walking indices **from the end** because collapsing shifts the rows below. Then restore the filters.
  - **Reentrancy guard:** expand/collapse/filter calls fire `TRADE_SKILL_UPDATE` themselves. Set `RS.scanning = true` around the scan and ignore updates while it's set, or the debounce loops forever. Atlas-CFM hooks `TradeSkillFrame_Update`, which these calls also run.
  - Craft (Enchanting) has headers too: use `ExpandCraftSkillLine(0)` / `CollapseCraftSkillLine`. Those two are **not live-checked yet**; verify with a `/run` before relying on them.
- **Storage:** `RecipeScanDB.chars["Realm-Name"] = {class, race, faction, scannedAt, professions = {[name] = {rank, max, kind = "item"|"spell", ids = {...}}}}`. Realm comes from `GetRealmName()`.
- **Export**, one versioned plain-text format:
  ```
  RS1
  char;<realm>;<name>;<faction>;<class>;<race>;<scannedAt>
  prof;<name>;<rank>;<max>;<item|spell>;<id>,<id>,...
  ```
  One `char` line per character, followed by its `prof` lines. With SuperWoW (`type(ExportFile) == "function"`), write `ExportFile("RecipeScan", text)` after each scan and on `/recipescan export`. That gives `Imports\RecipeScan.txt`; one file covers every character because it's built from the account-wide DB. Without SuperWoW, `/recipescan export` opens a copyable multi-line EditBox with the same text. The site also accepts the dropped `WTF/Account/<ACC>/SavedVariables/RecipeScan.lua`; the TS parser only needs the Lua table subset that `pipeline/recipescan/lua.py` handles.
- **Checks before shipping:** `luac -p` on every file, `bash ~/.claude/skills/vanilla-wow-addon/scripts/verify.sh addon/RecipeScan <outDir> RecipeScan`, a Lua 5.0 syntax review (no `#`, `%`, `...` expressions, `gmatch`), then a live test in the user's client.

## Phase 3: website
- Scaffold `web/` (Vite React TS, Tailwind + shadcn/ui dark, TanStack Table + Virtual, cmdk). Leaflet comes in phase 4. Keep `web/public/data/` as is; the pipeline owns it.
- First screens:
  1. **Import**: drop `Imports\RecipeScan.txt` (SuperWoW route), paste the copy-box text, or drop the SavedVariables `RecipeScan.lua`. All three carry the same `RS1` data and are stored in IndexedDB. Show the user where each file lives (e.g. `<WoW folder>\Imports\RecipeScan.txt`).
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
