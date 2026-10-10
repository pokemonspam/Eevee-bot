import os, json, discord, requests, imagehash
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
        description_text = ""
        for uid, hunts in active.items():
            user = bot.get_user(int(uid)); name = user.name if user else f"UserID-{uid}"
            description_text += f"• **@{name}** is hunting: *{', '.join(hunts)}*\n"
        
        embed.description = description_text
        embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"❌ Error handling command: {e}")

@bot.group(name="cl", invoke_without_command=True)
async def cl_group(ctx):
    embed = discord.Embed(
        title="📋 Collection List Commands", 
        description="`e!cl add <name>` • Add a target to your collection list\n`e!cl remove <name>` • Remove a target\n`e!cl list` • View your collection wishlist\n`e!cl clear` • Wipe your collection list clean",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@cl_group.command(name="add")
async def cl_add(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a Pokémon! Example: `e!cl add Pikachu`")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid not in user_collections: user_collections[uid] = []
    if name not in user_collections[uid]:
        user_collections[uid].append(name); save_data()
        await ctx.send(f"✅ **{name}** has been added to your collection list!")
    else: await ctx.send(f"⚠️ **{name}** is already inside your tracking index.")

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
        total_count = len(sorted_list)
        
        lines = [f"• {n}" for n in sorted_list]
        
        embed = discord.Embed(
            title=f"📋 {ctx.author.name}'s Collection ({total_count})",
            description="\n".join(lines),
            color=discord.Color.red()
        )
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
    embed = discord.Embed(
        title="✨ Shiny Hunt Commands",
        description="`e!sh <name>` • Set your active single shiny target\n`e!sh remove <name>` • Stop tracking a shiny target\n`e!sh list` • View your active shiny target\n`e!sh clear` • Wipe your shiny tracking data",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@sh_group.command(name="add")
async def sh_add(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Please specify a target name!")
    uid, name = str(ctx.author.id), name.strip().title()
    
    if uid in shiny_hunts and shiny_hunts[uid] and shiny_hunts[uid] == [name]:
        return await ctx.send(f"⚠️ You are already actively tracking shiny **{name}**.")

    old_mon = shiny_hunts[uid][0] if (uid in shiny_hunts and shiny_hunts[uid]) else None
    shiny_hunts[uid] = [name]
    save_data()
    
    if old_mon:
        await ctx.send(f"✨ **{name}** is your new Shiny Hunt! *(Your previous target, **{old_mon}**, has been removed)*")
    else:
        await ctx.send(f"✨ **{name}** has been registered as your active Shiny Hunt!")

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
        embed = discord.Embed(
            title=f"🌟 {ctx.author.name}'s Active Shiny Target",
            description=f"• ✨ **{shiny_hunts[uid][0]}**",
            color=discord.Color.red()
        )
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
        
    embed = discord.Embed(
        title="📦 Server Reserve Commands",
        description="`e!r add <name>` • Add a Pokemon to global reserves\n`e!r remove <name>` • Remove from global reserves\n`e!r list` • View the shared server reserve list\n`e!r clear` • Reset the shared reserve list\n`e!r @user` • Inspect another user's priority targets",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@r_group.command(name="add")
async def r_add(ctx, *, name: str = None):
    if not name: return await ctx.send("⚠️ Specify a Pokémon name! Example: `e!r add Mewtwo`")
    global reserve_list; name = name.strip().title()
    if name not in reserve_list:
        reserve_list.append(name); save_data()
        await ctx.send(f"📦 **{name}** has been added to the global Server Reserve manifest!")
    else: await ctx.send(f"⚠️ **{name}** already resides inside the server reserve catalog.")

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
        embed = discord.Embed(
            title=f"📋 Shared Server Reserve List ({len(reserve_list)})",
            description="\n".join(lines),
            color=discord.Color.red()
        )
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
