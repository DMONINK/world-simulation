"""
simulation/evolution.py — Evolution milestone tracking.

Each clan advances through 5 lore-defined stages as sim_year crosses
threshold years (see clans.CLAN_LORE[...]["evolution_path"]). This module
just detects the *transition* so engine.py can fire a proper narrative
EVOLUTION event the moment it happens — milestones are story moments, not
silent stat bumps.
"""

from simulation import clans as clans_module


def check_for_evolution(clan_state, sim_year):
    """Returns the new stage dict if clan_state just crossed into a new
    evolution stage this check, else None. Does not mutate clan_state —
    the caller is responsible for persisting the new evolution_index."""
    clan_name = clan_state["name"]
    new_index = clans_module.evolution_stage_index(clan_name, sim_year)
    if new_index > clan_state["evolution_index"]:
        path = clans_module.CLAN_LORE[clan_name]["evolution_path"]
        return {"index": new_index, "stage": path[new_index]}
    return None


def evolution_unlocks_summary(clan_name, stage_index):
    """A short human-readable note of what changed mechanically, for
    flavoring narrative text beyond the raw lore description."""
    notes = {
        ("Aura Knights", 2): "Aura Channeling is now available to elite warriors.",
        ("Aura Knights", 3): "Mounted cavalry and full aura weaponry have entered service.",
        ("Iron Covenant", 3): "Anti-magic constructs can now be built, blunting the Conclave's edge.",
        ("Iron Covenant", 4): "Underground rail networks now connect every forge-city.",
        ("Sylvan Circle", 3): "The Circle can now actively corrupt enemy-held terrain.",
        ("Void Reapers", 3): "Full void phasing mastery allows dimensional ambush tactics.",
        ("Stone Covenant", 2): "Magma channeling has entered the Covenant's military doctrine.",
        ("Arcane Conclave", 3): "Long-range devastation spells and arcane constructs are operational.",
    }
    return notes.get((clan_name, stage_index), "")
