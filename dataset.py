import json
import os
import urllib.request

# 1. Regional Form Registry Mapping
REGIONAL_FORMS = {
    # Alolan Forms
    "alolan ninetales": "Alolan Ninetales", "alolan vulpix": "Alolan Vulpix",
    "alolan geodude": "Alolan Geodude", "alolan graveler": "Alolan Graveler",
    "alolan raticate": "Alolan Raticate", "alolan rattata": "Alolan Rattata",
    "alolan persian": "Alolan Persian", "alolan meowth": "Alolan Meowth",
    "alolan exeggutor": "Alolan Exeggutor", "alolan dugtrio": "Alolan Dugtrio",
    "alolan diglett": "Alolan Diglett", "alolan grimer": "Alolan Grimer",
    "alolan golem": "Alolan Golem", "alolan sandshrew": "Alolan Sandshrew",
    "alolan sandslash": "Alolan Sandslash", "alolan marowak": "Alolan Marowak",
    "alolan raichu": "Alolan Raichu", "alolan muk": "Alolan Muk",

    # Galarian Forms & Evolutions
    "galarian linoone": "Galarian Linoone", "galarian yamask": "Galarian Yamask",
    "galarian slowpoke": "Galarian Slowpoke", "galarian slowbro": "Galarian Slowbro",
    "galarian slowking": "Galarian Slowking", "galarian farfetch'd": "Galarian Farfetch'd",
    "galarian farfetchd": "Galarian Farfetch'd", "galarian rapidash": "Galarian Rapidash",
    "galarian ponyta": "Galarian Ponyta", "galarian mr. mime": "Galarian Mr. Mime",
    "galarian weezing": "Galarian Weezing", "galarian zigzagoon": "Galarian Zigzagoon",
    "galarian corsola": "Galarian Corsola", "galarian darumaka": "Galarian Darumaka",
    "galarian stunfisk": "Galarian Stunfisk", "galarian darmanitan": "Galarian Darmanitan",
    "galarian zen darmanitan": "Galarian Zen Darmanitan", "obstagoon": "Obstagoon",
    "sirfetch'd": "Sirfetch'd", "sirfetchd": "Sirfetch'd", "cursola": "Cursola",
    "runerigus": "Runerigus", "mr. rime": "Mr. Rime", "perrserker": "Perrserker",
    "galarian moltres": "Galarian Moltres", "galarian articuno": "Galarian Articuno",
    "galarian zapdos": "Galarian Zapdos",

    # Hisuian Forms & Evolutions
    "hisuian growlithe": "Hisuian Growlithe", "hisuian arcanine": "Hisuian Arcanine",
    "hisuian electrode": "Hisuian Electrode", "hisuian voltorb": "Hisuian Voltorb",
    "hisuian typhlosion": "Hisuian Typhlosion", "hisuian lilligant": "Hisuian Lilligant",
    "hisuian samurott": "Hisuian Samurott", "hisuian sneasel": "Hisuian Sneasel",
    "hisuian decidueye": "Hisuian Decidueye", "hisuian qwilfish": "Hisuian Qwilfish",
    "hisuian braviary": "Hisuian Braviary", "hisuian avalugg": "Hisuian Avalugg",
    "hisuian zoroark": "Hisuian Zoroark", "hisuian zorua": "Hisuian Zorua",
    "hisuian sliggoo": "Hisuian Sliggoo", "hisuian goodra": "Hisuian Goodra",
    "basculegion": "Basculegion", "sneasler": "Sneasler", "overqwil": "Overqwil",

    # Paldean Forms & Breeds
    "paldean wooper": "Paldean Wooper", "combat breed tauros": "Combat Breed Tauros",
    "blaze breed tauros": "Blaze Breed Tauros", "aqua breed tauros": "Aqua Breed Tauros"
}

