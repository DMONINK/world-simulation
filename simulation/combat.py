"""
simulation/combat.py — Combat resolution.

Translates clan traits, terrain, evolution stage, and the loose circular
weakness system into a single battle outcome: who wins, how many losses
each side takes, and how decisive it was. The actual story text is built
afterward by narrative.py — this module only produces numbers and a
structured outcome dict.
"""

import random

OPEN_FIELD_BIOMES = {"Plains", "Desert", "Coastal", "Arctic"}
SYLVAN_TERRAIN = {"Forest", "Swamp"}
SYLVAN_BAD_TERRAIN = {"Plains", "Desert", "Arctic"}

# (attacker, defender) -> multiplier applied to the attacker's effective
# power. Encodes the lore-described weakness relationships, not just the
# tidy 5-clan cycle (Stone Covenant deliberately breaks the cycle).
WEAKNESS_BONUS = {
    ("Aura Knights", "Void Reapers"): 1.12,        # honor + iron morale counters ambush/propaganda
    ("Aura Knights", "Stone Covenant"): 1.15,      # golden energy fractures stone
    ("Void Reapers", "Arcane Conclave"): 1.22,     # reaching mages before they cast is devastating
    ("Arcane Conclave", "Iron Covenant"): 1.22,    # magic counters Iron severely (fades after anti-magic constructs)
    ("Arcane Conclave", "Aura Knights"): 1.15,     # pure magic bypasses aura shielding
    ("Iron Covenant", "Sylvan Circle"): 1.15,      # industry/deforestation destroys terrain advantage
    ("Sylvan Circle", "Aura Knights"): 1.12,       # nature magic drains aura over long campaigns
    ("Sylvan Circle", "Void Reapers"): 1.15,       # roots expose underground movement
    ("Stone Covenant", "Iron Covenant"): 1.25,     # geological attacks devastate infrastructure
    ("Void Reapers", "Stone Covenant"): 1.08,      # poison works, slowly — minor edge in any single battle
}

# Iron Covenant's anti-magic constructs come online with Covenant War
# Machines (evolution index 3). After that, Arcane Conclave's bonus vs them
# is halved.
IRON_ANTI_MAGIC_EVOLUTION_INDEX = 3


def _weakness_multiplier(attacker, defender, defender_evolution_index):
    mult = WEAKNESS_BONUS.get((attacker, defender), 1.0)
    if attacker == "Arcane Conclave" and defender == "Iron Covenant":
        if defender_evolution_index >= IRON_ANTI_MAGIC_EVOLUTION_INDEX:
            mult = 1.0 + (mult - 1.0) * 0.5
    return mult


def compute_power(clan, army_size, biome, is_attacker, evolution_index,
                   fortification=0, cornered=False, grief_active=False, rng=None):
    """Base effective combat power for one side, before the weakness
    matchup multiplier is applied."""
    rng = rng or random
    power = float(army_size) * rng.uniform(0.80, 1.20)

    if clan == "Aura Knights":
        if biome in OPEN_FIELD_BIOMES:
            power *= 1.40
        if grief_active:
            power *= 0.75  # Grief of Legends: leader died this cycle

    elif clan == "Arcane Conclave":
        power *= 1.12  # Arcane Devastation gives a slight inherent edge;
        # the real tradeoff of Glass Cannon shows up in casualty_multiplier()
        # below — they hit decently but bleed badly when it goes wrong.

    elif clan == "Iron Covenant":
        if not is_attacker:
            power *= (1.15 + 0.30 * fortification)  # Fortress Builders, scales with how dug-in they are
        if evolution_index >= 3:
            power *= 1.15  # War Machine Doctrine online

    elif clan == "Sylvan Circle":
        if biome in SYLVAN_TERRAIN:
            power *= 1.60  # Terrain Mastery (home ground)
        elif biome in SYLVAN_BAD_TERRAIN:
            power *= 0.70  # weakened far from home terrain

    elif clan == "Void Reapers":
        power *= 1.08  # Void Phasing's main effect lives in casualty_multiplier();
        # a small power edge here represents the unpredictability of hit-and-run tactics.
        if biome in OPEN_FIELD_BIOMES:
            power *= 0.55  # terrible at direct, open-field warfare

    elif clan == "Stone Covenant":
        power *= 1.05  # Geological Endurance contributes a little raw power;
        # the larger effect (3x health) is applied to casualties, not power.

    if cornered:
        power *= 1.50  # Cornered Beast

    return power


