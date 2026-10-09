# Export addon: live client checks

Questions the RecipeScan export addon depends on. Each needs a `/run` result from the real client (modded 1.12.1: Turtle base + SuperWoW, nampower, ClassicAPI) before code is written, per the `vanilla-wow-addon` skill. API signatures from `wow-api-type-definitions/Client/Function/TradeSkill.d.lua` and `Crafting.d.lua` are 2006 wowpedia data and unverified.

Paste each line into chat exactly as written. Each is 250 characters or fewer, including `/run `. Report the printed output (a screenshot is fine) and record it in the **Result** line.

Notes:
- Atlas-CFM's search box and "have materials" filter on the profession window only filter **its own** display (`TSF.BuildList` in `Atlas-CFM/CFMLoot/Core/ProfessionHooks.lua`). They do not change what `GetNumTradeSkills` returns, so they don't affect the scan.
- `||` in printed links is intentional. It shows the raw link text, e.g. `|Hitem:4343:...`, instead of a clickable link.

---

## C1: TradeSkill scan returns crafted item IDs
Open **Tailoring** (or any profession except Enchanting), expand all headers, then:
```
/run local n,h,k,l=GetNumTradeSkills(),0,0 for i=1,n do local _,t=GetTradeSkillInfo(i) if t=="header" then h=h+1 else k=k+1 l=l or GetTradeSkillItemLink(i) end end print(GetTradeSkillLine(),n,h,k,l and string.gsub(l,"|","||"))
```
- **Expect:** `Tailoring <rows> <headers> <recipes> ||cff...||Hitem:<craftedItemId>:...`
- **Confirms:** `GetTradeSkillLine` returns the English name, headers report type `"header"`, and the item link contains the crafted item ID.
- **Result:** **Confirmed (2026-10-09):** `Tailoring 78 5 73 [Mageweave Bag]`. TradeSkill works, `GetTradeSkillLine` is English, headers are `"header"`. The printed link only showed `[Name]`, so the ID format is still open (see C9).

## C2: Collapsed headers hide recipes; `ExpandTradeSkillSubClass(0)` expands all
With the same window, **collapse one or two headers** first, then:
```
/run local function c() local k=0 for i=1,GetNumTradeSkills() do local _,t=GetTradeSkillInfo(i) if t~="header" then k=k+1 end end return k end local a=c() ExpandTradeSkillSubClass(0) print(a,c())
```
- **Expect:** first number smaller than the second, and the headers open again.
- **Confirms:** the scan has to expand first, and index 0 means "all".
- **Result:** **Confirmed:** `18 73` with 2 headers collapsed. Collapsed headers hide recipes, and `ExpandTradeSkillSubClass(0)` expands all.

## C3: Subclass / slot filters hide recipes and can be reset
In the window's dropdowns, pick **one subclass** (e.g. "Cloth") and/or **one slot**, then:
```
/run local function c() local k=0 for i=1,GetNumTradeSkills() do local _,t=GetTradeSkillInfo(i) if t~="header" then k=k+1 end end return k end local a=c() SetTradeSkillSubClassFilter(0,1,1) SetTradeSkillInvSlotFilter(0,1,1) print(a,c())
```
- **Expect:** first number smaller than the second, and the dropdowns show "All" again.
- **Confirms:** the filter reset calls and their `(0, 1, 1)` arguments work on this client.
- **Also tell me:** does the native window have a search box or a "have materials" checkbox **with Atlas-CFM disabled**? If it does, it's another filter to clear.
- **Result:** **Inconclusive:** `73 73`. Probably no filter was active, so this is retested programmatically in C11. Search box / have-materials question still open.

## C4: Craft API (Enchanting) returns the spell ID
Open **Enchanting**, then:
```
/run local n,l=GetNumCrafts() for i=1,n do local _,_,t=GetCraftInfo(i) if t~="header" and not l then l=GetCraftItemLink(i) end end print(GetCraftDisplaySkillLine(),n,l and string.gsub(l,"|","||"))
```
- **Expect:** `Enchanting <rows> ||cff...||Henchant:<spellId>||h[Enchant ...]...`
- **Confirms:** the Craft frame link carries the craft spell ID, which matches `recipes.spell` in `web/public/data/recipes.json`.
- **Result:** **Confirmed:** `Enchanting 42 [Enchant Bracer - Vampirism]`. Craft API works for Enchanting. Link format is still open (see C10).

