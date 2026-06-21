"""
simulation/survival.py — All anti-early-death survival mechanics.

This is the module the brief calls out as fixing "5 of 6 clans die in the
first 10 days." Every rule here is non-negotiable and is checked after
every event that touches population or territory.

Rule 1: Starting population floor / elimination threshold.
Rule 2: Last Bastion Protocol (70%+ territory loss -> hidden stronghold retreat).
Rule 3: Cornered Beast (below 20% of peak population -> combat/recruitment buffs).
Rule 4/5: Diplomatic Moratorium & Total War Delay — handled in diplomacy.py / ai.py.
Rule 6: Geographic Separation — handled in world.py.
Rule 7: The 300-Year Hard Lock — population can never functionally drop
        below MIN_POPULATION_FOR_ELIMINATION before sim year 300; Last
        Bastion is force-invoked instead.
Rule 8: Rebuilding Momentum (big battle loss -> temporary recovery buffs).
Rule 9: Era-based population floors.
"""

import random

import config
from database import db


def era_population_floor(sim_year):
    for start, end, floor in config.POPULATION_FLOORS:
        if start <= sim_year <= end:
            return floor
    return config.MIN_POPULATION_FOR_ELIMINATION


def choose_last_bastion_region(clan_name, rng=None):
    """Picks a hidden stronghold: prefer the clan's own remaining
    territory; if none remains, find unclaimed ground near their
    ancestral home region."""
    rng = rng or random
    owned = db.get_regions_owned_by(clan_name)
    if owned:
        return rng.choice(owned)["id"]

    from simulation.world import CLAN_ANCHORS
    cx, cy = CLAN_ANCHORS[clan_name]["pos"]
    for radius in (15, 25, 40, 70, 120, 200):
        candidates = db.get_neutral_regions_near(cx, cy, radius)
        if candidates:
            return rng.choice(candidates)["id"]
    # Last resort: any region at all.
    all_regions = db.get_all_regions()
    return rng.choice(all_regions)["id"] if all_regions else None


def invoke_last_bastion(clan_state, sim_year, rng=None):
    """Rule 2 / Rule 7. Retreats the clan's surviving population to a
    hidden stronghold. Mutates clan_state IN PLACE (critical: callers
    further up the chain — run_full_survival_check, events._persist —
    hold their own reference to this same dict and will db.upsert_clan()
    it again later; if this function mutated a separately-fetched copy
    instead, that later upsert would silently overwrite is_last_bastion
    back to False). Returns the region_id chosen, or None if the world has
    no regions at all (should never happen post-genesis)."""
    clan_name = clan_state["name"]
    region_id = choose_last_bastion_region(clan_name, rng=rng)
    if region_id is not None:
        db.set_last_bastion(region_id, clan_name)

    clan_state["is_last_bastion"] = True
    floor = era_population_floor(sim_year) if sim_year < config.FIRST_ELIMINATION_YEAR_MINIMUM else config.MIN_POPULATION_FOR_ELIMINATION
    clan_state["population"] = max(clan_state["population"], floor)
    clan_state["territory_count"] = db.count_regions_owned_by(clan_name)
    db.upsert_clan(clan_state)
    return region_id


def territory_loss_fraction(clan_name, peak_territory):
    current = db.count_regions_owned_by(clan_name)
    if peak_territory <= 0:
        return 0.0
    return 1.0 - (current / peak_territory)


def _track_peak_territory(clan_state):
    current = db.count_regions_owned_by(clan_state["name"])
    peak = clan_state["extra_state"].get("peak_territory", current)
    peak = max(peak, current)
    clan_state["extra_state"]["peak_territory"] = peak
    return peak


def check_last_bastion_trigger(clan_state, sim_year, rng=None):
    """Returns True (and invokes it) if this clan just crossed the 70%
    territory-loss threshold (measured against its own historical peak)
    and isn't already in Last Bastion mode."""
    if clan_state["is_last_bastion"] or clan_state["is_eliminated"]:
        return False
    peak_territory = _track_peak_territory(clan_state)
    loss_frac = territory_loss_fraction(clan_state["name"], peak_territory)
    if loss_frac >= config.LAST_BASTION_TERRITORY_LOSS_TRIGGER:
        invoke_last_bastion(clan_state, sim_year, rng=rng)
        return True
    return False


