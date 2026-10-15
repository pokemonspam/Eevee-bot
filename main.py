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
    get_pokemon_variants,
    get_base_pokemon,
    validate_species,
    POKEMON_FORMS,
    REGIONAL_FORMS
)


# Setup Bot Client
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix= ("E!","e!") , intents=intents)

# Setup MongoDB
mongo_url = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client["pokemon_bot"]
bot.db = db

@bot.event
async def setup_hook():
    await bot.load_extension("starboard")
    print("✅ Loaded starboard extension successfully!")

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
    await bot.change_presence(activity=discord.Game(name="E!sh | E!cl | E!r"))


    # ==========================================
# ⚡ SPAWN PING LISTENER
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    # Ensure message is from Pokétwo (ID: 716390085896962058) and in a guild
    if message.guild and message.author.id == 716390085896962058:
        if message.embeds:
            embed = message.embeds[0]
            if embed.title and "wild pokémon has appeared" in embed.title.lower():
                spawned_pokemon = None

                # Extract Pokédex ID directly from Pokétwo's image URL (e.g., .../images/25.png -> 25)
                if embed.image and embed.image.url:
                    match = re.search(r'/images/(\d+)\.png', embed.image.url)
                    if match:
                        dex_id = int(match.group(1))
                        from dataset import get_pokemon_by_id
                        spawned_pokemon = get_pokemon_by_id(dex_id)

                if spawned_pokemon:
                    guild_id = message.guild.id
                    target_clean = spawned_pokemon.lower()
                    formatted_target = format_pokemon_name(target_clean)

                    pings_to_send = []

                    # A. Check Shiny Hunt Pings (E!sh)
                    sh_cursor = shiny_col.find({"target": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    sh_users = await sh_cursor.to_list(length=100)
                    for doc in sh_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"✨ {member.mention} (Shiny Hunt)")

                    # B. Check Collection Pings (E!cl)
                    col_cursor = collections_col.find({"pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    col_users = await col_cursor.to_list(length=100)
                    for doc in col_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"📦 {member.mention} (Collection)")

                    # C. Check Reserves Pings (E!r)
                    res_cursor = reserves_col.find({"guild_id": guild_id, "pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    res_users = await res_cursor.to_list(length=100)
                    for doc in res_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"🔒 {member.mention} (Reserved)")

                    # Dispatch the pings into the spawn channel if any matches were found
                    if pings_to_send:
                        ping_content = f"**Spawn Alert:** `{formatted_target}`\n" + " | ".join(pings_to_send)
                        await message.channel.send(ping_content)

    # CRITICAL: Always process commands so E!sh, E!cl, E!r still work
    await bot.process_commands(message)


                    # -------------------------------------------------------------
                    # A. Check Shiny Hunt Pings (E!sh)
                    # -------------------------------------------------------------
                    sh_cursor = shiny_col.find({"target": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    sh_users = await sh_cursor.to_list(length=100)
                    for doc in sh_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"✨ {member.mention} (Shiny Hunt)")

                    # -------------------------------------------------------------
                    # B. Check Collection Pings (E!cl)
                    # -------------------------------------------------------------
                    col_cursor = collections_col.find({"pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    col_users = await col_cursor.to_list(length=100)
                    for doc in col_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"📦 {member.mention} (Collection)")

                    # -------------------------------------------------------------
                    # C. Check Reserves Pings (E!r)
                    # -------------------------------------------------------------
                    res_cursor = reserves_col.find({"guild_id": guild_id, "pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                    res_users = await res_cursor.to_list(length=100)
                    for doc in res_users:
                        member = message.guild.get_member(doc["user_id"])
                        if member:
                            pings_to_send.append(f"🔒 {member.mention} (Reserved)")

                    # Dispatch the pings into the spawn channel if any matches were found
                    if pings_to_send:
                        ping_content = f"**Spawn Alert:** `{formatted_target}`\n" + " | ".join(pings_to_send)
                        await message.channel.send(ping_content)

    # CRITICAL: Ensures commands like E!sh, E!cl, E!r are processed even with on_message active
    await bot.process_commands(message)

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
            "**`E!cl`** - Display this collection help list.\n"
            "**`E!cl list`** - View your personal collection list.\n"
            "**`E!cl add <mons>`** - Add Pokémon to your collection.\n"
            "**`E!cl remove <mons>`** - Remove Pokémon from your collection.\n"
            "**`E!cl clear`** - Clear your entire collection."
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
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
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
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
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
# 📋 RESERVE COMMANDS (E!r)
# ==========================================

@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, target: discord.Member = None, page: int = 1):
    if target:
        await reserve_user(ctx, target=target, page=page)
        return

    embed = discord.Embed(
        title="📋 Reserve Commands",
        description=(
            "## View & Lookup Commands\n"
            "**`E!r`** - Display this reserve command help list.\n"
            "**`E!r list`** - View all active server reserves.\n"
            "**`E!r @user`** - View reserved Pokémon for a specific user.\n"
            "**`E!r search <mons>`** - Search which users have specific Pokémon reserved.\n\n"
            "## Management Commands (Staff)\n"
            "**`E!r add <mons> [@user]`** - Add Pokémon/families to reserves.\n"
            "**`E!r remove <mons> [@user]`** - Remove specified reserves.\n"
            "**`E!r clear @user`** - Clear all reserves for a specific user.\n"
            "**`E!r clear`** - Clear all reserves across the entire server.\n"
            "**`E!r e @mainuser`** - Exchange reserves from a replied message.\n\n"
            "## Admin Role Permissions\n"
            "**`E!r role list`** - View authorized staff roles.\n"
            "**`E!r role add @Role`** - Grant reserve staff permissions.\n"
            "**`E!r role remove @Role`** - Revoke reserve staff permissions."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)



@reserve_group.command(name="list")
async def reserve_list(ctx, page: int = 1):
    try:
        cursor = reserves_col.find({"guild_id": ctx.guild.id})
        reserves = await cursor.to_list(length=1000)

        if not reserves:
            embed = discord.Embed(
                description="🔍 No active reserves found for this server.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        mon_to_users = {}
        for doc in reserves:
            user_id = doc["user_id"]
            member = ctx.guild.get_member(user_id)
            user_mention = member.mention if member else f"<@{user_id}>"
            
            for mon in doc.get("pokemon", []):
                formatted_mon = format_pokemon_name(mon)
                if formatted_mon not in mon_to_users:
                    mon_to_users[formatted_mon] = []
                if user_mention not in mon_to_users[formatted_mon]:
                    mon_to_users[formatted_mon].append(user_mention)

        formatted_lines = [
            f"• **{mon}** - {', '.join(users)}"
            for mon, users in sorted(mon_to_users.items(), key=lambda item: item[0].lower())
        ]

        view = ReservePaginationView(ctx.author.id, formatted_lines, per_page=20)
        if 1 <= page <= view.total_pages:
            view.current_page = page

        if view.total_pages > 1:
            await ctx.send(embed=view.get_embed(), view=view)
        else:
            await ctx.send(embed=view.get_embed())

    except Exception as e:
        print(f"Error in reserve_list: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))



@reserve_group.command(name="e")
async def reserve_exchange(ctx, main_user: discord.Member = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to use staff exchange commands.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not ctx.message.reference:
        embed = discord.Embed(
            description="❌ Please reply to a message containing the user list (e.g., `@user - all furfrou, alolan vulpix, pikachu`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        await ctx.send(embed=discord.Embed(description="❌ Could not fetch the replied message.", color=discord.Color.red()))
        return

    if main_user:
        giver_id = main_user.id
    elif replied_msg.author and not replied_msg.author.bot:
        giver_id = replied_msg.author.id
    else:
        giver_id = ctx.author.id

    giver_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": giver_id})
    giver_pokemon = set(giver_doc.get("pokemon", [])) if giver_doc else set()

    if not giver_pokemon:
        giver_mention = f"<@{giver_id}>"
        embed = discord.Embed(
            description=f"❌ {giver_mention} has no Pokémon in their reserves to give away.",
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
                        error_report.append(f"`{criterion}` (for {user.display_name}) - No matching Pokémon found in <@{giver_id}>'s reserves")
                
                else:
                    formatted_mon = format_pokemon_name(criterion)
                    
                    if formatted_mon in current_giver_pool:
                        user_valid_mons.append(formatted_mon)
                        current_giver_pool.remove(formatted_mon)
                    elif criterion in current_giver_pool:
                        user_valid_mons.append(criterion)
                        current_giver_pool.remove(criterion)
                    else:
                        error_report.append(f"`{criterion}` (for {user.display_name}) - Not in <@{giver_id}>'s reserves or typed wrong")

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
            description=f"✅ Exchange successful!\n Successfully distributed **{transfers_made}** Pokémon from <@{giver_id}>'s reserves.",
            color=discord.Color.green()
        )
    elif transfers_made > 0 and error_report:
        embed = discord.Embed(
            description=(
                f"⚠️ Distributed valid Pokémon (**{transfers_made}** transferred from <@{giver_id}>), but encountered some issues:\n\n"
                f"❌ **What went wrong:**\n• " + "\n• ".join(error_report)
            ),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            description=(
                f"❌ Exchange failed. None of the specified Pokémon could be transferred.\n\n"
                f"❌ **What went wrong:**\n• " + ("\n• ".join(error_report) if error_report else "No valid entries found in the replied message.")
            ),
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)




@reserve_group.command(name="add")
async def reserve_add(ctx, *, args: str = None):
    try:
        if not await is_staff(ctx):
            embed = discord.Embed(
                description="❌ You do not have permission to modify reserves.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if not args:
            embed = discord.Embed(
                description="❌ Please specify Pokémon to reserve (e.g. `E!r add Charmander @User`).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        target_user = ctx.author
        if ctx.message.mentions:
            target_user = ctx.message.mentions[0]
            for mention in ctx.message.mentions:
                args = args.replace(mention.mention, "").replace(f"<@!{mention.id}>", "")

        raw_list = parse_pokemon_list(args)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            
            await reserves_col.update_one(
                {"guild_id": ctx.guild.id, "user_id": target_user.id},
                {"$addToSet": {"pokemon": {"$each": unique_mons}}},
                upsert=True
            )
            added_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Added to reserves for {target_user.mention}: **{added_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Added valid Pokémon, but ignored unknown items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error in reserve_add: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


@reserve_group.command(name="remove")
async def reserve_remove(ctx, *, args: str = None):
    try:
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

        raw_list = parse_pokemon_list(args)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            
            await reserves_col.update_one(
                {"guild_id": ctx.guild.id, "user_id": target_user.id},
                {"$pull": {"pokemon": {"$in": unique_mons}}}
            )
            removed_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Removed from reserves for {target_user.mention}: **{removed_str}**",
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
        print(f"Error in reserve_remove: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))




@reserve_group.command(name="search")
async def reserve_search(ctx, *, mon: str = None):
    try:
        if not mon:
            embed = discord.Embed(
                description="❌ Please specify a Pokémon to search.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        is_all = mon.startswith("all ")
        clean_mon = mon[4:].strip() if is_all else mon.strip()

        if is_all:
            target_mons = get_pokemon_variants(clean_mon)
        elif clean_mon in POKEMON_FORMS:
            target_mons = [get_base_pokemon(clean_mon)]
        elif clean_mon in REGIONAL_FORMS:
            target_mons = [REGIONAL_FORMS[clean_mon]]
        else:
            target_mons = [format_pokemon_name(clean_mon)]

        cursor = reserves_col.find({"guild_id": ctx.guild.id})
        all_reserves = await cursor.to_list(length=1000)

        mon_to_users = {}

        for doc in all_reserves:
            user_id = doc["user_id"]
            member = ctx.guild.get_member(user_id)
            user_mention = member.mention if member else f"<@{user_id}>"

            user_pokemon = [format_pokemon_name(p) for p in doc.get("pokemon", [])]

            for target in target_mons:
                formatted_target = format_pokemon_name(target)
                if formatted_target in user_pokemon:
                    if formatted_target not in mon_to_users:
                        mon_to_users[formatted_target] = []
                    if user_mention not in mon_to_users[formatted_target]:
                        mon_to_users[formatted_target].append(user_mention)

        if not mon_to_users:
            searched_name = f"All {format_pokemon_name(clean_mon)}" if is_all else format_pokemon_name(clean_mon)
            embed = discord.Embed(
                description=f"🔍 No user has reserved **{searched_name}**.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        formatted_lines = [
            f"• **{pokemon}** - {', '.join(users)}"
            for pokemon, users in sorted(mon_to_users.items())
        ]

        embed = discord.Embed(
            title=f"🔍 Reserve Search Results",
            description="\n".join(formatted_lines),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error in reserve_search: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))



@reserve_group.command(name="user")
async def reserve_user(ctx, target: discord.Member = None, page: int = 1):
    if not target:
        target = ctx.author

    user_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": target.id})
    if not user_doc or not user_doc.get("pokemon"):
        embed = discord.Embed(
            description=f"🔍 {target.mention} has no reserved Pokémon.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    all_pokemon = user_doc["pokemon"]
    formatted_lines = [f"• {format_pokemon_name(mon)}" for mon in sorted(all_pokemon)]

    title = f"📋 Reserves for {target.display_name}"
    view = ReservePaginationView(ctx.author.id, formatted_lines, title=title, per_page=20)
    
    if 1 <= page <= view.total_pages:
        view.current_page = page

    if view.total_pages > 1:
        await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send(embed=view.get_embed())



@reserve_group.command(name="clear")
async def reserve_clear(ctx, target: discord.Member = None):
    try:
        if not await is_staff(ctx):
            embed = discord.Embed(
                description="❌ You do not have permission to use staff commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if target:
            prompt_text = f"⚠️ Are you sure you want to clear all reserves for {target.mention}?"
        else:
            prompt_text = "⚠️ Are you sure you want to **clear ALL reserves** across the entire server?"

        embed = discord.Embed(
            description=prompt_text,
            color=discord.Color.gold()
        )
        view = ClearConfirmView(author_id=ctx.author.id, target_user=target, guild_id=ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    except Exception as e:
        print(f"Error in reserve_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


def parse_roles_from_input(ctx, raw_input: str):
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


@reserve_group.group(name="role", invoke_without_command=True)
async def reserve_role_group(ctx):
    embed = discord.Embed(
        title="🛡️ Reserve Staff Role Commands",
        description=(
            "**`E!r role list`** - View configured staff roles.\n"
            "**`E!r role add @Role1, @Role2`** - Grant reserve staff permissions.\n"
            "**`E!r role remove @Role1, @Role2`** - Revoke reserve staff permissions."
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
async def reserve_role_add(ctx, *, roles_input: str = None):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role (e.g. `E!r role add @Staff, @Mod`).",
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
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role to remove (e.g. `E!r role remove @Staff`).",
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


# ==========================================
# ✨️ SHINY HUNT COMMANDS (E!sh)
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
        description=f"**Current Active Hunt:** ✨️ **{target}**\n\nUse **`E!sh <mon>`** to set a new target.",
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
