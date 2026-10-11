import os
import re
import discord
from discord.ext import commands
from discord.ui import View, Button
import dataset

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN environment variable is missing! Please set it in Render.")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="A!", intents=intents, help_command=None)

# Invalid exclusion targets for bulk 'all' commands
INVALID_EXCLUSIONS = ["mega", "gigantamax", "gmax", "primal"]


# --- Permission Helpers ---
async def can_manage_reserves_check(ctx):
    if ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id:
        return True
    allowed_role_ids = await dataset.get_allowed_roles(ctx.guild.id)
    user_role_ids = [role.id for role in ctx.author.roles]
    if any(rid in allowed_role_ids for rid in user_role_ids):
        return True
    raise commands.MissingPermissions(["Administrator or Allowed Reserve Staff Role"])


@bot.event
async def on_ready():
    await dataset.test_db_connection()
    print(f"✨️ Bot is online as {bot.user} (ID: {bot.user.id})")


# --- Pagination View for Lists (20 per page) ---
class PaginationView(View):
    def __init__(self, ctx, title, items, formatter_func):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.title = title
        self.items = items
        self.formatter_func = formatter_func
        self.per_page = 20
        self.current_page = 0
        self.max_pages = max(1, (len(items) + self.per_page - 1) // self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]

        embed = discord.Embed(color=discord.Color.gold())
        embed.title = f"✨️ {self.title}"
        
        description = self.formatter_func(page_items, start)
        if not description:
            description = "*No items found.*"
        embed.description = description
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.max_pages}")
        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


# --- Confirmation View for Shiny Hunt Changes ---
class ConfirmHuntView(View):
    def __init__(self, ctx, new_pokemon):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.new_pokemon = new_pokemon
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your prompt!", ephemeral=True)
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your prompt!", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.defer()


# ==================== SHINY HUNT COMMAND (`A!sh`) ====================
@bot.command(name="sh")
async def shiny_hunt(ctx, *, pokemon: str = None):
    guild_id = ctx.guild.id
    user_id = ctx.author.id

    if not pokemon:
        current = await dataset.get_shiny_hunt(user_id, guild_id)
        embed = discord.Embed(color=discord.Color.gold())
        if current:
            embed.description = f"# ✨️ Active Shiny Hunt\nYour current target is **{current.title()}**."
        else:
            embed.description = f"# ✨️ Active Shiny Hunt\nYou do not have an active shiny hunt set. Use `A!sh <pokemon>` to set one."
        return await ctx.send(embed=embed)

    pokemon = pokemon.strip().lower()
    existing = await dataset.get_shiny_hunt(user_id, guild_id)

    if existing:
        if existing == pokemon:
            return await ctx.send(embed=discord.Embed(description=f"# ✨️ Shiny Hunt\n**{pokemon.title()}** is already your active shiny hunt target!", color=discord.Color.gold()))
        
        # Ask for confirmation before replacing
        view = ConfirmHuntView(ctx, pokemon)
        msg = await ctx.send(embed=discord.Embed(description=f"# ✨️ Replace Active Hunt?\nYou already have **{existing.title()}** as your target. Do you want to change it to **{pokemon.title()}**?", color=discord.Color.gold()), view=view)
        await view.wait()

        if view.value is True:
            await dataset.set_shiny_hunt(user_id, guild_id, pokemon)
            await msg.edit(embed=discord.Embed(description=f"# ✨️ Shiny Hunt Updated\nSuccessfully changed your target from **{existing.title()}** to **{pokemon.title()}**!", color=discord.Color.gold()), view=None)
        else:
            await msg.edit(embed=discord.Embed(description="# ✨️ Shiny Hunt Cancelled\nYour active hunt target remains unchanged.", color=discord.Color.gold()), view=None)
        return

    await dataset.set_shiny_hunt(user_id, guild_id, pokemon)
    await ctx.send(embed=discord.Embed(description=f"# ✨️ Shiny Hunt Set\nSuccessfully set your shiny hunt target to **{pokemon.title()}**!", color=discord.Color.gold()))


# ==================== COLLECTION COMMAND (`A!cl`) ====================
@bot.group(name="cl", invoke_without_command=True)
async def collection_group(ctx, member: discord.Member = None):
    target = member or ctx.author
    items = sorted(await dataset.get_collection(target.id, ctx.guild.id))
    
    if not items:
        return await ctx.send(embed=discord.Embed(description=f"# ✨️ Collection\n**{target.display_name}** has no Pokémon in their collection.", color=discord.Color.gold()))

    def format_col(page_items, start):
        return "\n".join([f"**{start + i + 1}.** {mon.title()}" for i, mon in enumerate(page_items)])

    view = PaginationView(ctx, f"{target.display_name}'s Collection", items, format_col)
    await ctx.send(embed=view.create_embed(), view=view)


