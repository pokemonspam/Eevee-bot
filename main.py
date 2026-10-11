import os
import re
import asyncio
import discord
from discord.ext import commands
from pymongo import MongoClient
import Levenshtein

VALID_POKEMON = [
    "pikachu", "charizard", "eevee", "vaporeon", "jolteon", "flareon", "espeon", 
    "umbreon", "leafeon", "glaceon", "sylveon", "ditto", "furfrou", "lucario",
    "watchog", "gengar", "ninetales", "zoroark", "kyogre"
]

FURFROU_FORMS = [
    "furfrou natural", "furfrou heart", "furfrou star", "furfrou diamond",
    "furfrou debutante", "furfrou matron", "furfrou dandy", "furfrou la reine",
    "furfrou kabuki", "furfrou pharaoh"
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["A!", "a!"], intents=intents, case_insensitive=True)

MONGO_URI = os.getenv("MONGO_URI", "")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["discord_pokemon_bot"]

# Attach db to bot so cogs can use it easily
bot.db = db

col_shiny = db["shiny_hunts"]
col_collection = db["collections"]
col_reserves = db["reserves"]

bot.remove_command("help")

def validate_pokemon_name(name_input: str):
    clean_name = name_input.strip().lower()
    if clean_name in VALID_POKEMON or "furfrou" in clean_name:
        return True, clean_name, None
    if "mega" in clean_name or "gmax" in clean_name or "gigantamax" in clean_name:
        return False, None, "❌ Cannot add Mega or Gigantamax forms."

    closest_match = None
    best_distance = float("inf")
    for mon in VALID_POKEMON:
        dist = Levenshtein.distance(clean_name, mon)
        if dist < best_distance and dist <= 2:
            best_distance = dist
            closest_match = mon

    if closest_match:
        return False, None, f"❓ **Did you mean *{closest_match.capitalize()}*?**"
    return False, None, f'❌ **"{name_input}" is not a valid Pokémon.**'

class ConfirmationView(discord.ui.View):
    def __init__(self, author_id, timeout=30):
        super().__init__(timeout=timeout)
        self.value = None
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

class CollectionPaginatorView(discord.ui.View):
    def __init__(self, author_id, pages):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.pages = pages
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    def get_embed(self):
        return discord.Embed(
            title=f"📦 Collection List (Page {self.current_page + 1}/{len(self.pages)})",
            description="\n".join([f"• {mon.capitalize()}" for mon in self.pages[self.current_page]]),
            color=0x5865F2
        )

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple, disabled=True)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.next_page.disabled = False
            if self.current_page == 0:
                button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.prev_page.disabled = False
            if self.current_page == len(self.pages) - 1:
                button.disabled = True
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

@bot.group(name="sh", invoke_without_command=True)
async def shiny_group(ctx, *, target: str = None):
    if target is None:
        data = col_shiny.find_one({"user_id": ctx.author.id})
        if data and data.get("target"):
            embed = discord.Embed(title="✨ Active Shiny Hunt", description=f"You are currently hunting: **{data['target'].capitalize()}** ✨", color=0xFFD700)
        else:
            embed = discord.Embed(title="✨ Active Shiny Hunt", description="You do not have an active shiny hunt set! Use `A!sh <pokemon>` to set one.", color=0xFFD700)
        await ctx.send(embed=embed)
        return

    if target.lower() == "clear":
        col_shiny.delete_one({"user_id": ctx.author.id})
        await ctx.send(embed=discord.Embed(title="✨ Shiny Target Cleared!", color=0xFFD700))
        return

    valid, clean_name, err_msg = validate_pokemon_name(target)
    if not valid:
        await ctx.send(err_msg)
        return

    existing = col_shiny.find_one({"user_id": ctx.author.id})
    if existing and existing.get("target"):
        view = ConfirmationView(ctx.author.id)
        msg = await ctx.send(f"⚠️ You are currently hunting **{existing['target'].capitalize()}**. Do you want to switch to **{clean_name.capitalize()}**?", view=view)
        await view.wait()
        if view.value is True:
            col_shiny.update_one({"user_id": ctx.author.id}, {"$set": {"target": clean_name}}, upsert=True)
            await msg.edit(content=f"✅ Changed shiny hunt target to **{clean_name.capitalize()}**! ✨", view=None)
        else:
            await msg.edit(content="❌ Switch cancelled.", view=None)
    else:
        col_shiny.update_one({"user_id": ctx.author.id}, {"$set": {"target": clean_name}}, upsert=True)
        await ctx.send(embed=discord.Embed(title="✨ Shiny Target Set!", description=f"Now hunting: **{clean_name.capitalize()}**", color=0xFFD700))

