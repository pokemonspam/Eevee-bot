import os, json, discord, requests, imagehash, difflib
from PIL import Image
from io import BytesIO
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="e!", intents=intents, help_command=None)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}; COLLECTION_FILE = "collection.json"

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

def validate_pokemon(input_name):
    """Uses a dynamic string matching distance threshold to catch spelling typos."""
    if not pokemon_db: return True, input_name.strip().title()
    clean_name = input_name.strip().title()
    valid_names = [d["name"] for d in pokemon_db.values()]
    if clean_name in valid_names: return True, clean_name
    matches = difflib.get_close_matches(clean_name, valid_names, n=1, cutoff=0.6)
    if matches: return False, matches[0]
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
        if not active: return await ctx.send("✨ No active shiny hunters found on this server! Use `e!sh <name>` to add targets.")
        embed = discord.Embed(title="🌟 Server Shiny Hunters Master List", color=discord.Color.red())
        description_text = "".join([f"• **@{bot.get_user(int(uid)).name if bot.get_user(int(uid)) else uid}** is hunting: *{', '.join(hunts)}*\n" for uid, hunts in active.items()])
        embed.description = description_text
        embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"❌ Error handling command: {e}")

@bot.group(name="cl", invoke_without_command=True)
async def cl_group(ctx):
    embed = discord.Embed(title="📋 Collection List Commands", description="`e!cl add <names>` • Separate names with commas\n`e!cl remove <name>` • Drop a target\n`e!cl list` • View your collection wishlist\n`e!cl clear` • Reset your list", color=discord.Color.red())
    await ctx.send(embed=embed)

@cl_group.command(name="add")
async def cl_add(ctx, *, raw_names: str = None):
    if not raw_names: return await ctx.send("⚠️ Please specify at least one Pokémon! Example: `e!cl add Pikachu, Eevee`")
    uid = str(ctx.author.id)
    if uid not in user_collections: user_collections[uid] = []
    
    parts = [p.strip() for p in raw_names.split(",") if p.strip()]
    added, duplicate, broken = [], [], []
    
    for raw in parts:
        is_valid, matched_name = validate_pokemon(raw)
        if is_valid:
            if matched_name not in user_collections[uid]:
                user_collections[uid].append(matched_name); added.append(matched_name)
            else: duplicate.append(matched_name)
        else:
            broken.append((raw, matched_name))
            
    if added or duplicate or broken: save_data()
    
    response = ""
    if added: response += f"✅ Added to collection: **{', '.join(added)}**\n"
    if duplicate: response += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
    for wrong, guess in broken:
        if guess: response += f"❌ **{wrong}** is wrong! Did you mean **{guess}**? Please type it again.\n"
        else: response += f"❌ **{wrong}** is not recognized! Please check the spelling and type it again.\n"
    await ctx.send(response)

@cl_group.command(name="remove", aliases=["del"])
async def cl_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid in user_collections and name in user_collections[uid]:
        user_collections[uid].remove(name); save_data()
        await ctx.send(f"❌ **{name}** has been removed from your tracking index.")
    else: await ctx.send(f"⚠️ Target **{name}** was not found inside your collection list.")

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
    is_valid, matched_name = validate_pokemon(name)
    
    if not is_valid:
        if matched_name: return await ctx.send(f"❌ **{name}** is wrong! Did you mean **{matched_name}**? Please type it again.")
        else: return await ctx.send(f"❌ **{name}** is not recognized! Please check the spelling and type it again.")

    if uid in shiny_hunts and shiny_hunts[uid] and shiny_hunts[uid] == [matched_name]:
        return await ctx.send(f"⚠️ You are already actively tracking shiny **{matched_name}**.")

    old_mon = shiny_hunts[uid][0] if (uid in shiny_hunts and shiny_hunts[uid]) else None
    shiny_hunts[uid] = [matched_name]; save_data()
    
    if old_mon: await ctx.send(f"✨ **{matched_name}** is your new Shiny Hunt! *(Your previous target, **{old_mon}**, has been removed)*")
    else: await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")

@sh_group.command(name="remove", aliases=["del"])
async def sh_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target to remove!")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid in shiny_hunts and shiny_hunts[uid] and name in shiny_hunts[uid]:
        shiny_hunts[uid].remove(name); save_data()
        await ctx.send(f"❌ **{name}** removed from your active hunting priorities.")
    else: await ctx.send(f"⚠️ Target **{name}** was not active on your tracking list.")

