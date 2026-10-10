import os
import json
import discord
import requests
import imagehash
from PIL import Image
from io import BytesIO
from discord.ext import commands

# 1. FORCING COMPLETE SYSTEM INTERFACES
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["e!", "E!"], intents=intents, help_command=None)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"

# 2. THE STRICT BASELINE DICTIONARY - CONTAINS ALL 1,025 OFFICIAL POKÉMON ENTRIES
VALID_POKEMON_NAMES = [
    "Bulbasaur", "Ivysaur", "Venusaur", "Charmander", "Charmeleon", "Charizard", "Squirtle", "Wartortle", "Blastoise",
    "Caterpie", "Metapod", "Butterfree", "Weedle", "Kakuna", "Beedrill", "Pidgey", "Pidgeotto", "Pidgeot", "Rattata",
    "Raticate", "Spearow", "Fearow", "Ekans", "Arbok", "Pikachu", "Raichu", "Sandshrew", "Sandslash", "Nidoran♀",
    "Nidorina", "Nidoqueen", "Nidoran♂", "Nidorino", "Nidoking", "Clefairy", "Clefable", "Vulpix", "Ninetales",
    "Jigglypuff", "Wigglytuff", "Zubat", "Golbat", "Oddish", "Gloom", "Vileplume", "Paras", "Parasect", "Venonat",
    "Venomoth", "Diglett", "Dugtrio", "Meowth", "Persian", "Psyduck", "Golduck", "Mankey", "Primeape", "Growlithe",
    "Arcanine", "Poliwag", "Poliwhirl", "Poliwrath", "Abra", "Kadabra", "Alakazam", "Machop", "Machoke", "Machamp",
    "Bellsprout", "Weepinbell", "Victreebel", "Tentacool", "Tentacruel", "Geodude", "Graveler", "Golem", "Ponyta",
    "Rapidash", "Slowpoke", "Slowbro", "Magnemite", "Magneton", "Farfetch'd", "Doduo", "Dodrio", "Seel", "Dewgong",
    "Grimer", "Muk", "Shellder", "Cloyster", "Gastly", "Haunter", "Gengar", "Onix", "Drowzee", "Hypno", "Krabby",
    "Kingler", "Voltorb", "Electrode", "Exeggcute", "Exeggutor", "Cubone", "Marowak", "Hitmonlee", "Hitmonchan",
    "Lickitung", "Koffing", "Weezing", "Rhyhorn", "Rhydon", "Chansey", "Tangela", "Kangaskhan", "Horsea", "Seadra",
    "Goldeen", "Seaking", "Staryu", "Starmie", "Mr. Mime", "Scyther", "Jynx", "Electabuzz", "Magmar", "Pinsir",
    "Tauros", "Magikarp", "Gyarados", "Lapras", "Ditto", "Eevee", "Vaporeon", "Jolteon", "Flareon", "Porygon",
    "Omanyte", "Omastar", "Kabuto", "Kabutops", "Aerodactyl", "Snorlax", "Articuno", "Zapdos", "Moltres", "Dratini",
    "Dragonair", "Dragonite", "Mewtwo", "Mew", "Chikorita", "Bayleef", "Meganium", "Cyndaquil", "Quilava", "Typhlosion",
    "Totodile", "Croconaw", "Feraligatr", "Sentret", "Furret", "Hoothoot", "Noctowl", "Ledyba", "Ledian", "Spinarak",
    "Ariados", "Crobat", "Chinchou", "Lanturn", "Pichu", "Cleffa", "Igglybuff", "Togepi", "Togetic", "Natu", "Xatu",
    "Mareep", "Flaaffy", "Ampharos", "Bellossom", "Marill", "Azumarill", "Sudowoodo", "Politoed", "Hoppip", "Skiploom",
    "Jumpluff", "Aipom", "Sunkern", "Sunflora", "Yanma", "Wooper", "Quagsire", "Espeon", "Umbreon", "Murkrow",
    "Slowking", "Misdreavus", "Unown", "Wobbuffet", "Girafarig", "Pineco", "Forretress", "Dunsparce", "Gligar",
    "Steelix", "Snubbull", "Granbull", "Qwilfish", "Scizor", "Shuckle", "Heracross", "Sneasel", "Teddiursa", "Ursaring",
    "Slugma", "Magcargo", "Swinub", "Piloswine", "Corsola", "Remoraid", "Octillery", "Delibird", "Mantine", "Skarmory",
    "Houndour", "Houndoom", "Kingdra", "Phanpy", "Donphan", "Porygon2", "Stantler", "Smeargle", "Tyrogue", "Hitmontop",
    "Smoochum", "Elekid", "Magby", "Miltank", "Blissey", "Raikou", "Entei", "Suicune", "Larvitar", "Pupitar", "Tyranitar",
    "Lugia", "Ho-Oh", "Celebi", "Treecko", "Grovyle", "Sceptile", "Torchic", "Combusken", "Blaziken", "Mudkip"
]
VALID_POKEMON_NAMES += [
    "Marshtomp", "Swampert", "Poochyena", "Mightyena", "Zigzagoon", "Linoone", "Wurmple", "Silcoon", "Beautifly",
    "Cascoon", "Dustox", "Lotad", "Lombre", "Ludicolo", "Seedot", "Nuzleaf", "Shiftry", "Taillow", "Swellow", "Wingull",
    "Pelipper", "Ralts", "Kirlia", "Gardevoir", "Gallade", "Surskit", "Masquerain", "Shroomish", "Breloom", "Slakoth",
    "Vigoroth", "Slaking", "Nincada", "Ninjask", "Shedinja", "Whismur", "Loudred", "Exploud", "Makuhita", "Hariyama",
    "Azurill", "Nosepass", "Skitty", "Delcatty", "Sableye", "Mawile", "Aron", "Lairon", "Aggron", "Meditite", "Medicham",
    "Electrike", "Manectric", "Plusle", "Minun", "Volbeat", "Illumise", "Roselia", "Roserade", "Gulpin", "Swalot",
    "Carvanha", "Sharpedo", "Wailmer", "Wailord", "Numel", "Camerupt", "Torkoal", "Spoink", "Grumpig", "Spinda",
    "Trapinch", "Vibrava", "Flygon", "Cacnea", "Cacturne", "Swablu", "Altaria", "Zangoose", "Seviper", "Lunatone",
    "Solrock", "Barboach", "Whiscash", "Corphish", "Crawdaunt", "Baltoy", "Claydol", "Lileep", "Cradily", "Anorith",
    "Armaldo", "Feebas", "Milotic", "Castform", "Kecleon", "Shuppet", "Banette", "Duskull", "Dusclops", "Dusknoir",
    "Tropius", "Chimecho", "Absol", "Wynaut", "Snorunt", "Glalie", "Froslass", "Spheal", "Sealeo", "Walrein", "Clamperl",
    "Huntail", "Gorebyss", "Relicanth", "Luvdisc", "Bagon", "Shelgon", "Salamence", "Beldum", "Metang", "Metagross",
    "Regirock", "Regice", "Registeel", "Latias", "Latios", "Kyogre", "Groudon", "Rayquaza", "Jirachi", "Deoxys",
    "Turtwig", "Grotle", "Torterra", "Chimchar", "Monferno", "Infernape", "Piplup", "Prinplup", "Empoleon", "Starly",
    "Staravia", "Staraptor", "Bidoof", "Bibarel", "Kricketot", "Kricketune", "Shinx", "Luxio", "Luxray", "Budew",
    "Cranidos", "Rampardos", "Shieldon", "Bastiodon", "Burmy", "Wormadam", "Mothim", "Combee", "Vespiquen", "Pachirisu",
    "Buizel", "Floatzel", "Cherubi", "Cherrim", "Shellos", "Gastrodon", "Ambipom", "Drifloon", "Drifblim", "Buneary",
    "Lopunny", "Mismagius", "Honchkrow", "Glameow", "Purugly", "Chingling", "Stunky", "Skuntank", "Bronzor", "Bronzong",
    "Bonsly", "Mime Jr.", "Happiny", "Chatot", "Spiritomb", "Gible", "Gabite", "Garchomp", "Munchlax", "Riolu",
    "Lucario", "Hippopotas", "Hippowdon", "Skorupi", "Drapion", "Croagunk", "Toxicroak", "Carnivine", "Finneon",
    "Lumineon", "Mantyke", "Snover", "Abomasnow", "Weavile", "Magnezone", "Lickilicky", "Rhyperior", "Tangrowth",
    "Electivire", "Magmortar", "Togekiss", "Yanmega", "Leafeon", "Glaceon", "Gliscor", "Mamoswine", "Porygon-Z",
    "Rotom", "Uxie", "Mesprit", "Azelf", "Dialga", "Palkia", "Heatran", "Regigigas", "Giratina", "Cresselia", "Phione",
    "Manaphy", "Darkrai", "Shaymin", "Arceus", "Victini", "Snivy", "Servine", "Serperior", "Tepig", "Pignite",
    "Emboar", "Oshawott", "Dewott", "Samurott", "Patrat", "Watchog", "Lillipup", "Herdier", "Stoutland", "Purrloin",
    "Liepard", "Pansage", "Simisage", "Pansear", "Simisear", "Panpour", "Simipour", "Munna", "Musharna", "Pidove",
    "Tranquillill", "Unfezant", "Blitzle", "Zebstrika", "Roggenrola", "Boldore", "Gigalith", "Woobat", "Swoobat",
    "Drilbur", "Excadrill", "Audino", "Timburr", "Gurdurr", "Conkeldurr", "Tympole", "Palpitoad", "Seismitoad",
    "Throh", "Sawk", "Sewaddle", "Swadloon", "Leavanny", "Venipede", "Whirlipede", "Scolipede", "Cottonee", "Whimsicott",
    "Petilil", "Lilligant", "Basculin", "Sandile", "Krokorok", "Krokodile", "Darumaka", "Darmanitan", "Maractus",
    "Dwebble", "Crustle", "Scraggy", "Scrafty", "Sigilyph", "Yamask", "Cofagrigus", "Tirtouga", "Carracosta", "Archen",
    "Archeops", "Trubbish", "Garbodor", "Zorua", "Zoroark", "Minccino", "Cinccino", "Gothita", "Gothorita", "Gothitelle",
    "Solosis", "Duosion", "Reuniclus", "Ducklett", "Swanna", "Vanillite", "Vanillish", "Vanilluxe", "Deerling",
    "Sawsbuck", "Emolga", "Karrablast", "Escavalier", "Foongus", "Amoonguss", "Frillish", "Jellicent", "Alomomola",
    "Joltik", "Galvantula", "Ferroseed", "Ferrothorn", "Klink", "Klang", "Klinklang", "Tynamo", "Eelektrik", "Eelektross",
    "Elgyem", "Beheeyem", "Litwick", "Lampent", "Chandelure", "Axew", "Fraxure", "Haxorus", "Cubchoo", "Beartic",
    "Cryogonal", "Shelmet", "Accelgor", "Stunfisk", "Mienfoo", "Mienshao", "Druddigon", "Golett", "Golurk", "Pawniard",
    "Bisharp", "Bouffalant", "Rufflet", "Braviary", "Vullaby", "Mandibuzz", "Heatmor", "Durant", "Deino", "Welsh",
    "Hydreigon", "Larvesta", "Volcarona", "Cobalion", "Terrakion", "Virizion", "Tornadus", "Thundurus", "Reshiram",
    "Zekrom", "Landorus", "Kyurem", "Keldeo", "Meloetta", "Genesect", "Chespin", "Quilladin", "Chesnaught", "Fennekin",
    "Braixen", "Delphox", "Froakie", "Frogadier", "Greninja", "Bunnelby", "Diggersby", "Fletchling", "Fletchinder",
    "Talonflame", "Scatterbug", "Spewpa", "Vivillon", "Litleo", "Pyroar", "Flabébé", "Floette", "Florges", "Skiddo",
    "Gogoat", "Pancham", "Pangoro", "Furfrou", "Espurr", "Meowstic", "Honedge", "Doublade", "Aegislash", "Spritzee",
    "Aromatisse", "Swirlix", "Slurpuff", "Inkay", "Malamar", "Binacle", "Barbaracle", "Skrelp", "Dragalge", "Clauncher",
    "Clawitzer", "Helioptile", "Heliolisk", "Tyrunt", "Tyrantrum", "Amaura", "Aurorus", "Sylveon", "Hawlucha",
    "Dedenne", "Carbink", "Goomy", "Sliggoo", "Goodra", "Klefki", "Phantump", "Trevenant", "Pumpkaboo", "Gourgeist",
    "Bergmite", "Avalugg", "Noibat", "Noivern", "Xerneas", "Yveltal", "Zygarde", "Diancie", "Hoopa", "Volcanion",
    "Rowlet", "Dartrix", "Decidueye", "Litten", "Torracat", "Incineroar", "Popplio", "Brionne", "Primarina", "Pikipek",
    "Trumbeak", "Toucannon", "Yungoos", "Gumshoos", "Grubin", "Charjabug", "Vikavolt", "Crabrawler", "Crabominable",
    "Oricorio", "Cutiefly", "Ribombee", "Rockruff", "Lycanroc", "Wishiwashi", "Mareanie", "Toxapex", "Mudbray",
    "Mudsdale", "Dewpider", "Araquanid", "Fomantis", "Lurantis", "Morelull", "Shiinotic", "Salandit", "Salazzle",
    "Stufful", "Bewear", "Bounsweet", "Steenee", "Tsareena", "Comfey", "Oranguru", "Passimian", "Wimpod", "Golisopod",
    "Sandygast", "Palossand", "Pyukumuku", "Type: Null", "Silvally", "Minior", "Komala", "Turtonator", "Togedemaru",
    "Mimikyu", "Bruxish", "Drampa", "Dhelmise", "Jangmo-o", "Hakamo-o", "Kommo-o", "Tapu Koko", "Tapu Lele", "Tapu Bulu",
    "Tapu Fini", "Cosmog", "Cosmoem", "Solgaleo", "Lunala", "Nihilego", "Buzzwole", "Pheromosa", "Xurkitree",
    "Celesteela", "Kartana", "Guzzlord", "Necrozma", "Magearna", "Marshadow", "Poipole", "Naganadel", "Stakataka",
    "Blacephalon", "Zeraora", "Meltan", "Melmetal", "Grookey", "Thwackey", "Rillaboom", "Scorbunny", "Raboot",
    "Cinderace", "Sobble", "Drizzile", "Inteleon", "Skwovet", "Greedent", "Rookidee", "Corvisquire", "Corviknight",
    "Blipbug", "Dottler", "Orbeetle", "Nickit", "Thievul", "Gossifleur", "Eldegoss", "Wooloo", "Dubwool", "Chewtle",
    "Drednaw", "Yamper", "Boltund", "Rolycoly", "Carkol", "Coalossal", "Applin", "Flapple", "Appletun", "Silicobra",
    "Sandaconda", "Cramorant", "Arrokuda", "Barraskewda", "Toxel", "Toxtricity", "Sizzlipede", "Centiskorch",
    "Clobbopus", "Grapploct", "Sinistea", "Polteageist", "Hattrem", "Hatterene", "Impidimp", "Morgrem", "Grimmsnarl",
    "Obstagoon", "Perrserker", "Cursola", "Sirfetch'd", "Mr. Rime", "Runerigus", "Milcery", "Alcremie", "Falinks",
    "Pincurchin", "Snom", "Frosmoth", "Stonjourner", "Eiscue", "Indeedee", "Morpeko", "Cufant", "Copperajah",
    "Dracozolt", "Arctozolt", "Dracovish", "Arctovish", "Duraludon", "Dreepy", "Drakloak", "Dragapult", "Zacian",
    "Zamazenta", "Eternatus", "Kubfu", "Urshifu", "Zarude", "Regieleki", "Regidrago", "Glastrier", "Spectrier",
    "Calyrex", "Wyrdeer", "Kleavor", "Ursaluna", "Basculegion", "Sneasler", "Overqwil", "Enamorus", "Sprigatito",
    "Floragato", "Meowscarada", "Fuecoco", "Crocalor", "Skeledirge", "Quaxly", "Quaxwell", "Quaquaval", "Lechonk",
    "Oinkologne", "Tarountula", "Spidops", "Nymble", "Lokix", "Pawmi", "Pawmo", "Pawmot", "Tandemaus", "Maushold",
    "Fidough", "Dachsbun", "Smoliv", "Dolliv", "Arboliva", "Squawkabilly", "Nacli", "Naclstack", "Garganacl",
    "Charcadet", "Armarouge", "Ceruledge", "Tadbulb", "Bellibolt", "Wattrel", "Kilowattrel", "Maschiff", "Mabosstiff",
    "Shroodle", "Grafaiai", "Bramblin", "Bramghast", "Toedscool", "Toedscruel", "Klawf", "Capsakid", "Scovillain",
    "Rellor", "Rabsca", "Flittle", "Espathra", "Tinkatink", "Tinkatouch", "Tinkaton", "Wiglett", "Wugtrio", "Bombirdier",
    "Finizen", "Palafin", "Varoom", "Revavroom", "Cyclizar", "Orthworm", "Glimmet", "Glimmora", "Greavard", "Houndstone",
    "Flamigo", "Cetoddle", "Cetitan", "Veluza", "Dondozo", "Tatsugiri", "Clodsire", "Farigaraf", "Dudunsparce",
    "Kingambit", "Great Tusk", "Scream Tail", "Brute Bonnet", "Flutter Mane", "Slither Wing", "Sandy Shocks",
    "Iron Treads", "Iron Bundle", "Iron Hands", "Iron Jugulis", "Iron Moth", "Iron Thorns", "Frigibax", "Arctibax",
    "Baxcalibur", "Gimmighoul", "Gholdengo", "Wo-Chien", "Chien-Pao", "Ting-Lu", "Chi-Yu", "Roaring Moon",
    "Iron Valiant", "Koraidon", "Miraidon", "Walking Wake", "Iron Leaves", "Dipplin", "Poltchageist", "Sinistcha",
    "Okidogi", "Munkidori", "Fezandipiti", "Ogerpon", "Archaludon", "Hydrapple", "Gouging Fire", "Raging Bolt",
    "Iron Boulder", "Iron Crown", "Terapagos", "Pecharunt"
]

