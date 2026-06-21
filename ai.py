"""
simulation/ai.py — Clan decision-making AI.

Each clan, when it acts, rolls a weighted decision from clans.DECISION_WEIGHTS,
adjusted by situational modifiers (cornered, last-bastion, diplomatic
moratorium, grudge levels, evolution stage). Once a decision is chosen,
this module also picks a concrete target where one is needed (a region to
expand into, an enemy to raid, a clan to declare war on or seek alliance
with, or a clan-special action's target).

engine.py is responsible for actually executing the chosen intent (running
combat, moving territory ownership, firing events) — this module only
decides *what* a clan wants to do.
"""

import random

import config
from database import db
from simulation import clans as clans_module
from simulation import world as world_module
from simulation import diplomacy
from simulation import combat


def _situational_modifiers(clan_name, clan_state, sim_year):
    mods = {d: 1.0 for d in clans_module.DECISIONS}
    cornered = clan_state["extra_state"].get("cornered", False)
    last_bastion = clan_state["is_last_bastion"]

    if cornered:
        mods["EXPAND"] *= 0.25
        mods["RECRUIT"] *= 1.6
        mods["FORTIFY"] *= 1.4
        mods["DECLARE_WAR"] *= 0.4
        mods["RAID"] *= 0.6

    if last_bastion:
        mods["EXPAND"] *= 0.1
        mods["RAID"] *= 0.3
        mods["DECLARE_WAR"] *= 0.2
        mods["FORTIFY"] *= 1.8
        mods["RECRUIT"] *= 1.5
        mods["SEEK_ALLIANCE"] *= 1.5

    if diplomacy.is_diplomatic_moratorium(sim_year):
        mods["DECLARE_WAR"] *= 0.05  # only skirmishes/raids allowed (Rule 4)
    elif sim_year < config.TOTAL_WAR_UNLOCK_YEAR:
        mods["DECLARE_WAR"] *= 0.45  # discouraged but possible (Rule 5)

    if clan_name == "Stone Covenant":
        # Infinite patience: never rushes to war regardless of provocation.
        mods["DECLARE_WAR"] *= 0.5

    # Dramatic-action cooldown: a clan gets at most one DECLARE_WAR /
    # BETRAY_ALLIANCE / SPECIAL action per sim year. Without this, a clan
    # whose personality heavily favors SPECIAL (Void Reapers, Arcane
    # Conclave) ends up re-attempting the same assassination or strike
    # against the same target dozens of times in a single year, which reads
    # as chaotic spam rather than history. Routine actions (EXPAND, FORTIFY,
    # RESEARCH, RECRUIT, RAID) are unaffected.
    if clan_state["extra_state"].get("last_dramatic_action_year") == sim_year:
        mods["DECLARE_WAR"] *= 0.03
        mods["BETRAY_ALLIANCE"] *= 0.03
        mods["SPECIAL"] *= 0.03

    return mods