## C5: Which window Jewelcrafting uses
Open **Jewelcrafting** and run **C1**. If C1 prints `nil 0 ...`, run **C4** instead.
- **Confirms:** whether the Turtle profession uses TradeSkill (crafted item IDs) or Craft (spell IDs). Repeat for Survival if you have it; it's not in the site yet.
- **Result:** **Confirmed:** `Jewelcrafting 18 5 13 [Copper Staff]`. Jewelcrafting uses the **TradeSkill** API (crafted item IDs).

## C6: Events fire when the windows open and update
```
/run RSD=RSD or CreateFrame("Frame") for _,e in ipairs({"TRADE_SKILL_SHOW","TRADE_SKILL_UPDATE","CRAFT_SHOW","CRAFT_UPDATE","CHAT_MSG_SKILL"}) do RSD:RegisterEvent(e) end RSD:SetScript("OnEvent",function() print(event,arg1) end)
```
Then open and close Tailoring and Enchanting, and craft one item if you can.
- **Expect:** `TRADE_SKILL_SHOW`, then one or more `TRADE_SKILL_UPDATE`; `CRAFT_SHOW` / `CRAFT_UPDATE` for Enchanting.
- **Confirms:** which events the addon should scan on.
- **Stop it with:** `/run RSD:UnregisterAllEvents()`
- **Result:** **Confirmed:** `TRADE_SKILL_UPDATE` fires *before* `TRADE_SKILL_SHOW`, and `CRAFT_UPDATE` before `CRAFT_SHOW`. Each craft fires `TRADE_SKILL_UPDATE` 1–2 times. `arg1` is stale (`LeftButton`/`nil`), so these events have no args. `CHAT_MSG_SKILL` didn't fire (no skill-up). Plan: scan on `*_SHOW`, then rescan on `*_UPDATE` with a debounce (`C_Timer.After`).

## C7: Skill ranks for the "learnable now" filter
```
/run for i=1,GetNumSkillLines() do local n,h,_,r,_,_,m=GetSkillLineInfo(i) if not h then print(i,n,r,m) end end
```
- **Expect:** one line per skill, e.g. `12 Tailoring 245 300`.
- **Confirms:** the return order of `GetSkillLineInfo` (name, isHeader, isExpanded, rank, numTempPoints, modifier, maxRank).
- **Result:** **Confirmed:** returns `name, isHeader, isExpanded, rank, temp, modifier, maxRank` (e.g. `7 Tailoring 251 300`). Turtle's Survival shows up as a skill line. Jewelcrafting was **not** in this list; was C5 run on another character? (see C12)

## C8: SuperWoW file export
```
/run print(type(ExportFile),type(ImportFile),SUPERWOW_VERSION)
```
- If the first value is `function`, also run `/run ExportFile("recipescan_test","hello")`, then search the WoW folder for `recipescan_test` and tell me the path.
- **Confirms:** whether the addon can write the export file directly, instead of the user copying text or uploading SavedVariables.
- **Result:** **Confirmed:** `function function 1.5`. SuperWoW 1.5 `ExportFile("recipescan_test", ...)` wrote `F:\Octo_WoW\Imports\recipescan_test.txt`. The addon can write the export file itself when SuperWoW is present; it still needs a fallback for players without SuperWoW. Overwrite/append, newlines and size are open (C13, C14).

---

# Follow-up checks (round 2)

## C9: TradeSkill link type and ID
Open Tailoring:
```
/run for i=1,GetNumTradeSkills() do local l=GetTradeSkillItemLink(i) if l then local _,_,t,id=string.find(l,"H(%a+):(%d+)") print(i,t,id,GetTradeSkillInfo(i)) return end end
```
- **Expect:** `<row> item <craftedItemId> <name> <type> ...` (e.g. `item 4245` for Small Silk Pack).
- **Result:** **Confirmed:** `2 item 10050 Mageweave Bag medium 0 nil`. The TradeSkill link is `item:<craftedItemId>`. `GetTradeSkillInfo` returns `name, type ("header"/"optimal"/"medium"/"easy"/"trivial"), numAvailable, isExpanded` (nil on recipe rows).

