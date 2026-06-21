"""
simulation/world.py — World generation.

Builds the 200x200 (40,000 region) map: biome placement, resource
distribution, rare resource nodes, procedural region names, and each clan's
starting territory cluster around their lore-defined home region.

Biome placement uses layered value-noise "affinity" fields (one per biome)
plus a Gaussian bump centered on each clan's anchor point that favors their
primary terrain. Each region's biome is whichever affinity field wins at
that cell. This produces natural-looking contiguous biome clusters instead
of salt-and-pepper noise, while still guaranteeing each clan starts on
appropriate terrain.

NOTE: this module uses numpy purely for fast noise-field generation (no
external services, no API keys — still 100% free). It is the one addition
to the dependency list beyond what the original brief specified, because it
keeps a 40,000-cell world-gen pass fast and the biome clustering natural.
"""

import random
import math
import numpy as np

import config

# ---------------------------------------------------------------------------
# CLAN HOME ANCHORS — positions chosen so each clan starts in a different
# region of the map (Rule 6: Geographic Separation).
# ---------------------------------------------------------------------------
CLAN_ANCHORS = {
    "Aura Knights": {
        "pos": (100, 100),
        "label": "Central Golden Plains",
        "primary_biomes": ["Plains", "Mountain"],
        "start_radius": 9,
    },
    "Arcane Conclave": {
        "pos": (181, 92),
        "label": "Eastern Spire Peaks",
        "primary_biomes": ["Ethereal Wastes", "Mountain"],
        "start_radius": 7,
    },
    "Iron Covenant": {
        "pos": (96, 16),
        "label": "Northern Iron Highlands",
        "primary_biomes": ["Mountain", "Underground"],
        "start_radius": 8,
    },
    "Sylvan Circle": {
        "pos": (16, 104),
        "label": "Western Ancient Forest",
        "primary_biomes": ["Forest", "Swamp", "Coastal"],
        "start_radius": 9,
    },
    "Void Reapers": {
        "pos": (104, 183),
        "label": "Southern Hollow Caverns",
        "primary_biomes": ["Underground", "Swamp"],
        "start_radius": 7,
    },
    "Stone Covenant": {
        "pos": (171, 175),
        "label": "Volcanic Rim Territories",
        "primary_biomes": ["Mountain", "Volcanic", "Underground"],
        "start_radius": 8,
    },
}

# Resources eligible per biome (Ember Core is excluded — it is rare-node only)
RESOURCE_BIOME_MAP = {
    "Food": ["Plains", "Forest", "Coastal"],
    "Iron": ["Mountain", "Underground"],
    "Timber": ["Forest"],
    "Stone": ["Mountain", "Volcanic"],
    "Mana Crystals": ["Ethereal Wastes", "Mountain"],
    "Void Essence": ["Underground", "Swamp"],
    "Living Wood": ["Forest"],
    "Sunstone": ["Desert", "Plains"],
    "Deepstone": ["Volcanic", "Underground"],
}

# Resources that can appear as one of the 65 hidden RARE nodes, with weights.
RARE_RESOURCE_WEIGHTS = {
    "Ember Core": 12,       # legendary, Volcanic only
    "Mana Crystals": 18,
    "Void Essence": 18,
    "Living Wood": 18,
    "Sunstone": 17,
    "Deepstone": 17,
}
RARE_RESOURCE_BIOME_MAP = {
    "Ember Core": ["Volcanic"],
    "Mana Crystals": ["Ethereal Wastes", "Mountain"],
    "Void Essence": ["Underground", "Swamp"],
    "Living Wood": ["Forest"],
    "Sunstone": ["Desert", "Plains"],
    "Deepstone": ["Volcanic", "Underground"],
}

ADJECTIVES = [
    "Old", "Lost", "Forgotten", "Silent", "Broken", "Hollow", "Bright", "Shadowed",
    "Whispering", "Restless", "Wild", "Iron", "Golden", "Pale", "Deep", "High",
    "Low", "Ashen", "Frozen", "Burning", "Drowned", "Sunken", "Twin", "Lonely",
    "Crimson", "Gray", "Far", "Black", "White", "Hidden", "Endless", "Quiet",
    "Bitter", "Withered", "Sundered", "Echoing", "Salt", "Bone", "Glass", "Iron-Veined",
]

