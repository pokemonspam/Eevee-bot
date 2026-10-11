import os
import re
import discord
from discord.ext import commands
import pymongo
import starboard

# ==========================================
# 1. MONGODB ATLAS CLOUD CONNECTION
# ==========================================
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = None

if MONGO_URI:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI)
        db = mongo_client["pokebot_db"]
        
        collections_col = db["collections"]
        hunts_col = db["shiny_hunts"]
        reserves_col = db["reserves"]
        starboard_col = db["starboard_config"]
        print("[DATABASE] Successfully connected to MongoDB Atlas Cloud!")
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to connect to MongoDB: {e}")
        mongo_client = None
else:
    print("[WARNING] MONGO_URI environment variable not set.")

# ==========================================
# 2. GLOBAL DATABASE HELPER CLASS
# ==========================================
class GlobalDatabase:
    @staticmethod
    def get_collection(user_id: str):
        if mongo_client is not None:
            doc = collections_col.find_one({"user_id": str(user_id)})
            return doc.get("pokemon", []) if doc else []
        return []

    @staticmethod
    def save_collection(user_id: str, pokemon_list: list):
        if mongo_client is not None:
            collections_col.update_one(
                {"user_id": str(user_id)},
                {"$set": {"pokemon": pokemon_list}},
                upsert=True
            )

    @staticmethod
    def get_shiny_hunt(user_id: str):
        if mongo_client is not None:
            doc = hunts_col.find_one({"user_id": str(user_id)})
            return doc.get("target") if doc else None
        return None

    @staticmethod
    def set_shiny_hunt(user_id: str, target_mon: str):
        if mongo_client is not None:
            hunts_col.update_one(
                {"user_id": str(user_id)},
                {"$set": {"target": target_mon}},
                upsert=True
            )

    @staticmethod
    def get_reserve(user_id: str):
        if mongo_client is not None:
            doc = reserves_col.find_one({"user_id": str(user_id)})
            return doc.get("reserved", []) if doc else []
        return []

    @staticmethod
    def save_reserve(user_id: str, reserve_list: list):
        if mongo_client is not None:
            reserves_col.update_one(
                {"user_id": str(user_id)},
                {"$set": {"reserved": reserve_list}},
                upsert=True
            )

    @staticmethod
    def load_starboard_config():
        if mongo_client is not None:
            doc = starboard_col.find_one({"_id": "config"})
            if doc:
                for category in starboard.starboard_channels:
                    if category in doc:
                        starboard.starboard_channels[category] = doc.get(category)

    @staticmethod
    def save_starboard_config():
        if mongo_client is not None:
            data = starboard.starboard_channels.copy()
            data["_id"] = "config"
            starboard_col.replace_one({"_id": "config"}, data, upsert=True)

# ==========================================
# 3. BOT INITIALIZATION
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"[BOT] Logged in as {bot.user} (ID: {bot.user.id})")
    GlobalDatabase.load_starboard_config()
    print("[STARBOARD] Saved channel configurations loaded from MongoDB.")

# ==========================================
# 4. COMMANDS
# ==========================================
@bot.command(name="hunt")
async def set_hunt(ctx, *, pokemon_name: str):
    user_id = str(ctx.author.id)
    target = pokemon_name.strip().title()
    GlobalDatabase.set_shiny_hunt(user_id, target)
    await ctx.send(f"✨ **{ctx.author.display_name}**, your shiny hunt target is now set to **{target}**!")

@bot.command(name="myhunt")
async def my_hunt(ctx):
    user_id = str(ctx.author.id)
    target = GlobalDatabase.get_shiny_hunt(user_id)
    if target:
        await ctx.send(f"🎯 **{ctx.author.display_name}**, you are currently hunting: **{target}**")
    else:
        await ctx.send("❌ You don't have an active shiny hunt target set! Use `!hunt <pokemon>`.")

@bot.command(name="addcol")
async def add_collection(ctx, *, pokemon_name: str):
    user_id = str(ctx.author.id)
    pokemon = pokemon_name.strip().title()
    collection = GlobalDatabase.get_collection(user_id)
    if pokemon not in collection:
        collection.append(pokemon)
        GlobalDatabase.save_collection(user_id, collection)
        await ctx.send(f"📦 Added **{pokemon}** to your collection!")
    else:
        await ctx.send(f"⚠️ **{pokemon}** is already in your collection!")

