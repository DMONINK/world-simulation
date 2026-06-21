"""
simulation/events.py — Event generation, resolution, and queuing.

This is the integration layer: it takes an AI decision (or an ambient random
roll) and turns it into real consequences — territory changes, battles,
diplomacy shifts, character lifecycle events — then hands the result to
narrative.py for prose and writes it to the event log via database/db.py.

Two entrypoints drive the simulation each tick (called from engine.py):
    process_clan_turn(clan_name, sim_year, sim_day, rng)   — AI-driven action
    roll_ambient_events(sim_year, sim_day, rng)            — flavor events
"""

import random

import config
from database import db
from simulation import clans as clans_module
from simulation import characters as characters_module
from simulation import combat
from simulation import narrative as nar
from simulation import diplomacy
from simulation import ai as ai_module
from simulation import survival
from simulation import evolution
from simulation import world as world_module


def _log(sim_year, sim_day, category, severity, clans_involved, title, narrative_text, region_id=None):
    db.insert_event(sim_year, sim_day, category, severity, clans_involved, title, narrative_text, region_id)


def _persist(clan_state, sim_year, rng=None):
    survival.run_full_survival_check(clan_state, sim_year, rng=rng)
    db.upsert_clan(clan_state)


def _leader_death_check(clan_name, sim_year, rng, cause_note, severity="major"):
    """Rolls a small chance that the clan's Supreme Leader was among the
    casualties of a major event. Returns the dead leader's dict, or None."""
    roster = db.get_characters_by_clan(clan_name, alive_only=True)
    leader = characters_module.pick_supreme_leader(roster)
    if not leader:
        return None
    if rng.random() < 0.06:  # leaders don't die often, but it happens
        characters_module.kill_character(leader, cause_note, sim_year)
        db.update_character(leader["id"], status=leader["status"], death_year=sim_year, notable_deeds=leader["notable_deeds"])
        successor = characters_module.succession_pick(roster)
        if successor:
            db.update_character(successor["id"], role=successor["role"])
            succ_text = nar.render_political({
                "character_name": successor["name"], "title": characters_module.SUPREME_LEADER_TITLE[clan_name],
                "clan": clan_name,
            }, rng, kind="succession")
            _log(sim_year, 0, "POLITICAL", "major", [clan_name],
                 f"{clan_name} {nar.conjugate(clan_name, 'Name', 'Names')} a New {characters_module.SUPREME_LEADER_TITLE[clan_name]}", succ_text)
        if clan_name == "Aura Knights":
            clan_state = db.get_clan(clan_name)
            survival.apply_grief_of_legends(clan_state, sim_year)
            db.upsert_clan(clan_state)
        return leader
    return None


# ---------------------------------------------------------------------------
# DECISION HANDLERS
# ---------------------------------------------------------------------------
def _handle_expand(clan_name, clan_state, sim_year, sim_day, rng):
    target = ai_module.find_expansion_target(clan_name, rng=rng)
    if not target:
        return
    pop_density = rng.randint(20, 70)
    fort = rng.randint(0, 1)
    db.update_region_owner(target["id"], clan_name, pop_density, fort)
    _persist(clan_state, sim_year, rng)
    if rng.random() < 0.25:  # not every settling needs a headline
        _log(sim_year, sim_day, "DISCOVERY", "minor", [clan_name],
             f"{clan_name} {nar.conjugate(clan_name, 'Settle', 'Settles')} {target['name']}",
             f"The {clan_name} {nar.conjugate(clan_name, 'have', 'has')} extended their reach into {target['name']}, a {target['biome'].lower()} "
             f"region that now answers to them.",
             region_id=target["id"])