def casualty_multiplier(clan):
    """Independent of who wins: how much a clan's own traits scale the
    losses it personally takes. Stone Covenant's tankiness and Arcane
    Conclave's fragility both live here rather than in the power formula,
    so a clan can win a fight and still bleed for it (or vice versa)."""
    if clan == "Stone Covenant":
        return 1.0 / 3.0   # Geological Endurance: 3x base health
    if clan == "Arcane Conclave":
        return 1.5         # Glass Cannon: -50% physical defense
    if clan == "Void Reapers":
        return 0.85        # Void Phasing softens losses slightly even when they lose
    return 1.0


def _enemy_terrain_penalty(defender_clan, biome):
    """Sylvan Circle's Terrain Mastery also weakens whoever is attacking
    them on their own ground."""
    if defender_clan == "Sylvan Circle" and biome in SYLVAN_TERRAIN:
        return 0.80
    return 1.0


def resolve_battle(attacker, defender, attacker_army, defender_army, biome,
                    attacker_evolution_index, defender_evolution_index,
                    attacker_fortification=0, defender_fortification=0,
                    attacker_cornered=False, defender_cornered=False,
                    attacker_grief=False, defender_grief=False, rng=None):
    """Resolves one battle. Returns a dict:
        winner, attacker_power, defender_power, attacker_losses,
        defender_losses, decisive (bool), margin (0-1)
    """
    rng = rng or random

    a_power = compute_power(attacker, attacker_army, biome, True, attacker_evolution_index,
                             fortification=attacker_fortification, cornered=attacker_cornered,
                             grief_active=attacker_grief, rng=rng)
    d_power = compute_power(defender, defender_army, biome, False, defender_evolution_index,
                             fortification=defender_fortification, cornered=defender_cornered,
                             grief_active=defender_grief, rng=rng)

    a_power *= _weakness_multiplier(attacker, defender, defender_evolution_index)
    d_power *= _weakness_multiplier(defender, attacker, attacker_evolution_index)
    a_power *= _enemy_terrain_penalty(defender, biome)

    total = a_power + d_power
    if total <= 0:
        attacker_wins = rng.random() < 0.5
        margin = 0.0
    else:
        a_share = a_power / total
        attacker_wins = a_share >= 0.5
        margin = abs(a_share - 0.5) * 2  # 0 = coin flip, 1 = total domination

    # Casualty rates: the loser always loses more. Both sides lose
    # proportionally to how badly the fight actually went, plus randomness.
    winner_loss_rate = rng.uniform(0.04, 0.16) * (1.0 - margin * 0.5)
    loser_loss_rate = rng.uniform(0.18, 0.42) * (0.6 + margin * 0.8)
    winner_loss_rate = min(winner_loss_rate, 0.35)
    loser_loss_rate = min(loser_loss_rate, 0.85)

    if attacker_wins:
        attacker_losses = int(attacker_army * winner_loss_rate)
        defender_losses = int(defender_army * loser_loss_rate)
    else:
        attacker_losses = int(attacker_army * loser_loss_rate)
        defender_losses = int(defender_army * winner_loss_rate)

    attacker_losses = int(attacker_losses * casualty_multiplier(attacker))
    defender_losses = int(defender_losses * casualty_multiplier(defender))

    return {
        "winner": attacker if attacker_wins else defender,
        "loser": defender if attacker_wins else attacker,
        "attacker_wins": attacker_wins,
        "attacker_power": round(a_power, 1),
        "defender_power": round(d_power, 1),
        "attacker_losses": max(0, attacker_losses),
        "defender_losses": max(0, defender_losses),
        "decisive": margin > 0.4,
        "margin": round(margin, 3),
    }


def army_size_estimate(population, territory_count, evolution_index, is_iron_covenant=False, is_void_reapers=False):
    """A rough standing-army estimate derived from population and
    development level — used when a clan needs to field a force but the
    simulation hasn't modeled units explicitly down to the soldier."""
    base_rate = 0.05 + 0.01 * evolution_index  # 5% scaling up to ~9% at max evolution
    if is_iron_covenant:
        base_rate *= 1.2  # The Workforce / Industrial Might
    if is_void_reapers:
        base_rate *= 0.6  # Population Cap — naturally rare, smaller forces
    size = int(population * base_rate)
    return max(50, size)