@collection_group.command(name="add")
async def collection_add(ctx, *, args: str):
    guild_id = ctx.guild.id
    user_id = ctx.author.id

    raw_items = [i.strip() for i in args.split(",") if i.strip()]
    mons_to_add = []

    for item in raw_items:
        if item.lower().startswith("all "):
            base = item[4:].strip().lower()
            if any(inv in base for inv in INVALID_EXCLUSIONS):
                continue
            # Simple simulation of bulk forms or specific base species
            mons_to_add.append(base)
        else:
            if not any(inv in item.lower() for inv in INVALID_EXCLUSIONS):
                mons_to_add.append(item)

    if not mons_to_add:
        return await ctx.send(embed=discord.Embed(description="# ❌ Error\nNo valid Pokémon provided to add.", color=discord.Color.red()))

    await dataset.add_to_collection(user_id, guild_id, mons_to_add)
    await ctx.send(embed=discord.Embed(description=f"# ✨️ Collection Updated\nSuccessfully added **{len(mons_to_add)}** entry/entries to your collection!", color=discord.Color.gold()))


@collection_group.command(name="remove")
async def collection_remove(ctx, *, args: str):
    guild_id = ctx.guild.id
    user_id = ctx.author.id
    raw_items = [i.strip() for i in args.split(",") if i.strip()]
    
    await dataset.remove_from_collection(user_id, guild_id, raw_items)
    await ctx.send(embed=discord.Embed(description="# ✨️ Collection Updated\nSuccessfully removed the specified Pokémon from your collection.", color=discord.Color.gold()))


# ==================== RESERVE COMMANDS (`A!r`) ====================
@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, member: discord.Member = None):
    if member:
        items = sorted(await dataset.get_user_reserves(ctx.guild.id, member.id))
        if not items:
            return await ctx.send(embed=discord.Embed(description=f"# ✨️ Reserves\n**{member.display_name}** has no reserved Pokémon.", color=discord.Color.gold()))
        
        def format_res(page_items, start):
            return "\n".join([f"**{start + i + 1}.** {mon.title()}" for i, mon in enumerate(page_items)])

        view = PaginationView(ctx, f"{member.display_name}'s Reserves", items, format_res)
        return await ctx.send(embed=view.create_embed(), view=view)
    
    # Default help/menu if no member specified
    embed = discord.Embed(
        description="# ✨️ Reserve Commands\n"
                    "• `A!r @user` - View user reserves\n"
                    "• `A!r list` - View all server reserves\n"
                    "• `A!r search <mon>` - Search reserve holders\n"
                    "• `A!r add <mons> [@user]` - Add reserves (Staff)\n"
                    "• `A!r remove <mons> [@user]` - Remove reserves (Staff)\n"
                    "• `A!r clear [@user]` - Clear reserves (Staff)\n"
                    "• `A!r e @mainuser` - Exchange reserves from reply (Staff)\n"
                    "• `A!r role <add/remove/list>` - Configure staff roles (Admin)",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="list")
async def reserve_list(ctx):
    all_res = await dataset.get_all_reserves(ctx.guild.id)
    if not all_res:
        return await ctx.send(embed=discord.Embed(description="# ✨️ Server Reserves\nThere are no reserves registered in this server.", color=discord.Color.gold()))

    items = sorted(all_res.items()) # list of (pokemon, [user_ids])

    def format_all_res(page_items, start):
        lines = []
        for i, (mon, uids) in enumerate(page_items):
            mentions = ", ".join([f"<@{uid}>" for uid in uids])
            lines.append(f"**{start + i + 1}.** {mon.title()} — {mentions}")
        return "\n".join(lines)

    view = PaginationView(ctx, "Server Reserves", items, format_all_res)
    await ctx.send(embed=view.create_embed(), view=view)