@sh_group.command(name="list", aliases=["view"])
async def sh_list(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]:
        embed = discord.Embed(title=f"🌟 {ctx.author.name}'s Active Shiny Target", description=f"• ✨ **{shiny_hunts[uid][0]}**", color=discord.Color.red())
        embed.set_footer(text="Eevee Tracking Hub | Est. 2026")
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title=f"🌟 {ctx.author.name}'s Shiny Target", description="✨ You are not currently tracking any shiny targets.", color=discord.Color.red())
        await ctx.send(embed=embed)

@sh_group.command(name="clear")
async def sh_clear(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]:
        shiny_hunts[uid] = []; save_data()
        await ctx.send("✨🗑️ Your active shiny tracking parameters have been cleared.")
    else: await ctx.send("⚠️ Your tracking list is already empty.")

@bot.group(name="r", invoke_without_command=True)
async def r_group(ctx):
    if ctx.message.mentions:
        target = ctx.message.mentions[0]; tid = str(target.id)
        c_dt = user_collections.get(tid, []); s_dt = shiny_hunts.get(tid, [])
        embed = discord.Embed(title=f"📋 Wishlist Profile for {target.name}", color=discord.Color.red())
        embed.add_field(name="🔹 Collection Targets", value=", ".join(sorted(c_dt)) if c_dt else "*None*", inline=False)
        embed.add_field(name="✨ Active Shiny Hunt", value=f"**{s_dt[0]}**" if s_dt else "*None*", inline=False)
        embed.set_footer(text="Eevee Registry Search Matrix")
        return await ctx.send(embed=embed)
    embed = discord.Embed(title="📦 Server Reserve Commands", description="`e!r add <names>` • Separate multiple names with commas\n`e!r remove <name>` • Remove from reserves\n`e!r list` • View server reserve list\n`e!r clear` • Reset shared list\n`e!r @user` • Inspect another user's list", color=discord.Color.red())
    await ctx.send(embed=embed)

@r_group.command(name="add")
async def r_add(ctx, *, raw_names: str = None):
    if not raw_names: return await ctx.send("⚠️ Specify at least one Pokémon name! Example: `e!r add Mewtwo, Lugia`")
    global reserve_list
    parts = [p.strip() for p in raw_names.split(",") if p.strip()]
    added, duplicate, broken = [], [], []
    
    for raw in parts:
        is_valid, matched_name = validate_pokemon(raw)
        if is_valid:
            if matched_name not in reserve_list:
                reserve_list.append(matched_name); added.append(matched_name)
            else: duplicate.append(matched_name)
        else: broken.append((raw, matched_name))
        
    if added or duplicate or broken: save_data()
    
    response = ""
    if added: response += f"📦 Added to server reserves: **{', '.join(added)}**\n"
    if duplicate: response += f"⚠️ Already on server reserves: **{', '.join(duplicate)}**\n"
    for wrong, guess in broken:
        if guess: response += f"❌ **{wrong}** is wrong! Did you mean **{guess}**? Please type it again.\n"
        else: response += f"❌ **{wrong}** is not recognized! Please check the spelling and type it again.\n"
    await ctx.send(response)

@r_group.command(name="remove", aliases=["del"])
async def r_remove(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Specify a reserve target name to remove!")
    global reserve_list; name = name.strip().title()
    if name in reserve_list:
        reserve_list.remove(name); save_data()
        await ctx.send(f"❌ **{name}** pulled from the Server Reserve index.")
    else: await ctx.send(f"⚠️ Target **{name}** does not exist inside the server profile repository.")

@r_group.command(name="list", aliases=["view"])
async def r_list(ctx):
    if reserve_list:
        lines = [f"• {n}" for n in sorted(reserve_list)]
        embed = discord.Embed(title=f"📋 Shared Server Reserve List ({len(reserve_list)})", description="\n".join(lines), color=discord.Color.red())
        embed.set_footer(text="Eevee Tracking Hub | Est. 2026")
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="📋 Shared Server Reserve List (0)", description="📦 The shared tracking registry is empty.", color=discord.Color.red())
        await ctx.send(embed=embed)

@r_group.command(name="clear")
async def r_clear(ctx):
    global reserve_list
    if reserve_list:
        reserve_list = []; save_data()
        await ctx.send("📦🗑️ **The shared server Reserve tracking list has been reset to empty.**")
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
                                        if sh and match == sh[0]: pings.append(f"<@{uid}> (✨ SHINY TARGET!)")
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
