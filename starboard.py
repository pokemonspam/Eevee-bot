import discord
from discord.ext import commands
import re

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.starboard_config = self.db["starboard_config"]

        # Your exact Pokétwo custom gender emojis
        self.MALE_EMOJI = "<:male:1566169579300851852>"
        self.FEMALE_EMOJI = "<:Female:1566169649249263627>"

        # 🦅 Rare Pokémon List
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
            "overqwil", "paldean wooper", "combat breed tauros", "blaze breed tauros", "aqua breed tauros",
            "star trim furfrou", "pharaoh trim furfrou", "kabuki trim furfrou", "la reine trim furfrou", 
            "matron trim furfrou", "dandy trim furfrou", "debutante trim furfrou", "heart trim furfrou", "diamond trim furfrou"
        }

    def is_rare(self, pokemon_name: str) -> bool:
        name_clean = pokemon_name.strip().lower()
        if name_clean in self.rare_pokemon:
            return True
        return any(family in name_clean for family in self.rare_families)

    def is_regional(self, pokemon_name: str) -> bool:
        name_clean = pokemon_name.strip().lower()
        return name_clean in self.regional_pokemon

    async def get_universal_sprite_url(self, guild_id: int, pokemon_name: str, form_str: str = "", is_shiny: bool = False) -> str:
        clean_name = pokemon_name.strip().lower()

        # 1. Check custom saved database sprites first
        config = await self.starboard_config.find_one({"guild_id": guild_id}) or {}
        custom_sprites = config.get("custom_sprites", {})
        if clean_name in custom_sprites:
            status = "shiny" if is_shiny else "normal"
            saved_url = custom_sprites[clean_name].get(status)
            if saved_url:
                return saved_url

        # 2. Standard Showdown & PokéAPI Fallback Logic
        combined = f"{form_str} {pokemon_name}".strip().lower()
        combined = combined.replace("é", "e")

        is_gmax = "gmax" in combined or "gigantamax" in combined or "eternamax" in combined

        if "rapid strike" in combined:
            slug = "urshifu-rapidstrike"
            pokeapi_id = 10227 if is_gmax else 10191
        elif "single strike" in combined:
            slug = "urshifu"
            pokeapi_id = 10226 if is_gmax else 892
        elif "toxtricity" in combined:
            pokeapi_id = 10219 if is_gmax else 849
            slug = "toxtricity" if is_gmax else ("toxtricity-lowkey" if "low key" in combined else "toxtricity")
        elif "eternatus" in combined:
            pokeapi_id = 10225 if is_gmax else 890
            slug = "eternatus-eternamax" if is_gmax else "eternatus"
        else:
            pokeapi_id = None
            clean = combined.replace("(gmax)", "").replace("gmax", "").replace("gigantamax", "").strip()
            region_map = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
            region_found = ""
            for reg_key, reg_val in region_map.items():
                if reg_key in clean:
                    region_found = f"-{reg_val}"
                    clean = clean.replace(reg_key, "").strip()

            noise_words = {"flower", "trim", "breed", "form", "forme", "mode", "partner", "size"}
            tokens = [t for t in clean.split() if t not in noise_words]
            
            if not tokens:
                slug = pokemon_name.lower().replace(" ", "")
            elif len(tokens) == 1:
                slug = tokens[0] + region_found
            else:
                slug = f"{tokens[-1]}-" + "-".join(tokens[:-1]) + region_found

        slug = slug.replace(".", "").replace("'", "").replace(":", "").replace(" ", "-")
        slug = re.sub(r"-+", "-", slug).strip("-")

        if is_gmax and not slug.endswith("-gmax") and not slug.endswith("-eternamax"):
            slug = slug + "-gmax"

        is_missing_gif = "urshifu" in slug and "gmax" in slug

        if not is_missing_gif:
            folder = "sprites/ani-shiny" if is_shiny else "sprites/ani"
            return f"https://play.pokemonshowdown.com/{folder}/{slug}.gif"

        if pokeapi_id:
            shiny_path = "shiny/" if is_shiny else ""
            return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{shiny_path}{pokeapi_id}.png"
        else:
            folder = "sprites/home-shiny" if is_shiny else "sprites/home"
            return f"https://play.pokemonshowdown.com/{folder}/{slug}.png"

    def parse_pokemon_data(self, content: str, default_author_mention: str) -> dict:
        trainer_match = re.search(r"<@!?(\d+)>", content)
        trainer_mention = trainer_match.group(0) if trainer_match else default_author_mention

        iv_match = re.search(r"(\d+(?:\.\d+)?)%", content)
        iv_str = f"{float(iv_match.group(1)):.2f}" if iv_match else "N/A"

        lvl_match = re.search(r"Level\s+(\d+)", content)
        level_str = lvl_match.group(1) if lvl_match else "N/A"

        pokemon_match = re.search(r"caught a Level \d+ (.*?)(?:!|\.|\()", content)
        raw_pokemon = pokemon_match.group(1).strip() if pokemon_match else "Pikachu"

        pokemon_name = re.sub(r'(?:<:\w+:\d+>|[:\s]*(?:unknown|:unknown:|\?|:female:|:male:|female|male|♀|♂))+$', '', raw_pokemon, flags=re.IGNORECASE).strip()
        pokemon_name = re.sub(r'<@!?\d+>', '', pokemon_name).strip(" :?<>")

        pokemon_name = re.sub(r'\s*\(?gmax\)?', '', pokemon_name, flags=re.IGNORECASE).strip()
        if "toxtricity" in pokemon_name.lower():
            pokemon_name = re.sub(r'^(low key|amped)\s+', '', pokemon_name, flags=re.IGNORECASE).strip()

        raw_gender_source = f"{content} {raw_pokemon}".lower()
        if any(tag in raw_gender_source for tag in ["female", "♀", "1566169649249263627", "1207734084210532483", ":female:", "1510903384180523028"]):
            gender = f" {self.FEMALE_EMOJI}"
        elif any(tag in raw_gender_source for tag in ["male", "♂", "1566169579300851852", "1207734081585152101", ":male:"]):
            gender = f" {self.MALE_EMOJI}"
        else:
            gender = " ?"

        form_match = re.search(r"\((.*?form.*?)\)", content, re.IGNORECASE)
        form_str = form_match.group(1).strip() if form_match else ""

        raw_lower = raw_pokemon.lower()
        if "low key" in raw_lower and not form_str:
            form_str = "Low Key"
        elif "amped" in raw_lower and not form_str:
            form_str = "Amped"
        elif "rapid strike" in raw_lower and not form_str:
            form_str = "Rapid Strike"
        elif "single strike" in raw_lower and not form_str:
            form_str = "Single Strike"

        if "gigantamax factor" in content.lower() or "gmax" in content.lower() or "gigantamax" in content.lower() or "1504098787658961028" in content:
            if "gmax" not in form_str.lower():
                form_str = f"{form_str} gmax".strip()

        chain_match = re.search(r"(?:chain:?\s*|streak:?\s*|streak reset[.!]\s*\(?\*\*?)(\d+)", content, re.IGNORECASE)
        chain_val = chain_match.group(1) if chain_match else None

        return {
            "trainer_mention": trainer_mention,
            "pokemon": pokemon_name,
            "gender": gender,
            "form": form_str,
            "level": level_str,
            "iv": iv_str,
            "chain": chain_val
        }

    async def get_category_embed(self, guild_id: int, category_key: str, data: dict, jump_url: str, all_detected_categories: list = None) -> discord.Embed:
        trainer_mention = data.get("trainer_mention", "Unknown Trainer")
        pokemon_name = data.get("pokemon", "Unknown Pokémon")
        gender = data.get("gender", "")
        form_str = data.get("form", "")

        if category_key.lower() == "gmax" and "gmax" not in form_str.lower():
            form_str = f"{form_str} gmax".strip()
        
        level = data.get("level", "N/A")
        iv = data.get("iv", "N/A")
        chain = data.get("chain", None)

        has_shiny = (all_detected_categories and "shiny" in all_detected_categories) or category_key.lower() == "shiny"
        has_gmax = (all_detected_categories and "gmax" in all_detected_categories) or ("gmax" in form_str.lower())
        is_shiny = (category_key.lower() == "shiny")
        is_gmax_cat = (category_key.lower() == "gmax")

        if has_shiny and has_gmax:
            theme = {"title": "✨⚔️ Shiny Gmax Catch Detected! ⚔️✨", "color": 0xFFD700}
        elif is_gmax_cat:
            theme = {"title": "⚔️ Gmax Catch Detected ⚔️", "color": 0xE74C3C}
        elif is_shiny:
            theme = {"title": "✨ Shiny Catch Detected! ✨", "color": 0xFFD700}
        else:
            category_themes = {
                "rare": {"title": "🦅 Rare Catch Detected 🦅", "color": 0x9B59B6},
                "regional": {"title": "🌍 Regional Catch Detected 🌍", "color": 0x1ABC9C},
                "high_iv": {"title": "📈 High IV Catch Detected 📈", "color": 0x2ECC71},
                "low_iv": {"title": "📉 Low IV Catch Detected 📉", "color": 0x3498DB}
            }
            theme = category_themes.get(category_key, {"title": "🌟 Starboard Catch Detected!", "color": 0x7289DA})
        
        embed = discord.Embed(title=theme["title"], color=theme["color"])

        description_lines = [
            f"**Trainer:** {trainer_mention}",
            f"**Pokémon:** {pokemon_name}{gender}",
            f"**Level:** {level}",
            f"**IV:** {iv}%"
        ]
        
        if chain is not None and chain != "":
            description_lines.append(f"**Chain:** {chain}")

        embed.description = "\n".join(description_lines)
        embed.timestamp = discord.utils.utcnow()
        
        sprite_is_shiny = is_shiny or has_shiny
        sprite_url = await self.get_universal_sprite_url(guild_id, pokemon_name, form_str, sprite_is_shiny)
        embed.set_thumbnail(url=sprite_url)
            
        return embed

    @commands.group(name="starboard", invoke_without_command=True, case_insensitive=True)
    async def starboard_group(self, ctx):
        embed = discord.Embed(
            title="📋 Starboard Configuration Commands List",
            description=(
                "**Link category to channel:**\n"
                "```E!starboard set <category> <#channel>```\n"
                "**Unlink/Clear a category:**\n"
                "```E!starboard clear <category>```\n\n"
                "**Custom Variant Sprite Saving:**\n"
                "• Reply to Dex card + `E!starsavenormal <mon name>`\n"
                "• Reply to Dex card + `E!starsaveshiny <mon name>`\n\n"
                "**Available Categories:**\n"
                "• `shiny`, `rare`, `high_iv`, `low_iv`, `regional`, `gmax`"
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

    @commands.command(name="starsavenormal")
    async def star_save_normal(self, ctx, *, pokemon_name: str):
        if not ctx.message.reference:
            await ctx.send("❌ Please **reply** to a Pokétwo Dex/Info message containing the image you want to save!")
            return

        try:
            target_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            image_url = None
            if target_msg.embeds:
                embed = target_msg.embeds[0]
                if embed.thumbnail and embed.thumbnail.url:
                    image_url = embed.thumbnail.url
                elif embed.image and embed.image.url:
                    image_url = embed.image.url

            if not image_url:
                await ctx.send("❌ Could not find an image/thumbnail in the replied message.")
                return

            clean_name = pokemon_name.strip().lower()
            await self.starboard_config.update_one(
                {"guild_id": ctx.guild.id},
                {"$set": {f"custom_sprites.{clean_name}.normal": image_url}},
                upsert=True
            )

            await ctx.send(f"✅ Successfully saved the **Normal** sprite for **{pokemon_name}**!")
        except Exception as e:
            await ctx.send(f"❌ Failed to save normal sprite: {e}")

    @commands.command(name="starsaveshiny")
    async def star_save_shiny(self, ctx, *, pokemon_name: str):
        if not ctx.message.reference:
            await ctx.send("❌ Please **reply** to a Pokétwo Dex/Info message containing the image you want to save!")
            return

        try:
            target_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            image_url = None
            if target_msg.embeds:
                embed = target_msg.embeds[0]
                if embed.thumbnail and embed.thumbnail.url:
                    image_url = embed.thumbnail.url
                elif embed.image and embed.image.url:
                    image_url = embed.image.url

            if not image_url:
                await ctx.send("❌ Could not find an image/thumbnail in the replied message.")
                return

            clean_name = pokemon_name.strip().lower()
            await self.starboard_config.update_one(
                {"guild_id": ctx.guild.id},
                {"$set": {f"custom_sprites.{clean_name}.shiny": image_url}},
                upsert=True
            )

            await ctx.send(f"✅ Successfully saved the **Shiny** sprite for **{pokemon_name}**!")
        except Exception as e:
            await ctx.send(f"❌ Failed to save shiny sprite: {e}")

    @commands.command(name="starboardtest", aliases=["sbtest"])
    async def starboard_test(self, ctx, category: str = None):
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
                parsed_data = self.parse_pokemon_data(target_msg.content, ctx.author.mention)
            except Exception as e:
                print(f"Starboard test parse note: {e}")

        if not parsed_data:
            parsed_data = {
                "trainer_mention": ctx.author.mention,
                "pokemon": "Peakychu",
                "gender": f" {self.MALE_EMOJI}",
                "form": "",
                "level": "50",
                "iv": "95.56",
                "chain": "1230"
            }

        target_categories = [category.lower()] if category else list(categories.keys())

        sent_count = 0
        for cat_key in target_categories:
            if cat_key in categories:
                ch_id = categories[cat_key]
                channel = ctx.guild.get_channel(ch_id)

                if channel:
                    dummy_cats = [category.lower()] if category else ["shiny"]
                    embed = await self.get_category_embed(ctx.guild.id, cat_key, parsed_data, jump_url, dummy_cats)
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=jump_url))
                    await channel.send(embed=embed, view=view)
                    sent_count += 1

        if sent_count > 0:
            await ctx.send(f"✅ **Starboard Test Sent!** Dispatched test embed(s) to configured channel(s).")
        else:
            await ctx.send("❌ Could not send test embeds. Make sure target channels exist and bot has permissions.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.id != 716390085896962058:
            return

        if "Congratulations" not in message.content and "You caught a" not in message.content:
            return

        content = message.content
        config = await self.starboard_config.find_one({"guild_id": message.guild.id}) or {}
        categories = config.get("categories", {})

        data = self.parse_pokemon_data(content, "Trainer")
        pokemon_name = data["pokemon"]
        try:
            iv_value = float(data["iv"])
        except ValueError:
            iv_value = None

        detected_categories = []

        if "These colors seem unusual..." in content or "✨" in content or "unusual" in content.lower():
            detected_categories.append("shiny")

        if "gigantamax factor" in content.lower() or "gmax" in content.lower() or "gigantamax" in content.lower() or "1504098787658961028" in content:
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

        final_categories_to_dispatch = []
        is_shiny_catch = "shiny" in detected_categories
        is_gmax_catch = "gmax" in detected_categories

        if is_shiny_catch:
            if "shiny" in categories:
                final_categories_to_dispatch.append("shiny")
        elif is_gmax_catch:
            if "gmax" in categories:
                final_categories_to_dispatch.append("gmax")
        else:
            if "high_iv" in detected_categories and "high_iv" in categories:
                final_categories_to_dispatch.append("high_iv")
            elif "low_iv" in detected_categories and "low_iv" in categories:
                final_categories_to_dispatch.append("low_iv")

        if "regional" in detected_categories and "regional" in categories:
            final_categories_to_dispatch.append("regional")
        if "rare" in detected_categories and "rare" in categories:
            final_categories_to_dispatch.append("rare")

        processed_channels = set()

        for category_key in final_categories_to_dispatch:
            if category_key in categories:
                target_channel_id = categories[category_key]
                if target_channel_id in processed_channels:
                    continue
                processed_channels.add(target_channel_id)

                target_channel = message.guild.get_channel(target_channel_id)
                if target_channel:
                    embed = await self.get_category_embed(message.guild.id, category_key, data, message.jump_url, detected_categories)
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=message.jump_url))
                    await target_channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Starboard(bot))
