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
bot = commands.Bot(command_prefix=["a!", "A!"], intents=intents, help_command=None, case_insensitive=True)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"
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
SPECIES_FORM_MATRIX = {
    "furfrou": ["Furfrou", "Heart Trim Furfrou", "Star Trim Furfrou", "Diamond Trim Furfrou", "Debutante Trim Furfrou", "Matron Trim Furfrou", "Dandy Trim Furfrou", "La Reine Trim Furfrou", "Kabuki Trim Furfrou", "Pharaoh Trim Furfrou"],
    "alcremie": ["Alcremie", "Strawberry Sweet Alcremie", "Berry Sweet Alcremie", "Love Sweet Alcremie", "Star Sweet Alcremie", "Clover Sweet Alcremie", "Flower Sweet Alcremie", "Ribbon Sweet Alcremie", "Vanilla Cream Alcremie", "Ruby Cream Alcremie", "Matcha Cream Alcremie", "Mint Cream Alcremie", "Lemon Cream Alcremie", "Salted Cream Alcremie", "Ruby Swirl Alcremie", "Caramel Swirl Alcremie", "Rainbow Swirl Alcremie"],
    "arceus": ["Arceus", "Bug Arceus", "Dark Arceus", "Dragon Arceus", "Electric Arceus", "Fairy Arceus", "Fighting Arceus", "Fire Arceus", "Flying Arceus", "Ghost Arceus", "Grass Arceus", "Ground Arceus", "Ice Arceus", "Poison Arceus", "Psychic Arceus", "Rock Arceus", "Steel Arceus", "Water Arceus"],
    "silvally": ["Silvally", "Bug Silvally", "Dark Silvally", "Dragon Silvally", "Electric Silvally", "Fairy Silvally", "Fighting Silvally", "Fire Silvally", "Flying Silvally", "Ghost Silvally", "Grass Silvally", "Ground Silvally", "Ice Silvally", "Poison Silvally", "Psychic Silvally", "Rock Silvally", "Steel Silvally", "Water Silvally"],
    "flabebe": ["Flabébé", "Red Flower Flabébé", "Yellow Flower Flabébé", "Orange Flower Flabébé", "Blue Flower Flabébé", "White Flower Flabébé"]
}
SPECIES_FORM_MATRIX.update({
    "floette": ["Floette", "Red Flower Floette", "Yellow Flower Floette", "Orange Flower Floette", "Blue Flower Floette", "White Flower Floette", "Eternal Flower Floette"],
    "florges": ["Florges", "Red Flower Florges", "Yellow Flower Florges", "Orange Flower Florges", "Blue Flower Florges", "White Flower Florges"],
    "vivillon": ["Vivillon", "Archipelago Vivillon", "Continental Vivillon", "Elegant Vivillon", "Garden Vivillon", "High Plains Vivillon", "Icy Snow Vivillon", "Jungle Vivillon", "Marine Vivillon", "Meadow Vivillon", "Modern Vivillon", "Monsoon Vivillon", "Ocean Vivillon", "Polar Vivillon", "River Vivillon", "Sandstorm Vivillon", "Savanna Vivillon", "Sun Vivillon", "Tundra Vivillon", "Fancy Vivillon", "Poké Ball Vivillon"],
    "unown": ["Unown A", "Unown B", "Unown C", "Unown D", "Unown E", "Unown F", "Unown G", "Unown H", "Unown I", "Unown J", "Unown K", "Unown L", "Unown M", "Unown N", "Unown O", "Unown P", "Unown Q", "Unown R", "Unown S", "Unown T", "Unown U", "Unown V", "Unown W", "Unown X", "Unown Y", "Unown Z", "Unown Question", "Unown Exclamation"],
    "deoxys": ["Deoxys", "Attack Deoxys", "Defense Deoxys", "Speed Deoxys"],
    "rotom": ["Rotom", "Heat Rotom", "Wash Rotom", "Frost Rotom", "Fan Rotom", "Mow Rotom", "Phone Rotom", "DJ Rotom"],
    "wormadam": ["Wormadam", "Plant Cloak Wormadam", "Sandy Cloak Wormadam", "Trash Cloak Wormadam"]
})
SPECIES_FORM_MATRIX.update({
    "vulpix": ["Vulpix", "Alolan Vulpix"],
    "ninetales": ["Ninetales", "Alolan Ninetales"],
    "growlithe": ["Growlithe", "Hisuian Growlithe"],
    "arcanine": ["Arcanine", "Hisuian Arcanine"],
    "zorua": ["Zorua", "Hisuian Zorua"],
    "zoroark": ["Zoroark", "Hisuian Zoroark"],
    "articuno": ["Articuno", "Galarian Articuno"],
    "zapdos": ["Zapdos", "Galarian Zapdos"],
    "moltres": ["Moltres", "Galarian Moltres"],
    "rattata": ["Rattata", "Alolan Rattata"],
    "raticate": ["Raticate", "Alolan Raticate"],
    "sandshrew": ["Sandshrew", "Alolan Sandshrew"],
    "sandslash": ["Sandshrew", "Alolan Sandslash"],
    "meowth": ["Meowth", "Alolan Meowth", "Galarian Meowth"],
    "persian": ["Persian", "Alolan Persian"],
    "diglett": ["Diglett", "Alolan Diglett"],
    "dugtrio": ["Dugtrio", "Alolan Dugtrio"],
    "geodude": ["Geodude", "Alolan Geodude"],
    "graveler": ["Graveler", "Alolan Graveler"],
    "golem": ["Golem", "Alolan Golem"],
    "grimer": ["Grimer", "Alolan Grimer"],
    "muk": ["Muk", "Alolan Muk"],
    "exeggutor": ["Exeggutor", "Alolan Exeggutor"],
    "marowak": ["Marowak", "Alolan Marowak"]
})
FLAT_POKEMON_REGISTRY = {}
for base_key, forms_list in SPECIES_FORM_MATRIX.items():
    for f_name in forms_list:
        FLAT_POKEMON_REGISTRY[f_name.lower().replace("é", "e").strip()] = f_name

