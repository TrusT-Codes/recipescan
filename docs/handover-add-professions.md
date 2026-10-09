# Handover: scraping vendor recipes from OctoWow + Wowhead Classic

Goal: add more professions (Alchemy, Blacksmithing, Engineering, Cooking, First Aid, ...) to the recipescan page.
Currently done: Tailoring, Leatherworking, Enchanting. Everything below was verified live for those three unless marked UNVERIFIED.

## Repo layout
- `data/ow.txt`, `data/wh.txt`: scraped data (formats below). `data/disen.txt`: `recipeId|mat name` (tailoring only).
- `build.py` (Python 2.7, `python build.py`): merges data, injects JSON into `template.html`, writes `index.html`.
- `template.html`: UI, faction filters, checkbox + route planner (`ZONES`, `FPS`, `LINKS` = hand-built travel model).

## Data file formats (what build.py expects)
- Vendor line: `V|npcId|name|[allianceReact,hordeReact]|Zone x,y; Zone2 x,y` (react: 1 friendly, 0/null neutral, -1 hostile; zone list may be empty)
- OctoWow recipe line: `I|profession|recipeItemId|<qualityDigit>Pattern: Name|requiredSkill|vendorId,vendorId`
- Wowhead recipe line: `I|profession|recipeItemId|Pattern: Name|requiredSkill|createdItemId or None|vendorId,vendorId`
- Only recipes WITH at least one vendor are written. NPC ids are shared between both sites, vendors are keyed by id.

## Constraints that cost time (read first)
1. OctoWow (`https://octowow.st/db/`, AoWoW-based) sits behind a BlazingFast/Cloudflare-style JS challenge. `curl` gets only the challenge page. It works from the built-in browser pane: navigate to `https://octowow.st/db/`, wait ~6 s until the title is "OctoWow Database", then `fetch('/db/?...')` same-origin from page JS.
2. Wowhead Classic works with `curl -s -L -A "Mozilla/5.0"` initially, but after ~250 rapid requests CloudFront returns `403 "The request could not be satisfied"` (919-byte body). The block lasted 10-30 min and also blocked the browser pane. Fix: pace requests. What worked: strictly sequential fetches, 2.5 s sleep between, on 403/short body retry with backoff `20s * attempt` (up to 6). 548 item pages took ~25 min. Treat any body < 5000 bytes as a failure.
3. Browser JS tool has a ~45 s timeout. Start a background async loop that writes to `window.X` plus a `window.DONE` flag, then poll with `await new Promise(r=>setTimeout(r,40000))`. Navigating the tab destroys all `window` state.
4. Use one browser tab per site (`tabs_create`, then pass `tabId` on EVERY javascript call; omitting it runs in the default tab, which happened twice). Hidden panes throttle timers: `tabs_select` the tab you are running a paced loop in.
5. Getting data out of the browser: easiest was returning a compact pipe-delimited string from JS and saving it with the file Write tool. A localhost receiver (python `BaseHTTPServer`, JS `fetch('http://127.0.0.1:PORT/file',{method:'POST',mode:'no-cors',body})`) was set up but UNVERIFIED because the tabs died first. Bash heredocs broke on apostrophes in names; the Write tool refused `/tmp` paths.
6. Keep intermediate files inside a repo folder, not `/tmp`. Do not leave the shell cwd inside a folder you later `rm -rf`.

## OctoWow procedure
- Recipe list per profession: `/db/?items=9.<subclass>`. Verified: `9.1` Leatherworking, `9.2` Tailoring, `9.8` Enchanting. UNVERIFIED (standard item subclass order): 3 Engineering, 4 Blacksmithing, 5 Cooking, 6 Alchemy, 7 First Aid, 9 Fishing. Check by reading item names in the result.
- Parse list: `html.match(/id:'items'[^]*?data: (\[[^]*?\])\}\);/)` then `eval(m[1])` -> objects with `id`, `name` (leading digit = quality, strip it), `level`.
- Per item page `/db/?item=ID`: vendors via `html.match(/id:'sold-by'[^]*?data:\s*(\[[^]*?\])\}\);/)` (note: no space after `id:`). Entries: `{name,id,location:[zoneId],react:[A,H],stock,cost,...}`. Required skill: `html.match(/Requires (?:Tailoring|Leatherworking|Enchanting) \((\d+)\)/)` (extend the profession alternation).
- Per NPC page `/db/?npc=ID`: `[...html.matchAll(/coords: (\[\[[^\n]*?\]\])\}\);g_setSelectedLink\(this, 'mapper'\); return false\\?"[^>]*>([^<]+)</g)]` gives coordinate list + zone name per match; take first `[x,y]` per zone.
- Throughput: batches of 6 parallel were OK; ~465 items + 123 NPCs took ~15 min with the tab in front.
- OctoWow zone names have typos; build.py `ALIASES` fixes them. Unmapped custom Turtle zone "Azeroth" cannot be routed.

