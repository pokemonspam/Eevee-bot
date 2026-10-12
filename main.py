import os
import re
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

# Import dataset helpers and registries from dataset.py
from dataset import (
    parse_pokemon_list,
    format_pokemon_name,
    get_evolution_family,
    validate_species,
    POKEMON_FORMS,
    REGIONAL_FORMS
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

        lines = [f"• {mon}" for mon in current_mons]

        embed = discord.Embed(
            title=f"📦 Your Collection (Page {self.current_page}/{self.total_pages})",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total Pokémon: {len(self.all_pokemon)}")
        return embed

    @discord.ui.button(label="  ◀️  ", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This list belongs to someone else.", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    
    @discord.ui.button(label="  ▶️  ", style=discord.ButtonStyle.primary, custom_id="next_page")
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
class ReservePaginationView(discord.ui.View):
    def __init__(self, author_id, formatted_lines, title="📋 Server Reserves", per_page=20):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.formatted_lines = formatted_lines
        self.title = title
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(formatted_lines) + per_page - 1) // per_page)

    def get_embed(self):
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        current_lines = self.formatted_lines[start_idx:end_idx]

        embed = discord.Embed(
            title=f"{self.title} (Page {self.current_page}/{self.total_pages})",
            description="\n".join(current_lines) if current_lines else "No active reserves.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Total Reserved Entries: {len(self.formatted_lines)}")
        return embed

    @discord.ui.button(label="  ◀️  ", style=discord.ButtonStyle.primary, custom_id="reserve_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="  ▶️  ", style=discord.ButtonStyle.primary, custom_id="reserve_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        if self.current_page < self.total_pages:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

class ClearConfirmView(discord.ui.View):
    def __init__(self, author_id, target_user=None, guild_id=None):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.target_user = target_user
        self.guild_id = guild_id
        self.confirmed = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, custom_id="clear_yes")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        if self.target_user:
            await reserves_col.delete_one({"guild_id": self.guild_id, "user_id": self.target_user.id})
            embed = discord.Embed(
                description=f"✅ Cleared all reserves for {self.target_user.mention}.",
                color=discord.Color.green()
            )
        else:
            await reserves_col.delete_many({"guild_id": self.guild_id})
            embed = discord.Embed(
                description="✅ Cleared all reserves across the entire server.",
                color=discord.Color.green()
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, custom_id="clear_no")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            description="❌ Reserve clear action canceled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=self)

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
    try:
        if not mons:
            embed = discord.Embed(
                description="❌ Please specify at least one Pokémon to add.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        raw_list = parse_pokemon_list(mons)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            clean_item = item.replace("all ", "").strip()
            
            if validate_species(clean_item) or validate_species(item):
                # Check if it's a form group or requested with "all"
                if clean_item in POKEMON_FORMS or item.startswith("all "):
                    forms = get_evolution_family(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(item if validate_species(item) else clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            await collections_col.update_one(
                {"user_id": ctx.author.id},
                {"$addToSet": {"pokemon": {"$each": unique_mons}}},
                upsert=True
            )
            added_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Added to your collection: **{added_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Added valid Pokémon, but ignored invalid items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        print(f"Error in collection_add: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


@collection_group.command(name="remove")
async def collection_remove(ctx, *, mons: str = None):
    try:
        if not mons:
            embed = discord.Embed(
                description="❌ Please specify at least one Pokémon to remove.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        raw_list = parse_pokemon_list(mons)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            clean_item = item.replace("all ", "").strip()
            
            if validate_species(clean_item) or validate_species(item):
                if clean_item in POKEMON_FORMS or item.startswith("all "):
                    forms = get_evolution_family(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(item if validate_species(item) else clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            await collections_col.update_one(
                {"user_id": ctx.author.id},
                {"$pull": {"pokemon": {"$in": unique_mons}}}
            )
            removed_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Removed from your collection: **{removed_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Removed valid Pokémon, but ignored unknown items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        print(f"Error in collection_remove: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))

@collection_group.command(name="clear")
async def collection_clear(ctx):
    try:
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
    except Exception as e:
        print(f"Error in collection_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


# ==========================================
# 📋 RESERVE SYSTEM & ROLE MANAGEMENT (main.py)
# ==========================================

def parse_roles_from_input(ctx, raw_input: str):
    """Extract valid discord.Role objects and invalid role names from comma-separated input."""
    items = [item.strip() for item in raw_input.split(",") if item.strip()]
    valid_roles = []
    invalid_roles = []

    for item in items:
        role = None
        match = re.search(r"<@&(\d+)>", item)
        if match:
            role_id = int(match.group(1))
            role = ctx.guild.get_role(role_id)
        elif item.isdigit():
            role = ctx.guild.get_role(int(item))
        else:
            role = discord.utils.get(ctx.guild.roles, name=item)

        if role:
            valid_roles.append(role)
        else:
            invalid_roles.append(item)

    return valid_roles, invalid_roles


@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, target: discord.Member = None):
    """View reserves. Default: Own reserves or specified user's reserves."""
    target_user = target if target else ctx.author
    
    doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": target_user.id})
    pokemon_list = doc.get("pokemon", []) if doc else []

    if not pokemon_list:
        embed = discord.Embed(
            description=f"ℹ️ {target_user.mention} has no reserved Pokémon.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    formatted_list = "\n• ".join(pokemon_list)
    embed = discord.Embed(
        title=f"📦 Reserved Pokémon — {target_user.display_name}",
        description=f"• {formatted_list}",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Total Reserved: {len(pokemon_list)}")
    await ctx.send(embed=embed)


# ------------------------------------------
# 🔓 PUBLIC COMMANDS
# ------------------------------------------

@reserve_group.command(name="list")
async def reserve_list_alias(ctx, target: discord.Member = None):
    """Alias for viewing reserves."""
    await reserve_group(ctx, target)


@reserve_group.command(name="search")
async def reserve_search(ctx, *, pokemon: str):
    """Search who has a specific Pokémon reserved across the server."""
    query_mon = pokemon.strip().lower()
    
    cursor = reserves_col.find({"guild_id": ctx.guild.id})
    results = []

    async for doc in cursor:
        user_mons = doc.get("pokemon", [])
        matches = [m for m in user_mons if query_mon in m.lower()]
        if matches:
            member = ctx.guild.get_member(doc["user_id"])
            user_str = member.mention if member else f"User ID `{doc['user_id']}`"
            results.append(f"{user_str}: {', '.join(matches)}")

    if not results:
        embed = discord.Embed(
            description=f"🔍 No reservations found matching **{pokemon}**.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"🔍 Search Results for '{pokemon}'",
        description="\n".join(results),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# ------------------------------------------
# 🛡️ STAFF COMMANDS
# ------------------------------------------

@reserve_group.command(name="e")
async def reserve_exchange(ctx):
    """Exchange / transfer Pokémon by replying to a formatted list."""
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You need Reserve Staff permissions to use the exchange command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not ctx.message.reference:
        embed = discord.Embed(
            description="❌ Please reply to a message containing the transfer list (e.g., `@user - all furfrou, alolan vulpix`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        await ctx.send(embed=discord.Embed(description="❌ Could not fetch the replied message.", color=discord.Color.red()))
        return

    giver_id = ctx.author.id
    giver_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": giver_id})
    giver_pokemon = set(giver_doc.get("pokemon", [])) if giver_doc else set()

    if not giver_pokemon:
        embed = discord.Embed(
            description="❌ You don't have any Pokémon in your reserves to give away.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    current_giver_pool = set(giver_pokemon)
    lines = replied_msg.content.split("\n")
    
    transfers_made = 0
    error_report = []
    total_pulled_mons = [] 

    for line in lines:
        if not line.strip():
            continue
        
        mentioned_users = [m for m in replied_msg.mentions if str(m.id) in line or m.mention in line]
        if not mentioned_users:
            continue

        parts = line.split("-") if "-" in line else line.split(":")
        if len(parts) < 2:
            continue
        
        pokemon_raw_text = parts[1].strip()
        criteria_list = [c.strip() for c in pokemon_raw_text.split(",") if c.strip()]

        for user in mentioned_users:
            user_valid_mons = []

            for criterion in criteria_list:
                crit_lower = criterion.lower()

                if crit_lower.startswith("all "):
                    target_species = crit_lower[4:].strip()
                    matching_mons = [
                        mon for mon in current_giver_pool 
                        if target_species in mon.lower() or mon.lower().startswith(target_species)
                    ]
                    
                    if matching_mons:
                        user_valid_mons.extend(matching_mons)
                        for m in matching_mons:
                            current_giver_pool.remove(m)
                    else:
                        error_report.append(f"`{criterion}` (for {user.display_name}) - No matching Pokémon in reserves")
                else:
                    formatted_mon = format_pokemon_name(criterion)
                    
                    if formatted_mon in current_giver_pool:
                        user_valid_mons.append(formatted_mon)
                        current_giver_pool.remove(formatted_mon)
                    elif criterion in current_giver_pool:
                        user_valid_mons.append(criterion)
                        current_giver_pool.remove(criterion)
                    else:
                        error_report.append(f"`{criterion}` (for {user.display_name}) - Not in reserves or typed wrong")

            if user_valid_mons:
                await reserves_col.update_one(
                    {"guild_id": ctx.guild.id, "user_id": user.id},
                    {"$addToSet": {"pokemon": {"$each": user_valid_mons}}},
                    upsert=True
                )
                transfers_made += len(user_valid_mons)
                total_pulled_mons.extend(user_valid_mons)

    if total_pulled_mons:
        await reserves_col.update_one(
            {"guild_id": ctx.guild.id, "user_id": giver_id},
            {"$pull": {"pokemon": {"$in": total_pulled_mons}}}
        )

    if transfers_made > 0 and not error_report:
        embed = discord.Embed(
            description=f"✅ Exchange successful! Transferred **{transfers_made}** Pokémon from your reserves.",
            color=discord.Color.green()
        )
    elif transfers_made > 0 and error_report:
        embed = discord.Embed(
            description=(
                f"⚠️ Transferred **{transfers_made}** valid Pokémon, but encountered issues:\n\n"
                f"❌ **What went wrong:**\n• " + "\n• ".join(error_report)
            ),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            description=(
                f"❌ Exchange failed. None of the specified Pokémon could be transferred.\n\n"
                f"❌ **What went wrong:**\n• " + ("\n• ".join(error_report) if error_report else "No valid line format found.")
            ),
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


@reserve_group.command(name="add")
async def reserve_add_staff(ctx, target: discord.Member, *, pokemon: str):
    """Add Pokémon to a user's reserves."""
    if not await is_staff(ctx):
        embed = discord.Embed(description="❌ You need Reserve Staff permissions to use this command.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    parsed_mons = [format_pokemon_name(p) for p in pokemon.split(",") if p.strip()]
    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": target.id},
        {"$addToSet": {"pokemon": {"$each": parsed_mons}}},
        upsert=True
    )

    embed = discord.Embed(
        description=f"✅ Added **{', '.join(parsed_mons)}** to {target.mention}'s reserves.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="remove")
async def reserve_remove_staff(ctx, target: discord.Member, *, pokemon: str):
    """Remove Pokémon from a user's reserves."""
    if not await is_staff(ctx):
        embed = discord.Embed(description="❌ You need Reserve Staff permissions to use this command.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    parsed_mons = [format_pokemon_name(p) for p in pokemon.split(",") if p.strip()]
    await reserves_col.update_one(
        {"guild_id": ctx.guild.id, "user_id": target.id},
        {"$pull": {"pokemon": {"$in": parsed_mons}}}
    )

    embed = discord.Embed(
        description=f"✅ Removed specified Pokémon from {target.mention}'s reserves.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="clear")
async def reserve_clear_staff(ctx, target: discord.Member = None):
    """Clear reserves. A!r clear = ENTIRE SERVER | A!r clear @user = SPECIFIC USER."""
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You need Reserve Staff or Administrator permissions to use the clear command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if target:
        await reserves_col.delete_one({"guild_id": ctx.guild.id, "user_id": target.id})
        embed = discord.Embed(
            description=f"🗑️ Successfully cleared all reserved Pokémon for {target.mention}.",
            color=discord.Color.green()
        )
    else:
        result = await reserves_col.delete_many({"guild_id": ctx.guild.id})
        embed = discord.Embed(
            description=f"⚠️ **Server Master Wipe:** Cleared reserves for **{result.deleted_count}** user(s) across the entire server.",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


# ------------------------------------------
# ⚙️ ADMIN ROLE COMMANDS
# ------------------------------------------

@reserve_group.group(name="role", invoke_without_command=True)
async def reserve_role_group(ctx):
    """Help embed for reserve staff role configuration."""
    embed = discord.Embed(
        title="⚙️ Reserve Staff Role Commands",
        description=(
            "`A!r role add @role1, @role2` - Add staff roles\n"
            "`A!r role remove @role1, @role2` - Remove staff roles\n"
            "`A!r role list` - View configured staff roles"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="add")
async def reserve_role_add(ctx, *, roles_input: str = None):
    """Add one or multiple roles to Reserve Staff."""
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role (e.g. `A!r role add @Staff, @Moderator`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    valid_roles, invalid_roles = parse_roles_from_input(ctx, roles_input)

    if not valid_roles and invalid_roles:
        embed = discord.Embed(
            description=f"❌ Could not find any valid roles from: `{', '.join(invalid_roles)}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    role_ids = [r.id for r in valid_roles]
    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$addToSet": {"roles": {"$each": role_ids}}},
        upsert=True
    )

    added_mentions = ", ".join([r.mention for r in valid_roles])
    desc = f"✅ {added_mentions} were added successfully."
    if invalid_roles:
        desc += f"\n❌ **Could not find / Invalid roles:** `{', '.join(invalid_roles)}`"

    embed = discord.Embed(description=desc, color=discord.Color.green())
    await ctx.send(embed=embed)


@reserve_role_group.command(name="remove")
async def reserve_role_remove(ctx, *, roles_input: str = None):
    """Remove one or multiple roles to Reserve Staff."""
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role to remove (e.g. `A!r role remove @Staff, FakeRole`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    valid_roles, invalid_roles = parse_roles_from_input(ctx, roles_input)

    if not valid_roles and invalid_roles:
        embed = discord.Embed(
            description=f"❌ Could not find any valid roles from: `{', '.join(invalid_roles)}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    role_ids = [r.id for r in valid_roles]
    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$pull": {"roles": {"$in": role_ids}}}
    )

    removed_mentions = ", ".join([r.mention for r in valid_roles])
    desc = f"✅ {removed_mentions} were removed successfully."
    if invalid_roles:
        desc += f"\n❌ **Could not find / Invalid roles:** `{', '.join(invalid_roles)}`"

    embed = discord.Embed(description=desc, color=discord.Color.green())
    await ctx.send(embed=embed)


@reserve_role_group.command(name="list")
async def reserve_role_list(ctx):
    """View all configured Reserve Staff roles."""
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

@shiny_group.command(name="clear")
async def shiny_clear(ctx):
    try:
        result = await shiny_col.delete_one({"user_id": ctx.author.id})
        if result.deleted_count > 0:
            embed = discord.Embed(
                description="✅ Your active shiny hunt has been cleared.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                description="❌ You do not have an active shiny hunt to clear.",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Error in shiny_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))



# Run Bot safely from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
