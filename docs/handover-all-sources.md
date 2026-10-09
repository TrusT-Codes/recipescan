# Handover: all recipe sources (trainer, quest, drop, reputation vendor)

The page lists every Classic recipe of the 8 Wowhead professions plus OctoWow's Jewelcrafting, not only vendor-sold ones.
A recipe row has one or more **source entries**: vendor, reputation vendor, trainer, quest reward, drop.

## Data files
| File | Producer | Content |
| --- | --- | --- |
| `data/ow.txt`, `data/ow_crafting.txt`, `data/wh.txt`, `data/wh_crafting.txt` | earlier vendor scrape (see `handover-add-professions.md`) | vendor NPCs with coordinates, vendor-sold recipes |
| `data/recipes_wh.txt` | `scripts/scrape_wowhead.py emit` | every Wowhead recipe: skill, crafted item + quality, reputation, all sources |
| `data/recipes_ow.txt` | browser-pane script below | OctoWow-only recipes (custom Turtle-style content) and all Jewelcrafting |
| `data/wh_npcs.txt` | `scrape_wowhead.py emit` | trainers / vendors that are not in `wh.txt`/`ow.txt` (vendor-format lines with coordinates) |
| `data/zones.txt` | `scrape_wowhead.py emit` | zone id -> name for drop mobs and quests |
| `data/items.txt` | extended by `emit` | crafted item quality / item level / class (feeds the disenchant columns) |

Line format (both recipe files):
```
R|profession|key|source|name|skill|teachSpellId|craftedItemId|craftedQuality|repFaction|repLevel
S|key|V|npcId|name|zoneIds|react            vendor (react = [alliance,horde])
S|key|T|npcId                               trainer (NPC must exist in a V| line)
S|key|Q|questId|name|side|zone              quest reward (side 1 Alliance, 2 Horde, 3 both; zone = id or name)
S|key|D|npcId|name|zoneIds|react|pct        drop
S|key|X|label                               world drop / container loot, shown as one line
```
`key` is the recipe item id, or `s<spellId>` for trainer-only recipes. `S` lines belong to the `R` line above them.

## Build rules (`build.py`)
- A vendor that sells a recipe whose item says "Requires <faction> - <level>" is typed **Reputation**, not Vendor. The row gets the Reputation column value.
- Skill level: Wowhead `learnedat` wins; OctoWow rows use `Requires <profession> (N)` on the recipe item, then the **lowest** non-empty value of the craft spell's skill breakdown (orange/yellow/green/grey; for 56058 Pure Shining Moonstone that is 180). `?` only remains where OctoWow has no breakdown (Small Pearl Ring, Shining Copper Cuffs).
- Recipes whose item teaches no spell (OctoWow ids 76, 77, 55076, 70242) are skipped unless they already had a vendor.
- Rarity is the crafted item quality for every row (`q`); iLvl (`i`) and the disenchant mats stay Tailoring/Leatherworking/Blacksmithing/Engineering only.
- Season of Discovery recipes are excluded (`data/sod_excluded.txt` plus every recipe item id >= 200000).

## Wowhead (`scripts/scrape_wowhead.py`, Python 3, plain `curl`)
Stages: `lists items trainers quests npcs emit`. Pages are cached in `scratch/cache` (git-ignored), so re-running is cheap.
- `spells/professions/<slug>` (secondary: `spells/secondary-skills/cooking|first-aid`) embeds `var listviewspells`: `learnedat`, `colors`, `creates`, `quality`, `source` (6 = trainer).
- `items/recipes/<slug>` embeds `var listviewitems`; `items?filter=86;<id>;0` lists crafted items (item level in `level`).
- Item pages: `teaches-recipe`, `sold-by`, `dropped-by` (`count/outof` = drop chance), `pick-pocketed-from`, `contained-in-*`, `fished-in`, `reward-from-q`; the tooltip holds `Requires <faction> - <level>`.
- Trainers: spell pages list `taught-by-npc`; NPC pages list `teaches-recipe`. The script seeds trainers from a spread of spells, reads each NPC page and falls back to the spell page for spells nobody covers.
- Rate limit: CloudFront answers 403 (919 byte body) after a few hundred fast requests, also to a second parallel process. `fetch` paces at 3 s and backs off; never run two crawlers at once.

## OctoWow (browser pane only, see `handover-add-professions.md` for the challenge page)
- Recipe lists `/db/?items=9.<sub>` (1 LW, 2 tailoring, 3 engineering, 4 BS, 5 cooking, 6 alchemy, 7 first aid, 8 enchanting, 10 jewelcrafting); the OctoWow-only ones are those not on Wowhead.
- Item page listviews: `sold-by`, `dropped-by`, `reward-of` (quest). The tooltip holds `Requires ...` and the `?spell=` of the taught spell; the craft spell is that id + 1.
- Spell lists `/db/?spells=11.<skill>` (cooking/first aid: `9.185` / `9.129`) give `colors` per craft spell.
- Crafted item and quality: the craft spell page links the item (`<span class="qN"><a href="?item=ID">`); otherwise search by name (`/db/?search=`), the digit in front of the name is the quality.
- OctoWow tooltips list several `Requires` lines (skill, specialisation, faction); split on `Requires ` and test each piece for `<faction> - <level>` instead of anchoring on the first one.
- OctoWow answers 503 under load: 3 parallel requests with ~150 ms pauses were fine.
- Do not click inside the pane while a harvest runs (a stray click navigated away and wiped `window` state). Persist results to `localStorage` before exporting.
- There is no trainer data for Jewelcrafting on OctoWow (the one "Jewelcrafting Trainer" NPC teaches junk spells), so JC recipes without a recipe item are not listed.
- Zone ids: OctoWow has no `?zone=` pages; ids are the standard WoW area ids and are named through Wowhead.

## Known gaps
- Spells that only a quest, discovery, PvP vendor or event teaches and that have no recipe item are not listed.
- "Requires Goldsmith / Gemology" (OctoWow Jewelcrafting specialisations) is not shown anywhere.
- Quest locations show the zone of the quest giver, not coordinates; drops show zones only. The route planner only uses NPCs with coordinates.