BIOME_NOUNS = {
    "Plains": ["Fields", "Plain", "Flats", "Meadow", "Prairie", "Grassland", "Steppe", "Reach"],
    "Forest": ["Woods", "Forest", "Thicket", "Grove", "Hollow", "Timberland", "Glade", "Canopy"],
    "Mountain": ["Peak", "Ridge", "Summit", "Crag", "Highlands", "Spire", "Bluff", "Pass"],
    "Desert": ["Dunes", "Wastes", "Sands", "Expanse", "Flats", "Mirage", "Erg"],
    "Swamp": ["Mire", "Fen", "Bog", "Marsh", "Sump", "Quagmire", "Sloughs"],
    "Arctic": ["Tundra", "Icefield", "Frostlands", "Glacier", "Permafrost", "Rime"],
    "Coastal": ["Shore", "Coast", "Bay", "Cape", "Reach", "Tideflats", "Strand"],
    "Underground": ["Depths", "Caverns", "Hollow", "Underdark", "Burrow", "Warren", "Catacombs"],
    "Volcanic": ["Cinderlands", "Ashfields", "Caldera", "Magma Flats", "Emberreach", "Scar"],
    "Ethereal Wastes": ["Wastes", "Rift", "Veil", "Nullspace", "Driftlands", "Shimmer", "Tear"],
}


def _box_blur(field, passes=2):
    """Cheap separable box blur using numpy, edge-padded."""
    for _ in range(passes):
        p = np.pad(field, 1, mode="edge")
        field = (
            p[0:-2, 0:-2] + p[0:-2, 1:-1] + p[0:-2, 2:] +
            p[1:-1, 0:-2] + p[1:-1, 1:-1] + p[1:-1, 2:] +
            p[2:, 0:-2] + p[2:, 1:-1] + p[2:, 2:]
        ) / 9.0
    return field