# 2. Multi-Form Registries
POKEMON_FORMS = {
    # Generation 1 & Kanto Forms
    "pikachu": ["Pikachu", "Partner Pikachu"],
    "meowth": ["Meowth", "Alolan Meowth", "Galarian Meowth"],
    "ponyta": ["Ponyta", "Galarian Ponyta"],
    "rapidash": ["Rapidash", "Galarian Rapidash"],
    "slowpoke": ["Slowpoke", "Galarian Slowpoke"],
    "slowbro": ["Slowbro", "Galarian Slowbro"],
    "farfetch'd": ["Farfetch'd", "Galarian Farfetch'd"],
    "farfetchd": ["Farfetch'd", "Galarian Farfetch'd"],
    "marowak": ["Marowak", "Alolan Marowak"],
    "weezing": ["Weezing", "Galarian Weezing"],
    "eevee": ["Eevee", "Partner Eevee"],
    "articuno": ["Articuno", "Galarian Articuno"],
    "zapdos": ["Zapdos", "Galarian Zapdos"],
    "moltres": ["Moltres", "Galarian Moltres"],

    # Generation 2 & Johto Forms
    "pichu": ["Pichu", "Spiky-eared Pichu"],
    "unown": [
        "Unown", "Unown A", "Unown B", "Unown C", "Unown D", "Unown E", "Unown F", "Unown G", 
        "Unown H", "Unown I", "Unown J", "Unown K", "Unown L", "Unown M", "Unown N", "Unown O", 
        "Unown P", "Unown Q", "Unown R", "Unown S", "Unown T", "Unown U", "Unown V", "Unown W", 
        "Unown X", "Unown Y", "Unown Z", "Unown Exclamation", "Unown Question"
    ],
    "corsola": ["Corsola", "Galarian Corsola"],

    # Generation 3 & Hoenn Forms
    "castform": ["Castform", "Sunny Castform", "Rainy Castform", "Snowy Castform"],
    "deoxys": ["Deoxys", "Attack Deoxys", "Defense Deoxys", "Speed Deoxys"],

    # Generation 4 & Sinnoh Forms
    "burmy": ["Burmy", "Sandy Burmy", "Trash Burmy"],
    "wormadam": ["Wormadam", "Sandy Wormadam", "Trash Wormadam"],
    "cherrim": ["Cherrim", "Sunshine Cherrim"],
    "rotom": [
        "Rotom", "Heat Rotom", "Wash Rotom", "Frost Rotom", "Fan Rotom", 
        "Mow Rotom", "DJ Rotom", "Rotom Pokédex", "Rotom Phone", "Rotom Drone"
    ],
    "arceus": [
        "Arceus", "Bug Arceus", "Dark Arceus", "Dragon Arceus", "Electric Arceus", 
        "Fighting Arceus", "Fire Arceus", "Flying Arceus", "Ghost Arceus", "Grass Arceus", 
        "Ground Arceus", "Ice Arceus", "Poison Arceus", "Psychic Arceus", "Rock Arceus", 
        "Steel Arceus", "Water Arceus", "Fairy Arceus"
    ],

    # Generation 5 & Unova Forms
    "darmanitan": ["Darmanitan", "Zen Darmanitan"],
    "basculin": ["Basculin", "White-Striped Basculin"],
    "kyurem": ["Kyurem", "White Kyurem", "Black Kyurem"],
    "meloetta": ["Meloetta", "Pirouette Forme Meloetta"],
    "genesect": ["Genesect", "High-speed Flight Configuration Genesect"],

    # Generation 6 & Kalos Forms
    "greninja": ["Greninja", "Ash-Greninja"],
    "flabébé": ["Flabébé", "Yellow Flower Flabébé", "Orange Flower Flabébé", "Blue Flower Flabébé", "White Flower Flabébé"],
    "flabebe": ["Flabébé", "Yellow Flower Flabébé", "Orange Flower Flabébé", "Blue Flower Flabébé", "White Flower Flabébé"],
    "floette": ["Floette", "Yellow Flower Floette", "Orange Flower Floette", "Blue Flower Floette", "White Flower Floette", "Eternal Flower Floette"],
    "florges": ["Florges", "Yellow Flower Florges", "Orange Flower Florges", "Blue Flower Florges", "White Flower Florges"],
    "furfrou": [
        "Furfrou", "Heart Trim Furfrou", "Star Trim Furfrou", "Diamond Trim Furfrou", 
        "Debutante Trim Furfrou", "Matron Trim Furfrou", "Dandy Trim Furfrou", 
        "La Reine Trim Furfrou", "Kabuki Trim Furfrou", "Pharaoh Trim Furfrou"
    ],
    "meowstic": ["Meowstic", "Female Meowstic"],
    "pumpkaboo": ["Pumpkaboo", "Small Size Pumpkaboo", "Large Size Pumpkaboo", "Super Size Pumpkaboo"],
    "xerneas": ["Xerneas", "Neutral Xerneas"],
    "zygarde": ["Zygarde", "10% Zygarde", "Complete Zygarde", "Zygarde Cell", "Zygarde Core"],

    # Generation 7 & Alola Forms
    "oricorio": ["Oricorio", "Pom-pom Oricorio", "Pa'u Oricorio", "Sensu Oricorio"],
    "lycanroc": ["Lycanroc", "Midnight Lycanroc", "Dusk Lycanroc"],
    "wishiwashi": ["Wishiwashi", "School Forme Wishiwashi"],
    "silvally": [
        "Silvally", "Bug Silvally", "Dark Silvally", "Dragon Silvally", "Electric Silvally", 
        "Fighting Silvally", "Fire Silvally", "Flying Silvally", "Ghost Silvally", "Grass Silvally", 
        "Ground Silvally", "Ice Silvally", "Poison Silvally", "Psychic Silvally", "Rock Silvally", 
        "Steel Silvally", "Water Silvally", "Fairy Silvally"
    ],

    # Generation 8 & Galar Forms
    "cramorant": ["Cramorant", "Gulping Cramorant", "Gorging Cramorant"],
    "toxtricity": ["Toxtricity", "Low Key Toxtricity"],
    "alcremie": [
        "Alcremie", "Berry Sweet Alcremie", "Love Sweet Alcremie", "Star Sweet Alcremie", 
        "Clover Sweet Alcremie", "Flower Sweet Alcremie", "Ribbon Sweet Alcremie"
    ],
    "eiscue": ["Eiscue", "Noice Face Eiscue"],
    "morpeko": ["Morpeko", "Hangry Mode Morpeko"],
    "zamazenta": ["Zamazenta", "Crowned Shield Zamazenta"],
    "urshifu": ["Urshifu", "Rapid Strike Urshifu"],
    "zarude": ["Zarude", "Dada Zarude"],

    # Generation 9 & Paldea Forms
    "maushold": ["Maushold", "Family of Three Maushold"],
    "squawkabilly": ["Squawkabilly", "Blue Squawkabilly", "Yellow Squawkabilly", "White Squawkabilly"],
    "palafin": ["Palafin", "Hero Palafin"],
    "tatsugiri": ["Tatsugiri", "Droopy Tatsugiri", "Stretchy Tatsugiri"],
    "dudunsparce": ["Dudunsparce", "Three-Segment Dudunsparce"],
    "gimmighoul": ["Gimmighoul", "Roaming Gimmighoul"],
    "oinkologne": ["Oinkologne", "Female Oinkologne"],
    "terapagos": ["Terapagos", "Terastal Form Terapagos"]
}

