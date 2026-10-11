import os
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

# Import dataset helpers from dataset.py
from dataset import (
    parse_pokemon_list,
    format_pokemon_name,
    get_evolution_family,
    validate_species,
    POKEMON_FORMS
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


# --- Interactive Pagination View ---
class CollectionPaginationView(discord.ui.View):
    def __init__(self, user_id, all_pokemon, per_page=20):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.all_pokemon = all_pokemon
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = (len(all_pokemon) + per_page - 1) // per_page

    def get_embed(self):
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        current_mons = self.all_pokemon[start_idx:end_idx]

        # Formatted with bullet points • instead of numbers
        lines = [f"• {mon}" for mon in current_mons]

        embed = discord.Embed(
            title=f"📦 Your Collection (Page {self.current_page}/{self.total_pages})",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total Pokémon: {len(self.all_pokemon)}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This list belongs to someone else.", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This list belongs to someone else.", ephemeral=True)
            return

        if self.current_page < self.total_pages:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


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
async def collection_list(ctx, page: int = 1):
    user_doc = await collections_col.find_one({"user_id": ctx.author.id})
    if not user_doc or not user_doc.get("pokemon"):
        embed = discord.Embed(
            description="❌ Your collection is currently empty.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    all_pokemon = user_doc["pokemon"]
    view = CollectionPaginationView(ctx.author.id, all_pokemon)
    
    if page >= 1 and page <= view.total_pages:
        view.current_page = page

    # Only show buttons if there are multiple pages
    if view.total_pages > 1:
        await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send(embed=view.get_embed())


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
    invalid_items = []

    for item in raw_list:
        clean_item = item.replace("all ", "").strip()
        
        if validate_species(clean_item):
            if clean_item in POKEMON_FORMS or item.startswith("all "):
                forms = get_evolution_family(clean_item)
                final_mons.extend(forms)
            else:
                final_mons.append(format_pokemon_name(clean_item))
        else:
            invalid_items.append(item)

    # Add valid Pokémon to database immediately
    if final_mons:
        unique_mons = list(dict.fromkeys(final_mons))
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

    # Notify user about invalid names
    if invalid_items:
        bad_words = ", ".join([f'"{w}"' for w in invalid_items])
        embed = discord.Embed(
            description=f"⚠️ {bad_words} is not a valid Pokémon or form.",
            color=discord.Color.gold()
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
    invalid_items = []

    for item in raw_list:
        clean_item = item.replace("all ", "").strip()
        
        if validate_species(clean_item):
            if clean_item in POKEMON_FORMS or item.startswith("all "):
                forms = get_evolution_family(clean_item)
                final_mons.extend(forms)
            else:
                final_mons.append(format_pokemon_name(clean_item))
        else:
            invalid_items.append(item)

    # Remove valid Pokémon from database immediately
    if final_mons:
        unique_mons = list(dict.fromkeys(final_mons))
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

    # Notify user about invalid names
    if invalid_items:
        bad_words = ", ".join([f'"{w}"' for w in invalid_items])
        embed = discord.Embed(
            description=f"⚠️ {bad_words} is not a valid Pokémon or form.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)



@collection_group.command(name="clear")
async def collection_clear(ctx):
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
    # If a user mention or ID is provided directly after A!r
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
        embed.set_footer(text=f"Total Reserved: {len(user_doc['pokemon'])}")
        await ctx.send(embed=embed)
        return

    # Default Help Menu
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
            "**`A!r e @mainuser`** - Exchange reserves from a replied message.\n\n"
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


@reserve_group.command(name="e")
async def reserve_exchange(ctx, main_user: discord.Member = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to exchange reserves.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not main_user:
        embed = discord.Embed(
            description="❌ Please specify the main user to exchange reserves with (e.g., `A!r e @User`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not ctx.message.reference or not ctx.message.reference.message_id:
        embed = discord.Embed(
            description="❌ Please **reply to a message** containing the Pokémon list while running this command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        embed = discord.Embed(
            description="❌ Could not fetch the replied message.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    raw_content = replied_msg.content
    if not raw_content and replied_msg.embeds:
        raw_content = replied_msg.embeds[0].description or ""

    if not raw_content:
        embed = discord.Embed(
            description="❌ The replied message contains no text or readable Pokémon.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    raw_list = [m.strip().lower() for m in raw_content.replace("\n", ",").split(",") if m.strip()]
    final_mons = []

    for item in raw_list:
        clean_item = item.replace("all ", "").strip()
        if validate_species(clean_item):
            if clean_item in POKEMON_FORMS or item.startswith("all "):
                forms = get_evolution_family(clean_item)
                final_mons.extend(forms)
            else:
                final_mons.append(format_pokemon_name(clean_item))

    if not final_mons:
        embed = discord.Embed(
            description="❌ No valid Pokémon species or forms found in the replied message.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    unique_mons = list(dict.fromkeys(final_mons))

    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": main_user.id},
        {"$pull": {"pokemon": {"$in": unique_mons}}}
    )

    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
        {"$addToSet": {"pokemon": {"$each": unique_mons}}},
        upsert=True
    )

    exchanged_str = ", ".join(unique_mons)
    embed = discord.Embed(
        title="🔄 Reserve Exchange Successful",
        description=(
            f"Transferred **{len(unique_mons)}** Pokémon from {main_user.mention} to {ctx.author.mention}.\n\n"
            f"**Exchanged Pokémon:**\n{exchanged_str}"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="add")
async def reserve_add(ctx, *, args: str = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to modify reserves.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not args:
        embed = discord.Embed(
            description="❌ Please specify Pokémon to reserve (e.g. `A!r add Charmander @User`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    target_user = ctx.author
    if ctx.message.mentions:
        target_user = ctx.message.mentions[0]
        for mention in ctx.message.mentions:
            args = args.replace(mention.mention, "").replace(f"<@!{mention.id}>", "")

    raw_list = [m.strip().lower() for m in args.split(",") if m.strip()]
    final_mons = []
    invalid_items = []

    for item in raw_list:
        clean_item = item.replace("all ", "").strip()
        if validate_species(clean_item):
            if clean_item in POKEMON_FORMS or item.startswith("all "):
                forms = get_evolution_family(clean_item)
                final_mons.extend(forms)
            else:
                final_mons.append(format_pokemon_name(clean_item))
        else:
            invalid_items.append(item)

    if invalid_items:
        bad_words = ", ".join([f'"{w}"' for w in invalid_items])
        embed = discord.Embed(
            description=f"❌ {bad_words} is not a valid Pokémon or form.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    unique_mons = list(dict.fromkeys(final_mons))

    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": target_user.id},
        {"$addToSet": {"pokemon": {"$each": unique_mons}}},
        upsert=True
    )

    added_str = ", ".join(unique_mons)
    embed = discord.Embed(
        description=f"✅ Added to reserves for {target_user.mention}: **{added_str}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="remove")
async def reserve_remove(ctx, *, args: str = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to modify reserves.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not args:
        embed = discord.Embed(
            description="❌ Please specify Pokémon to remove from reserves.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    target_user = ctx.author
    if ctx.message.mentions:
        target_user = ctx.message.mentions[0]
        for mention in ctx.message.mentions:
            args = args.replace(mention.mention, "").replace(f"<@!{mention.id}>", "")

    raw_list = [m.strip().lower() for m in args.split(",") if m.strip()]
    final_mons = []

    for item in raw_list:
        clean_item = item.replace("all ", "").strip()
        if validate_species(clean_item):
            if clean_item in POKEMON_FORMS or item.startswith("all "):
                forms = get_evolution_family(clean_item)
                final_mons.extend(forms)
            else:
                final_mons.append(format_pokemon_name(clean_item))

    unique_mons = list(dict.fromkeys(final_mons))

    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": target_user.id},
        {"$pull": {"pokemon": {"$in": unique_mons}}}
    )

    removed_str = ", ".join(unique_mons)
    embed = discord.Embed(
        description=f"✅ Removed from reserves for {target_user.mention}: **{removed_str}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="search")
async def reserve_search(ctx, *, mon: str = None):
    if not mon:
        embed = discord.Embed(
            description="❌ Please specify a Pokémon to search.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    formatted_mon = format_pokemon_name(mon)
    cursor = reserves_col.find({
        "guild_id": ctx.guild.id, 
        "pokemon": {"$regex": f"^{formatted_mon}$", "$options": "i"}
    })
    results = await cursor.to_list(length=50)

    if not results:
        embed = discord.Embed(
            description=f"🔍 No user has **{formatted_mon}** reserved.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    users = []
    for doc in results:
        member = ctx.guild.get_member(doc["user_id"])
        users.append(member.mention if member else f"User ID {doc['user_id']}")

    embed = discord.Embed(
        title=f"🔍 Reserve Search: {formatted_mon}",
        description="**Reserved by:**\n" + "\n".join(users),
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
        await reserves_col.delete_one({"guild_id": ctx.guild.id, "user_id": target.id})
        embed = discord.Embed(
            description=f"✅ Cleared all reserves for {target.mention}.",
            color=discord.Color.green()
        )
    else:
        await reserves_col.delete_many({"guild_id": ctx.guild.id})
        embed = discord.Embed(
            description="✅ Cleared all reserves across the entire server.",
            color=discord.Color.green()
        )
    await ctx.send(embed=embed)


# --- Reserve Staff Role Management Subgroup ---

@reserve_group.group(name="role", invoke_without_command=True)
async def reserve_role_group(ctx):
    embed = discord.Embed(
        title="🛡️ Reserve Staff Role Commands",
        description=(
            "**`A!r role list`** - View configured staff roles.\n"
            "**`A!r role add @Role`** - Grant reserve staff permissions.\n"
            "**`A!r role remove @Role`** - Revoke reserve staff permissions."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="list")
async def reserve_role_list(ctx):
    doc = await roles_col.find_one({"guild_id": ctx.guild.id})
    if not doc or not doc.get("roles"):
        embed = discord.Embed(
            description="ℹ️ No staff roles configured. Administrators have default access.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    roles = [f"<@&{rid}>" for rid in doc["roles"]]
    embed = discord.Embed(
        title="🛡️ Authorized Reserve Staff Roles",
        description="\n".join(roles),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="add")
async def reserve_role_add(ctx, role: discord.Role = None):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not role:
        embed = discord.Embed(
            description="❌ Please mention a valid role (e.g. `A!r role add @Staff`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$addToSet": {"roles": role.id}},
        upsert=True
    )
    embed = discord.Embed(
        description=f"✅ Granted reserve staff permissions to {role.mention}.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="remove")
async def reserve_role_remove(ctx, role: discord.Role = None):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not role:
        embed = discord.Embed(
            description="❌ Please mention a valid role to remove.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$pull": {"roles": role.id}}
    )
    embed = discord.Embed(
        description=f"✅ Revoked reserve staff permissions from {role.mention}.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# ==========================================
# ✨️ SHINY HUNT COMMANDS (A!sh)
# ==========================================

@bot.group(name="sh", invoke_without_command=True)
async def shiny_group(ctx, *, target_mon: str = None):
    if target_mon:
        clean_target = target_mon.strip().lower()
        if not validate_species(clean_target):
            embed = discord.Embed(
                description=f"❌ **{target_mon}** is not a valid Pokémon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        formatted_mon = format_pokemon_name(clean_target)
        await shiny_col.update_one(
            {"user_id": ctx.author.id},
            {"$set": {"target": formatted_mon}},
            upsert=True
        )
        embed = discord.Embed(
            description=f"✅ Set active shiny hunt to ✨️ **{formatted_mon}**.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return

    user_doc = await shiny_col.find_one({"user_id": ctx.author.id})
    target = user_doc.get("target", "None") if user_doc else "None"

    embed = discord.Embed(
        title="✨️ Shiny Hunt",
        description=f"**Current Active Hunt:** ✨️ **{target}**\n\nUse **`A!sh <mon>`** to set a new target.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)


# Run Bot safely from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
