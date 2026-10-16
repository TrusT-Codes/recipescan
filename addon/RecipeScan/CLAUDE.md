# CLAUDE.md

Guidance for Claude Code in this addon folder.

## What this is

`RecipeScan`: scans learned profession recipes and exports them for the RecipeScan website. Addon for a **modified World of Warcraft Vanilla 1.12.1 client** (OctoWow, Turtle WoW-derived) extended by **SuperWoW**, **nampower**, **ClassicAPI**, **UnitXP_SP3**. Lua **5.0**. No build step, no automated tests: the client loads `RecipeScan.toc` from `Interface/AddOns/RecipeScan/`.

**Always load the `vanilla-wow-addon` skill before writing or reviewing code here.** It holds the Lua 5.0 rules, live-confirmed client/mod API facts, known pitfalls and proven patterns. This file only adds what is specific to this addon.

## Comment style: WHAT, not WHY

Comments say what code does, one short line max. Exception: a short warning when an ordering must stay as written.

## Commands

- Syntax-check every touched file: `luac50 -p <File>.lua` (Lua 5.0.3, `C:\Tools\lua50\`) + `lua50 ~/.claude/skills/vanilla-wow-addon/scripts/lint50.lua <File>.lua`. The global `PostToolUse` hook (`~/.claude/skills/vanilla-wow-addon/scripts/hook-lua50.sh`) runs both automatically after edits.
- Stub-load harness: `bash ~/.claude/skills/vanilla-wow-addon/scripts/verify.sh "$PWD" <outDir outside repo> RecipeScan`.
- Runtime testing: live, in the user's client. Uncertain behavior → `/run` check (≤ 250 chars incl. `/run `), recorded in `../../docs/addon-live-checks.md`.

## Architecture

- Global table `RecipeScan` (local alias `RS`; `/run` needs the full name).
- SavedVariables: `RecipeScanDB` (account-wide): `chars["Realm-Name"] = {realm, name, faction, class, race, scannedAt, professions = {[name] = {rank, max, kind = "item"|"spell", ids}}}`, `autoExport`.
- Login flag: `RS.loginDone`; event handlers and slash commands return until it is set.
- Files, in `.toc` load order:
  1. `Core.lua`: global table, print, DB defaults, current character entry.
  2. `Scan.lua`: TradeSkill scan (reset filters, expand all, read links, restore) and Craft (Enchanting) scan.
  3. `Export.lua`: `RS1` text format, SuperWoW `ExportFile`, copy-box fallback.
  4. `Events.lua`: event frame, debounce (`C_Timer.NewTimer`), reentrancy guard, slash commands; loads last.
- Rescan: on `*_SHOW`, then 0.5 s after the last `*_UPDATE`. `RS.scanning` plus a 0.3 s quiet window ignore the updates the scan's own expand/filter calls fire.
- Export format and site contract: `../../docs/handoff-phase2-3.md`.

## Git

- Base branch: `main`. Stage files by exact path.
