import re

# Standard Multi-form and Variant mappings
MULTI_FORM_MAP = {
    # Custom Overrides
    "rotom": ["Rotom", "Heat Rotom", "Wash Rotom", "Frost Rotom", "Fan Rotom", "Mow Rotom", "DJ Rotom"],
    "burmy": ["Sand Burmy", "Trash Burmy"],
    "lycanroc": ["Lycanroc", "Midnight Lycanroc", "Dusk Lycanroc"],
    "morpeko": ["Morpeko", "Hangry Morpeko"],
    "meloetta": ["Meloetta", "Pirouette Meloetta"],
    "koraidon": ["Koraidon", "Sprinting Build Koraidon", "Gliding Build Koraidon"],
    "miraidon": ["Drive Mode Miraidon", "Glide Mode Miraidon"],
    "terapagos": ["Terapagos", "Terastal Terapagos"],
    "genesect": ["Genesect", "High-speed flight configuration Genesect"],
    "tatsugiri": ["Tatsugiri", "Droopy Tatsugiri", "Stretchy Tatsugiri"],

    # Screenshot Mappings
    "shellos": ["Shellos", "West Sea Shellos", "East Sea Shellos"],
    "gastrodon": ["Gastrodon", "West Sea Gastrodon", "East Sea Gastrodon"],
    "basculin": ["Basculin", "Red-Striped Basculin", "Blue-Striped Basculin", "White-Striped Basculin"],
    "deerling": ["Deerling", "Spring Deerling", "Summer Deerling", "Autumn Deerling", "Winter Deerling"],
    "sawsbuck": ["Sawsbuck", "Spring Sawsbuck", "Summer Sawsbuck", "Autumn Sawsbuck", "Winter Sawsbuck"],
    "wishiwashi": ["Wishiwashi", "Solo Wishiwashi", "School Wishiwashi"],
    "toxtricity": ["Toxtricity", "Amped Toxtricity", "Low Key Toxtricity"],
    "alcremie": [
        "Alcremie", "Berry Sweet Alcremie", "Love Sweet Alcremie", 
        "Star Sweet Alcremie", "Clover Sweet Alcremie", "Flower Sweet Alcremie", "Ribbon Sweet Alcremie"
    ],
    "maushold": ["Maushold", "Family of Three Maushold", "Family of Four Maushold"],
    "squawkabilly": [
        "Squawkabilly", "Green Squawkabilly", "Blue Squawkabilly", 
        "Yellow Squawkabilly", "White Squawkabilly"
    ],
    "palafin": ["Palafin", "Zero Palafin", "Hero Palafin"],
    "dudunsparce": ["Dudunsparce", "Two-Segment Dudunsparce", "Three-Segment Dudunsparce"],
    "gimmighoul": ["Gimmighoul", "Chest Gimmighoul", "Roaming Gimmighoul"],
    "ogerpon": [
        "Ogerpon", "Teal Mask Ogerpon", "Wellspring Mask Ogerpon", 
        "Hearthflame Mask Ogerpon", "Cornerstone Mask Ogerpon"
    ],
    "pikachu": ["Pikachu", "Partner Pikachu"],
    "eevee": ["Eevee", "Partner Eevee"],
    "cherrim": ["Cherrim", "Sunshine Cherrim"],
    "silvally": [
        "Silvally", "Fighting Silvally", "Flying Silvally", "Poison Silvally", "Ground Silvally", 
        "Rock Silvally", "Bug Silvally", "Ghost Silvally", "Steel Silvally", "Fire Silvally", 
        "Water Silvally", "Grass Silvally", "Electric Silvally", "Psychic Silvally", "Ice Silvally", 
        "Dragon Silvally", "Dark Silvally", "Fairy Silvally"
    ],
    "deoxys": ["Deoxys", "Attack Deoxys", "Defense Deoxys", "Speed Deoxys"],
    "marshadow": ["Marshadow", "Zenith Marshadow"],
    "xerneas": ["Xerneas", "Neutral Xerneas", "Active Xerneas"],
    "zarude": ["Zarude", "Dada Zarude"],
    "urshifu": ["Urshifu", "Single Strike Urshifu", "Rapid Strike Urshifu"],
    "zygarde": ["Zygarde", "10% Zygarde", "50% Zygarde", "Complete Zygarde"],
    "florges": [
        "Florges", "Red Flower Florges", "Yellow Flower Florges", 
        "Orange Flower Florges", "Blue Flower Florges", "White Flower Florges"
    ],
    "wormadam": ["Wormadam", "Plant Cloak Wormadam", "Sandy Cloak Wormadam", "Trash Cloak Wormadam"],
    "castform": ["Castform", "Sunny Castform", "Rainy Castform", "Snowy Castform"],
    "flabebe": [
        "Flabébé", "Red Flower Flabébé", "Yellow Flower Flabébé", 
        "Orange Flower Flabébé", "Blue Flower Flabébé", "White Flower Flabébé"
    ],
    "floette": [
        "Floette", "Red Flower Floette", "Yellow Flower Floette", 
        "Orange Flower Floette", "Blue Flower Floette", "White Flower Floette", "Eternal Flower Floette"
    ],
    "vivillon": [
        "Vivillon", "Icy Snow Vivillon", "Polar Vivillon", "Tundra Vivillon", "Continental Vivillon", 
        "Garden Vivillon", "Elegant Vivillon", "Meadow Vivillon", "Modern Vivillon", "Marine Vivillon", 
        "Archipelago Vivillon", "High Plains Vivillon", "Sandstorm Vivillon", "River Vivillon", 
        "Monsoon Vivillon", "Savanna Vivillon", "Sun Vivillon", "Ocean Vivillon", "Jungle Vivillon", 
        "Fancy Vivillon", "Poké Ball Vivillon"
    ],
    "pichu": ["Pichu", "Spiky-eared Pichu"],
    "arceus": [
        "Arceus", "Fighting Arceus", "Flying Arceus", "Poison Arceus", "Ground Arceus", 
        "Rock Arceus", "Bug Arceus", "Ghost Arceus", "Steel Arceus", "Fire Arceus", 
        "Water Arceus", "Grass Arceus", "Electric Arceus", "Psychic Arceus", "Ice Arceus", 
        "Dragon Arceus", "Dark Arceus", "Fairy Arceus"
    ],
    "furfrou": [
        "Furfrou", "Heart Trim Furfrou", "Star Trim Furfrou", "Diamond Trim Furfrou", 
        "Debutante Trim Furfrou", "Matron Trim Furfrou", "Dandy Trim Furfrou", 
        "La Reine Trim Furfrou", "Kabuki Trim Furfrou", "Pharaoh Trim Furfrou"
    ],
    "unown": [
        "Unown", "A Unown", "B Unown", "C Unown", "D Unown", "E Unown", "F Unown", "G Unown", 
        "H Unown", "I Unown", "J Unown", "K Unown", "L Unown", "M Unown", "N Unown", "O Unown", 
        "P Unown", "Q Unown", "R Unown", "S Unown", "T Unown", "U Unown", "V Unown", "W Unown", 
        "X Unown", "Y Unown", "Z Unown", "! Unown", "? Unown"
    ],
    "oricorio": ["Oricorio", "Pom-Pom Style Oricorio", "Pa'u Style Oricorio", "Sensu Style Oricorio"],
    "eiscue": ["Eiscue", "Ice Face Eiscue", "Noice Face Eiscue"],
    "cramorant": ["Cramorant", "Gulping Form Cramorant", "Gorging Form Cramorant"]
}

def is_valid_pokemon(name: str) -> bool:
    """Blocks Mega and Gigantamax forms strictly."""
    lowered = name.lower()
    if "mega " in lowered or "gigantamax" in lowered or "g-max" in lowered or lowered.startswith("gmax "):
        return False
    return True

def get_all_forms(pokemon_name: str) -> list:
    """Returns all variants of a species if available."""
    key = pokemon_name.strip().lower()
    if key in MULTI_FORM_MAP:
        return MULTI_FORM_MAP[key]
    return [pokemon_name.strip().title()]
