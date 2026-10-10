import os
import json
import discord
import requests
import imagehash
import re
from PIL import Image
from io import BytesIO
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["e!", "E!"], intents=intents, help_command=None)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"

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
            reserve_data = db_data.get("reserve_data", {})  
    else: user_collections, shiny_hunts, reserve_data = {}, {}, []
except Exception as e:
    print(f"[CRITICAL] Storage Initialization Error: {e}")
    user_collections, shiny_hunts, reserve_data = {}, {}, []
def save_data():
    try:
        temp_file = COLLECTION_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({"collection": user_collections, "shiny": shiny_hunts, "reserve_data": reserve_data}, f, indent=4)
        os.replace(temp_file, COLLECTION_FILE)
    except Exception as e: print(f"[ERROR] Failed to save disk block: {e}")

def strict_pokemon_check(input_name):
    clean_search = input_name.strip().lower()
    for official_name in VALID_POKEMON_NAMES:
        if official_name.lower() == clean_search: return True, official_name
    return False, None

class DynamicListPaginator(discord.ui.View):
    def __init__(self, data_list, card_title, chunk_size=20):
        super().__init__(timeout=180)
        self.data_list = data_list
        self.card_title = card_title
        self.chunk_size = chunk_size
        self.current_page = 0
        self.total_pages = max(1, (len(data_list) - 1) // chunk_size + 1)

    def get_page_embed(self):
        start = self.current_page * self.chunk_size
        end = start + self.chunk_size
        chunk = self.data_list[start:end]
        
        embed = discord.Embed(title=f"{self.card_title} ({len(self.data_list)} Total)", color=discord.Color.red())
        embed.description = "\n".join(chunk)
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.grey)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else: await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.grey)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else: await interaction.response.defer()

@bot.event
async def on_ready():
    global pokemon_db; bot_user = bot.user if bot.user else "Eevee Bot"
    print("==========================================")
    print(f"STATUS: Successfully verified connection with Discord servers!")
    print(f"IDENTITY: Active as {bot_user}")
    print("==========================================")
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200: pokemon_db = response.json()
    except Exception as e: print(f"[CRITICAL] Cloud synchronization aborted: {e}")
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
    embed = discord.Embed(title="📋 Collection List Commands", description="`e!cl add <names>` • Add Pokémon (Separate entries with commas)\n`e!cl remove <name>` • Remove a target\n`e!cl list` • View your wishlist embed (20 entries per page)\n`e!cl clear` • Wipe list clean", color=discord.Color.red())
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
            if matched_name not in user_collections[uid]: user_collections[uid].append(matched_name); added.append(matched_name)
            else: duplicate.append(matched_name)
        else: broken.append(raw)
    if added or duplicate or broken: save_data()
    res = ""
    if added: res += f"✅ Added: **{', '.join(added)}**\n"
    if duplicate: res += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
    if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon! Blocked.\n"
    await ctx.send(res)

@cl_group.command(name="remove", aliases=["del"])
async def cl_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
    uid = str(ctx.author.id); is_valid, matched_name = strict_pokemon_check(name)
    if is_valid and uid in user_collections and matched_name in user_collections[uid]:
        user_collections[uid].remove(matched_name); save_data()
        await ctx.send(f"❌ **{matched_name}** has been removed.")
    else: await ctx.send(f"⚠️ Target Pokémon was not found inside your list.")

@cl_group.command(name="list", aliases=["view"])
async def cl_list(ctx):
    uid = str(ctx.author.id)
    if uid in user_collections and user_collections[uid]:
        formatted_wishlist = [f"• **{n}**" for n in sorted(user_collections[uid])]
        paginator = DynamicListPaginator(data_list=formatted_wishlist, card_title=f"📋 {ctx.author.name}'s Collection Wishlist")
        await ctx.send(embed=paginator.get_page_embed(), view=paginator)
    else: await ctx.send("📁 Your collection list is empty.")

@cl_group.command(name="clear")
async def cl_clear(ctx):
    user_collections[str(ctx.author.id)] = []; save_data(); await ctx.send("🗑 Wiped collection clean.")

@bot.group(name="sh", invoke_without_command=True)
async def sh_group(ctx, *, arg: str = None):
    if arg:
        arg_lower = arg.lower().strip()
        if arg_lower in ["list", "view"]: return await ctx.invoke(bot.get_command('sh list'))
        elif arg_lower == "clear": return await ctx.invoke(bot.get_command('sh clear'))
        elif arg_lower.startswith("remove ") or arg_lower.startswith("del "): return await ctx.invoke(bot.get_command('sh remove'), name=arg.split(" ", 1))
        else: return await ctx.invoke(bot.get_command('sh add'), name=arg.split(" ", 1) if arg_lower.startswith("add ") else arg)
    await ctx.send(embed=discord.Embed(title="✨ Shiny Hunt Commands", description="`e!sh <name>` • Set active shiny target\n`e!sh remove <name>` • Drop shiny target\n`e!sh list` • View target\n`e!sh clear` • Wipe data", color=discord.Color.red()))