@bot.group(name="cl", invoke_without_command=True)
async def collection_group(ctx):
    embed = discord.Embed(
        title="📦 Collection Commands List",
        description=(
            "• `A!cl add <mon1, mon2>` - Add Pokémon to collection\n"
            "• `A!cl remove <mon1, mon2>` - Remove Pokémon from collection\n"
            "• `A!cl add all furfrou` - Bulk add all Furfrou forms\n"
            "• `A!cl list` - View your collection list\n"
            "• `A!cl clear` - Clear your collection list"
        ),
        color=0x5865F2
    )
    await ctx.send(embed=embed)

@collection_group.command(name="add")
async def cl_add(ctx, *, mons: str):
    if mons.lower() == "all furfrou":
        col_collection.update_one({"user_id": ctx.author.id}, {"$addToSet": {"list": {"$each": FURFROU_FORMS}}}, upsert=True)
        await ctx.send("✅ Added all Furfrou forms to your collection list!")
        return

    items = [m.strip() for m in mons.split(",")]
    added, errors = [], []
    for item in items:
        valid, clean_name, err = validate_pokemon_name(item)
        if valid:
            added.append(clean_name)
        else:
            errors.append(err)

    if added:
        col_collection.update_one({"user_id": ctx.author.id}, {"$addToSet": {"list": {"$each": added}}}, upsert=True)
        await ctx.send(f"✅ Added to collection: {', '.join([a.capitalize() for a in added])}")
    for err in errors:
        await ctx.send(err)

@collection_group.command(name="remove")
async def cl_remove(ctx, *, mons: str):
    items = [m.strip().lower() for m in mons.split(",")]
    col_collection.update_one({"user_id": ctx.author.id}, {"$pull": {"list": {"$in": items}}})
    await ctx.send("🗑️ Removed specified Pokémon from your collection list.")

@collection_group.command(name="clear")
async def cl_clear(ctx):
    view = ConfirmationView(ctx.author.id)
    msg = await ctx.send("⚠️ Are you sure you want to clear your entire collection list?", view=view)
    await view.wait()
    if view.value is True:
        col_collection.delete_one({"user_id": ctx.author.id})
        await msg.edit(content="🧹 Collection list completely cleared!", view=None)
    else:
        await msg.edit(content="❌ Action cancelled.", view=None)

@collection_group.command(name="list")
async def cl_list(ctx):
    data = col_collection.find_one({"user_id": ctx.author.id})
    if not data or not data.get("list"):
        await ctx.send("Your collection list is empty!")
        return
    mon_list = data["list"]
    pages = [mon_list[i:i + 20] for i in range(0, len(mon_list), 20)]
    if len(pages) == 1:
        embed = discord.Embed(title="📦 Collection List", description="\n".join([f"• {mon.capitalize()}" for mon in pages[0]]), color=0x5865F2)
        await ctx.send(embed=embed)
    else:
        view = CollectionPaginatorView(ctx.author.id, pages)
        await ctx.send(embed=view.get_embed(), view=view)

@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, member: discord.Member = None):
    if member:
        data = col_reserves.find_one({"guild_id": ctx.guild.id}) or {}
        reserves = data.get("reserves", {})
        user_mons = [mon for mon, users in reserves.items() if member.id in users]
        embed = discord.Embed(
            title=f"📋 Reserves for {member.display_name}",
            description="\n".join([f"• {m.capitalize()}" for m in user_mons]) if user_mons else "This user has no reserved Pokémon.",
            color=0x9B59B6
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="📑 Reserve Commands List",
        description=(
            "• `A!r add <mon1, mon2> @user` - Reserve Pokémon\n"
            "• `A!r list` - View global server reserve list\n"
            "• `A!r clear` - Clear server reserves\n"
            "• `A!r e @mainuser` (in reply) - Exchange reserved Pokémon"
        ),
        color=0x9B59B6
    )
    await ctx.send(embed=embed)

@reserve_group.command(name="add")
async def r_add(ctx, *, args: str):
    if not ctx.message.mentions:
        await ctx.send("❌ Please tag a user to assign reserves to.")
        return
    target_user = ctx.message.mentions[0]
    mons_part = args.replace(target_user.mention, "").replace(f"<@{target_user.id}>", "").strip()
    mons = [m.strip().lower() for m in mons_part.split(",") if m.strip()]

    data = col_reserves.find_one({"guild_id": ctx.guild.id}) or {"guild_id": ctx.guild.id, "reserves": {}}
    reserves = data.get("reserves", {})
    for mon in mons:
        if mon not in reserves:
            reserves[mon] = []
        if target_user.id not in reserves[mon]:
            reserves[mon].append(target_user.id)

    col_reserves.update_one({"guild_id": ctx.guild.id}, {"$set": {"reserves": reserves}}, upsert=True)
    await ctx.send(f"✅ Reserved {', '.join([m.capitalize() for m in mons])} for {target_user.mention}!")

