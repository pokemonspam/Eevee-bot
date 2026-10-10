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
# CHANGED PREFIX ROUTING MATRIX TO A! AND a! ONLY
bot = commands.Bot(command_prefix=["a!", "A!"], intents=intents, help_command=None)

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
    "Pelipper", "Ralts", "Kirlia", "Gardevoir", "Gardevoir", "Gallade", "Surskit", "Masquerain", "Shroomish", "Breloom", "Slakoth",
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
    "Cryogonad", "Shelmet", "Accelgor", "Stunfisk", "Mienfoo", "Mienshao", "Druddigon", "Golett", "Golurk", "Pawniard",
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

class GlobalDatabase:
    user_collections = {}
    shiny_hunts = {}
    reserve_data = {}

try:
    if os.path.exists(COLLECTION_FILE):
        with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
            db_data = json.load(f)
            GlobalDatabase.user_collections = db_data.get("collection", {})
            GlobalDatabase.shiny_hunts = db_data.get("shiny", {})
            GlobalDatabase.reserve_data = db_data.get("reserve_data", {})
except Exception as e:
    print(f"[CRITICAL] Storage Initialization Error: {e}")
def save_data():
    try:
        temp_file = COLLECTION_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({
                "collection": GlobalDatabase.user_collections, 
                "shiny": GlobalDatabase.shiny_hunts, 
                "reserve_data": GlobalDatabase.reserve_data
            }, f, indent=4)
        os.replace(temp_file, COLLECTION_FILE)
    except Exception as e: 
        print(f"[ERROR] Failed to save database layer: {e}")

def strict_pokemon_check(input_name):
    clean_search = input_name.strip().lower()
    for official_name in VALID_POKEMON_NAMES:
        if official_name.lower() == clean_search: 
            return True, official_name
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
        else: 
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.grey)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else: 
            await interaction.response.defer()
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
            pokemon_db = response.json()
    except Exception as e: 
        print(f"[CRITICAL] Network cloud stream broken: {e}")

@bot.command(name="tags", aliases=["A!tags", "a!tags"])
async def tags_command(ctx):
    try:
        active = {uid: hunts for uid, hunts in GlobalDatabase.shiny_hunts.items() if hunts}
        if not active: 
            return await ctx.send("✨ No active shiny hunters found on this server! Use `a!sh add <name>`.")
        embed = discord.Embed(title="🌟 Server Shiny Hunters Master List", color=discord.Color.red())
        description_text = "".join([f"• **@{bot.get_user(int(uid)).name if bot.get_user(int(uid)) else uid}** is hunting: *{', '.join(hunts)}*\n" for uid, hunts in active.items()])
        embed.description = description_text
        embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: 
        await ctx.send(f"❌ Error handling command: {e}")
@bot.command(name="cl", aliases=["A!cl"])
async def cl_base_router(ctx, subcommand: str = None, *, arguments: str = None):
    if not subcommand:
        embed = discord.Embed(title="📋 Collection List Commands", description="`a!cl add <names>` • Add Pokémon (Separate entries with commas)\n`a!cl remove <name>` • Remove a target\n`a!cl list` • View your wishlist embed (20 entries per page)\n`a!cl clear` • Wipe list clean", color=discord.Color.red())
        return await ctx.send(embed=embed)
        
    sub_clean = subcommand.lower().strip()
    if sub_clean == "add":
        if not arguments: 
            return await ctx.send("⚠️ Please specify at least one Pokémon! Example: `a!cl add Pikachu, Eevee`")
        uid = str(ctx.author.id)
        if uid not in GlobalDatabase.user_collections: 
            GlobalDatabase.user_collections[uid] = []
        parts = [p.strip() for p in arguments.split(",") if p.strip()]
        added, duplicate, broken = [], [], []
        for raw in parts:
            is_valid, matched_name = strict_pokemon_check(raw)
            if is_valid:
                if matched_name not in GlobalDatabase.user_collections[uid]: 
                    GlobalDatabase.user_collections[uid].append(matched_name)
                    added.append(matched_name)
                else: 
                    duplicate.append(matched_name)
            else: 
                broken.append(raw)
        if added or duplicate or broken: 
            save_data()
        res = ""
        if added: res += f"✅ Added: **{', '.join(added)}**\n"
        if duplicate: res += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
        if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon! Blocked.\n"
        await ctx.send(res)
        
    elif sub_clean in ["remove", "del"]:
        if not arguments: 
            return await ctx.send("⚠️ Please specify a Pokémon to drop!")
        uid = str(ctx.author.id)
        is_valid, matched_name = strict_pokemon_check(arguments)
        if is_valid and uid in GlobalDatabase.user_collections and matched_name in GlobalDatabase.user_collections[uid]:
            GlobalDatabase.user_collections[uid].remove(matched_name)
            save_data()
            await ctx.send(f"❌ **{matched_name}** has been removed.")
        else: 
            await ctx.send(f"⚠️ Target Pokémon was not found inside your list.")
        
    elif sub_clean in ["list", "view"]:
        uid = str(ctx.author.id)
        if uid in GlobalDatabase.user_collections and GlobalDatabase.user_collections[uid]:
            formatted_wishlist = [f"• **{n}**" for n in sorted(GlobalDatabase.user_collections[uid])]
            paginator = DynamicListPaginator(data_list=formatted_wishlist, card_title=f"📋 {ctx.author.name}'s Collection Wishlist")
            await ctx.send(embed=paginator.get_page_embed(), view=paginator)
        else: 
            await ctx.send("📁 Your collection list is empty.")
        
    elif sub_clean == "clear":
        GlobalDatabase.user_collections[str(ctx.author.id)] = []
        save_data()
        await ctx.send("🗑 Wiped collection clean.")
