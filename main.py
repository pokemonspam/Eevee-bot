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
FORMS_MATRIX_URL = "https://githubusercontent.com"
pokemon_db = {}
SPECIES_FORM_MATRIX = {}
FLAT_POKEMON_REGISTRY = {}
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
    global pokemon_db, SPECIES_FORM_MATRIX, FLAT_POKEMON_REGISTRY
    bot_user = bot.user if bot.user else "Eevee Bot"
    print("==========================================")
    print(f"STATUS: Successfully verified connection with Discord servers!")
    print(f"IDENTITY: Active as {bot_user}")
    print("==========================================")
    try:
        matrix_response = requests.get(FORMS_MATRIX_URL, timeout=15)
        if matrix_response.status_code == 200:
            SPECIES_FORM_MATRIX = matrix_response.json()
            for base_key, forms_list in SPECIES_FORM_MATRIX.items():
                for f_name in forms_list:
                    FLAT_POKEMON_REGISTRY[f_name.lower().replace("é", "e").strip()] = f_name
            print(f"REGISTRY: Loaded official form tracking definitions into memory cache safely!")
    except Exception as e:
        print(f"[CRITICAL] Could not synchronize forms database from stream network: {e}")
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200: 
            pokemon_db = response.json()
    except Exception as e: 
        print(f"[CRITICAL] Network cloud stream broken: {e}")
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
                    target_base = raw[4:].strip()
                    all_forms = get_all_variant_forms(target_base)
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
                else: broken.append(raw)
            if added or duplicate or broken: save_data()
            res = ""
            if added: res += f"✅ Added: **{', '.join(added)}**\n"
            if duplicate: res += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
            if broken: res += f"❌ **{', '.join(broken)}** is invalid or a non-catchable form! Blocked.\n"
            await ctx.send(res)
        elif sub_clean in ["remove", "del"]:
            if not arguments: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
            is_valid, matched_name = strict_pokemon_check(arguments)
            if is_valid and uid in GlobalDatabase.user_collections and matched_name in GlobalDatabase.user_collections[uid]:
                GlobalDatabase.user_collections[uid].remove(matched_name); save_data()
                await ctx.send(f"❌ **{matched_name}** has been removed.")
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
            if not is_valid: return await ctx.send(f"❌ **{target}** is not a real Pokémon or valid form variant!")
            chk_lower = matched_name.lower()
            if "mega" in chk_lower or "gmax" in chk_lower: return await ctx.send(f"❌ **{matched_name}** is uncatchable! You can't hunt this form.")
            GlobalDatabase.shiny_hunts[uid] = [matched_name]; save_data()
            await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")
        elif sub_clean in ["remove", "del"]:
            target = name_arg if name_arg else subcommand
            is_valid, matched_name = strict_pokemon_check(target)
            if is_valid and uid in GlobalDatabase.shiny_hunts and matched_name in GlobalDatabase.shiny_hunts[uid]:
                GlobalDatabase.shiny_hunts[uid].remove(matched_name); save_data()
                await ctx.send(f"❌ **{matched_name}** removed from your hunting profile.")
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
            tid = str(mention_match.group(1)); target_user = await bot.fetch_user(int(tid))
            u_list = GlobalDatabase.reserve_data.get(tid, [])
            if u_list: return await ctx.send(embed=discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• **{n}**" for n in sorted(u_list)]), color=discord.Color.red()))
            else: return await ctx.send(embed=discord.Embed(title=f"📋 Server Reserves", description=f"📦 <@{tid}> has no Pokémon reserved currently.", color=discord.Color.red()))

        if sub_clean == "add":
            if not args: return await ctx.send("⚠️ Format: `a!r add Pikachu @user` or `a!r add all furfrou @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please mention a user to reserve the Pokémon for!")
            tid = str(mention_match.group(1)); raw_names = re.sub(r'<@!?\d+>', '', args).strip()
            if tid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[tid] = []
            if len(raw_names.lower()) >= 4 and raw_names.lower().startswith("all "):
                target_base = raw_names[4:].strip()
                all_forms = get_all_variant_forms(target_base)
                if not all_forms: return await ctx.send(f"❌ No catchable variants found matching **{target_base}** inside the database.")
                bulk_added = []
                for form in all_forms:
                    if form not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(form); bulk_added.append(form)
                if bulk_added: save_data()
                return await ctx.send(f"📦 Added **{len(bulk_added)}** Pokémon to reserves for <@{tid}>!")

            parts = [p.strip() for p in raw_names.split(",") if p.strip()]
            added, duplicate, broken = [], [], []
            for raw in parts:
                if len(raw.lower()) >= 4 and raw.lower().startswith("all "):
                    target_base = raw[4:].strip(); all_forms = get_all_variant_forms(target_base)
                    for form in all_forms:
                        if form not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(form); added.append(form)
                    continue
                is_valid, matched = strict_pokemon_check(raw)
                if is_valid:
                    chk_lower = matched.lower()
                    if "mega" in chk_lower or "gmax" in chk_lower: broken.append(f"{matched} (Uncatchable Form)"); continue
                    if matched not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(matched); added.append(matched)
                    else: duplicate.append(matched)
                else: broken.append(raw)
            if added or duplicate or broken: save_data()
            res = ""
            if added: res += f"📦 Added to reserves for <@{tid}>: **{', '.join(added)}**\n"
            if duplicate: res += f"⚠️ Already reserved: **{', '.join(duplicate)}**\n"
            if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon or form variant! Blocked.\n"
            await ctx.send(res)
        elif sub_clean in ["remove", "del"]:
            if not args: return await ctx.send("⚠️ Format: `a!r remove Pikachu @user` or `a!r remove @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please mention a user to remove reserves from!")
            tid = str(mention_match.group(1)); raw_input = re.sub(r'<@!?\d+>', '', args).strip()
            if not raw_input:
                if tid in GlobalDatabase.reserve_data and GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid] = []; save_data(); return await ctx.send(f"🗑️ Wiped all reserves for <@{tid}>!")
                else: return await ctx.send(f"⚠️ <@{tid}> has no active reserves.")
            parts = [p.strip() for p in raw_input.split(",") if p.strip()]
            removed, missing = [], []
            if tid in GlobalDatabase.reserve_data:
                for raw in parts:
                    is_valid, matched = strict_pokemon_check(raw)
                    if is_valid and matched in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].remove(matched); removed.append(matched)
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
            formatted_entries = [f"• **{name}** - {', '.join(pokemon_groups[name])}" for name in sorted(pokemon_groups.keys())]
            paginator = DynamicListPaginator(data_list=formatted_entries, card_title="📋 Shared Server Reserve Manifest", chunk_size=20)
            await ctx.send(embed=paginator.get_page_embed(), view=paginator)
        elif sub_clean == "clear": GlobalDatabase.reserve_data.clear(); save_data(); await ctx.send("📦🗑 Server Reserve Database file wiped clean!")
        elif sub_clean == "e":
            if not args: return await ctx.send("⚠️ Example: `a!r e @mainuser`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please specify the main user to exchange from!")
            mid = str(mention_match.group(1))
            if not ctx.message.reference: return await ctx.send("⚠️ You must **reply** directly to the target list message with this command!")
            try:
                replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id); lines = replied_msg.content.split("\n")
                if mid not in GlobalDatabase.reserve_data or not GlobalDatabase.reserve_data[mid]: return await ctx.send(f"❌ <@{mid}> has no active Pokémon reserved to exchange.")
                success_logs = []
                for line in lines:
                    if not line.strip() or "-" not in line: continue
                    left_part, right_part = line.split("-", 1); target_uid = None; uid_match = re.search(r'(\d+)', left_part)
                    if uid_match: target_uid = str(uid_match.group(1))
                    else:
                        clean_tag = left_part.replace('•', '').replace('*', '').strip().lower()
                        for member in ctx.guild.members:
                            if clean_tag in member.name.lower() or (member.nick and clean_tag in member.nickname.lower()): target_uid = str(member.id); break
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
            except Exception as e: print(f"Reserve exchange fault: {e}")
    except Exception as e: print(f"R Router fault: {e}")
@bot.listen("on_message")
async def poketwo_image_scanner(message):
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
                                if name.lower() == matched_lower or name.lower() == f"normal {matched_lower}": reserve_pings.append(f"<@{uid}>")
                        if reserve_pings: await message.channel.send(f"🔔 **Reserve Match Alert!** " + " ".join(list(set(reserve_pings))) + " - Target reserved for you!"); return
                        normal_pings = []
                        for uid, col in GlobalDatabase.user_collections.items():
                            for name in col:
                                if name.lower() == matched_lower or name.lower() == f"normal {matched_lower}": normal_pings.append(f"<@{uid}>")
                        if is_shiny:
                            for uid, sh in GlobalDatabase.shiny_hunts.items():
                                if sh and (sh.lower() == matched_lower or sh.lower() == f"normal {matched_lower}"): normal_pings.append(f"<@{uid}> (✨ SHINY!)")
                        if normal_pings: await message.channel.send(f"🔔 **List Alert!** " + " ".join(list(set(normal_pings))))
    except Exception as e: print(f"[SCANNER FAULT] Safely handled: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
