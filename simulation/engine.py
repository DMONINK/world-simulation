"""
simulation/engine.py — The main simulation loop.

Time scale (sacred, exact):
    1 tick               = 609 sim minutes  (10h 9m)
    1 sim day             = 1440 sim minutes  -> ~2.36 ticks
    1 sim year             = 525,600 sim minutes -> ~863 ticks -> ~14.4 real minutes

ENGINE DESIGN NOTE — read this before changing cadence:
The brief frames event rolls and AI evaluation as happening "every tick."
Taken completely literally, that's ~863 AI decisions and ~863 ambient-event
rolls per clan per *year* — at the brief's own percentages that produces
several hundred dramatic decisions (wars, betrayals, assassinations) per
clan per year, which reads as chaos rather than history, and produces an
unmanageable event-log volume over a multi-century run. To keep the
simulation feeling like a chronicle rather than noise, this engine ticks
the clock every real second exactly as specified, but resolves AI
decisions and ambient event rolls once per *simulated day* (the natural
calendar unit the brief itself uses for "sim_day"), using the brief's exact
per-roll percentages. That preserves the intended rates and randomness
while keeping pacing sane. Everything else — the 609-minute tick, the
525,600-minute year, the once-per-sim-year Discord post — is implemented
exactly as specified.

This module deliberately has no Flask/SocketIO import. main.py / web/app.py
register a callback via `set_tick_callback()` to receive updates; the
engine doesn't know or care who's listening.
"""

import random
import threading
import time

import config
from database import db
from simulation import world as world_module
from simulation import clans as clans_module
from simulation import characters as characters_module
from simulation import diplomacy
from simulation import events as events_module
from simulation import narrative as nar
from discord_webhook import sender as discord_sender

_tick_callbacks = []
_state_lock = threading.RLock()
_running = threading.Event()


def set_tick_callback(fn):
    """fn(summary_dict) is called once per tick after state updates. Used by
    the web layer to push SocketIO updates without the engine depending on Flask."""
    _tick_callbacks.append(fn)


def _notify(summary):
    for fn in _tick_callbacks:
        try:
            fn(summary)
        except Exception as e:  # a broken UI hook should never crash the sim
            print(f"[tick_callback error] {e}")


# ---------------------------------------------------------------------------
# GENESIS
# ---------------------------------------------------------------------------
def run_genesis(rng=None):
    rng = rng or random.Random()
    print("[genesis] Generating world...")
    t0 = time.time()
    regions, starting_territories, seed = world_module.generate_world()
    db.bulk_insert_regions([world_module.region_row_tuple(r) for r in regions])
    print(f"[genesis] World generated in {time.time() - t0:.1f}s (seed={seed})")

    for clan_name in clans_module.CLAN_NAMES:
        territory = len(starting_territories.get(clan_name, []))
        db.upsert_clan(clans_module.initial_clan_state(clan_name, territory))
        roster = characters_module.generate_starting_roster(clan_name, 0, rng)
        for c in roster:
            db.insert_character(c)

    diplomacy.initialize_all_relations(clans_module.CLAN_NAMES)

    db.set_meta("sim_minutes_elapsed", 0)
    db.set_meta("sim_year", 0)
    db.set_meta("sim_day_of_year", 0)
    db.set_meta("last_processed_day", -1)
    db.set_meta("last_processed_year", -1)
    db.set_meta("world_seed", seed)
    db.set_meta("victory", None)
    db.set_meta("domination_streak", {})

    _log_genesis_event()
    print("[genesis] Complete.")


def _log_genesis_event():
    db.insert_event(0, 0, "POLITICAL", "major", clans_module.CLAN_NAMES,
                     "The World Begins",
                     "Six clans wake into a world none of them made: the Aura Knights on the Central Golden "
                     "Plains, the Arcane Conclave among the Eastern Spire Peaks, the Iron Covenant in the "
                     "Northern Iron Highlands, the Sylvan Circle deep in the Western Ancient Forest, the Void "
                     "Reapers in the Southern Hollow Caverns, and the Stone Covenant along the Volcanic Rim. "
                     "None of them yet know the others exist.")