@bot.command(name="sh", aliases=["A!sh"])
async def sh_base_router(ctx, subcommand: str = None, *, name_arg: str = None):
    if not subcommand:
        embed = discord.Embed(title="✨ Shiny Hunt Commands", description="`a!sh add <name>` • Set active shiny target\n`a!sh remove <name>` • Drop shiny target\n`a!sh list` • View target\n`a!sh clear` • Wipe data", color=discord.Color.red())
        return await ctx.send(embed=embed)
        
    sub_clean = subcommand.lower().strip()
    
    if sub_clean not in ["add", "remove", "del", "list", "view", "clear"]:
        full_name = (subcommand + " " + name_arg) if name_arg else subcommand
        uid = str(ctx.author.id)
        is_valid, matched_name = strict_pokemon_check(full_name)
        if not is_valid: 
            return await ctx.send(f"❌ **{full_name}** is not a real Pokémon!")
        if uid in GlobalDatabase.shiny_hunts and GlobalDatabase.shiny_hunts[uid] == [matched_name]: 
            return await ctx.send(f"⚠️ Already tracking shiny **{matched_name}**.")
        GlobalDatabase.shiny_hunts[uid] = [matched_name]
        save_data()
        return await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")

    if sub_clean == "add":
        if not name_arg: 
            return await ctx.send("⚠️ Please specify a target name!")
        uid = str(ctx.author.id)
        is_valid, matched_name = strict_pokemon_check(name_arg)
        if not is_valid: 
            return await ctx.send(f"❌ **{name_arg}** is not a real Pokémon!")
        if uid in GlobalDatabase.shiny_hunts and GlobalDatabase.shiny_hunts[uid] == [matched_name]: 
            return await ctx.send(f"⚠️ Already tracking shiny **{matched_name}**.")
        GlobalDatabase.shiny_hunts[uid] = [matched_name]
        save_data()
        await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")
        
    elif sub_clean in ["remove", "del"]:
        if not name_arg: 
            return await ctx.send("⚠️ Please specify a target to remove!")
        uid = str(ctx.author.id)
        is_valid, matched_name = strict_pokemon_check(name_arg)
        if is_valid and uid in GlobalDatabase.shiny_hunts and matched_name in GlobalDatabase.shiny_hunts[uid]:
            GlobalDatabase.shiny_hunts[uid].remove(matched_name)
            save_data()
            await ctx.send(f"❌ **{matched_name}** removed.")
        else: 
            await ctx.send("⚠️ Target was not active on your list.")
        
    elif sub_clean in ["list", "view"]:
        uid = str(ctx.author.id)
        if uid in GlobalDatabase.shiny_hunts and GlobalDatabase.shiny_hunts[uid]:
            await ctx.send(embed=discord.Embed(title=f"🌟 {ctx.author.name}'s Active Shiny Target", description=f"• ✨ **{GlobalDatabase.shiny_hunts[uid]}**", color=discord.Color.red()))
        else: 
            await ctx.send("✨ You are not currently tracking any shiny targets.")
        
    elif sub_clean == "clear":
        GlobalDatabase.shiny_hunts[str(ctx.author.id)] = []
        save_data()
        await ctx.send("✨🗑 Shiny hunt cleared.")