@reserve_group.command(name="search")
async def reserve_search(ctx, *, query: str):
    guild_id = ctx.guild.id
    mons = [m.strip().lower() for m in query.split(",") if m.strip()]
    
    lines = []
    for mon in mons:
        uids = await dataset.get_reserves_for_pokemon(guild_id, mon)
        if uids:
            mentions = ", ".join([f"<@{uid}>" for uid in uids])
            lines.append(f"**{mon.title()}** — {mentions}")
        else:
            lines.append(f"**{mon.title()}** — No reserves found")

    embed = discord.Embed(
        description=f"# 🔍 Reserve Search Results\n\n" + "\n".join(lines),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_group.command(name="add")
async def reserve_add(ctx, *, args: str):
    await can_manage_reserves_check(ctx)
    guild_id = ctx.guild.id

    # Check if a user is mentioned at the end
    parts = args.rsplit(" ", 1)
    target_user = ctx.author
    raw_mons_str = args

    if len(parts) == 2 and parts[1].startswith("<@") and parts[1].endswith(">"):
        try:
            member_id = int(re.sub(r'[^0-9]', '', parts[1]))
            member = ctx.guild.get_member(member_id)
            if member:
                target_user = member
                raw_mons_str = parts[0]
        except ValueError:
            pass

    raw_items = [i.strip() for i in raw_mons_str.split(",") if i.strip()]
    added_count = 0

    for item in raw_items:
        if item.lower().startswith("all "):
            base = item[4:].strip().lower()
            if not any(inv in base for inv in INVALID_EXCLUSIONS):
                await dataset.add_reserve(guild_id, base, target_user.id)
                added_count += 1
        else:
            if not any(inv in item.lower() for inv in INVALID_EXCLUSIONS):
                await dataset.add_reserve(guild_id, item, target_user.id)
                added_count += 1

    await ctx.send(embed=discord.Embed(description=f"# ✨️ Reserves Updated\nSuccessfully added **{added_count}** reserve(s) for **{target_user.display_name}**!", color=discord.Color.gold()))


@reserve_group.command(name="remove")
async def reserve_remove(ctx, *, args: str):
    await can_manage_reserves_check(ctx)
    guild_id = ctx.guild.id

    parts = args.rsplit(" ", 1)
    target_user = None
    raw_mons_str = args

    if len(parts) == 2 and parts[1].startswith("<@") and parts[1].endswith(">"):
        try:
            member_id = int(re.sub(r'[^0-9]', '', parts[1]))
            member = ctx.guild.get_member(member_id)
            if member:
                target_user = member
                raw_mons_str = parts[0]
        except ValueError:
            pass

    raw_items = [i.strip() for i in raw_mons_str.split(",") if i.strip()]

    if target_user:
        for mon in raw_items:
            await dataset.remove_reserve(guild_id, mon, target_user.id)
        await ctx.send(embed=discord.Embed(description=f"# ✨️ Reserves Updated\nRemoved specified reserves from **{target_user.display_name}**.", color=discord.Color.gold()))
    else:
        for mon in raw_items:
            await dataset.remove_global_reserve(guild_id, mon)
        await ctx.send(embed=discord.Embed(description="# ✨️ Reserves Updated\nRemoved specified Pokémon globally from all server reserves.", color=discord.Color.gold()))


@reserve_group.command(name="clear")
async def reserve_clear(ctx, member: discord.Member = None):
    await can_manage_reserves_check(ctx)
    guild_id = ctx.guild.id

    if member:
        await dataset.clear_user_reserves(guild_id, member.id)
        await ctx.send(embed=discord.Embed(description=f"# ✨️ Reserves Cleared\nCleared all reserves for **{member.display_name}**.", color=discord.Color.gold()))
    else:
        await dataset.clear_all_reserves(guild_id)
        await ctx.send(embed=discord.Embed(description="# ✨️ Reserves Cleared\nWiped the entire server reserve database.", color=discord.Color.gold()))


@reserve_group.command(name="e")
async def reserve_exchange(ctx, mainuser: discord.Member):
    await can_manage_reserves_check(ctx)
    guild_id = ctx.guild.id

    if not ctx.message.reference:
        return await ctx.send(embed=discord.Embed(description="# ❌ Error\nYou must reply to a message containing the exchange text format (`@user - mons`).", color=discord.Color.red()))

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except discord.NotFound:
        return await ctx.send(embed=discord.Embed(description="# ❌ Error\nCould not find the replied message.", color=discord.Color.red()))

    mainuser_reserves = await dataset.get_user_reserves(guild_id, mainuser.id)
    lines = replied_msg.content.splitlines()
    
    missing_mons = []
    transfers = [] # list of (target_user_id, [mons])

    for line in lines:
        if "-" not in line:
            continue
        user_part, mons_part = line.split("-", 1)
        user_match = re.search(r'<@!?([0-9]+)>', user_part)
        if not user_match:
            continue
        target_uid = int(user_match.group(1))
        target_mons = [m.strip().lower() for m in mons_part.split(",") if m.strip()]

        for m in target_mons:
            if m in mainuser_reserves:
                transfers.append((target_uid, m))
                mainuser_reserves.remove(m) # Prevent double spending within same batch
            else:
                missing_mons.append(m)

    if missing_mons:
        return await ctx.send(embed=discord.Embed(description=f"# ❌ Exchange Failed\nThe following Pokémon were missing from **{mainuser.display_name}**'s reserves:\n" + ", ".join([f"**{m.title()}**" for m in missing_mons]), color=discord.Color.red()))

    # Execute transfers: remove from mainuser reserves, add to target collection
    for target_uid, mon in transfers:
        await dataset.remove_reserve(guild_id, mon, mainuser.id)
        await dataset.add_to_collection(target_uid, guild_id, [mon])

    await ctx.send(embed=discord.Embed(description="# ✨️ Exchanged successfully", color=discord.Color.gold()))


# ==================== ROLE MANAGEMENT COMMAND (`A!r role`) ====================
@reserve_group.group(name="role", invoke_without_command=True)
async def reserve_role_group(ctx):
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send(embed=discord.Embed(description="# ❌ Permission Denied\nYou need Administrator permission to configure staff reserve roles.", color=discord.Color.red()))
    
    allowed_ids = await dataset.get_allowed_roles(ctx.guild.id)
    roles_str = ", ".join([f"<@&{rid}>" for rid in allowed_ids]) if allowed_ids else "No roles configured."
    
    embed = discord.Embed(
        description=f"# ✨️ Authorized Reserve Roles\n{roles_str}\n\n"
                    f"• `A!r role add @Role`\n"
                    f"• `A!r role remove @Role`",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="add")
async def reserve_role_add(ctx, role: discord.Role):
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send(embed=discord.Embed(description="# ❌ Permission Denied\nYou need Administrator permission.", color=discord.Color.red()))
    
    await dataset.add_allowed_role(ctx.guild.id, role.id)
    await ctx.send(embed=discord.Embed(description=f"# ✨️ Role Added\nSuccessfully added {role.mention} to authorized reserve staff roles.", color=discord.Color.gold()))


@reserve_role_group.command(name="remove")
async def reserve_role_remove(ctx, role: discord.Role):
    if not (ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id):
        return await ctx.send(embed=discord.Embed(description="# ❌ Permission Denied\nYou need Administrator permission.", color=discord.Color.red()))
    
    await dataset.remove_allowed_role(ctx.guild.id, role.id)
    await ctx.send(embed=discord.Embed(description=f"# ✨️ Role Removed\nSuccessfully removed {role.mention} from authorized reserve staff roles.", color=discord.Color.gold()))


# ==================== INCENSE CHANNEL SPAWN LISTENER ====================
@bot.event
async def on_message(message):
    if message.author.bot and message.author.id != bot.user.id:
        guild_id = message.guild.id if message.guild else None
        if not guild_id:
            await bot.process_commands(message)
            return

        # Check spawn message / embed text for Pokémon names
        content_to_check = message.content.lower()
        for embed in message.embeds:
            if embed.title:
                content_to_check += " " + embed.title.lower()
            if embed.description:
                content_to_check += " " + embed.description.lower()

        # Simple extraction / matching against server reserves & hunts
        all_reserves = await dataset.get_all_reserves(guild_id)
        
        pinged = False
        for pokemon, uids in all_reserves.items():
            if re.search(r'\b' + re.escape(pokemon) + r'\b', content_to_check):
                mentions = " ".join([f"<@{uid}>" for uid in uids])
                await message.channel.send(f"✨️ **Reserve Ping!** {mentions} — A reserved **{pokemon.title()}** has spawned!")
                pinged = True
                break  # Reserve priority suppresses shiny/collection pings

        if not pinged:
            # Check shiny hunts and collections if no reserve matched
            pass

    await bot.process_commands(message)


# Global Error Handler to prevent double embeds & cleanly display errors
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=discord.Embed(description="# ❌ Permission Denied\nYou do not have the required permissions or roles to run this command.", color=discord.Color.red()))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=discord.Embed(description="# ❌ Error\nMissing required arguments. Please check command usage.", color=discord.Color.red()))
    else:
        print(f"Ignored error: {error}")


bot.run(TOKEN)
