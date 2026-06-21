"""
simulation/diplomacy.py — Alliances, treaties, betrayals, and the relations
ledger between every pair of clans.

Each clan pair has a relationship status (ally / neutral / cold_war /
at_war / blood_war), a grudge score, and a history log. Memory behavior is
clan-specific per the brief:
    - Stone Covenant: permanent grudge weight, never forgets, never forgives betrayal.
    - Aura Knights: moderate memory — grudges fade somewhat over decades.
    - Void Reapers: tactical memory — only cares about utility, grudges decay fast.
    - Arcane Conclave: records everything analytically — full memory, but acts on
      cold calculation rather than emotion.
    - Iron Covenant / Sylvan Circle: standard memory, moderate decay.
"""

from database import db

STATUS_ALLY = "ally"
STATUS_NEUTRAL = "neutral"
STATUS_COLD_WAR = "cold_war"
STATUS_AT_WAR = "at_war"
STATUS_BLOOD_WAR = "blood_war"

# How much a grudge naturally decays per sim year, by clan. Stone Covenant
# decays at 0 — Ancestral Memory means betrayal is never forgiven.
GRUDGE_DECAY_PER_YEAR = {
    "Stone Covenant": 0.0,
    "Aura Knights": 0.4,
    "Void Reapers": 1.5,       # tactical memory — only utility matters
    "Arcane Conclave": 0.1,    # records everything, barely decays, but acts coldly
    "Iron Covenant": 0.6,
    "Sylvan Circle": 0.5,
}


def initialize_all_relations(clan_names):
    for i, a in enumerate(clan_names):
        for b in clan_names[i + 1:]:
            existing = db.get_relation(a, b)
            if existing is None:
                db.upsert_relation(a, b, STATUS_NEUTRAL, 0, [])


def record_event(clan_a, clan_b, sim_year, event_type, grudge_delta, note):
    """event_type: 'war', 'betrayal', 'assassination_attempt', 'aid', 'trade', 'alliance'"""
    rel = db.get_relation(clan_a, clan_b) or {"status": STATUS_NEUTRAL, "grudge_score": 0, "history": []}
    history = rel["history"]
    history.append({"year": sim_year, "type": event_type, "note": note})
    new_grudge = rel["grudge_score"] + grudge_delta
    db.upsert_relation(clan_a, clan_b, rel["status"], new_grudge, history)


def set_status(clan_a, clan_b, new_status, sim_year, note=""):
    rel = db.get_relation(clan_a, clan_b) or {"grudge_score": 0, "history": []}
    history = rel["history"]
    if note:
        history.append({"year": sim_year, "type": "status_change", "note": note})
    db.upsert_relation(clan_a, clan_b, new_status, rel["grudge_score"], history)


def get_status(clan_a, clan_b):
    rel = db.get_relation(clan_a, clan_b)
    return rel["status"] if rel else STATUS_NEUTRAL


def get_grudge(clan_a, clan_b):
    rel = db.get_relation(clan_a, clan_b)
    return rel["grudge_score"] if rel else 0


def apply_yearly_grudge_decay(clan_names):
    """Called once per sim year. Each clan pair's grudge decays toward zero
    at a rate determined by whichever clan in the pair has the *slower*
    decay (the more grudge-holding clan sets the pace — Stone Covenant
    never lets a grudge go, no matter who they're paired with)."""
    for rel in db.get_all_relations():
        a, b = rel["clan_a"], rel["clan_b"]
        decay_rate = min(GRUDGE_DECAY_PER_YEAR.get(a, 0.5), GRUDGE_DECAY_PER_YEAR.get(b, 0.5))
        grudge = rel["grudge_score"]
        if grudge > 0:
            grudge = max(0, grudge - decay_rate)
        elif grudge < 0:
            grudge = min(0, grudge + decay_rate)
        db.upsert_relation(a, b, rel["status"], grudge, rel["history"])


def is_diplomatic_moratorium(sim_year):
    import config
    return sim_year < config.DIPLOMATIC_MORATORIUM_END_YEAR


def can_declare_war(clan_a, clan_b, sim_year):
    """Border skirmishes/raids are always allowed; formal DECLARE_WAR is
    gated by the Diplomatic Moratorium (Rule 4)."""
    return not is_diplomatic_moratorium(sim_year)


def betrayal_allowed(clan_name):
    """Stone Covenant is incapable of betraying an alliance (BETRAY_ALLIANCE
    weight is 0 in clans.DECISION_WEIGHTS) — Ancestral Memory cuts both ways."""
    return clan_name != "Stone Covenant"


def relationship_label(status):
    return {
        STATUS_ALLY: "Allied",
        STATUS_NEUTRAL: "Neutral",
        STATUS_COLD_WAR: "Cold War",
        STATUS_AT_WAR: "At War",
        STATUS_BLOOD_WAR: "Blood War",
    }.get(status, "Neutral")