## Wowhead procedure
- Recipe list: `https://www.wowhead.com/classic/items/recipes/<slug>`; verified slugs: `tailoring`, `leatherworking`, `enchanting` (others UNVERIFIED, likely `alchemy`, `blacksmithing`, `engineering`, `cooking`, `first-aid`). Page embeds item JSON; extract with `/\{"classs":9,[^{}]*?"id":(\d+),"level":(\d+),"name":"([^"]+)"[^{}]*?"skill":(\d+)/g`. Union these ids with the OctoWow ids.
- Per item `https://www.wowhead.com/classic/item=ID` (curl or browser):
  - Vendors: `/id: 'sold-by'[\s\S]*?data: ?(\[[\s\S]*?\]),?\s*\}\);/` then `JSON.parse`. GOTCHA: the array ends `}],\n});` with a trailing comma; a regex without `,?` matched nothing and forced a complete 25-minute re-run.
  - Entries: `{id,name,react:[A,H] (null = neutral),location:[zoneId],cost,stock}`.
  - Recipe info: `/id: 'teaches-recipe'[\s\S]*?data: ?(\[[\s\S]*?\]),?\s*\}\);/` -> spell object: `learnedat` (= required skill, use this), `creates:[itemId,min,max]` (absent for enchants), `skill:[professionId]`. Verified ids: 197 Tailoring, 165 Leatherworking, 333 Enchanting. UNVERIFIED: 171 Alchemy, 164 Blacksmithing, 202 Engineering, 185 Cooking, 129 First Aid.
- Per NPC `https://www.wowhead.com/classic/npc=ID`: `/"coords":(\[\[[\d.,\[\]]*?\]\]),"uiMapId":\d+,"uiMapName":"([^"]+)"/g` -> zone name + coords. Some NPCs (instance vendors) have none.
- Disenchant mats (tailoring only, weak): mat item pages (e.g. Strange Dust 10940, Greater Astral 11082, ...) have listview id `'disenchanted-from'` (NOT `'disenchanting'`) with source item ids. Invert it and look up each recipe's `creates` id. Only 7 of ~180 crafted items matched. Better idea not yet done: fetch each crafted item's quality + level and map to mat by level range.

## Merge rules (implemented in build.py)
- OctoWow wins on conflicts (required skill, reactions, coordinates); Wowhead only fills vendors OctoWow lacks.
- Dedupe vendors by NPC id; recipes by (profession, recipeItemId). Different recipe ids with the same name stay separate (e.g. Turtle variants).
- Wowhead's list includes later-patch/Turtle items (ids ~210000+, skill 305-320). They are currently kept; decide whether to filter.
- Faction: `react=[A,H]`. Alliance filter shows `a==1 or (a==0 and h<=0)`, Horde filter `h==1 or (h==0 and a<=0)`; so neutral (0,0) shows under both, hostile-to-both under neither.
- Link: Wowhead NPC page if the id came from the Wowhead scrape, else OctoWow `?npc=ID`.

## To add a profession
1. Scrape both sites with the procedure above (new OW subclass number, new WH slug, extend the "Requires X" regex and the WH profession-id map).
2. Append lines to `data/ow.txt` / `data/wh.txt` using the new profession key (e.g. `alchemy`).
3. `build.py`: add the key to the `ROWS` dict; extend `clean_name` (currently strips only `Pattern:`/`Formula:`; add `Plans:`, `Schematic:`, `Recipe:`, `Manual:`, `Technique:` as needed).
4. `template.html`: add `['alchemy','Alchemy']` to `PROFS`.
5. Run `python build.py`, then check every new vendor zone exists in `ZONES` in `template.html`, otherwise the route planner skips that vendor (add zone box `[landmass,cx,cy,w,h]` or an alias in build.py).
6. Open `index.html`: test filters, checkboxes and Create route.

## Honest limitations
- The travel model (zone positions, flight points, boat/zeppelin times) is hand-made, not game data. Routes are estimates.
- No reputation requirements in either source.
- Visual layout of the page was never checked by screenshot (pane was hidden); logic was verified through the DOM only.
