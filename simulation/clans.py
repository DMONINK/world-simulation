"""
simulation/clans.py — Static clan definitions.

This module holds everything about each clan that doesn't change at
runtime: lore, traits, weaknesses, evolution path, naming style, and the
personality-weighted decision matrix the AI uses. Dynamic state (current
population, territory, evolution index, relations) lives in the database
and is wrapped/queried elsewhere — this file is pure reference data.
"""

CLAN_NAMES = [
    "Aura Knights",
    "Arcane Conclave",
    "Iron Covenant",
    "Sylvan Circle",
    "Void Reapers",
    "Stone Covenant",
]

# The loose circular weakness chain (Stone Covenant disrupts it as a wildcard).
WEAKNESS_CYCLE = {
    "Aura Knights": "Void Reapers",
    "Void Reapers": "Arcane Conclave",
    "Arcane Conclave": "Iron Covenant",
    "Iron Covenant": "Sylvan Circle",
    "Sylvan Circle": "Aura Knights",
}

DECISIONS = [
    "EXPAND", "FORTIFY", "RESEARCH", "RECRUIT", "RAID", "DECLARE_WAR",
    "SEEK_ALLIANCE", "BETRAY_ALLIANCE", "SPECIAL",
]

SPECIAL_ACTION = {
    "Aura Knights": "CHALLENGE_TO_TRIAL",
    "Arcane Conclave": "MASS_SPELL",
    "Iron Covenant": "BUILD_MACHINE",
    "Sylvan Circle": "TERRAIN_CLAIM",
    "Void Reapers": "ASSASSINATE",
    "Stone Covenant": "GEOLOGICAL_EVENT",
}

# Decision weight matrix. Higher = more likely to be picked by the AI each
# tick a clan acts. These are relative weights, not probabilities — ai.py
# normalizes them and applies situational modifiers on top.
DECISION_WEIGHTS = {
    "Aura Knights": {
        "EXPAND": 8, "FORTIFY": 5, "RESEARCH": 3, "RECRUIT": 6, "RAID": 4,
        "DECLARE_WAR": 4, "SEEK_ALLIANCE": 5, "BETRAY_ALLIANCE": 1, "SPECIAL": 7,
    },
    "Arcane Conclave": {
        "EXPAND": 2, "FORTIFY": 3, "RESEARCH": 10, "RECRUIT": 3, "RAID": 3,
        "DECLARE_WAR": 2, "SEEK_ALLIANCE": 2, "BETRAY_ALLIANCE": 2, "SPECIAL": 9,
    },
    "Iron Covenant": {
        "EXPAND": 7, "FORTIFY": 9, "RESEARCH": 7, "RECRUIT": 6, "RAID": 4,
        "DECLARE_WAR": 4, "SEEK_ALLIANCE": 4, "BETRAY_ALLIANCE": 1, "SPECIAL": 7,
    },
    "Sylvan Circle": {
        "EXPAND": 4, "FORTIFY": 7, "RESEARCH": 2, "RECRUIT": 4, "RAID": 2,
        "DECLARE_WAR": 1, "SEEK_ALLIANCE": 7, "BETRAY_ALLIANCE": 1, "SPECIAL": 7,
    },
    "Void Reapers": {
        "EXPAND": 4, "FORTIFY": 3, "RESEARCH": 4, "RECRUIT": 3, "RAID": 8,
        "DECLARE_WAR": 2, "SEEK_ALLIANCE": 1, "BETRAY_ALLIANCE": 6, "SPECIAL": 10,
    },
    "Stone Covenant": {
        "EXPAND": 1, "FORTIFY": 10, "RESEARCH": 4, "RECRUIT": 4, "RAID": 2,
        "DECLARE_WAR": 1, "SEEK_ALLIANCE": 7, "BETRAY_ALLIANCE": 0, "SPECIAL": 9,
    },
}