def strict_pokemon_check(input_name):
    clean_search = " ".join(input_name.strip().lower().replace("-", " ").replace("é", "e").replace("♀", " f").replace("♂", " m").replace("'", "").split())
    if clean_search in FLAT_POKEMON_REGISTRY:
        return True, FLAT_POKEMON_REGISTRY[clean_search]
    words = clean_search.split()
    if len(words) > 1 and words[0] in ["alolan", "galarian", "hisuian", "paldean"]:
        region_map = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
        flipped = " ".join(words[1:]) + " " + region_map[words[0]]
        if flipped in FLAT_POKEMON_REGISTRY:
            return True, FLAT_POKEMON_REGISTRY[flipped]
    for p_id, d in pokemon_db.items():
        if d.get("name", "").lower().replace("é", "e") == clean_search:
            return True, d["name"]
    return False, None
def get_all_variant_forms(base_pokemon_name):
    clean_base = base_pokemon_name.strip().lower().replace("-", " ")
    if clean_base in SPECIES_FORM_MATRIX:
        return SPECIES_FORM_MATRIX[clean_base]
    discovered = []
    for f_name in FLAT_POKEMON_REGISTRY.values():
        if clean_base in f_name.lower():
            if "mega" in f_name.lower() or "gmax" in f_name.lower():
                continue
            discovered.append(f_name)
    return list(set(discovered))

@bot.event
async def on_ready():
    global pokemon_db
    print("==========================================")
    print(f"STATUS: Successfully verified connection! Systems active.")
    print("==========================================")
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200: pokemon_db = response.json()
    except Exception as e: print(f"[CRITICAL] Cloud stream broken: {e}")
@bot.command(name="tags")
async def tags_command(ctx, *, search_name: str = None):
    try:
        if not search_name: return await ctx.send("⚠️ Format: `a!tags <pokemon_name>`")
        is_valid, matched_name = strict_pokemon_check(search_name)
        if not is_valid: return await ctx.send(f"❌ **{search_name}** is not a real Pokémon or form variant!")
        active_hunters = []
        for uid, hunts in GlobalDatabase.shiny_hunts.items():
            if hunts and matched_name in hunts: active_hunters.append(f"• <@{uid}>")
        if not active_hunters: return await ctx.send(f"📋 No active shiny hunters found tracking **{matched_name}** right now.")
        embed = discord.Embed(title=f"📋 Shiny Hunters tracking {matched_name}", color=discord.Color.red())
        embed.description = "\n".join(active_hunters); embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"❌ Error handling command: {e}")