@bot.command(name="mycol")
async def view_collection(ctx):
    user_id = str(ctx.author.id)
    collection = GlobalDatabase.get_collection(user_id)
    if collection:
        await ctx.send(f"📋 **{ctx.author.display_name}'s Collection:**\n{', '.join(collection)}")
    else:
        await ctx.send("📂 Your collection is empty!")

@bot.command(name="reserve")
async def reserve_pokemon(ctx, *, pokemon_name: str):
    user_id = str(ctx.author.id)
    pokemon = pokemon_name.strip().title()
    reserves = GlobalDatabase.get_reserve(user_id)
    if pokemon not in reserves:
        reserves.append(pokemon)
        GlobalDatabase.save_reserve(user_id, reserves)
        await ctx.send(f"📌 Reserved **{pokemon}** for your list!")
    else:
        await ctx.send(f"⚠️ **{pokemon}** is already in your reserve list!")

@bot.command(name="myreserves")
async def view_reserves(ctx):
    user_id = str(ctx.author.id)
    reserves = GlobalDatabase.get_reserve(user_id)
    if reserves:
        await ctx.send(f"📝 **{ctx.author.display_name}'s Reserved Pokémon:**\n{', '.join(reserves)}")
    else:
        await ctx.send("📂 Your reserve list is empty!")

@bot.command(name="setstarboard")
@commands.has_permissions(administrator=True)
async def set_starboard(ctx, category: str, channel: discord.TextChannel):
    category = category.lower().strip()
    if category in starboard.starboard_channels:
        starboard.StarboardManager.set_channel(category, channel.id)
        await ctx.send(f"✅ Set {channel.mention} as the starboard channel for **{category}**!")
    else:
        valid_cats = ", ".join(starboard.starboard_channels.keys())
        await ctx.send(f"❌ Invalid category! Choose from: `{valid_cats}`")

# ==========================================
# 5. AUTOMATIC POKÉTWO CATCH LISTENER & ROUTER
# ==========================================
POKETWO_ID = 716390085896962058  # Pokétwo Discord ID

@bot.event
async def on_message(message):
    if message.author.bot and message.author.id != POKETWO_ID:
        await bot.process_commands(message)
        return

    if message.author.id == POKETWO_ID:
        content = message.content
        
        # Check if it's a catch confirmation message
        if "Congratulations" in content and "caught a" in content:
            user_match = re.search(r"<@!?(\d+)>", content)
            mon_match = re.search(r"caught a (?:level \d+ )?([✨\w\s-]+)!", content, re.IGNORECASE)
            
            if user_match and mon_match:
                catcher_id = user_match.group(1)
                caught_mon = mon_match.group(1).strip().lower()

                # 1. SHINY CHECK
                if "✨" in content or "shiny" in caught_mon:
                    await starboard.StarboardManager.process_starboard(message, "shiny")

                # 2. REGIONAL FORM CHECK (Galarian, Alolan, Hisuian, Paldean)
                regional_keywords = ["galarian", "alolan", "hisuian", "paldean"]
                if any(region in caught_mon for region in regional_keywords):
                    await starboard.StarboardManager.process_starboard(message, "regional")

                # 3. GIGANTAMAX CHECK
                if "gigantamax" in caught_mon or "g-max" in caught_mon:
                    await starboard.StarboardManager.process_starboard(message, "gmax")

                # 4. SHINY HUNT TARGET MATCH
                hunt_target = GlobalDatabase.get_shiny_hunt(catcher_id)
                if hunt_target and hunt_target.lower() in caught_mon:
                    await message.channel.send(f"🎉 <@{catcher_id}> caught their target shiny: **{caught_mon.title()}**!")

        # 5. IV CHECK (Parsing Pokétwo Embeds for IV Stats if applicable)
        if message.embeds:
            for embed in message.embeds:
                embed_text = (embed.description or "") + (embed.title or "")
                # Look for IV percentages (e.g., "95.56%" or "100%")
                iv_match = re.search(r"(\d+(?:\.\d+)?)\s*%", embed_text)
                if iv_match:
                    iv_value = float(iv_match.group(1))
                    if iv_value >= 90.0:
                        await starboard.StarboardManager.process_starboard(message, "high_iv")
                    elif iv_value == 0.0:
                        await starboard.StarboardManager.process_starboard(message, "low_iv")

    await bot.process_commands(message)

# ==========================================
# 6. BOT EXECUTION
# ==========================================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("[ERROR] DISCORD_TOKEN environment variable is missing!")