def decide_action(clan_name, clan_state, sim_year, rng=None):
    rng = rng or random
    base_weights = clans_module.DECISION_WEIGHTS[clan_name]
    mods = _situational_modifiers(clan_name, clan_state, sim_year)

    decisions, weights = [], []
    for d, w in base_weights.items():
        decisions.append(d)
        weights.append(max(0.01, w * mods.get(d, 1.0)))

    return rng.choices(decisions, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# TARGET SELECTION — territorial
# ---------------------------------------------------------------------------
def find_expansion_target(clan_name, rng=None, sample_size=120):
    """Frontier expansion: sample some of the clan's owned regions, look at
    their immediate neighbors, and return a neutral neighbor to claim."""
    rng = rng or random
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return None
    sample = rng.sample(owned, min(sample_size, len(owned)))
    candidates = []
    for region in sample:
        for nid in world_module.neighbors_of(region["id"]):
            neighbor = db.get_region(nid)
            if neighbor and neighbor["owner_clan"] is None:
                candidates.append(neighbor)
    if not candidates:
        return None
    # Prefer resource-rich, then break ties randomly.
    candidates.sort(key=lambda r: len(r["resources"]), reverse=True)
    top = candidates[: max(1, len(candidates) // 4)]
    return rng.choice(top)


def find_raid_target(clan_name, rng=None, sample_size=120):
    """Find a nearby enemy-owned region worth raiding (resource theft, not
    conquest — ownership doesn't change on a raid)."""
    rng = rng or random
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return None
    sample = rng.sample(owned, min(sample_size, len(owned)))
    candidates = []
    for region in sample:
        for nid in world_module.neighbors_of(region["id"]):
            neighbor = db.get_region(nid)
            if neighbor and neighbor["owner_clan"] and neighbor["owner_clan"] != clan_name:
                candidates.append(neighbor)
    if not candidates:
        return None
    candidates.sort(key=lambda r: len(r["resources"]), reverse=True)
    top = candidates[: max(1, len(candidates) // 3)]
    return rng.choice(top)


def find_war_frontier_region(clan_name, enemy_clan, rng=None, sample_size=200):
    """For DECLARE_WAR / battle resolution: find a region on the border
    between two clans (an enemy region adjacent to the attacker's
    territory) to serve as the battleground."""
    rng = rng or random
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return None
    sample = rng.sample(owned, min(sample_size, len(owned)))
    candidates = []
    for region in sample:
        for nid in world_module.neighbors_of(region["id"]):
            neighbor = db.get_region(nid)
            if neighbor and neighbor["owner_clan"] == enemy_clan:
                candidates.append(neighbor)
    if candidates:
        return rng.choice(candidates)
    # No direct border yet — these two clans haven't made contact.
    return None


# ---------------------------------------------------------------------------
# TARGET SELECTION — diplomatic / military
# ---------------------------------------------------------------------------
def choose_diplomatic_target(clan_name, sim_year, want_war, rng=None):
    """Picks an enemy/ally candidate clan. For war: prefer high grudge and
    a favorable weakness matchup, and avoid clans that counter *us* unless
    we're desperate. For alliance: prefer low grudge, non-countered clans."""
    rng = rng or random
    others = [c for c in clans_module.CLAN_NAMES if c != clan_name]
    scored = []
    for other in others:
        other_state = db.get_clan(other)
        if not other_state or other_state["is_eliminated"]:
            continue
        grudge = diplomacy.get_grudge(clan_name, other)
        status = diplomacy.get_status(clan_name, other)
        we_counter_them = combat.WEAKNESS_BONUS.get((clan_name, other), 1.0) > 1.0
        they_counter_us = combat.WEAKNESS_BONUS.get((other, clan_name), 1.0) > 1.0

        if want_war:
            if status in (diplomacy.STATUS_AT_WAR, diplomacy.STATUS_BLOOD_WAR):
                continue
            score = grudge + (15 if we_counter_them else 0) - (10 if they_counter_us else 0)
        else:
            if status == diplomacy.STATUS_ALLY:
                continue
            score = -grudge + (10 if not they_counter_us else 0)
        scored.append((score, other))

    if not scored:
        return None
    scored.sort(reverse=True)
    # Weighted toward the top candidates rather than always the single best,
    # so the world doesn't feel deterministic.
    top = scored[: min(3, len(scored))]
    return rng.choice(top)[1]


# ---------------------------------------------------------------------------
# SPECIAL ACTION TARGETING
# ---------------------------------------------------------------------------
def choose_assassination_target(target_clan, rng=None):
    """Void Reapers' ASSASSINATE: prefer Supreme Leaders and Generals."""
    rng = rng or random
    from simulation import characters as characters_module
    roster = db.get_characters_by_clan(target_clan, alive_only=True)
    leaders = [c for c in roster if c["role"] in (characters_module.ROLE_SUPREME_LEADER, characters_module.ROLE_GENERAL)]
    pool = leaders if leaders else roster
    return rng.choice(pool) if pool else None


def assassination_protection_level(character, target_clan):
    """Higher = harder to kill. Stone Covenant characters are nearly immune."""
    if target_clan == "Stone Covenant":
        return 0.92  # Ancestral Memory / sheer endurance — assassination almost never works
    from simulation import characters as characters_module
    base = {
        characters_module.ROLE_SUPREME_LEADER: 0.55,
        characters_module.ROLE_GENERAL: 0.40,
        characters_module.ROLE_CHAMPION: 0.45,
        characters_module.ROLE_INNOVATOR: 0.25,
        characters_module.ROLE_SHADOW_FIGURE: 0.30,
    }
    return base.get(character["role"], 0.30)
