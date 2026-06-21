"""
simulation/narrative.py — Converts raw simulation state into story text.

This is the heart of the "feels like a living world, not a number
generator" requirement. Nothing here should ever read like a battle report.
Every render function below picks from a bank of templates, fills in
clan-flavored language (an Aura Knights battle does not sound like a Void
Reapers battle), and returns prose.

Design:
- Each category (battle, discovery, political, disaster, character,
  betrayal, wonder, evolution) has its own template bank.
- `_SafeDict` lets every template reference any placeholder name freely —
  unresolved placeholders degrade to an empty string instead of crashing,
  so template authors don't have to thread every key through every call.
- `clan_voice()` returns clan-specific verbs/registers so the same
  underlying event (a battle, a discovery) reads differently depending on
  who it happened to.
"""

import random
import re


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


# Some clan names are grammatically plural ("Aura Knights", "Void Reapers")
# and some are singular collectives ("Arcane Conclave", "Iron Covenant",
# "Sylvan Circle", "Stone Covenant"). The possessive form is always
# mechanically fixable (Reapers's -> Reapers'), so that's done globally.
# Verb agreement ("has" vs "have") depends on whether the clan name is
# actually the grammatical subject of that verb in a given sentence, which
# a blanket regex can't reliably tell apart from a clan name that merely
# appears next to an unrelated verb — so verb agreement is instead resolved
# per-template via clan_has()/clan_is(), wherever a clan name is the
# deliberate subject.
PLURAL_CLANS = ("Aura Knights", "Void Reapers")


def _fix_plural_clan_grammar(text):
    for clan in PLURAL_CLANS:
        escaped = re.escape(clan)
        # Possessive: "Void Reapers's" -> "Void Reapers'"
        text = re.sub(rf"\b{escaped}'s\b", f"{clan}'", text)
    return text


def clan_has(clan_name):
    return "have" if clan_name in PLURAL_CLANS else "has"


def clan_is(clan_name):
    return "are" if clan_name in PLURAL_CLANS else "is"


def clan_was(clan_name):
    return "were" if clan_name in PLURAL_CLANS else "was"


def conjugate(clan_name, plural_form, singular_form):
    """Generic verb-agreement helper for ad-hoc text built outside the
    template system, e.g. conjugate(clan_name, 'have', 'has')."""
    return plural_form if clan_name in PLURAL_CLANS else singular_form


def _fmt(template, context):
    rendered = template.format_map(_SafeDict(context))
    return _fix_plural_clan_grammar(rendered)


def _cap(s):
    return s[0].upper() + s[1:] if s else s


def _inject_clan_verbs(context):
    """Populates clan_has / clan_is / clan_was for whichever clan keys are
    present (clan, clan_a, clan_b, attacker, defender) so templates can
    reference {clan_has} etc. without every call site doing it manually."""
    for key in ("clan", "clan_a", "clan_b", "attacker", "defender"):
        if key in context:
            suffix = "" if key == "clan" else f"_{key}"
            context[f"clan_has{suffix}"] = clan_has(context[key])
            context[f"clan_is{suffix}"] = clan_is(context[key])
            context[f"clan_was{suffix}"] = clan_was(context[key])
            context[f"clan_think{suffix}"] = conjugate(context[key], "think", "thinks")
    return context


# ---------------------------------------------------------------------------
# CLAN VOICE — per-clan vocabulary banks used to flavor generic templates.
# ---------------------------------------------------------------------------
CLAN_VOICE = {
    "Aura Knights": {
        "advance_verbs": ["marched", "advanced under banner", "rode out", "answered the muster"],
        "victory_words": ["a hard-won victory", "a triumph paid for in blood", "a battle worthy of song"],
        "defeat_words": ["a defeat that stung deeper than the wounds", "a loss they will not soon forgive themselves for", "a retreat that cost them more pride than ground"],
        "register": "noble and weighty, with an emphasis on honor and cost",
        "place_words": ["the Oath Stone", "the muster fields", "the golden banners"],
    },
    "Arcane Conclave": {
        "advance_verbs": ["calculated the hour and moved", "stepped through a prepared circle", "unveiled a working long in preparation", "arrived precisely when the numbers favored them"],
        "victory_words": ["a victory measured in probabilities collapsed correctly", "an outcome the Conclave had already modeled", "a calculated and total dominance"],
        "defeat_words": ["a result the theorists had not accounted for", "a miscalculation paid for in centuries of accumulated knowledge", "an anomaly the Circle is still trying to explain"],
        "register": "clinical, analytical, faintly alien",
        "place_words": ["the spire-cities", "the ley-line wards", "the Circle's archives"],
    },
    "Iron Covenant": {
        "advance_verbs": ["rolled forward on iron wheels", "deployed at first light", "advanced behind a wall of shields", "marched to the sound of the forge-horns"],
        "victory_words": ["a methodical, grinding victory", "a triumph of production over passion", "a win that the foundries will be proud of"],
        "defeat_words": ["a costly setback that the foundries will avenge in steel", "a loss that will be answered with twice the machines", "a defeat that will not be repeated twice"],
        "register": "practical, industrial, unsentimental",
        "place_words": ["the forge-cities", "the deep works", "the rail yards"],
    },
    "Sylvan Circle": {
        "advance_verbs": ["rose from the undergrowth", "emerged with the dawn mist", "moved as the forest moved", "answered with root and claw"],
        "victory_words": ["a victory the forest will remember", "a triumph the old trees will speak of for a century", "a battle the land itself seemed to fight for them"],
        "defeat_words": ["a wound the forest will need years to heal", "a loss that scarred more than soil", "a grief the groves will carry quietly"],
        "register": "patient, organic, attuned to the land",
        "place_words": ["the deep groves", "the root-paths", "the ancient canopy"],
    },
    "Void Reapers": {
        "advance_verbs": ["were already there before anyone noticed", "moved through the dark between one breath and the next", "had been watching for longer than anyone realized", "slipped past every ward that should have stopped them"],
        "victory_words": ["a victory no one saw coming, including the survivors", "an outcome that was decided before the first blow landed", "a triumph written in silence"],
        "defeat_words": ["a rare and uncomfortable failure", "a loss the Hollow will not speak of again", "a miscalculation in a clan that does not often miscalculate"],
        "register": "cryptic, unsettling, spoken as if from shadow",
        "place_words": ["the Hollow Caverns", "the spaces between", "the dark beneath the world"],
    },
    "Stone Covenant": {
        "advance_verbs": ["began moving years before anyone noticed", "answered, at last, after long deliberation", "arrived as the ground itself seemed to arrive", "had been preparing this for longer than most clans have existed"],
        "victory_words": ["an inevitability, not a surprise", "a victory the mountains themselves seemed to grant", "a triumph as patient and total as erosion"],
        "defeat_words": ["a wound the Covenant will remember for a thousand years", "a loss that will be repaid, eventually, without fail", "a setback measured against the long arc of centuries"],
        "register": "slow, geological, ancient",
        "place_words": ["the deep stone", "the ancestral halls", "the living mountain"],
    },
}