@bot.command(name="r", aliases=["A!r"])
async def r_base_router(ctx, subcommand: str = None, *, args: str = None):
    if not subcommand:
        if ctx.message.mentions:
            target_user = ctx.message.mentions
            tid = str(target_user.id)
            u_list = GlobalDatabase.reserve_data.get(tid, [])
            if u_list:
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• **{n}**" for n in sorted(u_list)]), color=discord.Color.red())
                return await ctx.send(embed=embed)
            else: 
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} (0)", description="📦 This user has no Pokémon reserved.", color=discord.Color.red())
                return await ctx.send(embed=embed)
                
        embed = discord.Embed(title="📦 Server Reserve Commands", description="`a!r add <names> @user` • Reserve Pokémon for a specific user (commas allowed)\n`a!r remove <names> @user` • Drop reserved targets from a user (commas allowed)\n`a!r remove @user` • Completely clear all active reserves for that user only\n`a!r @user` • View the reserved list for a specific person\n`a!r list` • View the entire server's reserve listings (20 entries per page)\n`a!r clear` • Wipe the absolute entire server reserve file data clean\n`a!r e @mainuser` • Reply to a list of trades to transfer them all from @mainuser", color=discord.Color.red())
        return await ctx.send(embed=embed)
        
    sub_clean = subcommand.lower().strip()
    
    if re.search(r'<@!?(\d+)>', subcommand):
        mention_match = re.search(r'<@!?(\d+)>', subcommand)
        tid = str(mention_match.group(1))
        try:
            target_user = await bot.fetch_user(int(tid))
            u_list = GlobalDatabase.reserve_data.get(tid, [])
            if u_list:
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• **{n}**" for n in sorted(u_list)]), color=discord.Color.red())
                return await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} (0)", description="📦 This user has no Pokémon reserved.", color=discord.Color.red())
                return await ctx.send(embed=embed)
        except: 
            return await ctx.send("❌ Could not resolve that user profile target lookup tag.")
    if sub_clean == "add":
        if not args: return await ctx.send("⚠️ Format: `a!r add Pikachu, Eevee @user`")
        mention_match = re.search(r'<@!?(\d+)>', args)
        if not mention_match: return await ctx.send("⚠️ Please mention a user to reserve the Pokémon for!")
        tid = str(mention_match.group(1)); raw_names = re.sub(r'<@!?\d+>', '', args).strip()
        parts = [p.strip() for p in raw_names.split(",") if p.strip()]
        if tid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[tid] = []
        added, duplicate, broken = [], [], []
        for raw in parts:
            is_valid, matched = strict_pokemon_check(raw)
            if is_valid:
                if matched not in GlobalDatabase.reserve_data[tid]:
                    GlobalDatabase.reserve_data[tid].append(matched)
                    added.append(matched)
                else: duplicate.append(matched)
            else: broken.append(raw)
        if added or duplicate or broken: save_data()
        res = ""
        if added: res += f"📦 Added to reserves for <@{tid}>: **{', '.join(added)}**\n"
        if duplicate: res += f"⚠️ Already reserved: **{', '.join(duplicate)}**\n"
        if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon! Blocked.\n"
        await ctx.send(res)
        
    elif sub_clean in ["remove", "del"]:
        if not args: return await ctx.send("⚠️ Format: `a!r remove Pikachu @user` or `a!r remove @user`")
        mention_match = re.search(r'<@!?(\d+)>', args)
        if not mention_match: return await ctx.send("⚠️ Please mention a user to remove reserves from!")
        tid = str(mention_match.group(1)); raw_input = re.sub(r'<@!?\d+>', '', args).strip()
        if not raw_input:
            if tid in GlobalDatabase.reserve_data and GlobalDatabase.reserve_data[tid]:
                GlobalDatabase.reserve_data[tid] = []
                save_data()
                return await ctx.send(f"🗑️ Wiped all reserves for <@{tid}>!")
            else: return await ctx.send(f"⚠️ <@{tid}> has no active reserves.")
        parts = [p.strip() for p in raw_input.split(",") if p.strip()]
        removed, missing = [], []
        if tid in GlobalDatabase.reserve_data:
            for raw in parts:
                is_valid, matched = strict_pokemon_check(raw)
                if is_valid and matched in GlobalDatabase.reserve_data[tid]: 
                    GlobalDatabase.reserve_data[tid].remove(matched)
                    removed.append(matched)
                else: missing.append(raw)
        if removed: save_data()
        res = ""
        if removed: res += f"❌ Removed from <@{tid}>: **{', '.join(removed)}**\n"
        if missing: res += f"⚠️ Not found on their list: **{', '.join(missing)}**\n"
        await ctx.send(res)
        
    elif sub_clean in ["list", "view"]:
        pokemon_groups = {}
        for uid, arr in GlobalDatabase.reserve_data.items():
            for name in arr:
                if name not in pokemon_groups: pokemon_groups[name] = []
                pokemon_groups[name].append(f"<@{uid}>")
        if not pokemon_groups: return await ctx.send(embed=discord.Embed(title="📋 Server Reserves Manifest (0)", description="📦 No Pokémon are currently reserved on this server.", color=discord.Color.red()))
        formatted_entries = []
        for name in sorted(pokemon_groups.keys()):
            users_str = ", ".join(pokemon_groups[name])
            formatted_entries.append(f"• **{name}** - {users_str}")
        paginator = DynamicListPaginator(data_list=formatted_entries, card_title="📋 Shared Server Reserve Manifest", chunk_size=20)
        await ctx.send(embed=paginator.get_page_embed(), view=paginator)
        
    elif sub_clean == "clear":
        GlobalDatabase.reserve_data.clear(); save_data(); await ctx.send("📦🗑 Server Reserve Database file wiped clean!")
        
    elif sub_clean == "e":
        if not args: return await ctx.send("⚠️ Example: `a!r e @mainuser`")
        mention_match = re.search(r'<@!?(\d+)>', args)
        if not mention_match: return await ctx.send("⚠️ Please specify the main user to exchange from!")
        mid = str(mention_match.group(1))
        if not ctx.message.reference: return await ctx.send("⚠️ You must **reply** directly to the target list message with this command!")
        try:
            replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            lines = replied_msg.content.split("\n")
            if mid not in GlobalDatabase.reserve_data or not GlobalDatabase.reserve_data[mid]: return await ctx.send(f"❌ <@{mid}> has no active Pokémon reserved to exchange.")
            success_logs = []
            for line in lines:
                if not line.strip() or "-" not in line: continue
                left_part, right_part = line.split("-", 1)
                target_uid = None
                uid_match = re.search(r'(\d+)', left_part)
                if uid_match: target_uid = str(uid_match.group(1))
                else:
                    clean_tag = left_part.replace('•', '').replace('*', '').strip().lower()
                    for member in ctx.guild.members:
                        if clean_tag in member.name.lower() or (member.nick and clean_tag in member.nickname.lower()):
                            target_uid = str(member.id); break
                if target_uid:
                    clean_pokemon_block = right_part.replace('•', '').replace('*', '').strip()
                    requested_names = [p.strip() for p in clean_pokemon_block.split(",") if p.strip()]
                    valid_transfers = []
                    for name in requested_names:
                        is_valid, matched_name = strict_pokemon_check(name)
                        if is_valid and matched_name in GlobalDatabase.reserve_data[mid]:
                            if target_uid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[target_uid] = []
                            if matched_name not in GlobalDatabase.reserve_data[target_uid]: GlobalDatabase.reserve_data[target_uid].append(matched_name)
                            valid_transfers.append(matched_name)
                    if valid_transfers:
                        for t_name in valid_transfers:
                            if t_name in GlobalDatabase.reserve_data[mid]: GlobalDatabase.reserve_data[mid].remove(t_name)
                        success_logs.append(f"• **{', '.join(valid_transfers)}** transferred from <@{mid}> to <@{target_uid}>")
            if success_logs: save_data(); await ctx.send(embed=discord.Embed(title="🔄 Reserve Exchange Ledger Summary", description="\n".join(success_logs), color=discord.Color.red()))
            else: await ctx.send("❌ Exchange failed! Make sure requested Pokémon are owned by the main user.")
        except Exception as e: await ctx.send(f"❌ Error reading message context strings: {e}")