CLAN_LORE = {
    "Aura Knights": {
        "full_name": "Order of the Radiant Vow",
        "lore": (
            "Born from wandering warriors who discovered that absolute willpower, "
            "forged through suffering, could manifest as a tangible golden force — "
            "Aura. They built a strict honor society where worth is proven through "
            "deeds, not lineage. Their cities burn like beacons at night. They do not "
            "fear death. They fear dying without purpose."
        ),
        "home_label": "Central Golden Plains",
        "primary_terrain": ["Plains", "Mountain"],
        "primary_resource": "Sunstone",
        "color": "#F4C430",
        "icon": "🔱",
        "traits": [
            {"name": "RADIANT DISCIPLINE", "desc": "+40% combat power in open-field battle."},
            {"name": "AURA CHANNELING", "desc": "Elite warriors amplify physical capability with golden energy; unlocked at Radiant Champions."},
            {"name": "HONOR BOUND", "desc": "Will never use poison, assassination, deception, or cowardly tactics. An assassination attempt against their leader triggers immediate blood war and a morale bonus."},
            {"name": "GRIEF OF LEGENDS", "desc": "When a named leader dies in battle: -25% combat power for 2 sim years."},
            {"name": "IRON MORALE", "desc": "Cannot be demoralized by psychological warfare or propaganda."},
        ],
        "weaknesses": [
            "Honor code makes them predictable and vulnerable to ambush.",
            "Pure magic attacks bypass aura shielding (vulnerable to Arcane Conclave).",
            "Nature magic slowly drains aura energy over long campaigns (vulnerable to Sylvan Circle).",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Wandering Warriors", "desc": "Basic fighters, small settlements."},
            {"year": 20, "stage": "Oath-Sworn Soldiers", "desc": "Organized military, first cities."},
            {"year": 60, "stage": "Radiant Champions", "desc": "Aura channeling discovered, elite units formed."},
            {"year": 120, "stage": "Vanguard of Light", "desc": "Full aura weaponry, mounted cavalry, fortress cities."},
            {"year": 200, "stage": "Ascendant Order", "desc": "Legendary warriors; aura becomes a cultural religion."},
        ],
        "naming": {
            "given": ["Aldric", "Maren", "Cassian", "Vael", "Tobian", "Selwyn", "Garrick", "Liora",
                       "Decimus", "Brennan", "Theron", "Isolde", "Roland", "Avice", "Marcus", "Edda"],
            "epithets": ["Sunveil", "of the Burning Oath", "Irondawn", "Brightspear", "Dawnshield",
                          "of the Golden Vow", "Sunsworn", "Lightbringer", "of the Radiant March", "Goldcrest"],
            "titles": ["High Commander", "Oathkeeper", "Champion", "Vow-Captain", "Dawnward"],
        },
        "strategic_personality": (
            "Honorable aggressor — expands through conquest but never pursues genocide. "
            "Prefers to subjugate rather than eliminate, and is the clan most likely to "
            "offer peace terms even while winning."
        ),
    },
    "Arcane Conclave": {
        "full_name": "The Unbound Circle",
        "lore": (
            "Ancient scholars who discovered that reality itself is mutable — that "
            "matter, time, and probability are just poorly understood rules waiting "
            "to be rewritten. They abandoned physical comfort, warmth, and community "
            "to pursue magical perfection. Their spire-cities glow faintly at all "
            "hours. Each mage lives for centuries. Each birth is an event. They are "
            "few. They are terrifying."
        ),
        "home_label": "Eastern Spire Peaks",
        "primary_terrain": ["Ethereal Wastes", "Mountain"],
        "primary_resource": "Mana Crystals",
        "color": "#8B5CF6",
        "icon": "🔮",
        "traits": [
            {"name": "ARCANE DEVASTATION", "desc": "Single mages can obliterate entire battalions, but require preparation time and mana."},
            {"name": "CENTURIES OF STUDY", "desc": "Research and technology discoveries happen 2x faster."},
            {"name": "SLOW BLOOD", "desc": "Population grows at 40% the normal rate. Births are rare and celebrated."},
            {"name": "GLASS CANNON", "desc": "-50% physical defense, +100% magical offense."},
            {"name": "SPELL MEMORY", "desc": "After losing to any tactic twice, develops a hard counter to it."},
        ],
        "weaknesses": [
            "Population is always small — every loss matters enormously.",
            "Mages must be safe to cast — Void Reapers who reach them before they cast are devastating.",
            "Research focus sometimes means neglected military logistics.",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Wandering Scholars", "desc": "Small groups, theory only."},
            {"year": 15, "stage": "Circle Initiates", "desc": "First spell formulations, basic magical defense."},
            {"year": 50, "stage": "Mage Adepts", "desc": "Offensive spells weaponized, first spire-cities."},
            {"year": 100, "stage": "Archmages", "desc": "Long-range devastation, magical shields, arcane constructs."},
            {"year": 180, "stage": "Reality Weavers", "desc": "Bending probability, time distortion, dimensional pockets."},
        ],
        "naming": {
            "given": ["Thessivax", "Orynthia", "Eruvax", "Sael", "Nyxandra", "Quovain", "Isthrael",
                       "Pheronyx", "Zalvethra", "Korrivax", "Ulthryn", "Xyriel", "Vorathiel", "Aexandrine"],
            "epithets": ["the Unbound", "Pale-Eye", "Null-Prophet", "of the Shifting Word", "the Reality-Touched",
                          "Star-Counted", "the Unwritten", "of the Spire", "Mind-Bound", "the Theorized"],
            "titles": ["Grand Theorist", "Archmage", "Circle-Speaker", "Null-Prophet", "Keeper of the Unbound"],
        },
        "strategic_personality": (
            "Calculating isolationist — prefers to let others fight while it researches. "
            "Enters wars only when the outcome is calculated as favorable, and strikes "
            "suddenly and overwhelmingly. Forms alliances through knowledge-sharing, not "
            "military pacts."
        ),
    },
    "Iron Covenant": {
        "full_name": "The Unyielding Forge",
        "lore": (
            "When the world was young and magic was alien to them, a group of "
            "survivors had nothing but their hands, their ingenuity, and an "
            "unshakeable refusal to accept the word impossible. They built what "
            "others conjured. They fought wars with machines when others used "
            "spells. Their underground forge-cities burn constantly, day and night. "
            "Rest is for the dead. Progress is the only god they know."
        ),
        "home_label": "Northern Iron Highlands",
        "primary_terrain": ["Mountain", "Underground"],
        "primary_resource": "Iron",
        "color": "#64748B",
        "icon": "⚙️",
        "traits": [
            {"name": "INDUSTRIAL MIGHT", "desc": "Mass-produces weapons, armor, and siege engines no other clan can match in volume."},
            {"name": "FORTRESS BUILDERS", "desc": "Settlements are 3x harder to siege; walls rebuild after damage over time."},
            {"name": "MAGICALLY INERT", "desc": "Cannot use or learn magic, but can build anti-magic constructs after Year 80."},
            {"name": "THE WORKFORCE", "desc": "+25% population growth rate; highest base population of any clan."},
            {"name": "WAR MACHINE DOCTRINE", "desc": "Late-game siege engines function as independent powerful units."},
        ],
        "weaknesses": [
            "Slow to mobilize — machines take time to deploy.",
            "Early military is weaker than most clans before machines are built.",
            "Stone Covenant's geological attacks destroy their infrastructure with frightening efficiency.",
            "Magic counters them severely until countermeasures are built.",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Survivor Craftsmen", "desc": "Basic tools, small mining operations."},
            {"year": 10, "stage": "Iron Militia", "desc": "Organized military, first fortifications."},
            {"year": 40, "stage": "Siege Engineers", "desc": "Catapults, ballistas, fortified walls."},
            {"year": 90, "stage": "Covenant War Machines", "desc": "Steam-powered mechanical units, anti-magic constructs."},
            {"year": 160, "stage": "Industrial Behemoth", "desc": "Walking siege platforms, underground rail networks, industrial cities."},
        ],
        "naming": {
            "given": ["Brund", "Dagra", "Helka", "Thrud", "Bjarn", "Grett", "Korin", "Sigrun",
                       "Halvard", "Ulrika", "Magnus", "Frida", "Othrun", "Brynhild"],
            "epithets": ["Ironhammer", "Smokefist", "Coalborn", "the Builder", "Gearhand", "Forgeborn",
                          "Anvilheart", "the Tireless", "Stoneknuckle", "Rivetborn"],
            "titles": ["Forge Master", "Warden of the Deep Works", "Master Engineer", "Iron-Speaker"],
        },
        "strategic_personality": (
            "Economic dominator — expands for resources, not glory. Prefers cold wars, "
            "trade embargoes, and proxy conflicts. Slow to start full war but near-"
            "impossible to stop once started. Never retreats unless absolutely forced; "
            "retreat is considered shameful."
        ),
    },
    "Sylvan Circle": {
        "full_name": "Children of the First Root",
        "lore": (
            "The oldest clan in the world — some say they predate the other five "
            "clans combined. They did not conquer the land. They became part of it. "
            "Their druids speak to trees that remember the world's birth. Their "
            "warriors ride creatures twice the size of warhorses. Their healers can "
            "regrow limbs in three days. They have no cities — their settlements are "
            "the forest. They do not fear death. They know something the others "
            "don't: the forest always grows back."
        ),
        "home_label": "Western Ancient Forest",
        "primary_terrain": ["Forest", "Swamp", "Coastal"],
        "primary_resource": "Living Wood",
        "color": "#22C55E",
        "icon": "🌿",
        "traits": [
            {"name": "REGENERATION", "desc": "All units heal 40% faster; destroyed settlements begin regrowing within 5 sim years."},
            {"name": "BEAST BONDING", "desc": "Can field tamed creatures (Giant Boars, Ancient Treants, Swamp Serpents) as elite units."},
            {"name": "TERRAIN MASTERY", "desc": "+60% combat power in controlled forests/swamps; enemies suffer -20% there."},
            {"name": "LIVING FORTIFICATIONS", "desc": "Self-repairing thorn-walls, root mazes, and vine barriers instead of stone walls."},
            {"name": "SLOW INNOVATION", "desc": "Technology develops at half the speed of other clans; they distrust machines."},
        ],
        "weaknesses": [
            "Severely weakened outside preferred terrain (-30% combat in plains, desert, arctic).",
            "Technology disadvantage grows over time.",
            "Iron Covenant's deforestation events actively destroy their terrain advantage.",
            "Arcane Conclave can burn their forests with fire-based spells.",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Grove Wanderers", "desc": "Nomadic, basic beast companions."},
            {"year": 25, "stage": "Forest Kin", "desc": "Permanent settlements, basic druidic magic."},
            {"year": 70, "stage": "Verdant Wardens", "desc": "Elder druids, large beast units, living fortifications."},
            {"year": 130, "stage": "Circle of the Ancient Root", "desc": "Geological plant-magic, can corrupt enemy terrain."},
            {"year": 210, "stage": "Rootbound Champions", "desc": "Ancient treant generals; the forest itself becomes a weapon."},
        ],
        "naming": {
            "given": ["Erindel", "Vethis", "Caelindra", "Ashgrove", "Tamsin", "Lorinel", "Brielle",
                       "Faelan", "Sorcha", "Ronan", "Niamh", "Cedric", "Maelys", "Oisin"],
            "epithets": ["of the Long Root", "Mosswhisper", "the Undying", "Greenward", "Thornveil",
                          "of the Deep Grove", "Leafsworn", "Wildheart", "of the First Bloom", "Barkbound"],
            "titles": ["Elder Druid", "Warden of the Root", "Grove-Speaker", "Keeper of the First Root"],
        },
        "strategic_personality": (
            "Reactive defender — almost never starts wars and is patient beyond "
            "measure. When their lands are invaded, they fight with ferocity that "
            "shocks enemies. Prefers to let enemies exhaust themselves before "
            "striking. Forms the most durable alliances and is the most devastating "
            "when betrayed."
        ),
    },
    "Void Reapers": {
        "full_name": "Children of the Hollow Dark",
        "lore": (
            "No written record predates them. No origin is agreed upon. Some say "
            "they crawled out of a wound in reality during an ancient magical "
            "experiment. Others say they are the shadows cast by the world's light, "
            "given hunger and will. They live in the spaces between — underground, "
            "in ruins, in the dark where other beings fear to go. They do not "
            "conquer. They do not build empires. They consume, spread, and wait. "
            "They are always watching."
        ),
        "home_label": "Southern Hollow Caverns",
        "primary_terrain": ["Underground", "Swamp"],
        "primary_resource": "Void Essence",
        "color": "#DC2626",
        "icon": "🕳️",
        "traits": [
            {"name": "ASSASSINATION MASTERY", "desc": "Can target and eliminate any named character. Success chance scales against the target's protection level."},
            {"name": "CORRUPTION NETWORK", "desc": "Can infiltrate enemy settlements and sow civil unrest, false information, and betrayal."},
            {"name": "HOLLOW MOVEMENT", "desc": "Armies move undetected through Underground regions, appearing where enemies don't expect them."},
            {"name": "VOID PHASING", "desc": "Units partially exist outside physical reality — 25% chance to simply not be hit."},
            {"name": "POPULATION CAP", "desc": "Can never sustain as large a population as other clans; naturally rare."},
        ],
        "weaknesses": [
            "Terrible at direct, open-field warfare — no morale systems, no formations.",
            "Cannot hold territory well without nearby underground access.",
            "Sylvan Circle's roots and living terrain expose underground movement.",
            "Stone Covenant cannot easily be assassinated — too durable, too ancient.",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Shadow Lurkers", "desc": "Small cells, basic poison crafting."},
            {"year": 20, "stage": "Void Stalkers", "desc": "Organized assassination network, underground movement mastered."},
            {"year": 65, "stage": "Reapers of Null", "desc": "Corruption magic, ability to destabilize entire governments."},
            {"year": 130, "stage": "Hollow Ascendants", "desc": "Full void phasing mastery, dimensional ambush, phantom armies."},
            {"year": 200, "stage": "The Unmade", "desc": "Can temporarily unmake small regions of reality, erasing terrain features."},
        ],
        "naming": {
            "given": ["Null-9", "Sev", "Vael", "Korrath", "Nyx-3", "Threll", "Maddox-Null",
                       "Vyx", "Crux", "Ashen-7", "Thessaly-Null", "Orin-Void"],
            "epithets": ["the Hollow Named", "Crux of Nothing", "Arbiter-of-Silence", "She-Who-Unmakes",
                          "of the Unseen Hour", "the Untraced", "Whisper-in-the-Dark", "the Erased"],
            "titles": ["Null Arbiter", "First Shadow", "Whisper-Lord", "Keeper of the Hollow"],
        },
        "strategic_personality": (
            "Chaotic manipulator — never fights fair and never intends to. Prefers "
            "to let other clans fight each other using leaked or fabricated "
            "information, striking only when others are exhausted. Fears sustained "
            "open-field warfare and the Sylvan Circle's terrain."
        ),
    },
    "Stone Covenant": {
        "full_name": "The Undying Accord",
        "lore": (
            "Before the other five clans drew their first breath, the Stone "
            "Covenant existed — part flesh, part living geological memory, part "
            "something that has no name. They remember when the mountains were "
            "young. They think in centuries the way others think in weeks. They are "
            "not cruel. They are not unkind. But they are ancient in ways that make "
            "all other ambitions look like children playing at war. When the Stone "
            "Covenant finally decides to act, the earth itself answers."
        ),
        "home_label": "Volcanic Rim Territories",
        "primary_terrain": ["Mountain", "Volcanic", "Underground"],
        "primary_resource": "Stone",
        "color": "#78716C",
        "icon": "🗻",
        "traits": [
            {"name": "GEOLOGICAL ENDURANCE", "desc": "Units have 3x the base health of other clans' equivalents."},
            {"name": "EARTH COMMAND", "desc": "Can trigger controlled earthquakes, raise stone walls from nothing, divert rivers, cause localized volcanic events."},
            {"name": "ANCESTRAL MEMORY", "desc": "Cannot be deceived, manipulated, or fooled. Remembers every interaction with every clan since Year 1. Betrayal is never forgiven."},
            {"name": "THE WEIGHT OF AGES", "desc": "Movement speed is 60% of other clans; decisions are slow but never wrong."},
            {"name": "GEOLOGICAL FORTRESS", "desc": "Settlements are built into mountains and cannot be bombed, burned, or magically razed easily."},
        ],
        "weaknesses": [
            "Glacially slow to mobilize — enemies can retreat before they arrive.",
            "Cannot cross large water bodies without significant engineering.",
            "Cannot chase fleeing enemies effectively.",
            "Void Reapers' poisons, applied slowly over years, are one of the few things that can kill them.",
            "Aura Knights' concentrated golden energy can fracture stone.",
        ],
        "evolution_path": [
            {"year": 0, "stage": "Stone Kin", "desc": "Semi-sentient elemental beings, crude geological powers."},
            {"year": 30, "stage": "Covenant Elders", "desc": "Formal society, basic geological manipulation."},
            {"year": 80, "stage": "Geological Vanguard", "desc": "Earthquake military doctrine, magma channeling."},
            {"year": 150, "stage": "Earth Speakers", "desc": "Long-range geological attacks, can reshape entire regions."},
            {"year": 250, "stage": "Living Mountain", "desc": "Individual units become semi-geological entities; generals are walking fortresses."},
        ],
        "naming": {
            "given": ["Grendual", "Basalt", "Ardenvok", "Granite", "Schist", "Tor", "Obsidia",
                       "Quarrin", "Dolmen", "Cairnoth", "Slate", "Ferrok"],
            "epithets": ["the Unmoved", "Who-Remembers", "Stone Speaker", "the One Called Granite",
                         "of the First Quarry", "the Patient", "Ageless", "the Foundation-Born"],
            "titles": ["Stone Speaker", "Elder of the Accord", "Foundation-Keeper", "Voice of the Mountain"],
        },
        "strategic_personality": (
            "Infinite patience — does not react to provocations quickly, planning "
            "responses over decades. Forms the most durable alliances of any clan "
            "(their word, once given, is eternal). When they finally declare war, it "
            "is always because they have spent fifty years preparing for it. They "
            "never rush. They never bluff."
        ),
    },
}