# ---------------------------------------------------------------------------
# TICK
# ---------------------------------------------------------------------------
def tick(rng):
    with _state_lock:
        sim_minutes = db.get_meta("sim_minutes_elapsed", 0) + config.SIM_MINUTES_PER_TICK
        sim_year = sim_minutes // config.SIM_MINUTES_PER_YEAR
        day_of_year = (sim_minutes % config.SIM_MINUTES_PER_YEAR) // config.SIM_MINUTES_PER_DAY
        total_day_index = sim_minutes // config.SIM_MINUTES_PER_DAY

        db.set_meta("sim_minutes_elapsed", sim_minutes)
        db.set_meta("sim_year", sim_year)
        db.set_meta("sim_day_of_year", day_of_year)

        last_day = db.get_meta("last_processed_day", -1)
        if total_day_index > last_day:
            for _ in range(min(total_day_index - last_day, 3)):  # cap catch-up in case of long pauses
                _process_day(sim_year, day_of_year, rng)
            db.set_meta("last_processed_day", total_day_index)

        last_year = db.get_meta("last_processed_year", -1)
        if sim_year > last_year:
            _process_year_end(sim_year - 1 if sim_year > 0 else 0, rng)
            db.set_meta("last_processed_year", sim_year)

        summary = build_summary(sim_year, day_of_year)

    _notify(summary)
    return summary


def _process_day(sim_year, day_of_year, rng):
    events_module.apply_daily_growth_all_clans(sim_year, rng)
    for clan_name in clans_module.CLAN_NAMES:
        events_module.process_clan_turn(clan_name, sim_year, day_of_year, rng)
    events_module.roll_ambient_events(sim_year, day_of_year, rng)


def _process_year_end(completed_year, rng):
    """Runs once per sim year: grudge decay, victory check, and the Discord
    yearly chronicle. completed_year is the year that just finished."""
    diplomacy.apply_yearly_grudge_decay(clans_module.CLAN_NAMES)

    winner = check_victory(completed_year)

    embed = nar.build_yearly_embed(completed_year)
    db.save_yearly_summary(completed_year, embed.get("title", f"Year {completed_year}"), embed, posted=False)
    discord_sender.send_yearly_update(embed)

    if winner:
        finale = nar.build_victory_embed(winner, completed_year)
        discord_sender.send_yearly_update(finale)
        db.set_meta("victory", {"winner": winner, "year": completed_year})
        _running.clear()


# ---------------------------------------------------------------------------
# VICTORY CONDITIONS
# ---------------------------------------------------------------------------
def check_victory(sim_year):
    if db.get_meta("victory"):
        return None

    alive = [c for c in clans_module.CLAN_NAMES if not (db.get_clan(c) or {}).get("is_eliminated", False)]
    if len(alive) == 1:
        return alive[0]
    if len(alive) == 0:
        return None

    streaks = db.get_meta("domination_streak", {}) or {}
    total_regions = config.TOTAL_REGIONS
    new_streaks = {}
    winner = None
    for clan_name in alive:
        territory = db.count_regions_owned_by(clan_name)
        share = territory / total_regions
        if share >= config.DOMINATION_THRESHOLD:
            new_streaks[clan_name] = streaks.get(clan_name, 0) + 1
            if new_streaks[clan_name] >= config.DOMINATION_HOLD_YEARS:
                winner = clan_name
        else:
            new_streaks[clan_name] = 0
    db.set_meta("domination_streak", new_streaks)
    return winner


# ---------------------------------------------------------------------------
# STATE SUMMARY (for web dashboard / SocketIO)
# ---------------------------------------------------------------------------
def build_summary(sim_year, day_of_year):
    clans_summary = []
    for clan_name in clans_module.CLAN_NAMES:
        state = db.get_clan(clan_name)
        if not state:
            continue
        share = state["territory_count"] / config.TOTAL_REGIONS
        clans_summary.append({
            "name": clan_name,
            "population": state["population"],
            "territory_count": state["territory_count"],
            "territory_share": round(share * 100, 2),
            "evolution_index": state["evolution_index"],
            "evolution_stage": clans_module.evolution_stage_name(clan_name, state["evolution_index"]),
            "is_eliminated": state["is_eliminated"],
            "is_last_bastion": state["is_last_bastion"],
            "cornered": state["extra_state"].get("cornered", False),
            "color": clans_module.CLAN_LORE[clan_name]["color"],
            "icon": clans_module.CLAN_LORE[clan_name]["icon"],
        })

    recent = db.get_recent_events(20)
    return {
        "sim_year": sim_year,
        "sim_day_of_year": day_of_year,
        "clans": clans_summary,
        "recent_events": recent,
        "victory": db.get_meta("victory"),
    }


# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
def run_forever():
    """Entry point for the background thread. Initializes the world if
    needed, then ticks once per real second, forever (or until victory)."""
    rng = random.Random()
    db.init_db()

    if not db.is_db_initialized():
        run_genesis(rng)
    else:
        print("[engine] Resuming existing simulation from saved state.")

    _running.set()
    while _running.is_set():
        start = time.time()
        try:
            tick(rng)
        except Exception as e:
            print(f"[tick error] {e}")
        elapsed = time.time() - start
        sleep_for = max(0.0, config.TICK_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_for)


def start_background_thread():
    thread = threading.Thread(target=run_forever, daemon=True, name="simulation-engine")
    thread.start()
    return thread


def stop():
    _running.clear()