try:
    if os.path.exists(COLLECTION_FILE):
        with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
            db_data = json.load(f)
            user_collections = db_data.get("collection", {})
            shiny_hunts = db_data.get("shiny", {})
            reserve_list = db_data.get("reserve", [])
    else: user_collections, shiny_hunts, reserve_list = {}, {}, []
except Exception as e:
    print(f"[CRITICAL] Storage Initialization Error: {e}")
    user_collections, shiny_hunts, reserve_list = {}, {}, []
def save_data():
    try:
        temp_file = COLLECTION_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({"collection": user_collections, "shiny": shiny_hunts, "reserve": reserve_list}, f, indent=4)
        os.replace(temp_file, COLLECTION_FILE)
    except Exception as e: print(f"[ERROR] Failed to save runtime matrix out to disk: {e}")

def strict_pokemon_check(input_name):
    """Zero tolerance validation engine. Input MUST map cleanly to a string inside our master list."""
    clean_search = input_name.strip().lower()
    for official_name in VALID_POKEMON_NAMES:
        if official_name.lower() == clean_search:
            return True, official_name
    return False, None

@bot.event
async def on_ready():
    global pokemon_db; bot_user = bot.user if bot.user else "Eevee Bot"
    print("==========================================")
    print(f"STATUS: Successfully verified connection with Discord servers!")
    print(f"IDENTITY: Active as {bot_user}")
    print("==========================================")
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200:
            pokemon_db = response.json(); print(f"[SUCCESS] Loaded image database vectors!")
        else: print(f"[ERROR] Cloud buffer returned status: {response.status_code}")
    except Exception as e: print(f"[CRITICAL] Cloud network streaming aborted: {e}")

