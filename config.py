"""
config.py — Central configuration for the World Simulation.

Every tunable constant in the simulation lives here. Nothing in the rest of
the codebase should hard-code a magic number that's defined in this file.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# WORLD
# ---------------------------------------------------------------------------
WORLD_WIDTH = 200
WORLD_HEIGHT = 200
TOTAL_REGIONS = WORLD_WIDTH * WORLD_HEIGHT  # 40,000

BIOMES = [
    "Plains", "Forest", "Mountain", "Desert", "Swamp",
    "Arctic", "Coastal", "Underground", "Volcanic", "Ethereal Wastes",
]

RESOURCES = [
    "Food", "Iron", "Timber", "Stone", "Mana Crystals", "Void Essence",
    "Living Wood", "Sunstone", "Deepstone", "Ember Core",
]

# Which biomes can roll which resources
RESOURCE_BIOME_MAP = {
    "Food": ["Plains", "Forest", "Coastal"],
    "Iron": ["Mountain", "Underground"],
    "Timber": ["Forest"],
    "Stone": ["Mountain", "Volcanic"],
    "Mana Crystals": ["Ethereal Wastes", "Mountain"],
    "Void Essence": ["Underground", "Swamp"],
    "Living Wood": ["Forest"],  # only the "Ancient Forest" sub-tag
    "Sunstone": ["Desert", "Plains"],
    "Deepstone": ["Volcanic", "Underground"],
    "Ember Core": ["Volcanic"],
}

RARE_NODE_COUNT = 65  # hidden rare resource nodes scattered across the world

# ---------------------------------------------------------------------------
# TIME SCALE (sacred — do not approximate)
# ---------------------------------------------------------------------------
TICK_INTERVAL_SECONDS = 1
SIM_MINUTES_PER_TICK = 609          # 10 hours, 9 minutes per real second
SIM_MINUTES_PER_HOUR = 60
SIM_HOURS_PER_DAY = 24
SIM_MINUTES_PER_DAY = SIM_MINUTES_PER_HOUR * SIM_HOURS_PER_DAY  # 1440
SIM_DAYS_PER_YEAR = 365
SIM_MINUTES_PER_YEAR = SIM_MINUTES_PER_DAY * SIM_DAYS_PER_YEAR  # 525,600

# ---------------------------------------------------------------------------
# POPULATION & SURVIVAL
# ---------------------------------------------------------------------------
STARTING_POPULATION_PER_CLAN = 50_000
MIN_POPULATION_FOR_ELIMINATION = 500
FIRST_ELIMINATION_YEAR_MINIMUM = 300

# Era-based population floors: (start_year, end_year, floor)
POPULATION_FLOOR_ERA_1 = (1, 50, 20_000)
POPULATION_FLOOR_ERA_2 = (51, 150, 10_000)
POPULATION_FLOOR_ERA_3 = (151, 299, 2_000)
POPULATION_FLOORS = [POPULATION_FLOOR_ERA_1, POPULATION_FLOOR_ERA_2, POPULATION_FLOOR_ERA_3]

# Last Bastion Protocol
LAST_BASTION_TERRITORY_LOSS_TRIGGER = 0.70   # 70%+ territory lost triggers retreat
LAST_BASTION_DEFENSE_MULTIPLIER = 6.0
LAST_BASTION_DISCOVERY_CHANCE_PER_YEAR = 0.30

# Cornered Beast
CORNERED_BEAST_POP_THRESHOLD = 0.20  # below 20% of peak population
CORNERED_BEAST_COMBAT_BONUS = 0.50
CORNERED_BEAST_RECRUIT_BONUS = 0.30

# Rebuilding Momentum (after losing >20% of army in one battle)
REBUILD_ARMY_LOSS_TRIGGER = 0.20
REBUILD_RESOURCE_BONUS = 0.35
REBUILD_RECRUIT_BONUS = 0.15
REBUILD_DURATION_YEARS = 10

# ---------------------------------------------------------------------------
# DIPLOMATIC / WAR TIMELINE
# ---------------------------------------------------------------------------
DIPLOMATIC_MORATORIUM_END_YEAR = 50   # no formal wars before this year
TOTAL_WAR_UNLOCK_YEAR = 100           # AI stops avoiding "elimination" as a goal after this

# ---------------------------------------------------------------------------
# EVENT PROBABILITIES (rolled per clan, per tick)
# ---------------------------------------------------------------------------
EVENT_CHANCE_MINOR = 0.15
EVENT_CHANCE_MAJOR = 0.03
EVENT_CHANCE_CATASTROPHIC = 0.005
EVENT_CHANCE_CROSS_CLAN = 0.05

# ---------------------------------------------------------------------------
# DISCORD
# ---------------------------------------------------------------------------
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

EMBED_COLOR_WAR = 0xFF0000
EMBED_COLOR_DISCOVERY = 0xFFD700
EMBED_COLOR_POLITICAL = 0x9B59B6
EMBED_COLOR_PEACE = 0x2ECC71
EMBED_COLOR_ELIMINATION = 0x000000
EMBED_COLOR_FIRST_CONTACT = 0x3498DB

# ---------------------------------------------------------------------------
# WORLD GENERATION SEED
# ---------------------------------------------------------------------------
WORLD_SEED = None  # set an int for reproducible worlds, or leave None for random

# ---------------------------------------------------------------------------
# VICTORY CONDITIONS
# ---------------------------------------------------------------------------
DOMINATION_THRESHOLD = 0.85
DOMINATION_HOLD_YEARS = 10

# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("SIM_DB_PATH", os.path.join(os.path.dirname(__file__), "database", "simulation.db"))

# ---------------------------------------------------------------------------
# WEB / FLASK
# ---------------------------------------------------------------------------
FLASK_HOST = "0.0.0.0"
FLASK_PORT = int(os.environ.get("PORT", 3000))
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "world-simulation-dev-key-change-me")

# Map render dimensions (compressed for browser performance)
MAP_RENDER_WIDTH = 100
MAP_RENDER_HEIGHT = 50
ASCII_MAP_WIDTH = 50
ASCII_MAP_HEIGHT = 25

# Clan accent colors (hex strings, used in UI)
CLAN_COLORS = {
    "Aura Knights": "#F4C430",
    "Arcane Conclave": "#8B5CF6",
    "Iron Covenant": "#64748B",
    "Sylvan Circle": "#22C55E",
    "Void Reapers": "#DC2626",
    "Stone Covenant": "#78716C",
}
