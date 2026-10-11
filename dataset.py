import json
import os

# Complete Evolutionary & Family Mappings
EVOLUTION_FAMILIES = {
    # Kanto Families
    "bulbasaur": ["bulbasaur", "ivysaur", "venusaur"],
    "charmander": ["charmander", "charmeleon", "charizard"],
    "squirtle": ["squirtle", "wartortle", "blastoise"],
    "pidgey": ["pidgey", "pidgeotto", "pidgeot"],
    "rattata": ["rattata", "raticate"],
    "pikachu": ["pichu", "pikachu", "raichu"],
    "sandshrew": ["sandshrew", "sandslash"],
    "vulpix": ["vulpix", "ninetales"],
    "jigglypuff": ["igglybuff", "jigglypuff", "wigglytuff"],
    "meowth": ["meowth", "persian", "perrserker"],
    "psyduck": ["psyduck", "golduck"],
    "growlithe": ["growlithe", "arcanine"],
    "abra": ["abra", "kadabra", "alakazam"],
    "machop": ["machop", "machoke", "machamp"],
    "geodude": ["geodude", "graveler", "golem"],
    "gastly": ["gastly", "haunter", "gengar"],
    "onix": ["onix", "steelix"],
    "eevee": ["eevee", "vaporeon", "jolteon", "flareon", "espeon", "umbreon", "leafeon", "glaceon", "sylveon"],
    "dratini": ["dratini", "dragonair", "dragonite"],
    "mewtwo": ["mewtwo"],
    
    # Regional & Special Lines
    "zigzagoon": ["zigzagoon", "linoone", "obstagoon"],
    "slowpoke": ["slowpoke", "slowbro", "slowking"],
    "farfetchd": ["farfetchd", "sirfetchd"],
    "corsola": ["corsola", "cursola"],
    "darumaka": ["darumaka", "darmanitan"],
    "yamask": ["yamask", "cofagrigus", "runerigus"]
}

# Regional Forms Registry
REGIONAL_FORMS = {
    "galarian": ["zigzagoon", "linoone", "meowth", "ponyta", "rapidash", "slowpoke", "slowbro", "slowking", "farfetchd", "corsola", "darumaka", "darmanitan", "yamask", "articuno", "zapdos", "moltres"],
    "alolan": ["rattata", "raticate", "raichu", "sandshrew", "sandslash", "vulpix", "ninetales", "diglett", "dugtrio", "meowth", "persian", "geodude", "graveler", "golem", "grimer", "muk", "exeggutor", "marowak"],
    "hisuian": ["growlithe", "arcanine", "voltorb", "electrode", "typhlosion", "qwilfish", "sneasel", "samurott", "lilligant", "zorua", "zoroark", "braviary", "sliggoo", "goodra", "avalugg", "decidueye"]
}

# Gigantamax Eligible Pokémon
GMAX_SPECIES = [
    "venusaur", "charizard", "blastoise", "butterfree", "pikachu", "meowth",
    "machamp", "gengar", "kingler", "lapras", "eevee", "snorlax", "garbodor",
    "melmetal", "rillaboom", "cinderace", "inteleon", "corviknight", "orbeetle",
    "drednaw", "coalossal", "flapple", "appletun", "sandaconda", "toxtricity",
    "centiskorch", "hatterene", "grimmsnarl", "alcremie", "copperajah", "duraludon", "urshifu"
]

POKEMON_DATASET = {}


def load_dataset(file_path: str = "pokemon_data.json"):
    """Loads external JSON dataset if available, otherwise relies on internal maps."""
    global POKEMON_DATASET
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                POKEMON_DATASET = json.load(f)
            print(f"✅ Loaded {len(POKEMON_DATASET)} Pokémon from external JSON file.")
        except Exception as e:
            print(f"⚠️ Error reading {file_path}: {e}")
            POKEMON_DATASET = {}
    else:
        print("ℹ️ External pokemon_data.json not found. Using built-in evolution & regional mapping rules.")


def normalize_name(name: str) -> str:
    """Standardizes names for matching."""
    return name.strip().lower()


def format_pokemon_name(name: str) -> str:
    """Formats Pokémon names cleanly for embeds."""
    cleaned = name.strip().lower()
    
    # Preserve GMax indicators
    if cleaned.startswith("gmax ") or cleaned.endswith(" gmax"):
        core = cleaned.replace("gmax", "").strip().title()
        return f"⚡ G-Max {core}"
        
    return cleaned.title()


def parse_pokemon_list(input_str: str) -> list[str]:
    """Parses comma-separated inputs into clean, title-cased names."""
    if not input_str:
        return []
    raw_list = input_str.split(",")
    cleaned = [format_pokemon_name(m) for m in raw_list if m.strip()]
    return list(dict.fromkeys(cleaned))


def get_evolution_family(species: str) -> list[str]:
    """Returns the full evolutionary line for a given species name."""
    norm = normalize_name(species)
    for family, members in EVOLUTION_FAMILIES.items():
        if norm in members or norm == family:
            return [m.title() for m in members]
    return [species.strip().title()]


def is_gmax_eligible(species: str) -> bool:
    """Checks if a species is capable of Gigantamaxing."""
    norm = normalize_name(species).replace("g-max", "").replace("gmax", "").strip()
    return norm in GMAX_SPECIES


def validate_species(name: str) -> bool:
    """Validates if a species exists in local maps or JSON dataset."""
    norm = normalize_name(name)
    if POKEMON_DATASET:
        return norm in POKEMON_DATASET
    
    # Fallback to local keys
    if norm in EVOLUTION_FAMILIES or any(norm in line for line in EVOLUTION_FAMILIES.values()):
        return True
    return False


# Auto-load dataset on module import
load_dataset()