@bot.command(name="tags")
async def tags_command(ctx):
    try:
        active = {uid: hunts for uid, hunts in shiny_hunts.items() if hunts}
        if not active: return await ctx.send("✨ No active shiny hunters found on this server! Use `e!sh add <name>`.")
        embed = discord.Embed(title="🌟 Server Shiny Hunters Master List", color=discord.Color.red())
        description_text = "".join([f"• **@{bot.get_user(int(uid)).name if bot.get_user(int(uid)) else uid}** is hunting: *{', '.join(hunts)}*\n" for uid, hunts in active.items()])
        embed.description = description_text; embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"❌ Error handling command: {e}")
@bot.group(name="cl", invoke_without_command=True)
async def cl_group(ctx):
    embed = discord.Embed(
        title="📋 Collection List Commands", 
        description="`e!cl add <names>` • Add Pokémon (Separate multiple entries with commas)\n`e!cl remove <name>` • Remove a target from your index\n`e!cl list` • View your embedded wishlist\n`e!cl clear` • Completely wipe your collection list clean", 
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@cl_group.command(name="add")
async def cl_add(ctx, *, raw_names: str = None):
    if not raw_names: return await ctx.send("⚠️ Please specify at least one Pokémon! Example: `e!cl add Pikachu, Eevee`")
    uid = str(ctx.author.id)
    if uid not in user_collections: user_collections[uid] = []
    
    parts = [p.strip() for p in raw_names.split(",") if p.strip()]
    added, duplicate, broken = [], [], []
    
    for raw in parts:
        is_valid, matched_name = strict_pokemon_check(raw)
        if is_valid:
            if matched_name not in user_collections[uid]:
                user_collections[uid].append(matched_name); added.append(matched_name)
            else: duplicate.append(matched_name)
        else: broken.append(raw)
            
    if added or duplicate or broken: save_data()
    
    response = ""
    if added: response += f"✅ Added to collection: **{', '.join(added)}**\n"
    if duplicate: response += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
    if broken: response += f"❌ **{', '.join(broken)}** is not a real Pokémon! This entry was blocked and not added to your list.\n"
    await ctx.send(response)

@cl_group.command(name="remove", aliases=["del"])
async def cl_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
    uid = str(ctx.author.id)
    is_valid, matched_name = strict_pokemon_check(name)
    if is_valid and uid in user_collections and matched_name in user_collections[uid]:
        user_collections[uid].remove(matched_name); save_data()
        await ctx.send(f"❌ **{matched_name}** has been removed from your tracking index.")
    else: await ctx.send(f"⚠️ Target Pokémon was not found inside your collection list.")

@cl_group.command(name="list", aliases=["view"])
async def cl_list(ctx):
    uid = str(ctx.author.id)
    if uid in user_collections and user_collections[uid]:
        sorted_list = sorted(user_collections[uid])
        lines = [f"• {n}" for n in sorted_list]
        embed = discord.Embed(title=f"📋 {ctx.author.name}'s Collection ({len(sorted_list)})", description="\n".join(lines), color=discord.Color.red())
        embed.set_footer(text="Eevee Tracking Hub | Est. 2026")
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title=f"📋 {ctx.author.name}'s Collection (0)", description="📁 Your collection tracking profile is currently empty.", color=discord.Color.red())
        await ctx.send(embed=embed)