def clan_voice(clan_name):
    return CLAN_VOICE.get(clan_name, CLAN_VOICE["Aura Knights"])


TIME_DESCRIPTORS = [
    "the final days of winter", "the first warm week of spring", "a moonless night",
    "the height of the harvest season", "a week of unbroken rain", "the longest day of the year",
    "the dead of a bitter winter", "a season of strange omens", "the quiet weeks after the thaw",
    "a week no almanac had warned of", "the first frost of the year", "a sky the color of old iron",
    "a summer that refused to end", "the grey hour before dawn", "a year already heavy with rumor",
]

EVOCATIVE_NUMBERS = [
    (50, "a handful"), (200, "a few hundred"), (800, "the better part of a thousand"),
    (1500, "well over a thousand"), (3000, "several thousand"), (6000, "thousands upon thousands"),
    (999999, "a number too large to read aloud without flinching"),
]


def evocative_number(n):
    for threshold, phrase in EVOCATIVE_NUMBERS:
        if n <= threshold:
            return phrase
    return EVOCATIVE_NUMBERS[-1][1]


def generate_battle_name(region_name, rng=None):
    rng = rng or random
    pattern = rng.choice([
        "The Battle of {r}", "The Siege of {r}", "The Burning of {r}", "The Fall of {r}",
        "The Stand at {r}", "The Massacre at {r}", "The Long Night at {r}", "The Breaking of {r}",
    ])
    return pattern.format(r=region_name)


# ---------------------------------------------------------------------------
# BATTLE TEMPLATES (25+)
# ---------------------------------------------------------------------------
BATTLE_TEMPLATES = [
    "{battle_name}, Year {sim_year}. {attacker_strength} {attacker} soldiers {attacker_verb} into {region_name} under {attacker_general}. {outcome_description}. {consequence_line}",
    "Under {time_description}, {attacker_general} led the {attacker_possessive} host into {region_name}, contested by {defender_general} of the {defender}. {outcome_description}. {casualty_line}",
    "{battle_name} lasted {duration}. {casualty_line} {survivor_line}",
    "The {defender} had held {region_name} for generations before the {attacker} {attacker_verb}. {outcome_description}. {consequence_line}",
    "Word reached {defender_general} too late: the {attacker} were already inside {region_name}. {outcome_description}. {casualty_line}",
    "{attacker_general} swore the {attacker} would take {region_name} before the season turned. {outcome_description}. {survivor_line}",
    "Few expected the {attacker} to risk {region_name}. {attacker_general} did so anyway. {outcome_description}. {consequence_line}",
    "{region_name} had never seen war until {attacker_general}'s host arrived. {outcome_description}. {casualty_line}",
    "The {defender_possessive} banners still flew over {region_name} when the {attacker} {attacker_verb}. By the time the dust settled, {outcome_description_lower}. {consequence_line}",
    "{defender_general} dug in at {region_name}, certain the ground favored the {defender}. {outcome_description}. {casualty_line}",
    "It began, as these things often do, with a single scout's report from {region_name}. It ended with {battle_name}. {outcome_description}. {survivor_line}",
    "{attacker_general} had {attacker_strength} {attacker} soldiers and a plan three years in the making for {region_name}. {outcome_description}. {consequence_line}",
    "No herald announced the {attacker_possessive} arrival at {region_name} — only the {defender_possessive} scouts, and then it was too late. {outcome_description}. {casualty_line}",
    "{battle_name} is already being told two different ways: the {attacker_possessive} version, and the truth. {outcome_description}. {survivor_line}",
    "The {defender} called for reinforcements from {region_name}. None arrived in time. {outcome_description}. {consequence_line}",
    "{attacker_general} did not sleep the night before {battle_name}. By morning, it no longer mattered. {outcome_description}. {casualty_line}",
    "Rain turned the fields of {region_name} to mud before the {attacker} ever arrived — and mud, as it turned out, favored no one evenly. {outcome_description}. {survivor_line}",
    "{defender_general} had faced the {attacker} before, at a cost still spoken of. {region_name} would be different — or so {defender_general} believed. {outcome_description}. {consequence_line}",
    "The old maps still call it {region_name}. After {battle_name}, the people who live there call it something else entirely. {outcome_description}. {casualty_line}",
    "{attacker_general} led from the front, against every piece of counsel given. {outcome_description} at {region_name}. {survivor_line}",
    "There was no formal declaration before {battle_name} — only the {attacker}, who {advance_phrase}. {outcome_description}. {consequence_line}",
    "{region_name} sat between two claims for a generation. {battle_name} settled the matter, for now. {outcome_description}. {casualty_line}",
    "{defender_general} had {defender_strength} {defender} defenders and the high ground at {region_name}. It was not enough. {outcome_description}. {survivor_line}",
    "Three signal fires were meant to warn {region_name} of an approach. Only one was ever lit. {outcome_description}. {consequence_line}",
    "{battle_name} will be remembered less for who won and more for what it cost both sides. {casualty_line} {survivor_line}",
    "The {attacker} called it liberation. The {defender} called it {region_name}, and called it home. {outcome_description}. {consequence_line}",
]

