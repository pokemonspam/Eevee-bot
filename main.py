import os
import json
import asyncio
import traceback
import discord
from discord.ext import commands
import requests
import imagehash
from PIL import Image
from io import BytesIO

# Using the robust Extension Bot structure for less buggy message routing
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="e!", intents=intents, help_command=None)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"

# Safe Data Matrix Loading
try:
    if os.path.exists(COLLECTION_FILE):
        with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
            db_data = json.load(f)
            user_collections = db_data.get("collection", {})
            shiny_hunts = db_data.get("shiny", {})
            reserve_list = db_data.get("reserve", [])
    else:
        user_collections, shiny_hunts, reserve_list = {}, {}, []
except Exception as e:
    print(f"[CRITICAL] Storage Initialization Error: {e}")
    user_collections, shiny_hunts, reserve_list = {}, {}, []

def save_data():
    """Failsafe storage engine with temporary write buffer protection"""
    try:
        temp_file = COLLECTION_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({
                "collection": user_collections, 
                "shiny": shiny_hunts, 
                "reserve": reserve_list
            }, f, indent=4)
        os.replace(temp_file, COLLECTION_FILE)
    except Exception as e:
        print(f"[ERROR] Failed to save runtime matrix out to disk: {e}")

@bot.event
async def on_ready():
    global pokemon_db
    name = bot.user.name if bot.user else "Eevee Bot"
    print(f"==========================================")
    print(f"STATUS: Loaded successfully as {name}!")
    print(f"SYSTEM: Initializing cloud pHash profiles...")
    print(f"==========================================")
    
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200:
            pokemon_db = response.json()
            print(f"[SUCCESS] Loaded {len(pokemon_db)} target vectors into local cache!")
        else:
            print(f"[ERROR] Cloud buffer returned status: {response.status_code}")
    except Exception as e:
        print(f"[CRITICAL] Cloud network streaming aborted: {e}")
@bot.command(name="tags")
async def tags_command(ctx):
    try:
        active = {uid: hunts for uid, hunts in shiny_hunts.items() if hunts}
        if not active:
            return await ctx.send("✨ No active shiny hunters found on this server! Use `e!sh add <name>`.")
        
        lines = ["🌟 **Server Shiny Hunters Master List:**\n"]
        for uid, hunts in active.items():
            user = bot.get_user(int(uid))
            name = user.name if user else f"UserID-{uid}"
            lines.append(f"• **@{name}** is hunting: *{', '.join(sorted(hunts))}*")
        await ctx.send("\n".join(lines))
    except Exception as e:
        await ctx.send(f"❌ Command Error inside tags framework: {e}")

@bot.group(name="cl", invoke_without_command=True)
async def cl_group(ctx):
    await ctx.send("📋 **Collection List Subcommands:**\n`e!cl add <name>` • `e!cl remove <name>` • `e!cl list` • `e!cl clear`")