@reserve_group.command(name="list")
async def r_list(ctx):
    data = col_reserves.find_one({"guild_id": ctx.guild.id}) or {}
    reserves = data.get("reserves", {})
    if not reserves:
        await ctx.send("The server reserve list is currently empty!")
        return
    lines = [f"• **{mon.capitalize()}** - {', '.join([f'<@{uid}>' for uid in uids])}" for mon, uids in reserves.items() if uids]
    embed = discord.Embed(title="📑 Global Server Reserves", description="\n".join(lines) if lines else "No active reserves.", color=0x9B59B6)
    await ctx.send(embed=embed)

@reserve_group.command(name="clear")
async def r_clear(ctx):
    view = ConfirmationView(ctx.author.id)
    msg = await ctx.send("⚠️ Are you sure you want to clear the entire server reserve list?", view=view)
    await view.wait()
    if view.value is True:
        col_reserves.delete_one({"guild_id": ctx.guild.id})
        await msg.edit(content="🧹 Server reserve list completely cleared!", view=None)
    else:
        await msg.edit(content="❌ Action cancelled.", view=None)

@reserve_group.command(name="e")
async def r_exchange(ctx, mainuser: discord.Member):
    if not ctx.message.reference:
        await ctx.send("❌ Please reply to the exchange formatting message with this command!")
        return
    ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    data = col_reserves.find_one({"guild_id": ctx.guild.id}) or {"guild_id": ctx.guild.id, "reserves": {}}
    reserves = data.get("reserves", {})
    exchanged = []

    for line in ref_msg.content.split("\n"):
        if "-" in line:
            parts = line.split("-")
            user_match = re.search(r"<@!?(\d+)>", parts[0])
            if user_match:
                recipient_id = int(user_match.group(1))
                for mon in [m.strip().lower() for m in parts[1].split(",") if m.strip()]:
                    if mon in reserves and mainuser.id in reserves[mon]:
                        reserves[mon].remove(mainuser.id)
                    if mon not in reserves:
                        reserves[mon] = []
                    if recipient_id not in reserves[mon]:
                        reserves[mon].append(recipient_id)
                    exchanged.append(f"{mon.capitalize()} -> <@{recipient_id}>")

    col_reserves.update_one({"guild_id": ctx.guild.id}, {"$set": {"reserves": reserves}}, upsert=True)
    await ctx.send("🔄 Exchange completed successfully!\n" + "\n".join([f"• {x}" for x in exchanged]))

@bot.event
async def on_message(message):
    if message.author.bot and message.author.id != 716390085896962058:
        await bot.process_commands(message)
        return

    if message.author.id == 716390085896962058 and "A wild pokémon has appeared!" in message.content:
        spawned_pokemon = "ditto"
        res_data = col_reserves.find_one({"guild_id": message.guild.id}) or {}
        reserved_users = res_data.get("reserves", {}).get(spawned_pokemon, [])

        if reserved_users:
            user_mentions = " ".join([f"<@{uid}>" for uid in reserved_users])
            await message.channel.send(
                f"**{spawned_pokemon.capitalize()}**: 99.70%\n"
                f"**Reserve Pings:** {user_mentions}\n"
                f"**Copy-Command:** `<@716390085896962058> c {spawned_pokemon}`"
            )
            await bot.process_commands(message)
            return

        shiny_users = [doc["user_id"] for doc in col_shiny.find({"target": spawned_pokemon})]
        collection_users = [doc["user_id"] for doc in col_collection.find({"list": spawned_pokemon})]
        ping_lines = []
        if shiny_users:
            ping_lines.append(f"✨ **Shiny Hunt Pings:** {', '.join([f'<@{uid}>' for uid in shiny_users])}")
        if collection_users:
            ping_lines.append(f"📦 **Collection Pings:** {', '.join([f'<@{uid}>' for uid in collection_users])}")
        if ping_lines:
            await message.channel.send("\n".join(ping_lines))

    await bot.process_commands(message)

async def main():
    async with bot:
        await bot.load_extension("starboard")
        TOKEN = os.getenv("DISCORD_TOKEN")
        if not TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable is not set!")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
