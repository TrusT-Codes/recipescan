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
- **Result:** _pending_

## C2: Collapsed headers hide recipes; `ExpandTradeSkillSubClass(0)` expands all
With the same window, **collapse one or two headers** first, then:
```
/run local function c() local k=0 for i=1,GetNumTradeSkills() do local _,t=GetTradeSkillInfo(i) if t~="header" then k=k+1 end end return k end local a=c() ExpandTradeSkillSubClass(0) print(a,c())
```
- **Expect:** first number smaller than the second, and the headers open again.
- **Confirms:** the scan has to expand first, and index 0 means "all".
- **Result:** _pending_

## C3: Subclass / slot filters hide recipes and can be reset
In the window's dropdowns, pick **one subclass** (e.g. "Cloth") and/or **one slot**, then:
```
/run local function c() local k=0 for i=1,GetNumTradeSkills() do local _,t=GetTradeSkillInfo(i) if t~="header" then k=k+1 end end return k end local a=c() SetTradeSkillSubClassFilter(0,1,1) SetTradeSkillInvSlotFilter(0,1,1) print(a,c())
```
- **Expect:** first number smaller than the second, and the dropdowns show "All" again.
- **Confirms:** the filter reset calls and their `(0, 1, 1)` arguments work on this client.
- **Also tell me:** does the native window have a search box or a "have materials" checkbox **with Atlas-CFM disabled**? If it does, it's another filter to clear.
- **Result:** _pending_

## C4: Craft API (Enchanting) returns the spell ID
Open **Enchanting**, then:
```
/run local n,l=GetNumCrafts() for i=1,n do local _,_,t=GetCraftInfo(i) if t~="header" and not l then l=GetCraftItemLink(i) end end print(GetCraftDisplaySkillLine(),n,l and string.gsub(l,"|","||"))
```
- **Expect:** `Enchanting <rows> ||cff...||Henchant:<spellId>||h[Enchant ...]...`
- **Confirms:** the Craft frame link carries the craft spell ID, which matches `recipes.spell` in `web/public/data/recipes.json`.
- **Result:** _pending_

## C5: Which window Jewelcrafting uses
Open **Jewelcrafting** and run **C1**. If C1 prints `nil 0 ...`, run **C4** instead.
- **Confirms:** whether the Turtle profession uses TradeSkill (crafted item IDs) or Craft (spell IDs). Repeat for Survival if you have it; it's not in the site yet.
- **Result:** _pending_

## C6: Events fire when the windows open and update
```
/run RSD=RSD or CreateFrame("Frame") for _,e in ipairs({"TRADE_SKILL_SHOW","TRADE_SKILL_UPDATE","CRAFT_SHOW","CRAFT_UPDATE","CHAT_MSG_SKILL"}) do RSD:RegisterEvent(e) end RSD:SetScript("OnEvent",function() print(event,arg1) end)
```
Then open and close Tailoring and Enchanting, and craft one item if you can.
- **Expect:** `TRADE_SKILL_SHOW`, then one or more `TRADE_SKILL_UPDATE`; `CRAFT_SHOW` / `CRAFT_UPDATE` for Enchanting.
- **Confirms:** which events the addon should scan on.
- **Stop it with:** `/run RSD:UnregisterAllEvents()`
- **Result:** _pending_

## C7: Skill ranks for the "learnable now" filter
```
/run for i=1,GetNumSkillLines() do local n,h,_,r,_,_,m=GetSkillLineInfo(i) if not h then print(i,n,r,m) end end
```
- **Expect:** one line per skill, e.g. `12 Tailoring 245 300`.
- **Confirms:** the return order of `GetSkillLineInfo` (name, isHeader, isExpanded, rank, numTempPoints, modifier, maxRank).
- **Result:** _pending_

## C8: SuperWoW file export
```
/run print(type(ExportFile),type(ImportFile),SUPERWOW_VERSION)
```
- If the first value is `function`, also run `/run ExportFile("recipescan_test","hello")`, then search the WoW folder for `recipescan_test` and tell me the path.
- **Confirms:** whether the addon can write the export file directly, instead of the user copying text or uploading SavedVariables.
- **Result:** _pending_

---

When results are in, add the confirmed facts to `~/.claude/skills/vanilla-wow-addon/references/client-facts.md` (section 4) as the skill asks, and update `docs/handoff-phase2-3.md`.
