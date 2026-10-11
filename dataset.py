import json
import os
import urllib.request# Multi-Form Registries (Refined Form Set)
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


load_dataset()