def enforce_population_floor(clan_state, sim_year, rng=None):
    """Rule 7 + Rule 9, combined. Applies era-based floors before Year 300.
    After Year 300, only the hard elimination floor
    (MIN_POPULATION_FOR_ELIMINATION) protects a clan, and even that is via
    Last Bastion rather than instant death — actual elimination requires
    population < 500 AND zero territory (checked separately in
    check_elimination)."""
    name = clan_state["name"]
    pop = clan_state["population"]

    if sim_year < config.FIRST_ELIMINATION_YEAR_MINIMUM:
        floor = era_population_floor(sim_year)
        if pop < floor:
            clan_state["population"] = floor
            if not clan_state["is_last_bastion"]:
                invoke_last_bastion(clan_state, sim_year, rng=rng)
            db.insert_event(
                sim_year, 0, "POLITICAL", "catastrophic", [name],
                f"{name} Retreat to the Ancient Stronghold",
                f"The {name} fell below the survivable threshold of this age and have retreated to "
                f"their ancient stronghold, invoking emergency recovery measures to rebuild from near ruin.",
            )
    else:
        if pop < config.MIN_POPULATION_FOR_ELIMINATION and not clan_state["is_last_bastion"]:
            invoke_last_bastion(clan_state, sim_year, rng=rng)

    return clan_state


def check_elimination(clan_state):
    """A clan is eliminated only if population < 500 AND it controls zero
    regions (Rule 1) — and only this check, nowhere else, may set
    is_eliminated."""
    if clan_state["is_eliminated"]:
        return True
    territory = db.count_regions_owned_by(clan_state["name"])
    if clan_state["population"] < config.MIN_POPULATION_FOR_ELIMINATION and territory == 0:
        clan_state["is_eliminated"] = True
        return True
    return False


def check_cornered_beast(clan_state):
    """Rule 3. Returns True/False and updates clan_state['extra_state']['cornered']
    in place. Caller is responsible for persisting."""
    peak = max(clan_state["peak_population"], 1)
    is_cornered = (clan_state["population"] / peak) < config.CORNERED_BEAST_POP_THRESHOLD
    clan_state["extra_state"]["cornered"] = is_cornered
    return is_cornered


def apply_rebuild_momentum(clan_state, sim_year, army_size_before, army_losses):
    """Rule 8. If a clan lost more than REBUILD_ARMY_LOSS_TRIGGER of its
    army in a single battle, grant the temporary recovery bonus."""
    if army_size_before <= 0:
        return False
    loss_pct = army_losses / army_size_before
    clan_state["extra_state"]["last_battle_loss_pct"] = loss_pct
    if loss_pct >= config.REBUILD_ARMY_LOSS_TRIGGER:
        clan_state["rebuild_momentum_until"] = sim_year + config.REBUILD_DURATION_YEARS
        return True
    return False


def has_rebuild_momentum(clan_state, sim_year):
    return sim_year < clan_state.get("rebuild_momentum_until", 0)


def apply_grief_of_legends(clan_state, sim_year):
    """Aura Knights-specific: -25% combat power for 2 sim years after a
    named leader dies in battle. Stored as an expiry year on the clan row."""
    if clan_state["name"] != "Aura Knights":
        return
    clan_state["grief_until"] = sim_year + 2


def is_grieving(clan_state, sim_year):
    return sim_year < clan_state.get("grief_until", 0)


def discovery_roll_for_last_bastion(discoverer_clan, target_clan, rng=None):
    """Rule 2: 30% discovery chance per sim year per adjacent clan."""
    rng = rng or random
    region = db.get_last_bastion_region(target_clan)
    if region is None:
        return False
    if discoverer_clan in region["last_bastion_discovered_by"]:
        return True  # already found
    if rng.random() < config.LAST_BASTION_DISCOVERY_CHANCE_PER_YEAR:
        db.mark_last_bastion_discovered(region["id"], discoverer_clan)
        return True
    return False


def run_full_survival_check(clan_state, sim_year, rng=None):
    """Convenience entrypoint called after any event that changes a clan's
    population or territory. Runs every relevant rule in the correct order
    and returns the (possibly mutated) clan_state. Does NOT persist —
    caller is expected to db.upsert_clan() the result."""
    if clan_state["is_eliminated"]:
        return clan_state

    check_last_bastion_trigger(clan_state, sim_year, rng=rng)
    enforce_population_floor(clan_state, sim_year, rng=rng)
    check_cornered_beast(clan_state)

    if sim_year >= config.FIRST_ELIMINATION_YEAR_MINIMUM:
        check_elimination(clan_state)

    clan_state["territory_count"] = db.count_regions_owned_by(clan_state["name"])
    clan_state["peak_population"] = max(clan_state["peak_population"], clan_state["population"])
    return clan_state