@bot.event
async def on_message(message):
    try:
        if message.author == bot.user: 
            return
        await bot.process_commands(message)
        if (message.author.name == "Pokétwo" or message.author.id == 716390085896962058) and message.embeds:
            for emb in message.embeds:
                if emb.image and emb.image.url:
                    url = emb.image.url
                    is_shiny = "shiny" in url.lower()
                    res = requests.get(url, timeout=10)
                    img = Image.open(BytesIO(res.content))
                    hsh = imagehash.phash(img, hash_size=8)
                    match, low_dist = None, 999
                    for p_id, d in pokemon_db.items():
                        dist = hsh - imagehash.hex_to_hash(d["phash"])
                        if dist < low_dist: 
                            low_dist = dist
                            match = d["name"]
                    if low_dist <= 12 and match:
                        await message.channel.send(f"🚨 **Spawn Detected!** Pattern matches **{match}**!")
                        reserve_pings = []
                        for uid, arr in GlobalDatabase.reserve_data.items():
                            if match in arr: 
                                reserve_pings.append(f"<@{uid}>")
                        if reserve_pings: 
                            await message.channel.send(f"🔔 **Reserve Match Alert!** " + " ".join(list(set(reserve_pings))) + " - Target reserved for you!")
                        else:
                            normal_pings = []
                            for uid, col in GlobalDatabase.user_collections.items():
                                if match in col: 
                                    normal_pings.append(f"<@{uid}>")
                            if is_shiny:
                                for uid, sh in GlobalDatabase.shiny_hunts.items():
                                    if sh and match == sh: 
                                        normal_pings.append(f"<@{uid}> (✨ SHINY!)")
                            if normal_pings: 
                                await message.channel.send(f"🔔 **Wishlist Alert!** " + " ".join(list(set(normal_pings))))
    except Exception as e: 
        print(f"[SCANNER FAULT] Safely handled: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