POKEMON_DATASET = set()


def load_dataset():
    global POKEMON_DATASET
    file_path = "pokemon_data.json"
    
    if not os.path.exists(file_path):
        try:
            print("⏳ Fetching complete Pokémon list...")
            url = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                species_list = [item["name"].lower() for item in data["results"]]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(species_list, f)
        except Exception as e:
            print(f"⚠️ Error fetching dataset: {e}")

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                POKEMON_DATASET = set(json.load(f))
            print(f"✅ Loaded {len(POKEMON_DATASET)} Pokémon into memory.")
        except Exception as e:
            print(f"⚠️ Error reading {file_path}: {e}")


def normalize_name(name: str) -> str:
    return name.strip().lower()


def format_pokemon_name(name: str) -> str:
    norm = normalize_name(name)
    if norm in REGIONAL_FORMS:
        return REGIONAL_FORMS[norm]
    return name.strip().title()


def get_evolution_family(species: str) -> list[str]:
    norm = normalize_name(species).replace("all ", "").strip()
    if norm in POKEMON_FORMS:
        return POKEMON_FORMS[norm]
    if norm in REGIONAL_FORMS:
        return [REGIONAL_FORMS[norm]]
    return [format_pokemon_name(species)]


def validate_species(name: str) -> bool:
    norm = normalize_name(name)
    clean_norm = norm.replace("all ", "").strip()
    
    if norm in REGIONAL_FORMS or clean_norm in REGIONAL_FORMS:
        return True
    if norm in POKEMON_DATASET or clean_norm in POKEMON_DATASET:
        return True
    if norm in POKEMON_FORMS or clean_norm in POKEMON_FORMS:
        return True
        
    for forms in POKEMON_FORMS.values():
        if any(norm == f.lower() or clean_norm == f.lower() for f in forms):
            return True
            
    return False


def parse_pokemon_list(raw_text: str) -> list[str]:
    """Helper to parse a raw string of comma-separated Pokémon names."""
    if not raw_text:
        return []
    return [m.strip().lower() for m in raw_text.split(",") if m.strip()]


# Initialize dataset loading on import
load_dataset()
