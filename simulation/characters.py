"""
simulation/characters.py — Named character generation and lifecycle.

Every clan maintains a living roster: one Supreme Leader, 2-4 Generals, 1-2
Innovators, and a growing list of Champions (created through battle). Void
Reapers additionally maintain Shadow Figures (covert agents with codenames).

Characters are born, age, fight, get crippled, become legendary, defect, get
captured, or die — and every one of those is meant to be a narrative beat,
not a silent stat change. This module only builds/mutates character
records; narrative.py turns the mutation into prose and engine.py decides
*when* a lifecycle event fires.
"""

import random

from simulation import clans

SUPREME_LEADER_TITLE = {
    "Aura Knights": "High Commander",
    "Arcane Conclave": "Grand Theorist",
    "Iron Covenant": "Forge Master",
    "Sylvan Circle": "Elder Druid",
    "Void Reapers": "Null Arbiter",
    "Stone Covenant": "Stone Speaker",
}

ROLE_SUPREME_LEADER = "SUPREME_LEADER"
ROLE_GENERAL = "GENERAL"
ROLE_INNOVATOR = "INNOVATOR"
ROLE_CHAMPION = "CHAMPION"
ROLE_SHADOW_FIGURE = "SHADOW_FIGURE"

STATUS_ALIVE = "alive"
STATUS_DEAD = "dead"
STATUS_CRIPPLED = "crippled"
STATUS_CAPTURED = "captured"
STATUS_DEFECTED = "defected"


def generate_name(clan_name, rng=None):
    rng = rng or random
    naming = clans.CLAN_LORE[clan_name]["naming"]
    given = rng.choice(naming["given"])
    if clan_name == "Void Reapers":
        # Void Reapers favor fragmented codename-style names; sometimes a
        # bare given name, sometimes given+epithet.
        if rng.random() < 0.4:
            return given
        epithet = rng.choice(naming["epithets"])
        return f"{given}, {epithet}"
    epithet = rng.choice(naming["epithets"])
    return f"{given} {epithet}"


def generate_titled_name(clan_name, role, rng=None):
    rng = rng or random
    name = generate_name(clan_name, rng)
    naming = clans.CLAN_LORE[clan_name]["naming"]
    if role == ROLE_SUPREME_LEADER:
        return f"{SUPREME_LEADER_TITLE[clan_name]} {name}"
    if role == ROLE_GENERAL:
        title = rng.choice([t for t in naming["titles"] if t != SUPREME_LEADER_TITLE[clan_name]] or naming["titles"])
        return f"{title} {name}" if rng.random() < 0.5 else name
    return name


def new_character(clan_name, role, birth_year, rng=None):
    rng = rng or random
    name = generate_titled_name(clan_name, role, rng)
    return {
        "clan": clan_name,
        "name": name,
        "role": role,
        "birth_year": birth_year,
        "death_year": None,
        "status": STATUS_ALIVE,
        "is_legendary": False,
        "notable_deeds": [],
        "injuries": [],
    }


def generate_starting_roster(clan_name, sim_year=0, rng=None):
    """Builds the initial named cast for a clan at genesis: one Supreme
    Leader, 2-4 Generals, 1-2 Innovators. Void Reapers also get 1-2 Shadow
    Figures. Champions are earned in play, not granted at genesis.

    Genesis characters are adults, not newborns — each is given a birth
    year in the past relative to sim_year so their age is plausible for
    their role from the very first tick."""
    rng = rng or random
    leader = new_character(clan_name, ROLE_SUPREME_LEADER, sim_year - rng.randint(35, 65), rng)
    roster = [leader]

    n_generals = rng.randint(2, 4)
    for _ in range(n_generals):
        roster.append(new_character(clan_name, ROLE_GENERAL, sim_year - rng.randint(28, 55), rng))

    n_innovators = rng.randint(1, 2)
    for _ in range(n_innovators):
        roster.append(new_character(clan_name, ROLE_INNOVATOR, sim_year - rng.randint(25, 60), rng))

    if clan_name == "Void Reapers":
        n_shadows = rng.randint(1, 2)
        for _ in range(n_shadows):
            roster.append(new_character(clan_name, ROLE_SHADOW_FIGURE, sim_year - rng.randint(22, 50), rng))

    return roster


def pick_supreme_leader(characters):
    for c in characters:
        if c["role"] == ROLE_SUPREME_LEADER and c["status"] not in (STATUS_DEAD, STATUS_DEFECTED, STATUS_CAPTURED):
            return c
    return None


def pick_random_combatant(characters, exclude_roles=None, rng=None):
    rng = rng or random
    exclude_roles = exclude_roles or []
    pool = [c for c in characters if c["status"] == STATUS_ALIVE and c["role"] not in exclude_roles]
    if not pool:
        return None
    return rng.choice(pool)


def promote_to_champion(character):
    """A General or unranked fighter who survives enough victories becomes
    a Champion — a legendary-track individual warrior."""
    character_role_was = character["role"]
    character["role"] = ROLE_CHAMPION
    character["notable_deeds"].append(
        f"Rose from {character_role_was.replace('_', ' ').title()} to Champion through valor in battle."
    )
    return character


def mark_legendary(character, reason):
    character["is_legendary"] = True
    character["notable_deeds"].append(reason)
    return character


def kill_character(character, cause, sim_year):
    character["status"] = STATUS_DEAD
    character["death_year"] = sim_year
    character["notable_deeds"].append(cause)
    return character


def cripple_character(character, injury_note):
    character["status"] = STATUS_CRIPPLED
    character["injuries"].append(injury_note)
    return character


def capture_character(character):
    character["status"] = STATUS_CAPTURED
    return character


def defect_character(character, new_clan, sim_year, reason):
    character["status"] = STATUS_DEFECTED
    character["clan"] = new_clan
    character["notable_deeds"].append(f"Year {sim_year}: {reason}")
    return character


def succession_pick(characters, dead_leader_role=ROLE_SUPREME_LEADER):
    """When a Supreme Leader dies, pick a successor — prefer Generals, then
    Champions, then Innovators, then anyone left standing."""
    priority = [ROLE_GENERAL, ROLE_CHAMPION, ROLE_INNOVATOR, ROLE_SHADOW_FIGURE]
    for role in priority:
        candidates = [c for c in characters if c["role"] == role and c["status"] == STATUS_ALIVE]
        if candidates:
            chosen = random.choice(candidates)
            chosen["role"] = dead_leader_role
            return chosen
    return None


def age_of(character, sim_year):
    return sim_year - character["birth_year"]


def death_of_old_age_chance(age):
    """Rough actuarial curve: negligible before 60, climbing steeply after."""
    if age < 60:
        return 0.0
    if age < 90:
        return 0.01 * ((age - 60) / 10)
    return min(0.5, 0.04 * ((age - 90) / 5 + 1))