def get_clan_def(name):
    return CLAN_LORE[name]


def evolution_stage_index(clan_name, sim_year):
    """Returns the index (0-4) of the current evolution stage for a clan
    given the simulation year."""
    path = CLAN_LORE[clan_name]["evolution_path"]
    idx = 0
    for i, stage in enumerate(path):
        if sim_year >= stage["year"]:
            idx = i
    return idx


def evolution_stage_name(clan_name, stage_index):
    return CLAN_LORE[clan_name]["evolution_path"][stage_index]["stage"]


def next_evolution_year(clan_name, current_index):
    path = CLAN_LORE[clan_name]["evolution_path"]
    if current_index + 1 < len(path):
        return path[current_index + 1]["year"]
    return None


def initial_clan_state(clan_name, territory_count):
    """The fresh-genesis runtime state for a clan, shaped for db.upsert_clan."""
    import config
    return {
        "name": clan_name,
        "population": config.STARTING_POPULATION_PER_CLAN,
        "peak_population": config.STARTING_POPULATION_PER_CLAN,
        "territory_count": territory_count,
        "evolution_index": 0,
        "is_eliminated": False,
        "is_last_bastion": False,
        "rebuild_momentum_until": 0,
        "grief_until": 0,
        "extra_state": {
            "strategy_focus": "EXPAND",
            "last_battle_loss_pct": 0.0,
            "cornered": False,
            "peak_territory": territory_count,
        },
    }