@sh_group.command(name="add")
async def sh_add(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target name!")
    uid = str(ctx.author.id); is_valid, matched_name = strict_pokemon_check(name)
    if not is_valid: return await ctx.send(f"❌ **{name}** is not a real Pokémon!")
    if uid in shiny_hunts and shiny_hunts[uid] == [matched_name]: return await ctx.send(f"⚠️ Already tracking shiny **{matched_name}**.")
    old_mon = shiny_hunts[uid] if (uid in shiny_hunts and shiny_hunts[uid]) else None
    shiny_hunts[uid] = [matched_name]; save_data()
    if old_mon: await ctx.send(f"✨ **{matched_name}** is your new Shiny Hunt! *(Previous target **{old_mon}** removed)*")
    else: await ctx.send(f"✨ **{matched_name}** registered as your active Shiny Hunt!")

@sh_group.command(name="remove", aliases=["del"])
async def sh_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target to remove!")
    uid = str(ctx.author.id); is_valid, matched_name = strict_pokemon_check(name)
    if is_valid and uid in shiny_hunts and matched_name in shiny_hunts[uid]: shiny_hunts[uid].remove(matched_name); save_data(); await ctx.send(f"❌ **{matched_name}** removed.")
    else: await ctx.send(f"⚠️ Target was not active on your list.")

@sh_group.command(name="list", aliases=["view"])
async def sh_list(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]: await ctx.send(embed=discord.Embed(title=f"🌟 {ctx.author.name}'s Active Shiny Target", description=f"• ✨ **{shiny_hunts[uid]}**", color=discord.Color.red()))
    else: await ctx.send("✨ You are not currently tracking any shiny targets.")

@sh_group.command(name="clear")
async def sh_clear(ctx):
    shiny_hunts[str(ctx.author.id)] = []; save_data(); await ctx.send("✨🗑 Shiny hunt cleared.")
@bot.group(name="r", invoke_without_command=True)
async def r_group(ctx):
    if ctx.message.mentions and not ctx.subcommand_passed:
        target_user = ctx.message.mentions
        tid = str(target_user.id)
        u_list = reserve_data.get(tid, [])
        if u_list:
            embed = discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• **{n}**" for n in sorted(u_list)]), color=discord.Color.red())
            return await ctx.send(embed=embed)
        else: return await ctx.send(embed=discord.Embed(title=f"📋 Reserves for {target_user.name} (0)", description="📦 This user has no Pokémon reserved.", color=discord.Color.red()))
            
    embed = discord.Embed(title="📦 Server Reserve Commands", description="`e!r add <names> @user` • Reserve Pokémon for a specific user (commas allowed)\n`e!r remove <names> @user` • Drop reserved targets from a user (commas allowed)\n`e!r remove @user` • Completely clear all active reserves for that user only\n`e!r @user` • View the reserved list for a specific person\n`e!r list` • View the entire server's reserve listings (20 entries per page)\n`e!r clear` • Wipe the absolute entire server reserve file data clean\n`e!r e @mainuser` • Reply to a list of trades to transfer them all from @mainuser", color=discord.Color.red())
    await ctx.send(embed=embed)

@r_group.command(name="add")
async def r_add(ctx, *, args: str = None):
    if not args or not ctx.message.mentions: return await ctx.send("⚠️ Format: `e!r add Pikachu, Eevee @user`")
    target_user = ctx.message.mentions; tid = str(target_user.id)
    raw_names = re.sub(r'<@!?\d+>', '', args).strip()
    parts = [p.strip() for p in raw_names.split(",") if p.strip()]
    if tid not in reserve_data: reserve_data[tid] = []
    added, duplicate, broken = [], [], []
    for raw in parts:
        is_valid, matched = strict_pokemon_check(raw)
        if is_valid:
            if matched not in reserve_data[tid]: reserve_data[tid].append(matched); added.append(matched)
            else: duplicate.append(matched)
        else: broken.append(raw)
    if added or duplicate or broken: save_data()
    res = ""
    if added: res += f"✅ Added to reserves for <@{tid}>: **{', '.join(added)}**\n"
    if duplicate: res += f"⚠️ Already reserved: **{', '.join(duplicate)}**\n"
    if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon! Blocked.\n"
    await ctx.send(res)

@r_group.command(name="remove", aliases=["del"])
async def r_remove(ctx, *, args: str = None):
    if not args or not ctx.message.mentions: return await ctx.send("⚠️ Format: `e!r remove Pikachu @user` or `e!r remove @user`")
    target_user = ctx.message.mentions; tid = str(target_user.id)
    raw_input = re.sub(r'<@!?\d+>', '', args).strip()
    if not raw_input:
        if tid in reserve_data and reserve_data[tid]:
            reserve_data[tid] = []; save_data(); return await ctx.send(f"🗑 Wiped all reserves for <@{tid}>!")
        else: return await ctx.send(f"⚠️ <@{tid}> has no active reserves.")
    parts = [p.strip() for p in raw_input.split(",") if p.strip()]
    removed, missing = [], []
    if tid in reserve_data:
        for raw in parts:
            is_valid, matched = strict_pokemon_check(raw)
            if is_valid and matched in reserve_data[tid]: reserve_data[tid].remove(matched); removed.append(matched)
            else: missing.append(raw)
    if removed: save_data()
    res = ""
    if removed: res += f"❌ Removed from <@{tid}>: **{', '.join(removed)}**\n"
    if missing: res += f"⚠️ Not found on their list: **{', '.join(missing)}**\n"
    await ctx.send(res)

@r_group.command(name="list", aliases=["view"])
async def r_list(ctx):
    formatted_entries = []
    for uid, arr in reserve_data.items():
        for name in arr: formatted_entries.append(f"• **{name}** - <@{uid}>")
            
    if not formatted_entries:
        return await ctx.send(embed=discord.Embed(title="📋 Server Reserves Manifest (0)", description="📦 No Pokémon are currently reserved on this server.", color=discord.Color.red()))
    
    formatted_entries.sort()
    paginator = DynamicListPaginator(data_list=formatted_entries, card_title="📋 Shared Server Reserve Manifest", chunk_size=20)
    await ctx.send(embed=paginator.get_page_embed(), view=paginator)

@r_group.command(name="clear")
async def r_clear(ctx):
    global reserve_data; reserve_data = {}; save_data(); await ctx.send("📦🗑 Server Reserve Database file wiped clean!")

@r_group.command(name="e")
async def r_exchange(ctx, main_user: discord.Member = None):
    if not main_user: return await ctx.send("⚠️ Example: `e!r e @mainuser`")
    if not ctx.message.reference: return await ctx.send("⚠️ You must **reply** directly to the target list message with this command!")
    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        lines = replied_msg.content.split("\n")
        mid = str(main_user.id)
        if mid not in reserve_data or not reserve_data[mid]: return await ctx.send(f"❌ <@{mid}> has no active Pokémon reserved to exchange.")
            
        success_logs = []
        for line in lines:
            if not line.strip(): continue
            
            # FIXED ROBUST REGEX PARSER: Extracts the targeted user token out of any point on the text line
            user_find = re.search(r'<@!?(\d+)>', line)
            if user_find:
                target_uid = str(user_find.group(1))
                
                # Wipe markers, user structures, and dashes to isolate the raw Pokemon name list block
                clean_chunk = re.sub(r'<@!?\d+>', '', line).replace('•', '').replace('-', '').replace('*', '').strip()
                
                # Split entry cleanly by commas to parse multi-Pokemon transfers per single message line
                requested_names = [p.strip() for p in clean_chunk.split(",") if p.strip()]
                
                valid_transfers = []
                for name in requested_names:
                    is_valid, matched_name = strict_pokemon_check(name)
                    if is_valid and matched_name in reserve_data[mid]:
                        reserve_data[mid].remove(matched_name)
                        if target_uid not in reserve_data: reserve_data[target_uid] = []
                        if matched_name not in reserve_data[target_uid]: reserve_data[target_uid].append(matched_name)
                        valid_transfers.append(matched_name)
                        
                if valid_transfers:
                    success_logs.append(f"• **{', '.join(valid_transfers)}** transferred from <@{mid}> to <@{target_uid}>")
                    
        if success_logs:
            save_data()
            await ctx.send(embed=discord.Embed(title="🔄 Reserve Exchange Ledger Summary", description="\n".join(success_logs), color=discord.Color.red()))
        else: await ctx.send("❌ Exchange failed! Verify your formatting and confirm requested Pokémon are owned by the main user.")
    except Exception as e: await ctx.send(f"❌ Error processing context data strings: {e}")

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
                        res = requests.get(url, timeout=10); img = Image.open(BytesIO(res.content)); hsh = imagehash.phash(img, hash_size=8)
                        match, low_dist = None, 999
                        for p_id, d in pokemon_db.items():
                            dist = hsh - imagehash.hex_to_hash(d["phash"])
                            if dist < low_dist: low_dist = dist; match = d["name"]
                        if low_dist <= 12 and match:
                            shiny_lbl = "✨ SHINY " if is_shiny else "wild "
                            await message.channel.send(f"🚨 **Spawn Detected!** Pattern matches **{match}**!")
                            
                            reserve_pings = []
                            for uid, arr in reserve_data.items():
                                if match in arr: reserve_pings.append(f"<@{uid}>")
                            if reserve_pings:
                                await message.channel.send(f"🔔 **Reserve Match Alert!** " + " ".join(list(set(reserve_pings))) + " - This target was specifically reserved for you!")
                            else:
                                normal_pings = []
                                for uid, col in user_collections.items():
                                    if match in col: normal_pings.append(f"<@{uid}>")
                                if is_shiny:
                                    for uid, sh in shiny_hunts.items():
                                        if sh and match == sh: normal_pings.append(f"<@{uid}> (✨ SHINY!)")
                                if normal_pings: await message.channel.send(f"🔔 **Wishlist Alert!** " + " ".join(list(set(normal_pings))))
    except Exception as general_err: print(f"[FATAL SCANNER LOG] Trapped safely: {general_err}")

bot.run(os.environ.get("DISCORD_TOKEN"))