def _handle_fortify(clan_name, clan_state, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    sample = rng.sample(owned, min(10, len(owned)))
    for region in sample:
        if region["fortification"] < 9:
            db.update_region_owner(region["id"], clan_name, region["population_density"], min(9, region["fortification"] + 1))
    _persist(clan_state, sim_year, rng)


def _handle_research(clan_name, clan_state, sim_year, sim_day, rng):
    clan_state["extra_state"]["research_progress"] = clan_state["extra_state"].get("research_progress", 0) + 1
    _persist(clan_state, sim_year, rng)
    if rng.random() < 0.35:
        _attempt_discovery(clan_name, sim_year, sim_day, rng)


def _handle_recruit(clan_name, clan_state, sim_year, sim_day, rng):
    # Population growth itself is handled once per day by apply_daily_growth()
    # below, tied to elapsed time rather than to how often this decision gets
    # picked. RECRUIT instead represents a short-term military readiness push.
    clan_state["extra_state"]["recruitment_boost_until"] = sim_year + 1
    _persist(clan_state, sim_year, rng)


def _handle_raid(clan_name, clan_state, sim_year, sim_day, rng):
    target_region = ai_module.find_raid_target(clan_name, rng=rng)
    if not target_region:
        return
    enemy_clan = target_region["owner_clan"]
    enemy_state = db.get_clan(enemy_clan)
    if not enemy_state or enemy_state["is_eliminated"]:
        return

    # Raids are border skirmishes, not conquest — a small percentage of the
    # victim's population is disrupted, most of which is simply lost in the
    # raid rather than gained by the raider.
    stolen_pop = max(5, int(enemy_state["population"] * rng.uniform(0.0006, 0.004)))
    enemy_state["population"] = max(0, enemy_state["population"] - stolen_pop)
    clan_state["population"] += stolen_pop // 3

    diplomacy.record_event(clan_name, enemy_clan, sim_year, "raid", grudge_delta=4,
                            note=f"{clan_name} raided {target_region['name']}")
    if diplomacy.get_status(clan_name, enemy_clan) == diplomacy.STATUS_NEUTRAL:
        diplomacy.set_status(clan_name, enemy_clan, diplomacy.STATUS_COLD_WAR, sim_year)

    _persist(clan_state, sim_year, rng)
    _persist(enemy_state, sim_year, rng)

    text = (f"A raiding party from the {clan_name} struck {target_region['name']}, stripping it of "
            f"{nar.evocative_number(stolen_pop)} worth of stores and people before the {enemy_clan} could respond. "
            f"It was a targeted theft, not conquest — the region remains {enemy_clan} territory, for now.")
    _log(sim_year, sim_day, "MILITARY", "minor", [clan_name, enemy_clan],
         f"Raid on {target_region['name']}", text, region_id=target_region["id"])


def _resolve_real_battle(attacker, defender, region, sim_year, sim_day, rng, declared_war=False):
    attacker_state = db.get_clan(attacker)
    defender_state = db.get_clan(defender)
    if not attacker_state or not defender_state:
        return
    if attacker_state["is_eliminated"] or defender_state["is_eliminated"]:
        return

    attacker_army = combat.army_size_estimate(
        attacker_state["population"], attacker_state["territory_count"], attacker_state["evolution_index"],
        is_iron_covenant=(attacker == "Iron Covenant"), is_void_reapers=(attacker == "Void Reapers"))
    defender_army = combat.army_size_estimate(
        defender_state["population"], defender_state["territory_count"], defender_state["evolution_index"],
        is_iron_covenant=(defender == "Iron Covenant"), is_void_reapers=(defender == "Void Reapers"))

    result = combat.resolve_battle(
        attacker, defender, attacker_army, defender_army, region["biome"],
        attacker_state["evolution_index"], defender_state["evolution_index"],
        attacker_fortification=0, defender_fortification=region["fortification"],
        attacker_cornered=attacker_state["extra_state"].get("cornered", False),
        defender_cornered=defender_state["extra_state"].get("cornered", False),
        attacker_grief=survival.is_grieving(attacker_state, sim_year),
        defender_grief=survival.is_grieving(defender_state, sim_year),
        rng=rng,
    )

    attacker_state["population"] = max(0, attacker_state["population"] - result["attacker_losses"])
    defender_state["population"] = max(0, defender_state["population"] - result["defender_losses"])

    if result["attacker_wins"]:
        db.update_region_owner(region["id"], attacker, region["population_density"], max(0, region["fortification"] - 1))

    survival.apply_rebuild_momentum(attacker_state, sim_year, attacker_army, result["attacker_losses"])
    survival.apply_rebuild_momentum(defender_state, sim_year, defender_army, result["defender_losses"])

    grudge_gain = 8 if result["decisive"] else 4
    diplomacy.record_event(attacker, defender, sim_year, "war",
                            grudge_delta=grudge_gain,
                            note=f"Battle at {region['name']}")
    diplomacy.set_status(attacker, defender, diplomacy.STATUS_AT_WAR, sim_year)

    # A meaningful chance either side's leadership took a hit in a decisive fight.
    if result["decisive"]:
        loser = result["loser"]
        cause = f"fallen at the {nar.generate_battle_name(region['name'], rng)}"
        _leader_death_check(loser, sim_year, rng, cause)

    _persist(attacker_state, sim_year, rng)
    _persist(defender_state, sim_year, rng)

    battle_text = nar.render_battle({
        "attacker": attacker, "defender": defender,
        "attacker_general": _general_name(attacker, rng), "defender_general": _general_name(defender, rng),
        "region_name": region["name"], "sim_year": sim_year,
        "attacker_wins": result["attacker_wins"],
        "attacker_strength": attacker_army, "defender_strength": defender_army,
        "attacker_losses": result["attacker_losses"], "defender_losses": result["defender_losses"],
    }, rng)

    severity = "major" if result["decisive"] else "minor"
    _log(sim_year, sim_day, "MILITARY", severity, [attacker, defender],
         nar.generate_battle_name(region["name"], rng), battle_text, region_id=region["id"])


def _general_name(clan_name, rng):
    roster = db.get_characters_by_clan(clan_name, alive_only=True)
    generals = [c for c in roster if c["role"] in (characters_module.ROLE_GENERAL, characters_module.ROLE_SUPREME_LEADER, characters_module.ROLE_CHAMPION)]
    if generals:
        return rng.choice(generals)["name"]
    return characters_module.generate_name(clan_name, rng)


def _handle_declare_war(clan_name, clan_state, sim_year, sim_day, rng):
    target = ai_module.choose_diplomatic_target(clan_name, sim_year, want_war=True, rng=rng)
    if not target:
        return
    diplomacy.set_status(clan_name, target, diplomacy.STATUS_AT_WAR, sim_year, note="formal declaration of war")
    diplomacy.record_event(clan_name, target, sim_year, "war_declared", grudge_delta=6,
                            note=f"{clan_name} declared war on {target}")
    _log(sim_year, sim_day, "POLITICAL", "major", [clan_name, target],
         f"{clan_name} {nar.conjugate(clan_name, 'Declare', 'Declares')} War on {target}",
         f"The {clan_name} {nar.conjugate(clan_name, 'have', 'has')} formally declared war on the {target}. Whatever peace existed between them is over.")

    frontier = ai_module.find_war_frontier_region(clan_name, target, rng=rng)
    if frontier:
        _resolve_real_battle(clan_name, target, frontier, sim_year, sim_day, rng, declared_war=True)


def _handle_seek_alliance(clan_name, clan_state, sim_year, sim_day, rng):
    target = ai_module.choose_diplomatic_target(clan_name, sim_year, want_war=False, rng=rng)
    if not target:
        return
    status = diplomacy.get_status(clan_name, target)
    if status == diplomacy.STATUS_ALLY:
        return
    diplomacy.set_status(clan_name, target, diplomacy.STATUS_ALLY, sim_year, note="alliance formed")
    diplomacy.record_event(clan_name, target, sim_year, "alliance", grudge_delta=-5,
                            note=f"{clan_name} and {target} formed an alliance")
    text = nar.render_political({"clan_a": clan_name, "clan_b": target}, rng, kind="alliance_formed")
    _log(sim_year, sim_day, "POLITICAL", "major", [clan_name, target],
         f"{clan_name} and {target} Form an Alliance", text)


def _handle_betray_alliance(clan_name, clan_state, sim_year, sim_day, rng):
    if not diplomacy.betrayal_allowed(clan_name):
        return
    allies = [c for c in clans_module.CLAN_NAMES
              if c != clan_name and diplomacy.get_status(clan_name, c) == diplomacy.STATUS_ALLY]
    if not allies:
        return
    target = rng.choice(allies)
    diplomacy.set_status(clan_name, target, diplomacy.STATUS_COLD_WAR, sim_year, note="alliance betrayed")
    diplomacy.record_event(clan_name, target, sim_year, "betrayal", grudge_delta=25,
                            note=f"{clan_name} betrayed their alliance with {target}")
    text = nar.render_betrayal({"clan_a": target, "clan_b": clan_name}, rng, kind="alliance_broken")
    _log(sim_year, sim_day, "BETRAYAL", "major", [clan_name, target],
         f"{clan_name} {nar.conjugate(clan_name, 'Betray', 'Betrays')} Their Alliance with {target}", text)


# ---------------------------------------------------------------------------
# CLAN-SPECIAL ACTIONS
# ---------------------------------------------------------------------------
def _special_void_assassinate(clan_name, clan_state, sim_year, sim_day, rng):
    target_clan = ai_module.choose_diplomatic_target(clan_name, sim_year, want_war=True, rng=rng)
    if not target_clan:
        return
    victim = ai_module.choose_assassination_target(target_clan, rng=rng)
    if not victim:
        return
    protection = ai_module.assassination_protection_level(victim, target_clan)
    success = rng.random() > protection

    if target_clan == "Aura Knights":
        # Honor Bound: any assassination attempt on them triggers immediate
        # blood war and a morale bonus, regardless of success.
        diplomacy.set_status(clan_name, target_clan, diplomacy.STATUS_BLOOD_WAR, sim_year,
                              note="assassination attempt against the Aura Knights")
        diplomacy.record_event(clan_name, target_clan, sim_year, "assassination_attempt", grudge_delta=30,
                                note=f"Void Reapers targeted {victim['name']}")
        text = (f"An assassin from the Hollow tried to reach {victim['name']} in the night. The Aura Knights "
                f"do not forgive this, and do not forget it — blood war has been declared, and the Order's "
                f"morale has only hardened in response.")
        _log(sim_year, sim_day, "BETRAYAL", "catastrophic", [clan_name, target_clan],
             "An Assassin in the Dark", text)
        if success:
            characters_module.kill_character(victim, "found dead before dawn, no mark of struggle visible", sim_year)
            db.update_character(victim["id"], status=victim["status"], death_year=sim_year, notable_deeds=victim["notable_deeds"])
        return

    if success:
        characters_module.kill_character(victim, "found dead, with no sign of how the killer entered", sim_year)
        db.update_character(victim["id"], status=victim["status"], death_year=sim_year, notable_deeds=victim["notable_deeds"])
        diplomacy.record_event(clan_name, target_clan, sim_year, "assassination", grudge_delta=20,
                                note=f"Void Reapers assassinated {victim['name']}")
        text = nar.render_character_death({"character_name": victim["name"], "clan": target_clan,
                                            "death_cause": "found dead with no trace of how the killer entered or left",
                                            "age_at_death": sim_year - victim["birth_year"]}, rng)
        _log(sim_year, sim_day, "BETRAYAL", "major", [clan_name, target_clan],
             f"{victim['name']} Is Dead", text)
        if victim["role"] == characters_module.ROLE_SUPREME_LEADER:
            roster = db.get_characters_by_clan(target_clan, alive_only=True)
            successor = characters_module.succession_pick(roster)
            if successor:
                db.update_character(successor["id"], role=successor["role"])
    else:
        diplomacy.record_event(clan_name, target_clan, sim_year, "assassination_attempt", grudge_delta=8,
                                note=f"failed attempt on {victim['name']}")
        text = (f"Something moved in the shadows near {victim['name']} — and then it was gone. The {target_clan} "
                f"{nar.conjugate(target_clan, 'increase', 'increases')} their guard, certain the Void Reapers will try again.")
        _log(sim_year, sim_day, "BETRAYAL", "minor", [clan_name, target_clan],
             "A Shadow in the Dark, and Nothing More", text)


def _special_stone_geological(clan_name, clan_state, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    region = rng.choice(owned)
    db.update_region_owner(region["id"], clan_name, region["population_density"], min(9, region["fortification"] + 2))
    text = (f"The ground beneath {region['name']} shifted at the Stone Covenant's command, raising new stone "
            f"defenses where there had been none. The mountains, once again, did exactly as asked.")
    _log(sim_year, sim_day, "NATURAL", "minor", [clan_name],
         f"Stone Covenant Reshapes {region['name']}", text, region_id=region["id"])


def _special_arcane_mass_spell(clan_name, clan_state, sim_year, sim_day, rng):
    if diplomacy.is_diplomatic_moratorium(sim_year):
        return  # Rule 4: no full military engagements before Year 50
    target_clan = ai_module.choose_diplomatic_target(clan_name, sim_year, want_war=True, rng=rng)
    if not target_clan:
        return
    frontier = ai_module.find_war_frontier_region(clan_name, target_clan, rng=rng)
    if not frontier:
        return
    _resolve_real_battle(clan_name, target_clan, frontier, sim_year, sim_day, rng)


def _special_sylvan_terrain_claim(clan_name, clan_state, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    sample = rng.sample(owned, min(80, len(owned)))
    claimed = None
    for region in sample:
        for nid in world_module.neighbors_of(region["id"]):
            neighbor = db.get_region(nid)
            if neighbor and neighbor["owner_clan"] is None and neighbor["biome"] in ("Forest", "Swamp"):
                claimed = neighbor
                break
        if claimed:
            break
    if not claimed:
        return
    db.update_region_owner(claimed["id"], clan_name, rng.randint(20, 60), 0)
    text = (f"The forest itself crept forward at {claimed['name']}, and what was wild ground yesterday answers "
            f"to the Sylvan Circle today. No army marched. None was needed.")
    _log(sim_year, sim_day, "DISCOVERY", "minor", [clan_name],
         f"The Forest Claims {claimed['name']}", text, region_id=claimed["id"])


def _special_iron_build_machine(clan_name, clan_state, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    sample = rng.sample(owned, min(6, len(owned)))
    for region in sample:
        db.update_region_owner(region["id"], clan_name, region["population_density"], min(9, region["fortification"] + 2))
    text = ("New war machines roll out from the Covenant's forge-cities — siege engines, ironclad walls, "
            "and the quiet promise that whoever comes for Iron Covenant territory will pay for every yard.")
    _log(sim_year, sim_day, "EVOLUTION", "minor", [clan_name], f"{clan_name} {nar.conjugate(clan_name, 'Unveil', 'Unveils')} New War Machines", text)


def _special_aura_challenge_trial(clan_name, clan_state, sim_year, sim_day, rng):
    target_clan = ai_module.choose_diplomatic_target(clan_name, sim_year, want_war=False, rng=rng)
    if not target_clan:
        return
    our_champion = _general_name(clan_name, rng)
    their_champion = _general_name(target_clan, rng)
    aura_wins = rng.random() < 0.55  # Radiant Discipline gives a slight edge in single combat too
    winner = clan_name if aura_wins else target_clan
    loser = target_clan if aura_wins else clan_name
    diplomacy.record_event(clan_name, target_clan, sim_year, "trial",
                            grudge_delta=-3 if aura_wins else 2,
                            note=f"Trial by combat: {our_champion} vs {their_champion}")
    text = (f"{our_champion} of the Aura Knights issued a formal Challenge to the Trial against {their_champion} "
            f"of the {target_clan} — honor-bound combat, witnessed by both clans, with no army committed to the "
            f"outcome. {winner} prevailed. {loser} accepted the result without contesting it, as custom demands.")
    _log(sim_year, sim_day, "CHARACTER", "minor", [clan_name, target_clan],
         f"Challenge to the Trial: {our_champion} vs {their_champion}", text)


SPECIAL_HANDLERS = {
    "Void Reapers": _special_void_assassinate,
    "Stone Covenant": _special_stone_geological,
    "Arcane Conclave": _special_arcane_mass_spell,
    "Sylvan Circle": _special_sylvan_terrain_claim,
    "Iron Covenant": _special_iron_build_machine,
    "Aura Knights": _special_aura_challenge_trial,
}


DECISION_HANDLERS = {
    "EXPAND": _handle_expand,
    "FORTIFY": _handle_fortify,
    "RESEARCH": _handle_research,
    "RECRUIT": _handle_recruit,
    "RAID": _handle_raid,
    "DECLARE_WAR": _handle_declare_war,
    "SEEK_ALLIANCE": _handle_seek_alliance,
    "BETRAY_ALLIANCE": _handle_betray_alliance,
}


def process_clan_turn(clan_name, sim_year, sim_day, rng=None):
    rng = rng or random
    clan_state = db.get_clan(clan_name)
    if not clan_state or clan_state["is_eliminated"]:
        return

    decision = ai_module.decide_action(clan_name, clan_state, sim_year, rng=rng)

    if decision in ("SPECIAL", "DECLARE_WAR", "BETRAY_ALLIANCE"):
        clan_state["extra_state"]["last_dramatic_action_year"] = sim_year
        db.upsert_clan(clan_state)

    if decision == "SPECIAL":
        handler = SPECIAL_HANDLERS.get(clan_name)
        if handler:
            handler(clan_name, clan_state, sim_year, sim_day, rng)
    else:
        handler = DECISION_HANDLERS.get(decision)
        if handler:
            handler(clan_name, clan_state, sim_year, sim_day, rng)

    check_evolution_milestone(clan_name, sim_year, sim_day, rng)


# ---------------------------------------------------------------------------
# EVOLUTION MILESTONES
# ---------------------------------------------------------------------------
def check_evolution_milestone(clan_name, sim_year, sim_day, rng=None):
    rng = rng or random
    clan_state = db.get_clan(clan_name)
    if not clan_state or clan_state["is_eliminated"]:
        return
    result = evolution.check_for_evolution(clan_state, sim_year)
    if result:
        clan_state["evolution_index"] = result["index"]
        db.upsert_clan(clan_state)
        stage = result["stage"]
        text = nar.render_evolution({
            "clan": clan_name, "stage_name": stage["stage"], "stage_description": stage["desc"],
        }, rng)
        unlock_note = evolution.evolution_unlocks_summary(clan_name, result["index"])
        if unlock_note:
            text += f" {unlock_note}"
        _log(sim_year, sim_day, "EVOLUTION", "major", [clan_name],
             f"{clan_name} {nar.conjugate(clan_name, 'Reach', 'Reaches')} {stage['stage']}", text)


# ---------------------------------------------------------------------------
# AMBIENT / RANDOM FLAVOR EVENTS
# ---------------------------------------------------------------------------
DISASTER_BIOME_HINTS = {
    "earthquake": None, "wildfire": ["Forest", "Plains"], "flood": ["Coastal", "Swamp", "Plains"],
    "magical storm": ["Ethereal Wastes", "Mountain"], "volcanic eruption": ["Volcanic"],
    "blizzard": ["Arctic"], "beast migration": None, "climate shift": None,
}


def _attempt_discovery(clan_name, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    region = rng.choice(owned)
    explorer = _general_name(clan_name, rng) if rng.random() < 0.3 else characters_module.generate_name(clan_name, rng)
    rare_resource = None
    if region["is_rare_node"] and clan_name not in region["rare_node_discovered_by"]:
        rare_resource = region["rare_node_resource"]
        discovered = region["rare_node_discovered_by"] + [clan_name]
        conn_update = db.get_region(region["id"])  # ensure freshest
        import json as _json
        db_conn = db.get_connection()
        db_conn.execute("UPDATE regions SET rare_node_discovered_by=? WHERE id=?",
                         (_json.dumps(discovered), region["id"]))
        db_conn.commit()

    ctx = {"clan": clan_name, "explorer": explorer, "region_name": region["name"], "biome": region["biome"]}
    if region["resources"]:
        ctx["resource"] = rng.choice(region["resources"])
    if rare_resource:
        ctx["discovery_name"] = f"a hidden vein of {rare_resource}"
        ctx["discovery_impact"] = "This is the kind of find that changes a clan's fortunes for a generation."
    text = nar.render_discovery(ctx, rng)
    severity = "major" if rare_resource else "minor"
    _log(sim_year, sim_day, "DISCOVERY", severity, [clan_name],
         f"{clan_name} {nar.conjugate(clan_name, 'Make', 'Makes')} a Discovery at {region['name']}", text, region_id=region["id"])


def _attempt_disaster(clan_name, sim_year, sim_day, rng, severity="minor"):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    region = rng.choice(owned)
    clan_state = db.get_clan(clan_name)
    # Disasters are meant to be narrative texture, not the dominant force in
    # a clan's population trajectory — at the rate these ambient rolls fire
    # over a year, even a "small" percentage compounds fast, so the per-event
    # impact here is deliberately light. Catastrophic rolls hit harder.
    loss_range = (0.0005, 0.004) if severity == "minor" else (0.002, 0.01)
    pop_loss = int(clan_state["population"] * rng.uniform(*loss_range))
    clan_state["population"] = max(0, clan_state["population"] - pop_loss)
    _persist(clan_state, sim_year, rng)
    text = nar.render_disaster({"clan": clan_name, "region_name": region["name"]}, rng)
    _log(sim_year, sim_day, "NATURAL", severity, [clan_name],
         f"Disaster Strikes {region['name']}", text, region_id=region["id"])


def _attempt_character_event(clan_name, sim_year, sim_day, rng):
    roster = db.get_characters_by_clan(clan_name, alive_only=True)
    if not roster:
        return
    roll = rng.random()
    if roll < 0.4:
        # birth
        new_char = characters_module.new_character(clan_name, characters_module.ROLE_INNOVATOR, sim_year, rng)
        new_char["role"] = "CITIZEN"
        db.insert_character(new_char)
        text = nar.render_character_birth({"clan": clan_name, "character_name": new_char["name"]}, rng)
        _log(sim_year, sim_day, "CHARACTER", "minor", [clan_name], f"A Birth Among the {clan_name}", text)
    elif roll < 0.75:
        # aging death check across the roster
        candidate = rng.choice(roster)
        age = characters_module.age_of(candidate, sim_year)
        if rng.random() < characters_module.death_of_old_age_chance(age):
            characters_module.kill_character(candidate, "of old age, surrounded by what family remained", sim_year)
            db.update_character(candidate["id"], status=candidate["status"], death_year=sim_year,
                                 notable_deeds=candidate["notable_deeds"])
            text = nar.render_character_death({"character_name": candidate["name"], "clan": clan_name,
                                                "death_cause": "of old age", "age_at_death": age}, rng)
            severity = "major" if candidate["role"] == characters_module.ROLE_SUPREME_LEADER else "minor"
            _log(sim_year, sim_day, "CHARACTER", severity, [clan_name], f"{candidate['name']} Has Died", text)
            if candidate["role"] == characters_module.ROLE_SUPREME_LEADER:
                successor = characters_module.succession_pick(roster)
                if successor:
                    db.update_character(successor["id"], role=successor["role"])
    else:
        # legendary promotion, rare
        candidate = rng.choice(roster)
        if not candidate["is_legendary"] and candidate["role"] in (characters_module.ROLE_GENERAL, characters_module.ROLE_CHAMPION):
            if rng.random() < 0.1:
                characters_module.mark_legendary(candidate, f"Year {sim_year}: deeds too great for ordinary record-keeping.")
                db.update_character(candidate["id"], is_legendary=True, notable_deeds=candidate["notable_deeds"])
                text = nar.render_character_legendary({"clan": clan_name, "character_name": candidate["name"]}, rng)
                _log(sim_year, sim_day, "CHARACTER", "major", [clan_name], f"{candidate['name']} Becomes Legendary", text)


def _attempt_wonder(clan_name, sim_year, sim_day, rng):
    owned = db.get_regions_owned_by(clan_name)
    if not owned:
        return
    region = rng.choice(owned)
    wonder_names = {
        "Aura Knights": "The Radiant Spire", "Arcane Conclave": "The Unbound Archive",
        "Iron Covenant": "The Undying Forge", "Sylvan Circle": "The First Root Sanctum",
        "Void Reapers": "The Hollow Monument", "Stone Covenant": "The Foundation Cairn",
    }
    text = nar.render_wonder({"clan": clan_name, "wonder_name": wonder_names.get(clan_name, "a great wonder"),
                               "region_name": region["name"]}, rng)
    _log(sim_year, sim_day, "WONDER", "major", [clan_name],
         f"{clan_name} {nar.conjugate(clan_name, 'Raise', 'Raises')} {wonder_names.get(clan_name, 'a Wonder')}", text, region_id=region["id"])


def _attempt_cross_clan_event(sim_year, sim_day, rng):
    alive = [c for c in clans_module.CLAN_NAMES if not (db.get_clan(c) or {}).get("is_eliminated", True)]
    if len(alive) < 2:
        return
    a, b = rng.sample(alive, 2)
    status = diplomacy.get_status(a, b)
    if status == diplomacy.STATUS_NEUTRAL and diplomacy.get_grudge(a, b) == 0:
        # treat as a potential first-contact flavor moment
        text = (f"Scouts from the {a} and the {b} crossed paths for what may be the first time either "
                f"clan has had direct contact with the other. Neither side moved against the other — yet.")
        _log(sim_year, sim_day, "POLITICAL", "minor", [a, b], f"First Contact: {a} and {b}", text)
    else:
        roll = rng.random()
        if roll < 0.5:
            _handle_raid(a, db.get_clan(a), sim_year, sim_day, rng)
        else:
            _handle_seek_alliance(a, db.get_clan(a), sim_year, sim_day, rng)


# ---------------------------------------------------------------------------
# DEMOGRAPHIC GROWTH — tied to elapsed time, not to AI decisions
# ---------------------------------------------------------------------------
# Annual growth rates. These are deliberately modest (real historical
# population growth rarely exceeds a few percent a year) — AI decisions
# (EXPAND, RECRUIT, RAID) influence territory, military readiness, and
# resource theft, but population itself grows on its own clock so a clan
# that happens to roll RECRUIT often doesn't snowball into the billions.
ANNUAL_GROWTH_RATE = {
    "Aura Knights": 0.032,
    "Arcane Conclave": 0.032 * 0.40,   # Slow Blood: 40% of normal rate — meant to stay small/fragile
    "Iron Covenant": 0.032 * 1.25,     # The Workforce: +25%
    "Sylvan Circle": 0.028,
    "Void Reapers": 0.022,             # also soft-capped below — Population Cap
    "Stone Covenant": 0.018,           # ancient, slow-changing, Weight of Ages
}
VOID_REAPER_POP_PER_TERRITORY = 300  # soft population ceiling scales with territory held


def apply_daily_growth(clan_name, sim_year, rng=None):
    rng = rng or random
    clan_state = db.get_clan(clan_name)
    if not clan_state or clan_state["is_eliminated"]:
        return

    annual_rate = ANNUAL_GROWTH_RATE.get(clan_name, 0.015)
    daily_rate = (1.0 + annual_rate) ** (1.0 / 365.0) - 1.0
    daily_rate *= rng.uniform(0.7, 1.3)  # day-to-day noise

    if clan_state["extra_state"].get("cornered"):
        daily_rate *= 0.4  # hard to grow population while fighting for survival
    if sim_year < clan_state["extra_state"].get("recruitment_boost_until", 0):
        daily_rate *= 1.15

    new_pop = clan_state["population"] * (1.0 + daily_rate)

    if clan_name == "Void Reapers":
        cap = max(clan_state["territory_count"] * VOID_REAPER_POP_PER_TERRITORY, 25000)
        if new_pop > cap:
            new_pop = clan_state["population"] + (cap - clan_state["population"]) * 0.05

    clan_state["population"] = max(0, int(new_pop))
    _persist(clan_state, sim_year, rng)


def apply_daily_growth_all_clans(sim_year, rng=None):
    rng = rng or random
    for clan_name in clans_module.CLAN_NAMES:
        apply_daily_growth(clan_name, sim_year, rng)


def roll_ambient_events(sim_year, sim_day, rng=None):
    rng = rng or random
    for clan_name in clans_module.CLAN_NAMES:
        clan_state = db.get_clan(clan_name)
        if not clan_state or clan_state["is_eliminated"]:
            continue

        if rng.random() < config.EVENT_CHANCE_MINOR:
            roll = rng.random()
            if roll < 0.45:
                _attempt_discovery(clan_name, sim_year, sim_day, rng)
            elif roll < 0.82:
                _attempt_character_event(clan_name, sim_year, sim_day, rng)
            else:
                _attempt_disaster(clan_name, sim_year, sim_day, rng, severity="minor")

        if rng.random() < config.EVENT_CHANCE_MAJOR:
            roll = rng.random()
            if roll < 0.5:
                _attempt_wonder(clan_name, sim_year, sim_day, rng)
            else:
                _attempt_character_event(clan_name, sim_year, sim_day, rng)

        if rng.random() < config.EVENT_CHANCE_CATASTROPHIC:
            _attempt_disaster(clan_name, sim_year, sim_day, rng, severity="catastrophic")

    if rng.random() < config.EVENT_CHANCE_CROSS_CLAN:
        _attempt_cross_clan_event(sim_year, sim_day, rng)