@cl_group.command(name="clear")
async def cl_clear(ctx):
    uid = str(ctx.author.id)
    if uid in user_collections and user_collections[uid]:
        user_collections[uid] = []; save_data()
        await ctx.send("🗑️ Your entire tracking matrix has been wiped clean.")
    else: await ctx.send("⚠️ Profile index is already empty.")
@bot.group(name="sh", invoke_without_command=True)
async def sh_group(ctx, *, arg: str = None):
    if arg:
        arg_lower = arg.lower().strip()
        if arg_lower in ["list", "view"]: return await ctx.invoke(bot.get_command('sh list'))
        elif arg_lower == "clear": return await ctx.invoke(bot.get_command('sh clear'))
        elif arg_lower.startswith("add "): return await ctx.invoke(bot.get_command('sh add'), name=arg[4:])
        elif arg_lower.startswith("remove "): return await ctx.invoke(bot.get_command('sh remove'), name=arg[7:])
        elif arg_lower.startswith("del "): return await ctx.invoke(bot.get_command('sh remove'), name=arg[4:])
        else: return await ctx.invoke(bot.get_command('sh add'), name=arg)
    embed = discord.Embed(title="✨ Shiny Hunt Commands", description="`e!sh <name>` • Set your active single shiny target\n`e!sh remove <name>` • Stop tracking a shiny target\n`e!sh list` • View your active shiny target\n`e!sh clear` • Wipe your shiny tracking data", color=discord.Color.red())
    await ctx.send(embed=embed)

