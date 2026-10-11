import os
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

# Import dataset helpers from dataset.py
from dataset import (
    parse_pokemon_list,
    format_pokemon_name,
    get_evolution_family,
    is_gmax_eligible,
    validate_species
)

# Setup Bot Client
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="A!", intents=intents)

# Setup MongoDB
mongo_url = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client["pokemon_bot"]

reserves_col = db["reserves"]
collections_col = db["collections"]
shiny_col = db["shiny_hunts"]
roles_col = db["staff_roles"]


# Helper: Check Reserve Staff Permissions
async def is_staff(ctx):
    if ctx.author.guild_permissions.administrator:
        return True
    doc = await roles_col.find_one({"guild_id": ctx.guild.id})
    if doc and "roles" in doc:
        user_role_ids = [role.id for role in ctx.author.roles]
        if any(rid in doc["roles"] for rid in user_role_ids):
            return True
    return False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="A!sh | A!cl | A!r"))


# ==========================================
# 📦 COLLECTION COMMANDS (A!cl)
# Strictly personal (No user lookup allowed)
# ==========================================

@bot.group(name="cl", invoke_without_command=True)
async def collection_group(ctx):
    embed = discord.Embed(
        title="📦 Collection Commands",
        description=(
            "**`A!cl`** - Display this collection help list.\n"
            "**`A!cl list`** - View your personal collection list.\n"
            "**`A!cl add <mons>`** - Add Pokémon to your collection.\n"
            "**`A!cl remove <mons>`** - Remove Pokémon from your collection.\n"
            "**`A!cl clear`** - Clear your entire collection."
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)


@collection_group.command(name="list")
async def collection_list(ctx):
    # Strictly retrieves author's collection
    user_doc = await collections_col.find_one({"user_id": ctx.author.id})
    if not user_doc or not user_doc.get("pokemon"):
        embed = discord.Embed(
            description="❌ Your collection is currently empty.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    mons = ", ".join(user_doc["pokemon"])
    embed = discord.Embed(
        title="📦 Your Collection",
        description=f"**List:** {mons}",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)



@collection_group.command(name="add")
async def collection_add(ctx, *, mons: str = None):
    if not mons:
        embed = discord.Embed(
            description="❌ Please specify at least one Pokémon to add.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    raw_list = [m.strip().lower() for m in mons.split(",") if m.strip()]
    final_mons = []

    for item in raw_list:
        if item.startswith("all "):
            target = item.replace("all ", "").strip()
            forms = get_evolution_family(target)
            if forms:
                final_mons.extend(forms)
            else:
                final_mons.append(target)
        else:
            final_mons.append(item)

    valid_mons = []
    for m in final_mons:
        if validate_species(m):
            valid_mons.append(format_pokemon_name(m))

    if not valid_mons:
        embed = discord.Embed(
            description="❌ No valid Pokémon species or forms were provided.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    unique_mons = list(dict.fromkeys(valid_mons))

    await collections_col.update_one(
        {"user_id": ctx.author.id},
        {"$addToSet": {"pokemon": {"$each": unique_mons}}},
        upsert=True
    )

    added_str = ", ".join(unique_mons)
    embed = discord.Embed(
        description=f"✅ Added to your collection: **{added_str}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@collection_group.command(name="remove")
async def collection_remove(ctx, *, mons: str = None):
    if not mons:
        embed = discord.Embed(
            description="❌ Please specify at least one Pokémon to remove.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    raw_list = [m.strip().lower() for m in mons.split(",") if m.strip()]
    final_mons = []

    for item in raw_list:
        if item.startswith("all "):
            target = item.replace("all ", "").strip()
            forms = get_evolution_family(target)
            if forms:
                final_mons.extend(forms)
            else:
                final_mons.append(target)
        else:
            final_mons.append(item)

    valid_mons = []
    for m in final_mons:
        if validate_species(m):
            valid_mons.append(format_pokemon_name(m))

    if not valid_mons:
        embed = discord.Embed(
            description="❌ No valid Pokémon species or forms were provided.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    unique_mons = list(dict.fromkeys(valid_mons))

    await collections_col.update_one(
        {"user_id": ctx.author.id},
        {"$pull": {"pokemon": {"$in": unique_mons}}}
    )

    removed_str = ", ".join(unique_mons)
    embed = discord.Embed(
        description=f"✅ Removed from your collection: **{removed_str}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)





@collection_group.command(name="clear")
async def collection_clear(ctx):
    # Clears the author's entire collection
    result = await collections_col.delete_one({"user_id": ctx.author.id})
    if result.deleted_count > 0:
        embed = discord.Embed(
            description="✅ Your collection has been completely cleared.",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            description="❌ Your collection is already empty.",
            color=discord.Color.red()
        )
    await ctx.send(embed=embed)



# ==========================================
# 📋 RESERVE COMMANDS (A!r)
# ==========================================

@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, target: discord.Member = None):
    # Lookup specific user reserves if @user is provided
    if target:
        user_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": target.id})
        if not user_doc or not user_doc.get("pokemon"):
            embed = discord.Embed(
                description=f"🔍 {target.mention} has no reserved Pokémon.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        mons = ", ".join(user_doc["pokemon"])
        embed = discord.Embed(
            title=f"📋 Reserves for {target.display_name}",
            description=f"**Reserved:** {mons}",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    # Default Help Menu with Compact Headers
    embed = discord.Embed(
        title="📋 Reserve Commands",
        description=(
            "## View & Lookup Commands\n"
            "**`A!r`** - Display this reserve command help list.\n"
            "**`A!r list`** - View all active server reserves.\n"
            "**`A!r @user`** - View reserved Pokémon for a specific user.\n"
            "**`A!r search <mons>`** - Search which users have specific Pokémon reserved.\n\n"
            "## Management Commands (Staff)\n"
            "**`A!r add <mons> [@user]`** - Add Pokémon/families to reserves.\n"
            "**`A!r remove <mons> [@user]`** - Remove specified reserves.\n"
            "**`A!r clear @user`** - Clear all reserves for a specific user.\n"
            "**`A!r clear`** - Clear all reserves across the entire server.\n"
            "**`A!r e @mainuser`** - Exchange reserves from replied message.\n\n"
            "## Admin Role Permissions\n"
            "**`A!r role list`** - View authorized staff roles.\n"
            "**`A!r role add @Role`** - Grant reserve staff permissions.\n"
            "**`A!r role remove @Role`** - Revoke reserve staff permissions."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="list")
async def reserve_list(ctx):
    cursor = reserves_col.find({"guild_id": ctx.guild.id})
    reserves = await cursor.to_list(length=100)

    if not reserves:
        embed = discord.Embed(
            description="🔍 No active reserves found for this server.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    lines = []
    for doc in reserves:
        member = ctx.guild.get_member(doc["user_id"])
        name = member.mention if member else f"User ID {doc['user_id']}"
        mons = ", ".join(doc.get("pokemon", []))
        lines.append(f"{name}: {mons}")

    embed = discord.Embed(
        title="📋 Server Reserves",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="clear")
async def reserve_clear(ctx, target: discord.Member = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to use staff commands.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if target:
        # Clear specific user reserves
        await reserves_col.delete_one({"guild_id": ctx.guild.id, "user_id": target.id})
        embed = discord.Embed(
            description=f"✅ Cleared all reserves for {target.mention}.",
            color=discord.Color.green()
        )
    else:
        # Full server-wide reset
        await reserves_col.delete_many({"guild_id": ctx.guild.id})
        embed = discord.Embed(
            description="✅ Cleared all reserves across the entire server.",
            color=discord.Color.green()
        )
    await ctx.send(embed=embed)


# ==========================================
# ✨️ SHINY HUNT COMMANDS (A!sh)
# ==========================================

@bot.group(name="sh", invoke_without_command=True)
async def shiny_group(ctx, *, target_mon: str = None):
    if target_mon:
        formatted_mon = format_pokemon_name(target_mon)
        await shiny_col.update_one(
            {"user_id": ctx.author.id},
            {"$set": {"target": formatted_mon}},
            upsert=True
        )
        embed = discord.Embed(
            description=f"✅ Set active shiny hunt target to ✨️ {formatted_mon}.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return

    user_doc = await shiny_col.find_one({"user_id": ctx.author.id})
    target = user_doc.get("target", "None") if user_doc else "None"

    embed = discord.Embed(
        title="✨️ Shiny Hunt Management",
        description=f"**Current Active Hunt:** ✨️ {target}\n\nUse **`A!sh <mon>`** to set a new target.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)


# Run Bot safely from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
