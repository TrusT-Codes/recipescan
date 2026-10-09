# Changelog

## Unreleased

### Added
- Jewelcrafting tab with the 7 vendor-sold recipes (OctoWow only; Wowhead Classic has no Jewelcrafting).
- Enchanting: Formula: Enchanted Gemstone Oil (skill 275, 8 vendors).
- `data/sod_excluded.txt`: list of excluded Season of Discovery recipes.

### Changed
- Required skill now prefers Wowhead's value over OctoWow's when both exist (fixes Dark Iron Bracers, Heavy Scorpid Bracers, Corehound Boots; fills Fiery Chain Girdle/Shoulders).
- Jewelcrafting required skill is unknown in the available data and is shown as "?".

### Removed
- 95 recipes added in Season of Discovery (Wowhead patch 1.15.x) across all professions. Highest listed skill is now 300.
