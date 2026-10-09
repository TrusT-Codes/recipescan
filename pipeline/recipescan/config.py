"""Paths and constants shared by all pipeline stages."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data')
EXTRACTED = os.path.join(DATA, 'extracted')
BUILD = os.path.join(ROOT, 'build')
WEB_DATA = os.path.join(ROOT, 'web', 'public', 'data')
PROTOTYPE = os.path.join(ROOT, 'index.html')

# Reference addons (git-ignored, read by `extract` only)
ADDONS = {
    'pfquest': os.path.join(ROOT, 'pfQuest'),
    'pfquest-octo': os.path.join(ROOT, 'pfQuest-octo'),
    'atlas-cfm': os.path.join(ROOT, 'Atlas-CFM'),
    'atlasloot': os.path.join(ROOT, 'AtlasLoot'),
}

# Atlas-CFM server profile that matches OctoWow (Turtle WoW data + Octo corrections)
ATLAS_SERVER = 'Turtle WoW'
ATLAS_SERVERS = {
    'TURTLE': 'Turtle WoW',
    'TURTLE1': 'Turtle WoW 1.17.2',
    'VANILLA_PLUS': 'Vanilla Plus',
    'CLASSIC': 'Classic',
}

# id, display name, kind, Atlas-CFM crafting table name prefixes
PROFESSIONS = [
    ('alchemy', 'Alchemy', 'primary', ('Alchemy',)),
    ('blacksmithing', 'Blacksmithing', 'primary', ('Smithing', 'Armorsmith', 'Weaponsmith', 'Axesmith', 'Hammersmith', 'Swordsmith')),
    ('enchanting', 'Enchanting', 'primary', ('Enchanting',)),
    ('engineering', 'Engineering', 'primary', ('Engineering', 'Gnomish', 'Goblin')),
    ('jewelcrafting', 'Jewelcrafting', 'primary', ('Jewelcrafting',)),
    ('leatherworking', 'Leatherworking', 'primary', ('Leather', 'Dragonscale', 'Elemental', 'Tribal')),
    ('tailoring', 'Tailoring', 'primary', ('Tailoring',)),
    ('cooking', 'Cooking', 'secondary', ('Cooking',)),
    ('firstaid', 'First Aid', 'secondary', ('FirstAid',)),
]
PROFESSION_IDS = [p[0] for p in PROFESSIONS]
ATLAS_SKIP_TABLES = ('EnchantingDisenchant',)

RECIPE_PREFIX = r'^(Pattern|Plans|Recipe|Formula|Schematic|Manual|Design|Technique)\s*:\s*'

# Recipe item ids at or above this are Season of Discovery (Wowhead 1.15.x)
SOD_MIN_ITEM_ID = 200000

# A drop source with more creatures than this is shown as one "world drop" entry on the site
WORLD_DROP_MIN_UNITS = 12

# Spawn points kept per NPC / object (pfQuest lists up to a few hundred for common mobs)
MAX_SPAWNS = 40
