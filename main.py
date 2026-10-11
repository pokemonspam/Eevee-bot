import os
import discord
from discord.ext import commands
from pymongo import MongoClient
from aiohttp import web

import dataset

# Initialize Discord Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["A!", "a!"], intents=intents, case_insensitive=True)

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
cluster = MongoClient(MONGO_URI)
db = cluster["pokemon_bot"]
collection_db = db["collections"]
hunt_db = db["hunts"]
reserve_db = db["reserves"]

# Lightweight Web Server for Render Port Detection
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

# --- COLLECTION COMMANDS (A!cl) ---
@bot.group(name="cl", invoke_without_command=True)
async def cl_group(ctx):
    embed = discord.Embed(
        title="Collection List Commands",
        description="`A!cl add <mon>` - Add Pokémon/Regionals\n"
                    "`A!cl add all <mon>` - Add all forms of a Pokémon\n"
                    "`A!cl remove <mon>` - Remove from collection\n"
                    "`A!cl show` - View collection",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@cl_group.command(name="add")
async def cl_add(ctx, *, name: str):
    if not dataset.is_valid_pokemon(name):
        return await ctx.send(embed=discord.Embed(description="Mega and Gigantamax forms cannot be added to collections!", color=discord.Color.red()))
    
    parts = name.split()
    if len(parts) > 1 and parts[0].lower() == "all":
        target = " ".join(parts[1:])
        forms = dataset.get_all_forms(target)
        collection_db.update_one({"user_id": ctx.author.id}, {"$addToSet": {"mons": {"$each": forms}}}, upsert=True)
        return await ctx.send(embed=discord.Embed(description=f"Added all forms of **{target.title()}** to your collection!", color=discord.Color.green()))
    
    formatted_name = name.strip().title()
    collection_db.update_one({"user_id": ctx.author.id}, {"$addToSet": {"mons": formatted_name}}, upsert=True)
    await ctx.send(embed=discord.Embed(description=f"Added **{formatted_name}** to your collection!", color=discord.Color.green()))

# --- SHINY HUNT COMMANDS (A!sh) ---
@bot.group(name="sh", invoke_without_command=True)
async def sh_group(ctx):
    embed = discord.Embed(
        title="Shiny Hunt Commands",
        description="`A!sh hunt <mon>` - Set your active shiny hunt\n"
                    "`A!sh show` - View your active shiny hunt",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@sh_group.command(name="hunt")
async def sh_hunt(ctx, *, name: str):
    if not dataset.is_valid_pokemon(name):
        return await ctx.send(embed=discord.Embed(description="Mega and Gigantamax forms cannot be shiny hunted!", color=discord.Color.red()))
    
    formatted_name = name.strip().title()
    hunt_db.update_one({"user_id": ctx.author.id}, {"$set": {"hunt": formatted_name}}, upsert=True)
    await ctx.send(embed=discord.Embed(description=f"Your shiny hunt target is now set to **{formatted_name}**!", color=discord.Color.gold()))

# --- RESERVE COMMANDS (A!r) ---
@bot.group(name="r", invoke_without_command=True)
async def r_group(ctx, member: discord.Member = None):
    if member:
        # User specific reserve lookup
        user_reserves = reserve_db.find({"user_id": member.id})
        mons = [r["pokemon"] for r in user_reserves]
        if not mons:
            return await ctx.send(embed=discord.Embed(description=f"**{member.display_name}** has no reserved Pokémon.", color=discord.Color.orange()))
        return await ctx.send(embed=discord.Embed(title=f"Reserves for {member.display_name}", description=", ".join(mons), color=discord.Color.blue()))
    
    embed = discord.Embed(
        title="Reserve Commands",
        description="`A!r add <mon>` - Reserve a Pokémon\n"
                    "`A!r remove <mon1, mon2>` - Remove Pokémon from global reserves\n"
                    "`A!r @user` - View reserves for a user\n"
                    "`A!r e @user` - Exchange reserves",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@r_group.command(name="remove")
async def r_remove(ctx, *, mons: str):
    mon_list = [m.strip().title() for m in mons.split(",")]
    result = reserve_db.delete_many({"pokemon": {"$in": mon_list}})
    await ctx.send(embed=discord.Embed(description=f"Removed **{result.deleted_count}** reserve entries for: {', '.join(mon_list)}", color=discord.Color.green()))

@r_group.command(name="e")
async def r_exchange(ctx, mainuser: discord.Member):
    reserves = list(reserve_db.find({"user_id": ctx.author.id}))
    if not reserves:
        return await ctx.send(embed=discord.Embed(description="You have no reserved Pokémon to exchange.", color=discord.Color.orange()))
    
    failed_mons = []
    successful_count = 0
    for entry in reserves:
        mon = entry["pokemon"]
        try:
            # Transfer logic
            collection_db.update_one({"user_id": mainuser.id}, {"$addToSet": {"mons": mon}}, upsert=True)
            reserve_db.delete_one({"_id": entry["_id"]})
            successful_count += 1
        except Exception:
            failed_mons.append(mon)
            
    if failed_mons:
        await ctx.send(embed=discord.Embed(
            description=f"Exchange partially completed. Failed to add: **{', '.join(failed_mons)}**", 
            color=discord.Color.red()
        ))
    else:
        await ctx.send(embed=discord.Embed(description="Exchange completed successfully!", color=discord.Color.green()))

async def main():
    async with bot:
        await start_dummy_server()
        TOKEN = os.getenv("DISCORD_TOKEN")
        if not TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable is missing!")
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