OUTCOME_DESCRIPTIONS_ATTACKER_WINS = [
    "The {defender_possessive} line broke before midday, and {region_name} changed hands by nightfall",
    "{attacker_general} walked the captured walls of {region_name} by evening, {victory_phrase}",
    "By the second day, the {defender_possessive} banners had been pulled down across {region_name}",
    "The {defender} fought hard, but {region_name} belonged to the {attacker} before the week was out",
    "What resistance the {defender} mustered at {region_name} was not enough — {victory_phrase}",
]

OUTCOME_DESCRIPTIONS_DEFENDER_WINS = [
    "The {attacker} broke against {region_name}'s defenses and withdrew before nightfall",
    "{defender_general} held {region_name}, and the {attacker} paid for every yard of ground they didn't take",
    "The {attacker_possessive} host shattered at {region_name} — {defeat_phrase}",
    "{region_name} remained in {defender} hands; the {attacker} retreated to lick their wounds",
    "The {attacker} underestimated {region_name}'s defenders, and the field showed it by dusk",
]

CONSEQUENCE_LINES = [
    "{region_name} will not look the same again for a generation.",
    "The grudge this leaves behind will outlast everyone who fought there.",
    "Both clans will tell this story differently for years to come.",
    "Refugees from {region_name} are already moving toward safer ground.",
    "The balance of power in the region has shifted, however slightly.",
    "Word of {battle_name} will reach every settlement within the month.",
    "Neither side has the strength to press the advantage immediately.",
    "This will not be the last time {region_name} is fought over.",
]

CASUALTY_LINE_TEMPLATES = [
    "{evocative_attacker_losses} of the {attacker} did not return; the {defender} lost {evocative_defender_losses}.",
    "The {attacker} buried {evocative_attacker_losses}. The {defender} buried more.",
    "Casualties on both sides were heavy — {evocative_attacker_losses} from the {attacker} alone.",
    "By the most honest count, {evocative_defender_losses} of the {defender_possessive} defenders fell.",
    "Neither clan's chroniclers agree on the dead, but {evocative_attacker_losses} is the number most repeated.",
]

SURVIVOR_LINE_TEMPLATES = [
    "Those who survived will carry {region_name} with them for the rest of their lives.",
    "{attacker_general} aged visibly in the weeks that followed.",
    "Among the dead was a name that will be remembered — and a hundred that won't.",
    "The survivors do not speak of it easily, even now.",
    "Somewhere in the chaos, a soldier no one expected to matter did something that will be sung about for years.",
]