def _noise_field(rng, width, height, base_res=10, octaves=4, blur_passes=2):
    """Multi-octave value noise: low-res random grids upsampled and blended,
    then smoothed. Produces a continuous field in roughly [0, 1]."""
    field = np.zeros((height, width))
    res = base_res
    amplitude = 1.0
    total_amp = 0.0
    for _ in range(octaves):
        low_h = max(2, height // res)
        low_w = max(2, width // res)
        low = rng.random((low_h, low_w))
        rep_h = height // low_h + 1
        rep_w = width // low_w + 1
        upsampled = np.kron(low, np.ones((rep_h, rep_w)))[:height, :width]
        field += amplitude * upsampled
        total_amp += amplitude
        amplitude *= 0.55
        res = max(2, res // 2)
    field /= total_amp
    field = _box_blur(field, passes=blur_passes)
    # normalize to [0, 1]
    field -= field.min()
    if field.max() > 0:
        field /= field.max()
    return field


def _gaussian_bump(width, height, cx, cy, sigma, amplitude=1.0):
    ys, xs = np.mgrid[0:height, 0:width]
    dist2 = (xs - cx) ** 2 + (ys - cy) ** 2
    return amplitude * np.exp(-dist2 / (2 * sigma * sigma))


def _region_name(rng, biome):
    adj = rng.choice(ADJECTIVES)
    noun = rng.choice(BIOME_NOUNS[biome])
    return f"{adj} {noun}"


def generate_world():
    """Generates the full world. Returns:
        regions: list of dicts (one per region, id = y*WORLD_WIDTH + x)
        starting_territories: dict[clan_name] -> list of region ids claimed at genesis
    """
    seed = config.WORLD_SEED if config.WORLD_SEED is not None else random.randint(0, 2_000_000_000)
    py_rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    W, H = config.WORLD_WIDTH, config.WORLD_HEIGHT
    biomes = config.BIOMES

    # 1. Build one affinity field per biome.
    affinity = {b: _noise_field(np_rng, W, H, base_res=14, octaves=4) for b in biomes}

    # 2. Bias each clan's primary biomes near their anchor so they start on
    #    the right terrain, without making the whole region monotone.
    for clan, info in CLAN_ANCHORS.items():
        cx, cy = info["pos"]
        bump = _gaussian_bump(W, H, cx, cy, sigma=info["start_radius"] * 1.8, amplitude=1.4)
        for b in info["primary_biomes"]:
            affinity[b] = affinity[b] + bump

    # 3. Elevation field (used for fortification defaults & flavor, and to
    #    gently nudge Mountain/Volcanic toward "high" terrain — kept subtle
    #    so no single biome swallows the map).
    elevation = _noise_field(np_rng, W, H, base_res=18, octaves=3)
    affinity["Mountain"] = affinity["Mountain"] + (elevation - 0.5) * 0.25
    affinity["Volcanic"] = affinity["Volcanic"] + (elevation - 0.5) * 0.12
    affinity["Plains"] = affinity["Plains"] - (elevation - 0.5) * 0.15
    affinity["Coastal"] = affinity["Coastal"] - (elevation - 0.5) * 0.20

    # 4. Stack fields and take argmax per cell to decide biome.
    stacked = np.stack([affinity[b] for b in biomes], axis=0)  # shape (10, H, W)
    biome_idx = np.argmax(stacked, axis=0)  # shape (H, W)

    # 5. Mark "Ancient Forest" sub-tag: Forest cells within range of the
    #    Sylvan Circle anchor (their lore-unique Living Wood source).
    sylvan_cx, sylvan_cy = CLAN_ANCHORS["Sylvan Circle"]["pos"]
    ancient_forest_radius = 26

    # 6. Build region rows.
    regions = []
    starting_territories = {clan: [] for clan in CLAN_ANCHORS}
    rare_node_cells = _pick_rare_node_cells(py_rng, W, H, config.RARE_NODE_COUNT)

    for y in range(H):
        for x in range(W):
            region_id = y * W + x
            biome = biomes[int(biome_idx[y, x])]
            elev = float(elevation[y, x])

            is_ancient_forest = False
            if biome == "Forest":
                d = math.hypot(x - sylvan_cx, y - sylvan_cy)
                is_ancient_forest = d <= ancient_forest_radius

            resources = _assign_resources(py_rng, biome, is_ancient_forest)

            is_rare = region_id in rare_node_cells
            rare_resource = None
            if is_rare:
                rare_resource = _pick_rare_resource_for_biome(py_rng, biome)
                if rare_resource is None:
                    is_rare = False  # biome had no compatible rare resource

            owner = None
            pop_density = 0
            fortification = 0
            for clan, info in CLAN_ANCHORS.items():
                cx, cy = info["pos"]
                if math.hypot(x - cx, y - cy) <= info["start_radius"]:
                    owner = clan
                    pop_density = py_rng.randint(40, 100)
                    fortification = py_rng.randint(1, 3)
                    starting_territories[clan].append(region_id)
                    break

            regions.append({
                "id": region_id,
                "x": x,
                "y": y,
                "name": _region_name(py_rng, biome),
                "biome": biome,
                "elevation": round(elev, 4),
                "resources": resources,
                "owner_clan": owner,
                "population_density": pop_density,
                "fortification": fortification,
                "is_rare_node": is_rare,
                "rare_node_resource": rare_resource,
                "rare_node_discovered_by": [],
                "is_last_bastion_for": None,
                "last_bastion_discovered_by": [],
            })

    return regions, starting_territories, seed


def _pick_rare_node_cells(rng, width, height, count):
    total = width * height
    return set(rng.sample(range(total), min(count, total)))


def _assign_resources(rng, biome, is_ancient_forest):
    """Up to 3 resources per region, chosen from what the biome supports."""
    candidates = [r for r, biomes in RESOURCE_BIOME_MAP.items() if biome in biomes]
    if biome == "Forest" and not is_ancient_forest:
        candidates = [c for c in candidates if c != "Living Wood"]
    if not candidates:
        return []
    rng.shuffle(candidates)
    n = rng.choices([0, 1, 2, 3], weights=[15, 35, 35, 15])[0]
    return candidates[:n]


def _pick_rare_resource_for_biome(rng, biome):
    eligible = [r for r, biomes in RARE_RESOURCE_BIOME_MAP.items() if biome in biomes]
    if not eligible:
        return None
    weights = [RARE_RESOURCE_WEIGHTS[r] for r in eligible]
    return rng.choices(eligible, weights=weights, k=1)[0]


def region_row_tuple(region):
    """Convert a region dict into the tuple shape expected by
    db.bulk_insert_regions (column order matters)."""
    import json
    return (
        region["id"], region["x"], region["y"], region["name"], region["biome"],
        region["elevation"], json.dumps(region["resources"]), region["owner_clan"],
        region["population_density"], region["fortification"],
        int(region["is_rare_node"]), region["rare_node_resource"],
        json.dumps(region["rare_node_discovered_by"]), region["is_last_bastion_for"],
        json.dumps(region["last_bastion_discovered_by"]),
    )


def neighbors_of(region_id):
    """4-directional neighbors (N/S/E/W) within map bounds."""
    W, H = config.WORLD_WIDTH, config.WORLD_HEIGHT
    x, y = region_id % W, region_id // W
    out = []
    if x > 0:
        out.append(region_id - 1)
    if x < W - 1:
        out.append(region_id + 1)
    if y > 0:
        out.append(region_id - W)
    if y < H - 1:
        out.append(region_id + W)
    return out


def distance(region_id_a, region_id_b):
    W = config.WORLD_WIDTH
    ax, ay = region_id_a % W, region_id_a // W
    bx, by = region_id_b % W, region_id_b // W
    return math.hypot(ax - bx, ay - by)