@cl_group.command(name="add")
async def cl_add(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Please specify a Pokémon! Example: `e!cl add Pikachu`")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid not in user_collections:
        user_collections[uid] = []
    if name not in user_collections[uid]:
        user_collections[uid].append(name)
        save_data()
        await ctx.send(f"✅ **{name}** has been added to your collection list!")
    else:
        await ctx.send(f"⚠️ **{name}** is already inside your tracking index.")

@cl_group.command(name="remove", aliases=["del"])
async def cl_remove(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Please specify a Pokémon to drop!")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid in user_collections and name in user_collections[uid]:
        user_collections[uid].remove(name)
        save_data()
        await ctx.send(f"❌ **{name}** has been removed from your tracking index.")
    else:
        await ctx.send(f"⚠️ Target **{name}** was not found inside your collection list.")

@cl_group.command(name="list", aliases=["view"])
async def cl_list(ctx):
    uid = str(ctx.author.id)
    if uid in user_collections and user_collections[uid]:
        lines = [f"{i+1}. **{n}**" for i, n in enumerate(sorted(user_collections[uid]))]
        await ctx.send(f"📋 **Your Personal Wishlist:**\n" + "\n".join(lines))
    else:
        await ctx.send("📁 Your collection tracking profile is currently empty.")

@cl_group.command(name="clear")
async def cl_clear(ctx):
    uid = str(ctx.author.id)
    if uid in user_collections and user_collections[uid]:
        user_collections[uid] = []
        save_data()
        await ctx.send("🗑️ Your entire tracking matrix has been wiped clean.")
    else:
        await ctx.send("⚠️ Profile index is already empty.")

@bot.group(name="sh", invoke_without_command=True)
async def sh_group(ctx, *, arg: str = None):
    # This allows typing either 'e!sh Pikachu' or 'e!sh add Pikachu' seamlessly
    if arg:
        arg_lower = arg.lower().strip()
        if arg_lower in ["list", "view"]:
            return await ctx.invoke(bot.get_command('sh list'))
        elif arg_lower == "clear":
            return await ctx.invoke(bot.get_command('sh clear'))
        elif arg_lower.startswith("add "):
            return await ctx.invoke(bot.get_command('sh add'), name=arg[4:])
        elif arg_lower.startswith("remove "):
            return await ctx.invoke(bot.get_command('sh remove'), name=arg[7:])
        elif arg_lower.startswith("del "):
            return await ctx.invoke(bot.get_command('sh remove'), name=arg[4:])
        else:
            return await ctx.invoke(bot.get_command('sh add'), name=arg)
    await ctx.send("✨ **Shiny Hunt Subcommands:**\n`e!sh <name>` • `e!sh remove <name>` • `e!sh list` • `e!sh clear`")

@sh_group.command(name="add")
async def sh_add(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Please specify a target name!")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid not in shiny_hunts:
        shiny_hunts[uid] = []
    if name not in shiny_hunts[uid]:
        shiny_hunts[uid].append(name)
        save_data()
        await ctx.send(f"✨ **{name}** has been registered to your Shiny Hunt list!")
    else:
        await ctx.send(f"⚠️ You are already actively tracking shiny **{name}**.")

@sh_group.command(name="remove", aliases=["del"])
async def sh_remove(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Please specify a target to remove!")
    uid, name = str(ctx.author.id), name.strip().title()
    if uid in shiny_hunts and name in shiny_hunts[uid]:
        shiny_hunts[uid].remove(name)
        save_data()
        await ctx.send(f"❌ **{name}** removed from your active hunting priorities.")
    else:
        await ctx.send(f"⚠️ Target **{name}** was not active on your tracking list.")

@sh_group.command(name="list", aliases=["view"])
async def sh_list(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]:
        lines = [f"{i+1}. ✨ **{n}**" for i, n in enumerate(sorted(shiny_hunts[uid]))]
        await ctx.send(f"🌟 **Your Active Shiny Priorities:**\n" + "\n".join(lines))
    else:
        await ctx.send("✨ You are not currently tracking any high priority shiny targets.")

@sh_group.command(name="clear")
async def sh_clear(ctx):
    uid = str(ctx.author.id)
    if uid in shiny_hunts and shiny_hunts[uid]:
        shiny_hunts[uid] = []
        save_data()
        await ctx.send("✨🗑️ Your active shiny tracking parameters have been cleared.")
    else:
        await ctx.send("⚠️ Your tracking list is already empty.")
@bot.group(name="r", invoke_without_command=True)
async def r_group(ctx):
    # Safe lookup logic handles mentions without ever crashing out the context object
    if ctx.message.mentions:
        target = ctx.message.mentions[0]
        tid = str(target.id)
        c_dt = user_collections.get(tid, [])
        s_dt = shiny_hunts.get(tid, [])
        summary = f"📋 **Target Profile Breakdown for {target.name}:**\n\n🔹 **Collection:** {', '.join(sorted(c_dt)) if c_dt else '*None*'}\n"
        summary += f"✨ **Shiny Hunts:** {', '.join(sorted(s_dt)) if s_dt else '*None*'}\n"
        return await ctx.send(summary)
    await ctx.send("📦 **Global Server Reserves:**\n`e!r add <name>` • `e!r remove <name>` • `e!r list` • `e!r clear` • `e!r @user`")

@r_group.command(name="add")
async def r_add(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Specify a Pokémon name! Example: `e!r add Mewtwo`")
    global reserve_list
    name = name.strip().title()
    if name not in reserve_list:
        reserve_list.append(name)
        save_data()
        await ctx.send(f"📦 **{name}** has been added to the global Server Reserve manifest!")
    else:
        await ctx.send(f"⚠️ **{name}** already resides inside the server reserve catalog.")

@r_group.command(name="remove", aliases=["del"])
async def r_remove(ctx, *, name: str = None):
    if not name:
        return await ctx.send("⚠️ Specify a reserve target name to remove!")
    global reserve_list
    name = name.strip().title()
    if name in reserve_list:
        reserve_list.remove(name)
        save_data()
        await ctx.send(f"❌ **{name}** pulled from the Server Reserve index.")
    else:
        await ctx.send(f"⚠️ Target **{name}** does not exist inside the server profile repository.")

@r_group.command(name="list", aliases=["view"])
async def r_list(ctx):
    if reserve_list:
        lines = [f"{i+1}. 📦 **{n}**" for i, n in enumerate(sorted(reserve_list))]
        await ctx.send(f"📋 **Server-Wide Priority Reserve Manifest:**\n" + "\n".join(lines))
    else:
        await ctx.send("📦 The shared tracking registry is empty. Deploy updates using `e!r add <name>`.")

@r_group.command(name="clear")
async def r_clear(ctx):
    global reserve_list
    if reserve_list:
        reserve_list = []
        save_data()
        await ctx.send("📦🗑️ **The shared server Reserve tracking list has been reset to empty.**")
    else:
        await ctx.send("⚠️ Matrix register is already empty.")

@bot.event
async def on_message(message):
    # Absolute background handler protection to bypass all text-parsing bugs completely
    try:
        if message.author == bot.user:
            return
            
        # 1. Standard command prefix processor execution
        await bot.process_commands(message)
        
        # 2. Fully shielded computer vision scanner loop targeting Poketwo embeds
        if message.author.name == "Pokétwo" or message.author.id == 716390085896962058:
            if message.embeds:
                for emb in message.embeds:
                    if emb.image and emb.image.url:
                        url = emb.image.url
                        is_shiny = "shiny" in url.lower()
                        
                        try:
                            # Stream file directly into temporary local bit vector array
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
                                shiny_lbl = "✨ SHINY " if is_shiny else "wild "
                                await message.channel.send(f"🚨 **Spawn Detected!** Visual patterns match a {shiny_lbl}**{match}**!")
                                
                                pings = []
                                for uid, col in user_collections.items():
                                    if match in col:
                                        pings.append(f"<@{uid}> (Collection)")
                                if is_shiny:
                                    for uid, sh in shiny_hunts.items():
                                        if match in sh:
                                            pings.append(f"<@{uid}> (✨ SHINY TARGET!)")
                                            
                                is_on_reserve = match in reserve_list
                                if pings or is_on_reserve:
                                    msg = "🔔 **Target Alert!** " + " ".join(pings)
                                    if is_on_reserve:
                                        msg += " ⚠️ **[Server Reserve Match Found!]**"
                                    await message.channel.send(msg)
                        except Exception as img_err:
                            print(f"[SCANNER FAULT] Image loop processing halted: {img_err}")
                            
    except Exception as general_err:
        print(f"[FATAL LOG ERROR] Trapped loop variance safely: {general_err}")
        traceback.print_exc()

# Clean execution context fetches private dashboard tokens safely
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("[CRITICAL SHUTDOWN] Your DISCORD_TOKEN is missing from your production configurations environment variables panel!")