def possessive(name):
    """Grammatically correct possessive for clan names: Knights' vs Conclave's."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def render_battle(context, rng=None):
    """context expects: attacker, defender, attacker_general, defender_general,
    region_name, sim_year, attacker_wins (bool), attacker_strength, defender_strength,
    attacker_losses, defender_losses. Returns prose."""
    rng = rng or random
    av = clan_voice(context["attacker"])
    dv = clan_voice(context["defender"])

    context = dict(context)
    context = _inject_clan_verbs(context)
    context.setdefault("battle_name", generate_battle_name(context["region_name"], rng))
    context.setdefault("time_description", rng.choice(TIME_DESCRIPTORS))
    context.setdefault("duration", rng.choice(["a single brutal afternoon", "three days", "barely an hour", "a week of skirmishes", "a single dreadful night"]))
    context.setdefault("attacker_verb", rng.choice(av["advance_verbs"]))
    context.setdefault("advance_phrase", rng.choice(av["advance_verbs"]))
    context.setdefault("victory_phrase", rng.choice(av["victory_words"]))
    context["attacker_possessive"] = possessive(context["attacker"])
    context["defender_possessive"] = possessive(context["defender"])

    if context.get("attacker_wins"):
        context.setdefault("defeat_phrase", rng.choice(dv["defeat_words"]))
    else:
        # the attacker is the one being repelled in this branch
        context.setdefault("defeat_phrase", rng.choice(av["defeat_words"]))

    outcome_pool = OUTCOME_DESCRIPTIONS_ATTACKER_WINS if context.get("attacker_wins") else OUTCOME_DESCRIPTIONS_DEFENDER_WINS
    outcome = _fmt(rng.choice(outcome_pool), context)
    context["outcome_description"] = outcome
    context["outcome_description_lower"] = outcome[0].lower() + outcome[1:] if outcome else outcome

    context["evocative_attacker_losses"] = evocative_number(context.get("attacker_losses", 0))
    context["evocative_defender_losses"] = evocative_number(context.get("defender_losses", 0))
    context["consequence_line"] = _cap(_fmt(rng.choice(CONSEQUENCE_LINES), context))
    context["casualty_line"] = _cap(_fmt(rng.choice(CASUALTY_LINE_TEMPLATES), context))
    context["survivor_line"] = _cap(_fmt(rng.choice(SURVIVOR_LINE_TEMPLATES), context))

    template = rng.choice(BATTLE_TEMPLATES)
    return _fmt(template, context)


# ---------------------------------------------------------------------------
# DISCOVERY TEMPLATES (15+)
# ---------------------------------------------------------------------------
DISCOVERY_TEMPLATES = [
    "Deep in the {biome} of {region_name}, {explorer} uncovered {discovery_name}. {discovery_impact}",
    "{explorer} had searched {region_name} for {search_duration} before finding {discovery_name}. {discovery_impact}",
    "It was pure chance that led {explorer} to {discovery_name} beneath {region_name}. {discovery_impact}",
    "The {clan} had long suspected something lay beneath {region_name}. {explorer} confirmed it: {discovery_name}. {discovery_impact}",
    "{discovery_name} had waited in {region_name} since long before the {clan} ever arrived. {explorer} was simply the first to notice. {discovery_impact}",
    "Reports of {discovery_name} near {region_name} were dismissed as rumor for years — until {explorer} returned with proof. {discovery_impact}",
    "{explorer}'s expedition into {region_name} was meant to map the terrain. Instead, they found {discovery_name}. {discovery_impact}",
    "What {explorer} found in {region_name} will change how the {clan} {clan_think} about {biome} terrain entirely: {discovery_name}. {discovery_impact}",
    "The {clan}'s scholars had theorized about {discovery_name} for a generation. {explorer} finally proved them right, in {region_name}. {discovery_impact}",
    "{region_name} gave up its secret reluctantly. {explorer} nearly didn't survive finding {discovery_name}. {discovery_impact}",
    "No one was looking for {discovery_name}. {explorer} found it anyway, in the most unlikely corner of {region_name}. {discovery_impact}",
    "{discovery_name}, hidden in {region_name} for longer than anyone can say, is now the {clan}'s to claim. {discovery_impact}",
    "It took {explorer} three attempts and one broken leg, but {region_name} finally yielded {discovery_name}. {discovery_impact}",
    "The {clan} sent {explorer} into {region_name} expecting nothing. They returned with {discovery_name}. {discovery_impact}",
    "{discovery_name} does not appear on any map of {region_name} — not yet. {explorer} is already working to change that. {discovery_impact}",
]

DISCOVERY_IMPACT_LINES = [
    "The {clan} will be stronger for it.",
    "Word is already spreading faster than the {clan} would like.",
    "Other clans will want to know how this was found.",
    "It will take years to understand what this truly means.",
    "For now, the {clan} {clan_is} keeping the details close.",
    "This alone may shift the balance of power in {region_name}.",
    "Not everyone in the {clan} is celebrating — some fear what it might attract.",
]

DISCOVERY_NAME_BANK = [
    "a vein of untouched {resource}", "an artifact no living scholar can identify", "ruins older than any clan's founding",
    "a sealed chamber that should not have been breachable", "a creature no bestiary describes",
    "a cache of {resource} far larger than expected", "an inscription written in no known tongue",
    "a structure that seems to predate the world's current shape", "a spring that runs the wrong color",
    "remains of a settlement no one has a record of", "a working device of unknown purpose",
]


def render_discovery(context, rng=None):
    rng = rng or random
    context = dict(context)
    context = _inject_clan_verbs(context)
    context.setdefault("search_duration", rng.choice(["weeks", "months", "the better part of a year", "three full seasons"]))
    context.setdefault("resource", rng.choice(["valuable ore", "untouched timber", "raw stone", "strange crystal"]))
    if "discovery_name" not in context:
        name_template = rng.choice(DISCOVERY_NAME_BANK)
        context["discovery_name"] = _fmt(name_template, context)
    context["discovery_impact"] = _cap(_fmt(rng.choice(DISCOVERY_IMPACT_LINES), context))
    template = rng.choice(DISCOVERY_TEMPLATES)
    return _fmt(template, context)


# ---------------------------------------------------------------------------
# POLITICAL TEMPLATES (12+)
# ---------------------------------------------------------------------------
POLITICAL_TEMPLATES = {
    "succession": [
        "{character_name} has been named {title} of the {clan}, succeeding a line that stretches back generations. {political_impact}",
        "A coup within the {clan} has placed {character_name} in power, displacing the previous leadership without bloodshed — this time. {political_impact}",
    ],
    "death": [
        "The {clan} mourns {character_name}, {title}, who has died after {reign_duration} of leadership. {political_impact}",
        "A succession crisis grips the {clan} after {character_name}'s sudden death left no clear heir. {political_impact}",
    ],
    "alliance_formed": [
        "{clan_a} and {clan_b} have formed an alliance, the first formal pact between them in living memory. {political_impact}",
        "Diplomats from {clan_a} were received by {clan_b} this year, and the two clans have agreed to stand together. {political_impact}",
    ],
    "alliance_broken": [
        "The alliance between {clan_a} and {clan_b} has collapsed, and neither side is saying exactly why. {political_impact}",
        "What was once a partnership between {clan_a} and {clan_b} is over, formally and publicly. {political_impact}",
    ],
    "decree": [
        "{character_name} delivered a decree to the {clan} that will reshape policy for a generation. {political_impact}",
        "{character_name}'s speech to the {clan} this year is already being repeated well beyond their borders. {political_impact}",
    ],
    "unrest": [
        "Civil unrest has broken out within {clan} territory, and {character_name} has been forced to respond. {political_impact}",
    ],
    "legendary": [
        "The {clan} {clan_has} formally recognized {character_name} as a legendary figure, the first such honor in years. {political_impact}",
    ],
    "first_contact": [
        "Diplomats from {clan_a} were received by {clan_b} for the first time in this simulation's history — a moment of genuine first contact. {political_impact}",
    ],
}

POLITICAL_IMPACT_LINES = [
    "The other clans are watching closely.",
    "It is too early to say what this will mean.",
    "Some within the clan are uneasy about what comes next.",
    "Trade and travel between the two are expected to follow.",
    "History, if it is kind, will remember this fondly. If not, it won't be remembered at all.",
    "Neighboring clans have taken notice.",
]


def render_political(context, rng=None, kind="decree"):
    rng = rng or random
    context = dict(context)
    context = _inject_clan_verbs(context)
    context.setdefault("reign_duration", rng.choice(["decades", "a single turbulent decade", "nearly half a century", "nearly a century"]))
    context["political_impact"] = rng.choice(POLITICAL_IMPACT_LINES)
    pool = POLITICAL_TEMPLATES.get(kind, POLITICAL_TEMPLATES["decree"])
    template = rng.choice(pool)
    return _fmt(template, context)


# ---------------------------------------------------------------------------
# DISASTER TEMPLATES (8+)
# ---------------------------------------------------------------------------
DISASTER_TEMPLATES = [
    "An earthquake tore through {region_name} this year, and the {clan} {clan_is} still counting what they lost.",
    "Wildfire swept across {region_name}, leaving the {clan} to rebuild from ash.",
    "Flooding turned {region_name} into marshland overnight, displacing everyone who called it home.",
    "A magical storm broke over {region_name}, and nothing about its aftermath behaves quite normally.",
    "{region_name} endured a volcanic eruption that no one in the {clan} saw coming.",
    "A blizzard buried {region_name} for weeks, and the {clan}'s supply lines have not recovered.",
    "Beasts migrating through {region_name} in unprecedented numbers have forced the {clan} to adapt or abandon the area.",
    "The climate around {region_name} shifted suddenly this year, and the {clan}'s farmers are already feeling it.",
]


def render_disaster(context, rng=None):
    rng = rng or random
    context = _inject_clan_verbs(dict(context))
    template = rng.choice(DISASTER_TEMPLATES)
    return _fmt(template, context)


# ---------------------------------------------------------------------------
# CHARACTER BIRTH/DEATH TEMPLATES (10+)
# ---------------------------------------------------------------------------
CHARACTER_DEATH_TEMPLATES = [
    "{character_name} has died, {death_cause}. The {clan} will feel the absence.",
    "{death_cause_capital}, {character_name}'s story ends — though it will be told for years.",
    "Word has reached every corner of {clan} territory: {character_name} is dead, {death_cause}.",
    "{character_name} did not survive {death_cause_context}. They were {age_at_death} years old.",
    "The {clan} will hold a remembrance for {character_name}, who died {death_cause}.",
    "{character_name}'s name will be added to the {clan}'s long list of the dead, {death_cause}.",
    "There will be no replacing {character_name}, who died {death_cause}, not truly — only succeeding them.",
]

CHARACTER_BIRTH_TEMPLATES = [
    "A child was born to the {clan} this year — {character_name}, who will not know how unremarkable that sounds until much later.",
    "{character_name} was born into the {clan}, one name among many that history may or may not remember.",
    "The {clan} celebrated a new birth this year: {character_name}.",
    "{character_name} entered the world this year, into a {clan} that is still being shaped by people who will one day be their elders.",
]

CHARACTER_INJURY_TEMPLATES = [
    "{character_name} survived {battle_name} but did not walk away whole — {injury_description}.",
    "{character_name} now commands from behind the lines, {injury_description}, since {battle_name}.",
    "{character_name} bears a permanent reminder of {battle_name}: {injury_description}.",
]

CHARACTER_LEGENDARY_TEMPLATES = [
    "{character_name} has become legendary among the {clan} — a name spoken with the kind of reverence reserved for the very few.",
    "The {clan} now speaks of {character_name} the way other clans speak of myths.",
    "{character_name}'s deeds have outgrown ordinary record-keeping; the {clan} now considers them legendary.",
]

CHARACTER_DEFECTION_TEMPLATES = [
    "{character_name} has defected from {old_clan} to {clan}, a betrayal that will not be forgotten quickly.",
    "In a move that has stunned both clans, {character_name} now stands with {clan} instead of {old_clan}.",
]

DEATH_CAUSES = [
    "fallen in battle", "after a long illness", "in their sleep, peacefully, after a long life",
    "in circumstances still being investigated", "defending their people to the last",
    "far from home, on a mission few knew the details of",
]


def render_character_death(context, rng=None):
    rng = rng or random
    context = dict(context)
    context.setdefault("death_cause", rng.choice(DEATH_CAUSES))
    context["death_cause_capital"] = context["death_cause"][0].upper() + context["death_cause"][1:]
    context.setdefault("death_cause_context", context["death_cause"])
    context.setdefault("age_at_death", "an age no record quite agrees on")
    template = rng.choice(CHARACTER_DEATH_TEMPLATES)
    return _fmt(template, context)


def render_character_birth(context, rng=None):
    rng = rng or random
    return _fmt(rng.choice(CHARACTER_BIRTH_TEMPLATES), context)


def render_character_injury(context, rng=None):
    rng = rng or random
    return _fmt(rng.choice(CHARACTER_INJURY_TEMPLATES), context)


def render_character_legendary(context, rng=None):
    rng = rng or random
    return _fmt(rng.choice(CHARACTER_LEGENDARY_TEMPLATES), context)


def render_character_defection(context, rng=None):
    rng = rng or random
    return _fmt(rng.choice(CHARACTER_DEFECTION_TEMPLATES), context)


# ---------------------------------------------------------------------------
# BETRAYAL TEMPLATES
# ---------------------------------------------------------------------------
BETRAYAL_TEMPLATES = {
    "alliance_broken": [
        "The alliance between {clan_a} and {clan_b} has been broken — by {clan_b}, and deliberately. {clan_a} will not forget this.",
        "{clan_b} struck at their own ally, {clan_a}, in a manner neither expected nor forgave.",
    ],
    "spy": [
        "A spy working for {clan_b} was discovered within {clan_a}'s ranks this year. The damage is still being assessed.",
    ],
    "assassination_attempt": [
        "An assassination attempt against {clan_b}'s leadership has {outcome_phrase}. The fallout will be severe regardless.",
    ],
}


def render_betrayal(context, rng=None, kind="alliance_broken"):
    rng = rng or random
    context = dict(context)
    context.setdefault("outcome_phrase", rng.choice(["failed, narrowly", "succeeded, to everyone's horror"]))
    pool = BETRAYAL_TEMPLATES.get(kind, BETRAYAL_TEMPLATES["alliance_broken"])
    return _fmt(rng.choice(pool), context)


# ---------------------------------------------------------------------------
# WONDER TEMPLATES
# ---------------------------------------------------------------------------
WONDER_TEMPLATES = [
    "Construction has begun on {wonder_name} in {region_name} — the {clan}'s most ambitious undertaking in years.",
    "{wonder_name} stands complete in {region_name} at last, after {build_duration} of labor. The {clan} will be remembered for it.",
    "The {clan} {clan_has} unveiled {wonder_name}, a landmark meant to outlast every clan currently alive to see it.",
]


def render_wonder(context, rng=None):
    rng = rng or random
    context = dict(context)
    context = _inject_clan_verbs(context)
    context.setdefault("build_duration", rng.choice(["years", "more than a decade", "a generation"]))
    return _fmt(rng.choice(WONDER_TEMPLATES), context)


# ---------------------------------------------------------------------------
# EVOLUTION MILESTONE TEMPLATES
# ---------------------------------------------------------------------------
EVOLUTION_TEMPLATES = [
    "The {clan} have reached a new age: {stage_name}. {stage_description} The other clans will feel this shift sooner or later.",
    "{stage_name} has arrived for the {clan}. {stage_description} It did not happen overnight, but it changes everything from here.",
    "Scholars among the {clan} are calling it {stage_name} — {stage_description_lower} Few outside the clan understand yet what this means.",
]


def render_evolution(context, rng=None):
    rng = rng or random
    context = dict(context)
    desc = context.get("stage_description", "")
    context["stage_description_lower"] = (desc[0].lower() + desc[1:]) if desc else desc
    return _fmt(rng.choice(EVOLUTION_TEMPLATES), context)


# ---------------------------------------------------------------------------
# YEARLY CHRONICLE (Discord embed) — the brief's "epic fantasy chronicle"
# ---------------------------------------------------------------------------
YEAR_TITLE_BANKS = {
    "war": ["Year of Blood and Banners", "The Year the Borders Burned", "A Year of Open War",
            "The Year No Peace Held", "Year of the Long Knives"],
    "discovery": ["The Year of Hidden Things Found", "A Year of Revelation", "The Year the World Gave Up a Secret",
                  "Year of New Light"],
    "political": ["The Year of Shifting Crowns", "A Year of New Names in Power", "The Year of the Broken Word"],
    "peaceful": ["A Quiet Year, and a Rare One", "The Year the World Held Its Breath", "A Year of Slow Growth"],
    "elimination": ["The Year a Clan Fell Silent", "The Year the World Lost One of Its Own"],
    "first_contact": ["The Year Strangers Met", "The Year the World Grew Smaller"],
    "mixed": ["A Year of Many Faces", "The Year Everything Moved at Once", "A Year Like Several Years at Once"],
}

CLAN_YEAR_TITLE_BANK = {
    "calm": ["A Season of Quiet", "The Long Pause", "A Year Without Incident"],
    "war": ["The Price of Ground", "Blood on the Border", "What the Battles Cost"],
    "discovery": ["What Was Found", "A Secret Uncovered", "The Find of a Generation"],
    "loss": ["A Year of Mourning", "What Was Lost", "The Hard Year"],
    "growth": ["A Year of Reach", "Roots Spreading Wider", "The Long Climb"],
    "political": ["A Change in Who Speaks for Them", "New Voices, Old Halls"],
}


def _event_priority(e):
    order = {"catastrophic": 3, "major": 2, "minor": 1}
    return order.get(e["severity"], 0)


def _year_theme(events):
    if not events:
        return "peaceful"
    cats = [e["category"] for e in events]
    sevs = [e["severity"] for e in events]
    if any(s == "catastrophic" for s in sevs) and cats.count("MILITARY") >= 1:
        return "elimination" if any("Retreat to the Ancient Stronghold" in e["title"] or "fell" in e["title"].lower() for e in events) else "war"
    n_military = cats.count("MILITARY")
    n_discovery = cats.count("DISCOVERY") + cats.count("WONDER")
    n_political = cats.count("POLITICAL") + cats.count("BETRAYAL")
    n_first_contact = sum(1 for e in events if "First Contact" in e["title"])
    if n_first_contact:
        return "first_contact"
    scores = {"war": n_military, "discovery": n_discovery, "political": n_political}
    top = max(scores, key=scores.get)
    if scores[top] == 0:
        return "peaceful"
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[0] - sorted_scores[1] <= 1:
        return "mixed"
    return top


def _embed_color(theme):
    import config
    return {
        "war": config.EMBED_COLOR_WAR, "elimination": config.EMBED_COLOR_ELIMINATION,
        "discovery": config.EMBED_COLOR_DISCOVERY, "political": config.EMBED_COLOR_POLITICAL,
        "peaceful": config.EMBED_COLOR_PEACE, "first_contact": config.EMBED_COLOR_FIRST_CONTACT,
        "mixed": config.EMBED_COLOR_POLITICAL,
    }.get(theme, config.EMBED_COLOR_PEACE)


def _clan_chronicle_section(clan_name, clan_events, rng):
    if not clan_events:
        return None
    clan_events = sorted(clan_events, key=_event_priority, reverse=True)
    top = clan_events[: rng.choice([2, 3])]
    sentences = []
    for e in top:
        sentences.append(e["narrative"])
    text = " ".join(sentences)
    # Keep this readable — trim to roughly 5 sentences worth of text.
    parts = text.split(". ")
    if len(parts) > 6:
        text = ". ".join(parts[:6]) + "."

    has_war = any(e["category"] == "MILITARY" for e in clan_events)
    has_discovery = any(e["category"] in ("DISCOVERY", "WONDER") for e in clan_events)
    has_loss = any(e["severity"] == "catastrophic" for e in clan_events)
    has_political = any(e["category"] in ("POLITICAL", "BETRAYAL") for e in clan_events)
    if has_loss:
        kind = "loss"
    elif has_war:
        kind = "war"
    elif has_discovery:
        kind = "discovery"
    elif has_political:
        kind = "political"
    else:
        kind = "growth"
    title = rng.choice(CLAN_YEAR_TITLE_BANK[kind])
    return title, text


def _world_overview(sim_year, clan_states, rng):
    import config
    alive = [c for c in clan_states if not c["is_eliminated"]]
    if not alive:
        return "The world is silent. No clan remains to shape what comes next."
    leader = max(alive, key=lambda c: c["territory_count"])
    leader_share = leader["territory_count"] / config.TOTAL_REGIONS * 100
    n_at_war = sum(1 for c in alive if c["extra_state"].get("cornered"))
    growth_words = rng.choice(["a period of steady growth", "an age of careful expansion", "a year of consolidation"])
    if leader_share > 30:
        power_line = f"The {leader['name']} now hold more ground than any other clan, controlling roughly {leader_share:.0f}% of the known world."
    else:
        power_line = f"No single clan yet dominates the map; the {leader['name']} hold the largest share of territory, but only barely."
    tone_line = f"This has been {growth_words} for most of the six." if n_at_war == 0 else \
        "More than one clan is fighting for its survival this year, and it shows."
    return f"{power_line} {tone_line}"


def _balance_of_power(clan_states, rng):
    import config
    alive = [c for c in clan_states if not c["is_eliminated"]]
    if len(alive) < 2:
        return "There is no balance left to speak of."
    by_territory = sorted(alive, key=lambda c: c["territory_count"], reverse=True)
    rising = by_territory[0]
    struggling = min(alive, key=lambda c: c["population"] / max(c["peak_population"], 1))
    if rising["name"] == struggling["name"]:
        return f"The {rising['name']} continue to set the pace this year, with no clan seriously contesting them yet."
    return (f"The {rising['name']} are ascendant, while the {struggling['name']} have seen better years and "
            f"know it. Historians watching closely expect this gap to matter sooner rather than later.")


def _what_stirs(events, rng):
    if not events:
        return "The world is quiet. For now."
    candidates = [e for e in events if e["category"] in ("POLITICAL", "BETRAYAL", "DISCOVERY", "MILITARY")]
    if not candidates:
        candidates = events
    pick = rng.choice(candidates[-min(5, len(candidates)):])
    teaser_templates = [
        f"Word is spreading about {pick['title']} — and not everyone is finished reacting to it.",
        f"What happened at {pick['title']} may not be over. Several clans are watching closely.",
        f"The consequences of {pick['title']} have only just begun to surface.",
    ]
    return rng.choice(teaser_templates)


def build_yearly_embed(sim_year, rng=None):
    """Builds the full Discord embed dict for one completed sim year, per
    the brief's epic-fantasy-chronicle format."""
    from database import db
    from simulation import clans as clans_module

    rng = rng or random
    events = db.get_events_for_year(sim_year)
    clan_states = [db.get_clan(c) for c in clans_module.CLAN_NAMES]
    clan_states = [c for c in clan_states if c]

    theme = _year_theme(events)
    year_title = rng.choice(YEAR_TITLE_BANKS.get(theme, YEAR_TITLE_BANKS["mixed"]))

    opening_candidates = sorted(events, key=_event_priority, reverse=True)
    if opening_candidates:
        opening_line = opening_candidates[0]["narrative"].split(". ")[0]
        if not opening_line.endswith("."):
            opening_line += "."
    else:
        opening_line = ("The year passed without a single moment loud enough to define it — "
                         "which is its own kind of history.")

    world_overview = _world_overview(sim_year, clan_states, rng)
    balance = _balance_of_power(clan_states, rng)
    stirs = _what_stirs(events, rng)

    lines = []
    lines.append(f"📜 **YEAR {sim_year} — {year_title.upper()}**")
    lines.append("")
    lines.append(f"*{opening_line}*")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"🌍 **THE WORLD IN YEAR {sim_year}**")
    lines.append(world_overview)
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("⚔️ **CLAN CHRONICLES**")
    lines.append("")

    any_clan_section = False
    for clan_name in clans_module.CLAN_NAMES:
        clan_events = [e for e in events if clan_name in e["clans_involved"]]
        section = _clan_chronicle_section(clan_name, clan_events, rng)
        icon = clans_module.CLAN_LORE[clan_name]["icon"]
        if section:
            title, text = section
            lines.append(f"{icon} **{clan_name.upper()}** — \"{title}\"")
            lines.append(text)
            lines.append("")
            any_clan_section = True
        clan_state = next((c for c in clan_states if c["name"] == clan_name), None)
        if clan_state and clan_state["is_eliminated"]:
            lines.append(f"{icon} **{clan_name.upper()}** has fallen. Their banners no longer fly anywhere in the world.")
            lines.append("")

    if not any_clan_section:
        lines.append("It was a quiet year across every clan's territory — the kind historians skip over, and the "
                      "kind the people living through it are grateful for.")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📊 **BALANCE OF POWER**")
    lines.append(balance)
    lines.append("")
    lines.append("🔮 **WHAT STIRS**")
    lines.append(stirs)
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    total_controlled = sum(c["territory_count"] for c in clan_states if not c["is_eliminated"])
    import config
    world_control_pct = round(total_controlled / config.TOTAL_REGIONS * 100, 1)
    footer_text = f"Sim Year {sim_year} | World settled: {world_control_pct}%"

    return {
        "title": f"Year {sim_year} — {year_title}",
        "description": "\n".join(lines),
        "color": _embed_color(theme),
        "footer": {"text": footer_text},
    }


