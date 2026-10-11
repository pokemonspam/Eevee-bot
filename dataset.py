import json
import os
import urllib.request

# Multi-Form Registries (Excluding 'Normal' variants, Chest Gimmighoul, and specified Terapagos forms)
POKEMON_FORMS = {
    "rotom": [
        "Rotom", "Heat Rotom", "Wash Rotom", "Frost Rotom", "Fan Rotom", 
        "Mow Rotom", "DJ Rotom", "Rotom Pokédex", "Rotom Phone", "Rotom Drone"
    ],
    "burmy": ["Burmy", "Sandy Burmy", "Trash Burmy"],
    "castform": ["Castform", "Sunny Castform", "Rainy Castform", "Snowy Castform"],
    "lycanroc": ["Lycanroc", "Midnight Lycanroc", "Dusk Lycanroc"],
    "flabébé": [
        "Flabébé", "Yellow Flower Flabébé", "Orange Flower Flabébé", 
        "Blue Flower Flabébé", "White Flower Flabébé"
    ],
    "flabebe": [
        "Flabébé", "Yellow Flower Flabébé", "Orange Flower Flabébé", 
        "Blue Flower Flabébé", "White Flower Flabébé"
    ],
    "floette": [
        "Floette", "Yellow Flower Floette", "Orange Flower Floette", 
        "Blue Flower Floette", "White Flower Floette"
    ],
    "vivillon": [
        "Vivillon", "Icy Snow Vivillon", "Polar Vivillon", "Tundra Vivillon", 
        "Continental Vivillon", "Garden Vivillon", "Elegant Vivillon", 
        "Modern Vivillon", "Marine Vivillon", "Archipelago Vivillon", 
        "High Plain Vivillon", "Sandstorm Vivillon", "River Vivillon", 
        "Monsoon Vivillon", "Savanna Vivillon", "Sun Vivillon", "Ocean Vivillon", 
        "Jungle Vivillon", "Fancy Vivillon", "Poké Ball Vivillon"
    ],
    "furfrou": [
        "Furfrou", "Heart Trim Furfrou", "Star Trim Furfrou", "Diamond Trim Furfrou", 
        "Debutante Trim Furfrou", "Matron Trim Furfrou", "Dandy Trim Furfrou", 
        "La Reine Trim Furfrou", "Kabuki Trim Furfrou", "Pharaoh Trim Furfrou"
    ],
    "unown": [
        "Unown", "Unown A", "Unown B", "Unown C", "Unown D", "Unown E", "Unown G", 
        "Unown H", "Unown I", "Unown J", "Unown K", "Unown L", "Unown M", "Unown N", 
        "Unown O", "Unown P", "Unown Q", "Unown R", "Unown S", "Unown T", "Unown U", 
        "Unown V", "Unown W", "Unown X", "Unown Y", "Unown Z", "Unown Exclamation", 
        "Unown Question"
    ],
    "oricorio": ["Oricorio", "Pom-pom Oricorio", "Pa'u Oricorio", "Sensu Oricorio"],
    "eiscue": ["Eiscue", "Noice Face Eiscue"],
    "cramorant": ["Cramorant", "Gulping Cramorant", "Gorging Cramorant"],
    "florges": [
        "Florges", "Yellow Flower Florges", "Orange Flower Florges", 
        "Blue Flower Florges", "White Flower Florges"
    ],
    "wormadam": ["Wormadam", "Sandy Wormadam", "Trash Wormadam"],
    "arceus": [
        "Arceus", "Bug Arceus", "Dark Arceus", "Dragon Arceus", "Electric Arceus", 
        "Fighting Arceus", "Fire Arceus", "Flying Arceus", "Ghost Arceus", 
        "Grass Arceus", "Ground Arceus", "Ice Arceus", "Poison Arceus", 
        "Psychic Arceus", "Rock Arceus", "Steel Arceus", "Water Arceus", "Fairy Arceus"
    ],
    "silvally": [
        "Silvally", "Bug Silvally", "Dark Silvally", "Dragon Silvally", 
        "Electric Silvally", "Fighting Silvally", "Fire Silvally", "Flying Silvally", 
        "Ghost Silvally", "Grass Silvally", "Ground Silvally", "Ice Silvally", 
        "Poison Silvally", "Psychic Silvally", "Rock Silvally", "Steel Silvally", 
        "Water Silvally", "Fairy Silvally"
    ],
    "deoxys": ["Deoxys", "Attack Deoxys", "Defense Deoxys", "Speed Deoxys"],
    "zygarde": ["Zygarde", "10% Zygarde", "Complete Zygarde", "Zygarde Cell", "Zygarde Core"],
    "xerneas": ["Xerneas", "Neutral Xerneas"],
    "urshifu": ["Urshifu", "Rapid Strike Urshifu"],
    "koraidon": ["Koraidon", "Sprinting Build Koraidon", "Gliding Build Koraidon"],
    "miraidon": ["Miraidon", "Drive Mode Miraidon", "Glide Mode Miraidon"],
    "terapagos": ["Terapagos", "Terastal Form Terapagos"],
    "alcremie": [
        "Alcremie", "Berry Sweet Alcremie", "Love Sweet Alcremie", "Star Sweet Alcremie", 
        "Clover Sweet Alcremie", "Flower Sweet Alcremie", "Ribbon Sweet Alcremie"
    ],
    "maushold": ["Maushold", "Family of Three Maushold", "Family of Four Maushold"],
    "tatsugiri": ["Tatsugiri", "Curly Tatsugiri", "Droopy Tatsugiri", "Stretchy Tatsugiri"],
    "squawkabilly": ["Squawkabilly", "Green Squawkabilly", "Blue Squawkabilly", "Yellow Squawkabilly", "White Squawkabilly"],
    "palafin": ["Palafin", "Zero Palafin", "Hero Palafin"],
    "dudunsparce": ["Dudunsparce", "Two-Segment Dudunsparce", "Three-Segment Dudunsparce"],
    "gimmighoul": ["Gimmighoul", "Roaming Gimmighoul"]
}

POKEMON_DATASET = set()


def load_dataset():
    """Loads or auto-fetches all official Pokémon species so you don't need manual terminal commands."""
    global POKEMON_DATASET
    file_path = "pokemon_data.json"
    
    # If the file doesn't exist yet, fetch it automatically on startup
    if not os.path.exists(file_path):
        try:
            print("⏳ Fetching complete Pokémon species list...")
            url = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                species_list = [item["name"].lower() for item in data["results"]]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(species_list, f)
        except Exception as e:
            print(f"⚠️ Could not auto-fetch pokemon_data.json: {e}")

    # Load into a set for lightning-fast lookups
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
    return name.strip().title()


def get_evolution_family(species: str) -> list[str]:
    norm = normalize_name(species).replace("all ", "").strip()
    if norm in POKEMON_FORMS:
        return POKEMON_FORMS[norm]
    return [format_pokemon_name(species)]


def validate_species(name: str) -> bool:
    norm = normalize_name(name)
    
    # 1. Check API dataset (~1025+ base mons)
    if norm in POKEMON_DATASET:
        return True
    
    # 2. Check form group keys
    if norm in POKEMON_FORMS:
        return True
        
    # 3. Check individual form variant names
    for forms in POKEMON_FORMS.values():
        if any(norm == f.lower() for f in forms):
            return True
            
    return False


# Initialize on import
load_dataset()
