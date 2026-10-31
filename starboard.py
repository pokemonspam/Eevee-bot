import discord
from discord.ext import commands
import re
from datetime import datetime

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.starboard_config = self.db["starboard_config"]

        # 🦅 Rare Pokémon List (Normalized lowercase for exact/partial matching)
        self.rare_pokemon = {
            "articuno", "zapdos", "moltres", "mewtwo", "mew", "raikou", "entei", "suicune", 
            "lugia", "ho-oh", "celebi", "regirock", "regice", "registeel", "latias", "latios", 
            "kyogre", "groudon", "rayquaza", "jirachi", "deoxys", "attack deoxys", "defense deoxys", 
            "speed deoxys", "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran", "regigigas", 
            "giratina", "cresselia", "phione", "manaphy", "darkrai", "shaymin", "victini", "cobalion", 
            "terrakion", "virizion", "tornadus", "thundurus", "reshiram", "zekrom", "landorus", 
            "kyurem", "keldeo", "meloetta", "pirouette meloetta", "genesect", "yveltal", "diancie", 
            "hoopa", "volcanion", "type: null", "tapu koko", "tapu lele", "tapu bulu", "tapu fini", 
            "cosmog", "cosmoem", "solgaleo", "lunala", "nihilego", "buzzwole", "pheromosa", "xurkitree", 
            "celesteela", "kartana", "guzzlord", "necrozma", "magearna", "marshadow", "poipole", 
            "naganadel", "stakataka", "blacephalon", "zeraora", "meltan", "kubfu", "zarude", "dada zarude", 
            "regieleki", "regidrago", "glastrier", "spectrier", "calyrex", "enamorus", "wo-chien", 
            "chien-pao", "ting-lu", "chi-yu", "okidogi", "munkidori", "fezandipiti", "terapagos", 
            "pecharunt", "zacian", "zamazenta", "eternatus", "melmetal", "galarian articuno", 
            "galarian moltres", "galarian zapdos"
        }

        # 🦅 Special "All <Species>" Rare Families
        self.rare_families = {
            "arceus", "ogerpon", "xerneas", "zygarde", "silvally", "urshifu", "koraidon", "miraidon"
        }

        # 🌍 Regional Pokémon List
        self.regional_pokemon = {
            "alolan ninetales", "alolan vulpix", "alolan geodude", "alolan graveler", "alolan raticate", 
            "alolan rattata", "alolan persian", "alolan meowth", "alolan exeggutor", "alolan dugtrio", 
            "alolan diglett", "alolan grimer", "alolan golem", "alolan sandshrew", "alolan sandslash", 
            "alolan marowak", "alolan raichu", "alolan muk", "galarian linoone", "galarian yamask", 
            "galarian slowpoke", "galarian slowbro", "galarian slowking", "galarian farfetch'd", 
            "galarian rapidash", "galarian ponyta", "galarian mr. mime", "galarian weezing", 
            "galarian zigzagoon", "galarian corsola", "galarian meowth", "galarian darumaka", 
            "galarian stunfisk", "galarian darmanitan", "galarian zen darmanitan", "obstagoon", 
            "sirfetch'd", "cursola", "runerigus", "mr. rime", "perrserker", "hisuian growlithe", 
            "hisuian arcanine", "hisuian electrode", "hisuian voltorb", "hisuian typhlosion", 
            "hisuian lilligant", "hisuian samurott", "hisuian sneasel", "hisuian decidueye", 
            "hisuian qwilfish", "hisuian braviary", "hisuian avalugg", "hisuian zoroark", 
            "hisuian zorua", "hisuian sliggoo", "hisuian goodra", "basculegion", "sneasler", 
            "overqwil", "paldean wooper", "combat breed tauros", "blaze breed tauros", "aqua breed tauros"
        }

    def is_rare(self, pokemon_name: str) -> bool:
        name_clean = pokemon_name.strip().lower()
        if name_clean in self.rare_pokemon:
            return True
        return any(family in name_clean for family in self.rare_families)

    def is_regional(self, pokemon_name: str) -> bool:
        name_clean = pokemon_name.strip().lower()
        return name_clean in self.regional_pokemon

    def build_external_sprite_url(self, pokemon_name: str, form_str: str = "", is_shiny: bool = False) -> str:
        """Constructs an online sprite URL from Showdown's asset CDN, handling forms and shinies."""
        full_name = f"{form_str} {pokemon_name}".strip().lower() if form_str else pokemon_name.lower()
        
        # Clean up formatting for URL compatibility
        clean = full_name.replace("alolan", "alola").replace("galarian", "galar").replace("hisuian", "hisui").replace("paldean", "paldea")
        clean = clean.replace("partner", "").replace("speed", "speed").replace("attack", "attack").replace("defense", "defense")
        clean = re.sub(r"[^a-z0-9\-]", "", clean.replace(" ", "-"))
        clean = re.sub(r"-+", "-", clean).strip("-")

        folder = "shiny" if is_shiny else "dex"
        return f"https://play.pokemonshowdown.com/sprites/{folder}/{clean}.png"

    def get_category_embed(self, category_key: str, data: dict, jump_url: str) -> discord.Embed:
        trainer_mention = data.get("trainer_mention", "Unknown Trainer")
        
        pokemon_name = data.get("pokemon", "Unknown Pokémon")
        pokemon_name = re.sub(r'(?:[:\s]*(?:male|female|unknown|♀|♂|\?|:male:|<:male:\d+>|:female:|<:female:\d+>|<:Female:\d+>))+$', '', pokemon_name, flags=re.IGNORECASE).strip()
        
        raw_gender = str(data.get("gender", "")).lower()
        if "♀" in raw_gender or "female" in raw_gender:
            gender = " ♀"
        elif "♂" in raw_gender or "male" in raw_gender:
            gender = " ♂"
        else:
            gender = "" # Left completely blank for genderless Pokémon

        form_str = data.get("form", "")
        form_info = f" ({form_str})" if form_str else ""
        level = data.get("level", "N/A")
        iv = data.get("iv", "N/A")
        chain = data.get("chain", None)

        category_themes = {
            "shiny": {"title": "✨ Shiny Catch Detected! ✨", "color": 0xFFD700},
            "rare": {"title": "🦅 Rare Catch Detected 🦅", "color": 0x9B59B6},
            "regional": {"title": "🌍 Regional Catch Detected 🌍", "color": 0x1ABC9C},
            "gmax": {"title": "⚔️ Gmax Catch Detected ⚔️", "color": 0xE74C3C},
            "high_iv": {"title": "📈 High IV Catch Detected 📈", "color": 0x2ECC71},
            "low_iv": {"title": "📉 Low IV Catch Detected 📉", "color": 0x3498DB}
        }

        theme = category_themes.get(category_key, {"title": "🌟 Starboard Catch Detected!", "color": 0x7289DA})
        
        embed = discord.Embed(title=theme["title"], color=theme["color"])

        description_lines = [
            f"**Trainer:** {trainer_mention}",
            f"**Pokémon:** {pokemon_name}{gender}{form_info}",
            f"**Level:** {level}",
            f"**IV:** {iv}%"
        ]
        if chain is not None:
            description_lines.append(f"**Chain:** {chain}")

        embed.description = "\n".join(description_lines)
        
        now = datetime.utcnow()
        formatted_date = now.strftime("%d/%m/%Y at %H:%M")
        embed.set_footer(text=formatted_date)
        
        # Pull sprite from external web host
        is_shiny = (category_key == "shiny")
        sprite_url = self.build_external_sprite_url(pokemon_name, form_str, is_shiny)
        embed.set_thumbnail(url=sprite_url)
            
        return embed

    @commands.group(name="starboard", invoke_without_command=True, case_insensitive=True)
    async def starboard_group(self, ctx):
        embed = discord.Embed(
            title="📋 Starboard Configuration Commands List",
            description=(
                "**Link category to channel:**\n"
                "```E!starboard set <category> <#channel> or e!starboard set <category> <#channel>```\n"
                "**Unlink/Clear a category:**\n"
                "```E!starboard clear <category> or e!starboard clear <category>```\n\n"
                "**Available Categories:**\n"
                "• `shiny`, `rare`, `high_iv`, `low_iv`, `regional`, `gmax`\n\n"
                "**Check Current Mappings:**\n"
                "```E!starboard channel or e!starboard channel```\n\n"
                "**Test Starboard Embed:**\n"
                "```E!starboardtest [category] (reply to a caught message)```"
            ),
            color=0x2B2D31
        )
        await ctx.send(embed=embed)

    @starboard_group.command(name="set")
    async def set_category_channel(self, ctx, category: str, channel: discord.TextChannel):
        valid_categories = ["shiny", "rare", "high_iv", "low_iv", "regional", "gmax"]
        cat_clean = category.lower()

        if cat_clean not in valid_categories:
            await ctx.send(f"❌ **Invalid Category.** Valid options are: `{', '.join(valid_categories)}`")
            return

        await self.starboard_config.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {f"categories.{cat_clean}": channel.id}},
            upsert=True
        )

        embed = discord.Embed(
            title="✅ Starboard Channel Configured",
            description=f"Successfully linked **`{cat_clean}`** catches to {channel.mention}!",
            color=0x57F287
        )
        await ctx.send(embed=embed)

    @starboard_group.command(name="clear", aliases=["remove", "unset", "delete"])
    async def clear_category_channel(self, ctx, category: str):
        valid_categories = ["shiny", "rare", "high_iv", "low_iv", "regional", "gmax"]
        cat_clean = category.lower()

        if cat_clean not in valid_categories:
            await ctx.send(f"❌ **Invalid Category.** Valid options are: `{', '.join(valid_categories)}`")
            return

        await self.starboard_config.update_one(
            {"guild_id": ctx.guild.id},
            {"$unset": {f"categories.{cat_clean}": ""}}
        )

        embed = discord.Embed(
            title="🗑️ Starboard Category Cleared",
            description=f"Successfully unlinked and removed **`{cat_clean}`**!",
            color=0xED4245
        )
        await ctx.send(embed=embed)

    @starboard_group.command(name="channel", aliases=["channels"])
    async def show_channel_mappings(self, ctx):
        config = await self.starboard_config.find_one({"guild_id": ctx.guild.id}) or {}
        categories = config.get("categories", {})

        category_labels = {
            "shiny": "✨ Shiny",
            "rare": "🦅 Rare",
            "high_iv": "📈 High IV",
            "low_iv": "📉 Low IV",
            "regional": "🌍 Regional",
            "gmax": "⚔️ Gmax"
        }

        mappings_text = []
        for cat_key, label in category_labels.items():
            ch_id = categories.get(cat_key)
            if ch_id:
                channel = ctx.guild.get_channel(ch_id)
                ch_text = channel.mention if channel else f"<#{ch_id}> (deleted)"
            else:
                ch_text = "`None`"
            mappings_text.append(f"• **{label}:** {ch_text}")

        embed = discord.Embed(
            title="📌 Starboard Channel Mappings",
            description="\n".join(mappings_text),
            color=0x5865F2
        )
        await ctx.send(embed=embed)

    @commands.command(name="starboardtest", aliases=["sbtest"])
    async def starboard_test(self, ctx, category: str = None):
        """Tests the starboard embed by parsing a replied message or creating sample data."""
        config = await self.starboard_config.find_one({"guild_id": ctx.guild.id}) or {}
        categories = config.get("categories", {})

        if not categories:
            await ctx.send("❌ No starboard channels configured yet! Use `E!starboard set <category> <#channel>` first.")
            return

        valid_categories = ["shiny", "rare", "high_iv", "low_iv", "regional", "gmax"]
        if category and category.lower() not in valid_categories:
            await ctx.send(f"❌ **Invalid Category.** Valid options are: `{', '.join(valid_categories)}`")
            return

        parsed_data = None
        jump_url = ctx.message.jump_url

        if ctx.message.reference:
            try:
                target_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                jump_url = target_msg.jump_url
                content = target_msg.content

                trainer_match = re.search(r"<@!?(\d+)>", content)
                trainer_mention = trainer_match.group(0) if trainer_match else ctx.author.mention

                iv_match = re.search(r"(\d+(?:\.\d+)?)%", content)
                iv_str = f"{float(iv_match.group(1)):.2f}" if iv_match else "85.50"

                lvl_match = re.search(r"Level\s+(\d+)", content)
                level_str = lvl_match.group(1) if lvl_match else "30"

                pokemon_match = re.search(r"caught a Level \d+ (.*?)(?:!|\.|\()", content)
                pokemon_name = pokemon_match.group(1).strip() if pokemon_match else "Pikachu"

                gender_match = re.search(r"([♀♂])", content)
                gender_str = gender_match.group(1) if gender_match else ""

                form_match = re.search(r"\((.*?form.*?)\)", content, re.IGNORECASE)
                form_str = form_match.group(1).strip() if form_match else ""

                chain_match = re.search(r"chain:?\s*(\d+)", content, re.IGNORECASE)
                chain_val = chain_match.group(1) if chain_match else None

                parsed_data = {
                    "trainer_mention": trainer_mention,
                    "pokemon": pokemon_name,
                    "gender": gender_str,
                    "form": form_str,
                    "level": level_str,
                    "iv": iv_str,
                    "chain": chain_val
                }
            except Exception as e:
                print(f"Starboard test parse note: {e}")

        if not parsed_data:
            parsed_data = {
                "trainer_mention": ctx.author.mention,
                "pokemon": "Pikachu",
                "gender": "♂",
                "form": "",
                "level": "50",
                "iv": "95.56",
                "chain": "102"
            }

        target_categories = [category.lower()] if category else list(categories.keys())

        sent_count = 0
        for cat_key in target_categories:
            if cat_key in categories:
                ch_id = categories[cat_key]
                channel = ctx.guild.get_channel(ch_id)

                if channel:
                    embed = self.get_category_embed(cat_key, parsed_data, jump_url)
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=jump_url))
                    await channel.send(embed=embed, view=view)
                    sent_count += 1

        if sent_count > 0:
            await ctx.send(f"✅ **Starboard Test Sent!** Dispatched test embed(s) to configured channel(s).")
        else:
            await ctx.send("❌ Could not send test embeds. Make sure the target channels still exist and the bot has permission to speak there.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.id != 716390085896962058:
            return

        if "Congratulations" not in message.content and "You caught a" not in message.content:
            return

        content = message.content
        config = await self.starboard_config.find_one({"guild_id": message.guild.id}) or {}
        categories = config.get("categories", {})

        trainer_match = re.search(r"<@!?(\d+)>", content)
        trainer_mention = trainer_match.group(0) if trainer_match else "Trainer"

        iv_value = None
        iv_match = re.search(r"(\d+(?:\.\d+)?)%", content)
        if iv_match:
            try:
                iv_value = float(iv_match.group(1))
            except ValueError:
                iv_value = None

        lvl_match = re.search(r"Level\s+(\d+)", content)
        level_str = lvl_match.group(1) if lvl_match else "N/A"

        pokemon_match = re.search(r"caught a Level \d+ (.*?)(?:!|\.|\()", content)
        pokemon_name = pokemon_match.group(1).strip() if pokemon_match else "Unknown Pokémon"

        gender_match = re.search(r"([♀♂])", content)
        gender_str = gender_match.group(1) if gender_match else ""

        form_match = re.search(r"\((.*?form.*?)\)", content, re.IGNORECASE)
        form_str = form_match.group(1).strip() if form_match else ""

        chain_match = re.search(r"chain:?\s*(\d+)", content, re.IGNORECASE)
        chain_val = chain_match.group(1) if chain_match else None

        data = {
            "trainer_mention": trainer_mention,
            "pokemon": pokemon_name,
            "gender": gender_str,
            "form": form_str,
            "level": level_str,
            "iv": f"{iv_value:.2f}" if iv_value is not None else "N/A",
            "chain": chain_val
        }

        detected_categories = []

        if "These colors seem unusual..." in content or "✨" in content:
            detected_categories.append("shiny")

        if "Woah! It seems that this pokémon has the Gigantamax Factor..." in content:
            detected_categories.append("gmax")

        if iv_value is not None:
            if iv_value >= 90.0:
                detected_categories.append("high_iv")
            elif iv_value < 10.0:
                detected_categories.append("low_iv")

        if self.is_regional(pokemon_name):
            detected_categories.append("regional")

        if self.is_rare(pokemon_name):
            detected_categories.append("rare")

        for category_key in detected_categories:
            if category_key in categories:
                target_channel_id = categories[category_key]
                target_channel = message.guild.get_channel(target_channel_id)

                if target_channel:
                    embed = self.get_category_embed(category_key, data, message.jump_url)
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=message.jump_url))
                    await target_channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Starboard(bot))