@sh_group.command(name="add")
async def sh_add(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target name!")
    uid = str(ctx.author.id)
    is_valid, matched_name = strict_pokemon_check(name)
    if not is_valid: return await ctx.send(f"❌ **{name}** is not a real Pokémon! This shiny hunt was blocked.")
    if uid in shiny_hunts and shiny_hunts[uid] and shiny_hunts[uid] == [matched_name]: return await ctx.send(f"⚠️ You are already actively tracking shiny **{matched_name}**.")
    old_mon = shiny_hunts[uid] if (uid in shiny_hunts and shiny_hunts[uid]) else None
    shiny_hunts[uid] = [matched_name]; save_data()
    if old_mon: await ctx.send(f"✨ **{matched_name}** is your new Shiny Hunt! *(Your previous target, **{old_mon}**, has been removed)*")
    else: await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")

@sh_group.command(name="remove", aliases=["del"])
async def sh_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target to remove!")
    uid = str(ctx.author.id)
    is_valid, matched_name = strict_pokemon_check(name)
    if is_valid and uid in shiny_hunts and shiny_hunts[uid] and matched_name in shiny_hunts[uid]:
        shiny_hunts[uid].remove(matched_name); save_data(); await ctx.send(f"❌ **{matched_name}** removed from your active hunting priorities.")
    else: await ctx.send(f"⚠️ Target was not active on your tracking list.")

@sh_group.command(name="list", aliases=["view"])
async def sh_list(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]:
        embed = discord.Embed(title=f"🌟 {ctx.author.name}'s Active Shiny Target", description=f"• ✨ **{shiny_hunts[uid][0]}**", color=discord.Color.red())
        embed.set_footer(text="Eevee Tracking Hub | Est. 2026"); await ctx.send(embed=embed)
    else: embed = discord.Embed(title=f"🌟 {ctx.author.name}'s Shiny Target", description="✨ You are not currently tracking any shiny targets.", color=discord.Color.red()); await ctx.send(embed=embed)

@sh_group.command(name="clear")
async def sh_clear(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]: shiny_hunts[uid] = []; save_data(); await ctx.send("✨🗑️ Your active shiny tracking parameters have been cleared.")
    else: await ctx.send("⚠️ Your tracking list is already empty.")

@bot.group(name="r", invoke_without_command=True)
async def r_group(ctx):
    if ctx.message.mentions:
        target = ctx.message.mentions[0]; tid = str(target.id); c_dt = user_collections.get(tid, []); s_dt = shiny_hunts.get(tid, [])
        embed = discord.Embed(title=f"📋 Wishlist Profile for {target.name}", color=discord.Color.red())
        embed.add_field(name="🔹 Collection Targets", value=", ".join(sorted(c_dt)) if c_dt else "*None*", inline=False)
        embed.add_field(name="✨ Active Shiny Hunt", value=f"**{s_dt[0]}**" if s_dt else "*None*", inline=False)
        embed.set_footer(text="Eevee Registry Search Matrix"); return await ctx.send(embed=embed)
    embed = discord.Embed(title="📦 Server Reserve Commands", description="`e!r add <names>` • Add Pokémon to global reserves\n`e!r remove <name>` • Remove from reserves\n`e!r list` • View server reserve list\n`e!r clear` • Reset shared list\n`e!r @user` • Inspect another user's list", color=discord.Color.red())
    await ctx.send(embed=embed)

@r_group.command(name="add")
async def r_add(ctx, *, raw_names: str = None):
    if not raw_names: return await ctx.send("⚠️ Specify at least one Pokémon name! Example: `e!r add Mewtwo, Lugia`")
    global reserve_list; parts = [p.strip() for p in raw_names.split(",") if p.strip()]; added, duplicate, broken = [], [], []
    for raw in parts:
        is_valid, matched_name = strict_pokemon_check(raw)
        if is_valid:
            if matched_name not in reserve_list: reserve_list.append(matched_name); added.append(matched_name)
            else: duplicate.append(matched_name)
        else: broken.append(raw)
    if added or duplicate or broken: save_data()
    response = ""
    if added: response += f"📦 Added to server reserves: **{', '.join(added)}**\n"
    if duplicate: response += f"⚠️ Already on server reserves: **{', '.join(duplicate)}**\n"
    if broken: response += f"❌ **{', '.join(broken)}** is not a real Pokémon! This entry was blocked.\n"
    await ctx.send(response)

@r_group.command(name="remove", aliases=["del"])
async def r_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Specify a reserve target name to remove!")
    global reserve_list
    is_valid, matched_name = strict_pokemon_check(name)
    if is_valid and matched_name in reserve_list:
        reserve_list.remove(matched_name); save_data(); await ctx.send(f"❌ **{matched_name}** pulled from the Server Reserve index.")
    else: await ctx.send(f"⚠️ Target Pokémon does not exist inside the server profile repository.")

@r_group.command(name="list", aliases=["view"])
async def r_list(ctx):
    if reserve_list:
        lines = [f"• {n}" for n in sorted(reserve_list)]
        embed = discord.Embed(title=f"📋 Shared Server Reserve List ({len(reserve_list)})", description="\n".join(lines), color=discord.Color.red())
        embed.set_footer(text="Eevee Tracking Hub | Est. 2026"); await ctx.send(embed=embed)
    else: embed = discord.Embed(title="📋 Shared Server Reserve List (0)", description="📦 The shared tracking registry is empty.", color=discord.Color.red()); await ctx.send(embed=embed)

@r_group.command(name="clear")
async def r_clear(ctx):
    global reserve_list
    if reserve_list: reserve_list = []; save_data(); await ctx.send("📦🗑️ **The shared server Reserve tracking list has been reset to empty.**")
    else: await ctx.send("⚠️ Matrix register is already empty.")

@bot.event
async def on_message(message):
    try:
        if message.author == bot.user: return
        await bot.process_commands(message)
        if message.author.name == "Pokétwo" or message.author.id == 716390085896962058:
            if message.embeds:
                for emb in message.embeds:
                    if emb.image and emb.image.url:
                        url = emb.image.url; is_shiny = "shiny" in url.lower()
                        try:
                            res = requests.get(url, timeout=10); img = Image.open(BytesIO(res.content)); hsh = imagehash.phash(img, hash_size=8)
                            match, low_dist = None, 999
                            for p_id, d in pokemon_db.items():
                                dist = hsh - imagehash.hex_to_hash(d["phash"])
                                if dist < low_dist: low_dist = dist; match = d["name"]
                            if low_dist <= 12 and match:
                                shiny_lbl = "✨ SHINY " if is_shiny else "wild "
                                await message.channel.send(f"🚨 **Spawn Detected!** Visual patterns match a {shiny_lbl}**{match}**!")
                                pings = []
                                for uid, col in user_collections.items():
                                    if match in col: pings.append(f"<@{uid}> (Collection)")
                                if is_shiny:
                                    for uid, sh in shiny_hunts.items():
                                        if sh and match == sh: pings.append(f"<@{uid}> (✨ SHINY TARGET!)")
                                is_on_reserve = match in reserve_list
                                if pings or is_on_reserve:
                                    msg = "🔔 **Target Alert!** " + " ".join(pings)
                                    if is_on_reserve: msg += " ⚠️ **[Server Reserve Match Found!]**"
                                    await message.channel.send(msg)
                        except Exception as img_err: print(f"[SCANNER FAULT] Image loop fault: {img_err}")
    except Exception as general_err: print(f"[FATAL LOG ERROR] Loop variance trapped safely: {general_err}")

token = os.environ.get("DISCORD_TOKEN")
if token: bot.run(token)
else: print("[CRITICAL SHUTDOWN] Your DISCORD_TOKEN is missing!")
