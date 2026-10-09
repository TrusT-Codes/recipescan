-- recipescan database (built by pipeline/run.py build; do not edit by hand)
-- origin columns name the data source a value came from: pfquest | ow | wh | atlas | atlasloot

PRAGMA foreign_keys = ON;

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE sources (
    id      TEXT PRIMARY KEY,           -- pfquest, pfquest-octo, atlas-cfm, atlasloot, wh, ow
    name    TEXT NOT NULL,
    version TEXT,
    commit_hash TEXT,
    date    TEXT,
    url     TEXT
);

CREATE TABLE professions (
    id   TEXT PRIMARY KEY,              -- tailoring, firstaid, ...
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('primary', 'secondary'))
);

CREATE TABLE zones (
    id   INTEGER PRIMARY KEY,           -- AreaTable id (same ids as pfQuest / Wowhead)
    name TEXT NOT NULL,
    parent_id    INTEGER,               -- parent zone for sub-areas
    continent_id INTEGER,               -- WorldMapArea map id: 0 Eastern Kingdoms, 1 Kalimdor, ...
    x_min REAL, y_min REAL,             -- WorldMapArea world bounds of the zone map (for map pins)
    x_max REAL, y_max REAL
);

CREATE TABLE items (
    id         INTEGER PRIMARY KEY,
    name       TEXT,
    quality    INTEGER,                 -- 0 poor .. 5 legendary
    item_level INTEGER,
    class      INTEGER,                 -- 2 weapon, 4 armor (only known for crafted items)
    quality_origin TEXT
);

CREATE TABLE recipes (
    id            TEXT PRIMARY KEY,     -- 's<craft spell id>', or 'i<recipe item id>' when the spell is unknown
    profession_id TEXT NOT NULL REFERENCES professions(id),
    spell_id      INTEGER UNIQUE,       -- craft spell; what the Craft API (Enchanting) reports
    name          TEXT NOT NULL,
    skill_req     INTEGER,              -- skill needed to learn
    skill_req_origin TEXT,
    skill_orange  INTEGER,              -- Atlas-CFM difficulty colours
    skill_yellow  INTEGER,
    skill_green   INTEGER,
    skill_grey    INTEGER,
    crafted_item_id  INTEGER REFERENCES items(id),   -- what the TradeSkill API reports
    crafted_qty_min  INTEGER,
    crafted_qty_max  INTEGER,
    station       TEXT,                 -- Anvil, Forge, Moonwell, ...
    rep_faction   TEXT,
    rep_level     TEXT,
    atlas_servers TEXT,                 -- Atlas-CFM server tags, comma separated
    atlas_visible INTEGER,              -- 1/0 visible for the configured server, NULL = not in Atlas-CFM
    listed        INTEGER NOT NULL,     -- 1 = shown on the site
    unlisted_reason TEXT,
    origins       TEXT NOT NULL         -- every source that contributed, comma separated
);
CREATE INDEX recipes_crafted ON recipes(profession_id, crafted_item_id);

CREATE TABLE recipe_items (               -- items that teach a recipe (Pattern:, Plans:, ...)
    item_id   INTEGER PRIMARY KEY REFERENCES items(id),
    recipe_id TEXT NOT NULL REFERENCES recipes(id)
);
CREATE INDEX recipe_items_recipe ON recipe_items(recipe_id);

CREATE TABLE reagents (
    recipe_id TEXT NOT NULL REFERENCES recipes(id),
    item_id   INTEGER NOT NULL REFERENCES items(id),
    count     INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, item_id)
);

CREATE TABLE tools (
    recipe_id TEXT NOT NULL REFERENCES recipes(id),
    item_id   INTEGER NOT NULL REFERENCES items(id),
    PRIMARY KEY (recipe_id, item_id)
);

CREATE TABLE npcs (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    faction TEXT,                        -- A, H, AH (friendly to), '' hostile to both, NULL unknown
    level   TEXT,
    rank    INTEGER,
    origin  TEXT NOT NULL
);

CREATE TABLE objects (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    faction TEXT
);

CREATE TABLE spawns (
    kind    TEXT NOT NULL CHECK (kind IN ('npc', 'object')),
    ref_id  INTEGER NOT NULL,
    zone_id INTEGER NOT NULL,
    x       REAL,                        -- zone map percent; NULL when only the zone is known
    y       REAL,
    origin  TEXT NOT NULL
);
CREATE INDEX spawns_ref ON spawns(kind, ref_id);

CREATE TABLE quests (
    id        INTEGER PRIMARY KEY,
    name      TEXT,
    level     INTEGER,
    min_level INTEGER,
    side      TEXT,                      -- A, H, AH
    zone_id   INTEGER,
    origin    TEXT NOT NULL
);

CREATE TABLE quest_starters (
    quest_id INTEGER NOT NULL REFERENCES quests(id),
    kind     TEXT NOT NULL CHECK (kind IN ('npc', 'object', 'item')),
    ref_id   INTEGER NOT NULL
);

CREATE TABLE recipe_sources (
    id        INTEGER PRIMARY KEY,
    recipe_id TEXT NOT NULL REFERENCES recipes(id),
    item_id   INTEGER,                   -- recipe item this source gives; NULL for trainer-taught spells
    type      TEXT NOT NULL CHECK (type IN ('vendor', 'trainer', 'quest', 'drop', 'object', 'world')),
    npc_id    INTEGER,
    object_id INTEGER,
    quest_id  INTEGER,
    chance    REAL,                      -- drop chance in percent
    stock     INTEGER,                   -- vendor limited stock (0 = unlimited)
    note      TEXT,                      -- world drop label, Atlas boss / instance name
    origin    TEXT NOT NULL
);
CREATE INDEX recipe_sources_recipe ON recipe_sources(recipe_id);

CREATE TABLE disenchant_rules (
    quality   INTEGER NOT NULL,
    kind      TEXT NOT NULL,             -- A armor, W weapon, * both
    ilvl_min  INTEGER NOT NULL,
    ilvl_max  INTEGER NOT NULL,
    material  TEXT NOT NULL,
    chance    REAL NOT NULL,
    quantity  TEXT NOT NULL
);

CREATE VIEW recipe_overview AS
SELECT r.id, r.profession_id, r.name, r.skill_req, r.listed,
       (SELECT group_concat(DISTINCT s.type) FROM recipe_sources s WHERE s.recipe_id = r.id) AS source_types,
       (SELECT group_concat(item_id) FROM recipe_items i WHERE i.recipe_id = r.id) AS recipe_items
FROM recipes r;