## C10: Craft link type and ID
Open Enchanting:
```
/run for i=1,GetNumCrafts() do local l=GetCraftItemLink(i) if l then local _,_,t,id=string.find(l,"H(%a+):(%d+)") print(i,t,id,GetCraftInfo(i)) return end end
```
- **Expect:** `<row> enchant <spellId> <name> ...`, e.g. `enchant 57146` for Enchant Bracer - Vampirism (recipe `s57146` in recipes.json).
- **Result:** **Confirmed:** `1 enchant 57146 Enchant Bracer - Vampirism  optimal 0 nil 0 0`. The Craft link is `enchant:<craftSpellId>`, which is the same id as recipe `s57146`. `GetCraftInfo` returns `name, subName, type, numAvailable, isExpanded, trainingPointCost, requiredLevel`.

## C11: Subclass filter set and reset in code
Open Tailoring with the dropdowns on "All":
```
/run local G,S=GetTradeSkillInfo,SetTradeSkillSubClassFilter local function c()local k=0 for i=1,GetNumTradeSkills() do local _,t=G(i) if t~="header" then k=k+1 end end return k end S(1,1,1)local a=c()S(0,1,1)print(a,c(),GetTradeSkillSubClasses())
```
- **Expect:** a smaller first number (only subclass 1), then `73`, then the subclass names.
- **Confirms:** filters hide recipes and `(0,1,1)` resets them.
- **Also tell me:** does the native window have a search box or a "have materials" checkbox with Atlas-CFM disabled?
- **Result:** **Confirmed:** `S(1,1,1)` limits the list to subclass 1 (Bag): 8 recipes. `S(0,1,1)` resets it: 73 with all headers expanded. Filters and collapsed headers are **independent**: with all headers collapsed both counts were `0 0`, and with only Bags expanded `8 8`. The scan must reset the filters **and** expand all headers. Subclasses: `Bag, Enchanting Bag, Cloth, Miscellaneous, Trade Goods`. Not answered: whether the native window has a search box or a have-materials checkbox without Atlas-CFM.

## C12: Jewelcrafting skill line
On the character with Jewelcrafting, run C7 again.
- **Confirms:** whether Jewelcrafting appears in `GetSkillLineInfo`, which the "learnable now" filter needs.
- **Result:** **No result given.** Still open whether Jewelcrafting appears in `GetSkillLineInfo`. Fallback to check: `GetTradeSkillLine()` may return `name, rank, maxRank` while the window is open (C15).

## C13: ExportFile overwrite or append, ImportFile return
```
/run ExportFile("recipescan_test","a\nb") ExportFile("recipescan_test","c") local s=ImportFile("recipescan_test") print(type(s),s and string.len(s),s)
```
- **Expect:** `string 1 c` means overwrite. `string 4 a b c`-ish means append.
- **Result:** **Confirmed:** `string 1 c`. `ExportFile` **overwrites**, and `ImportFile(name)` returns the file content as a string.

## C14: Newlines and size
```
/run ExportFile("recipescan_test","a\nb") local s=ImportFile("recipescan_test") print(string.len(s or ""),s)
```
- **Expect:** `3` and two lines, a and b. Also open `Imports\recipescan_test.txt` and say whether it shows two lines.
```
/run ExportFile("recipescan_test",string.rep("x",60000)) print(string.len(ImportFile("recipescan_test") or ""))
```
- **Expect:** `60000`. A full multi-character export is about 5–20 KB.
- **Result:** **Confirmed:** `3` and two lines a and b, and the `.txt` file also shows two lines, so `\n` is written as a line break. 60,000 characters round-trip intact.

## C15: Profession rank from the open window (for the next session)
Open Jewelcrafting:
```
/run print(GetTradeSkillLine())
```
Open Enchanting:
```
/run print(GetCraftDisplaySkillLine())
```
- **Expect:** `Jewelcrafting <rank> <maxRank>` and `Enchanting <rank> <maxRank>`. If only the name prints, rank has to come from `GetSkillLineInfo` (and C12 must be answered).
- **Result:** _pending_

---

When results are in, add the confirmed facts to `~/.claude/skills/vanilla-wow-addon/references/client-facts.md` (section 4) as the skill asks, and update `docs/handoff-phase2-3.md`.