@bot.command(name="cl", aliases=["A!cl"])
async def cl_base_router(ctx, subcommand: str = None, *, arguments: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="📋 Collection List Commands", description="`a!cl add <names>` • Add Pokémon (Separate entries with commas)\n`a!cl remove <name>` • Remove an entry\n`a!cl list` • View your list embed (20 entries per page)\n`a!cl clear` • Wipe list clean", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        uid = str(ctx.author.id)
        if sub_clean == "add":
            if not arguments: return await ctx.send("⚠️ Please specify at least one Pokémon! Example: `a!cl add Pikachu, Eevee`")
            if uid not in GlobalDatabase.user_collections: GlobalDatabase.user_collections[uid] = []
            
            if arguments.lower().startswith("all "):
                target_base = arguments[4:].strip()
                all_forms = get_all_variant_forms(target_base)
                if not all_forms: return await ctx.send(f"❌ No valid variants found matching **{target_base}** inside the database.")
                bulk_added = []
                for form in all_forms:
                    if form not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(form); bulk_added.append(form)
                if bulk_added: save_data()
                return await ctx.send(f"✅ Added **{len(bulk_added)}** Pokémon to your collections for this server!")

            parts = [p.strip() for p in arguments.split(",") if p.strip()]
            added, duplicate, broken = [], [], []
            for raw in parts:
                if raw.lower().startswith("all "):
                    target_base = raw[4:].strip(); all_forms = get_all_variant_forms(target_base)
                    for form in all_forms:
                        if form not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(form); added.append(form)
                    continue
                is_valid, matched_name = strict_pokemon_check(raw)
                if is_valid:
                    chk_lower = matched_name.lower()
                    if "mega" in chk_lower or "gmax" in chk_lower:
                        broken.append(f"{matched_name} (Uncatchable Form)")
                        continue
                    if matched_name not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(matched_name); added.append(matched_name)
                    else: duplicate.append(matched_name)
                else: 
                    title_name = " ".join([w.capitalize() for w in raw.split()])
                    if "mega" in title_name.lower() or "gmax" in title_name.lower():
                        broken.append(f"{title_name} (Uncatchable Form)")
                        continue
                    if title_name not in GlobalDatabase.user_collections[uid]:
                        GlobalDatabase.user_collections[uid].append(title_name)
                        added.append(title_name)
                    else: duplicate.append(title_name)
            if added or duplicate or broken: save_data()
            res = ""
            if added: res += f"✅ Added: **{', '.join(added)}**\n"
            if duplicate: res += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
            if broken: res += f"❌ **{', '.join(broken)}** Blocked.\n"
            await ctx.send(res)
        elif sub_clean in ["remove", "del"]:
            if not arguments: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
            is_valid, matched_name = strict_pokemon_check(arguments)
            final_name = matched_name if is_valid else " ".join([w.capitalize() for w in arguments.split()])
            if uid in GlobalDatabase.user_collections and final_name in GlobalDatabase.user_collections[uid]:
                GlobalDatabase.user_collections[uid].remove(final_name); save_data()
                await ctx.send(f"❌ **{final_name}** has been removed.")
            else: await ctx.send(f"⚠️ Target Pokémon was not found inside your list.")
            
        elif sub_clean in ["list", "view"]:
            if uid in GlobalDatabase.user_collections and GlobalDatabase.user_collections[uid]:
                formatted_wishlist = [f"• **{n}**" for n in sorted(GlobalDatabase.user_collections[uid])]
                paginator = DynamicListPaginator(data_list=formatted_wishlist, card_title=f"📋 {ctx.author.name}'s Collection List")
                await ctx.send(embed=paginator.get_page_embed(), view=paginator)
            else: await ctx.send("📁 Your collection list is empty.")
            
        elif sub_clean == "clear":
            GlobalDatabase.user_collections[uid] = []; save_data(); await ctx.send("🗑 Wiped collection list clean.")
    except Exception as e: print(f"CL Fault: {e}")
@bot.command(name="sh", aliases=["A!sh"])
async def sh_base_router(ctx, subcommand: str = None, *, name_arg: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="✨ Shiny Hunt Commands", description="`a!sh add <name>` • Set active shiny target\n`a!sh remove <name>` • Drop shiny target\n`a!sh list` • View hunt\n`a!sh clear` • Wipe data", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        uid = str(ctx.author.id)
        
        if sub_clean == "add" or (sub_clean not in ["remove", "del", "list", "view", "clear"]):
            target = name_arg if (sub_clean == "add" and name_arg) else subcommand
            is_valid, matched_name = strict_pokemon_check(target)
            final_name = matched_name if is_valid else " ".join([w.capitalize() for w in target.split()])
            chk_lower = final_name.lower()
            if "mega" in chk_lower or "gmax" in chk_lower:
                return await ctx.send(f"❌ **{final_name}** is uncatchable! You can't hunt this form.")
            GlobalDatabase.shiny_hunts[uid] = [final_name]; save_data()
            await ctx.send(f"✨ **{final_name}** has been registered as your active Shiny Hunt!")
            
        elif sub_clean in ["remove", "del"]:
            target = name_arg if name_arg else subcommand
            is_valid, matched_name = strict_pokemon_check(target)
            final_name = matched_name if is_valid else " ".join([w.capitalize() for w in target.split()])
            if uid in GlobalDatabase.shiny_hunts and final_name in GlobalDatabase.shiny_hunts[uid]:
                GlobalDatabase.shiny_hunts[uid].remove(final_name); save_data()
                await ctx.send(f"❌ **{final_name}** removed from your hunting profile.")
            else: await ctx.send("⚠️ Target was not active on your list.")
            
        elif sub_clean in ["list", "view"]:
            if uid in GlobalDatabase.shiny_hunts and GlobalDatabase.shiny_hunts[uid]:
                clean_names = ", ".join(GlobalDatabase.shiny_hunts[uid])
                await ctx.send(embed=discord.Embed(title=f"📋 {ctx.author.name}'s Active Shiny Hunt", description=f"• **{clean_names}**", color=discord.Color.red()))
            else: await ctx.send("✨ You are not currently tracking any shiny hunts.")
            
        elif sub_clean == "clear":
            GlobalDatabase.shiny_hunts[uid] = []; save_data(); await ctx.send("✨🗑 Shiny hunt cleared.")
    except Exception as e: print(f"SH Fault: {e}")
@bot.command(name="r", aliases=["A!r"])
async def r_base_router(ctx, subcommand: str = None, *, args: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="📦 Server Reserve Commands", description="`a!r add <names> @user` • Reserve Pokémon for a specific user (commas allowed)\n`a!r remove <names> @user` • Drop reserved targets from a user (commas allowed)\n`a!r remove @user` • Completely clear all active reserves for that user only\n`a!r @user` • View the reserved list for a specific person\n`a!r list` • View the entire server's reserve listings (20 entries per page)\n`a!r clear` • Wipe the absolute entire server reserve file data clean\n`a!r e @mainuser` • Reply to a list of trades to transfer them all from @mainuser", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        if re.search(r'<@!?(\d+)>', subcommand):
            mention_match = re.search(r'<@!?(\d+)>', subcommand)
            tid = str(mention_match.group(1)); target_user = await bot.fetch_user(int(tid)); u_list = GlobalDatabase.reserve_data.get(tid, [])
            if u_list: return await ctx.send(embed=discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• **{n}**" for n in sorted(u_list)]), color=discord.Color.red()))
            else: return await ctx.send(embed=discord.Embed(title=f"📋 Server Reserves", description=f"📦 <@{tid}> has no Pokémon reserved currently.", color=discord.Color.red()))

        if sub_clean == "add":
            if not args: return await ctx.send("⚠️ Format: `a!r add Pikachu @user` or `a!r add all furfrou @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please mention a user!")
            tid = str(mention_match.group(1)); raw_names = re.sub(r'<@!?\d+>', '', args).strip()
            if tid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[tid] = []
            if raw_names.lower().startswith("all "):
                target_base = raw_names[4:].strip(); all_forms = get_all_variant_forms(target_base)
                if not all_forms: return await ctx.send(f"❌ No valid variants found matching **{target_base}**.")
                for form in all_forms:
                    if form not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(form)
                save_data(); return await ctx.send(f"📦 Added **{len(all_forms)}** Pokémon to reserves for <@{tid}>!")

            parts = [p.strip() for p in raw_names.split(",") if p.strip()]; added, duplicate, broken = [], [], []
            for raw in parts:
                is_valid, matched = strict_pokemon_check(raw)
                final_name = matched if is_valid else " ".join([w.capitalize() for w in raw.split()])
                if "mega" in final_name.lower() or "gmax" in final_name.lower(): broken.append(f"{final_name} (Uncatchable)"); continue
                if final_name not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(final_name); added.append(final_name)
                else: duplicate.append(final_name)
            if added or duplicate or broken: save_data()
            await ctx.send(f"📦 Added to reserves for <@{tid}>: **{', '.join(added)}**")
            
        elif sub_clean in ["remove", "del"]:
            if not args: return await ctx.send("⚠️ Format: `a!r remove Pikachu @user` or `a!r remove @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Mention a user!")
            tid = str(mention_match.group(1)); raw_input = re.sub(r'<@!?\d+>', '', args).strip()
            if not raw_input:
                GlobalDatabase.reserve_data[tid] = []; save_data(); return await ctx.send(f"🗑️ Wiped reserves for <@{tid}>!")
            parts = [p.strip() for p in raw_input.split(",") if p.strip()]; removed = []
            if tid in GlobalDatabase.reserve_data:
                for raw in parts:
                    is_valid, matched = strict_pokemon_check(raw)
                    final_name = matched if is_valid else " ".join([w.capitalize() for w in raw.split()])
                    if final_name in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].remove(final_name); removed.append(final_name)
            if removed: save_data()
            await ctx.send(f"❌ Removed from <@{tid}>: **{', '.join(removed)}**")
        elif sub_clean in ["list", "view"]:
            pokemon_groups = {}
            for uid, arr in GlobalDatabase.reserve_data.items():
                for name in arr:
                    if name not in pokemon_groups: pokemon_groups[name] = []
                    pokemon_groups[name].append(f"<@{uid}>")
            formatted_entries = [f"• **{name}** - {', '.join(pokemon_groups[name])}" for name in sorted(pokemon_groups.keys())]
            if not formatted_entries: return await ctx.send("📦 No reserves found.")
            paginator = DynamicListPaginator(data_list=formatted_entries, card_title="📋 Server Reserves")
            await ctx.send(embed=paginator.get_page_embed(), view=paginator)
        elif sub_clean == "clear": GlobalDatabase.reserve_data.clear(); save_data(); await ctx.send("🗑 Wiped server reserves.")
    except Exception as e: print(f"R Fault: {e}")

@bot.listen("on_message")   
async def poketwo_image_scanner(message):
    import starboard
    await starboard.process_starboard_message(message)
    try:
        if message.author.bot and (message.author.name == "Pokétwo" or message.author.id == 716390085896962058) and message.embeds:
            for emb in message.embeds:
                if emb.image and emb.image.url:
                    url = emb.image.url; is_shiny = "shiny" in url.lower()
                    res = requests.get(url, timeout=10); img = Image.open(BytesIO(res.content)); hsh = imagehash.phash(img, hash_size=8)
                    match, low_dist = None, 999
                    for p_id, d in pokemon_db.items():
                        dist = hsh - imagehash.hex_to_hash(d["phash"])
                        if dist < low_dist: low_dist = dist; match = d["name"]
                    if low_dist <= 12 and match:
                        await message.channel.send(f"🚨 **Spawn Detected!** Pattern matches **{match}**!")
                        matched_lower = match.lower(); reserve_pings = []
                        for uid, arr in GlobalDatabase.reserve_data.items():
                            for name in arr:
                                if name.lower() == matched_lower: reserve_pings.append(f"<@{uid}>")
                        if reserve_pings: await message.channel.send(f"🔔 **Reserve Match Alert!** " + " ".join(list(set(reserve_pings)))); return
                        normal_pings = []
                        for uid, col in GlobalDatabase.user_collections.items():
                            for name in col:
                                if name.lower() == matched_lower: normal_pings.append(f"<@{uid}>")
                        if is_shiny:
                            for uid, sh in GlobalDatabase.shiny_hunts.items():
                                if sh and sh.lower() == matched_lower: normal_pings.append(f"<@{uid}> (✨ SHINY!)")
                        if normal_pings: await message.channel.send(f"🔔 **List Alert!** " + " ".join(list(set(normal_pings))))
    except Exception as e: print(f"[SCANNER FAULT] Safely handled: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