def build_victory_embed(winner_clan, sim_year, rng=None):
    from database import db
    from simulation import clans as clans_module
    import config

    rng = rng or random
    fallen = [c for c in clans_module.CLAN_NAMES if c != winner_clan]
    fallen_lines = []
    for c in fallen:
        state = db.get_clan(c)
        if state and state["is_eliminated"]:
            fallen_lines.append(f"— The {c} fell, their banners lost to history.")
        else:
            fallen_lines.append(f"— The {c} endured to the end, though the world no longer belonged to them.")

    lore = clans_module.CLAN_LORE[winner_clan]
    text = (
        f"👑 **{winner_clan.upper()} HAVE WON THE WORLD**\n\n"
        f"In Year {sim_year}, after generations of war, growth, betrayal, and survival, the {winner_clan} — "
        f"{lore['full_name']} — stand alone. {lore['strategic_personality']}\n\n"
        f"What the world looks like now bears little resemblance to the scattered, unfamiliar land six clans "
        f"woke into at Year 0. The {winner_clan} did not simply outlast the others — they out-adapted them.\n\n"
        + "\n".join(fallen_lines) +
        f"\n\nThe simulation has reached its end. This is the world the {winner_clan} built — or the world that "
        f"was left to them. History, as always, will be written by whoever survives to tell it."
    )
    return {
        "title": f"🏆 The World Belongs to the {winner_clan}",
        "description": text,
        "color": 0xFFD700,
        "footer": {"text": f"Final Year: {sim_year}"},
    }
