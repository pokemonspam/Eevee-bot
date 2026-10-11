import discord
from discord.ext import commands
import re

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Grabs db automatically from bot instance attached in main.py
        self.db = bot.db
        self.starboard_config = self.db["starboard_config"]

    def get_category_embed(self, category_key: str, data: dict, jump_url: str) -> discord.Embed:
        trainer_mention = data.get("trainer_mention", "Unknown Trainer")
        pokemon_name = data.get("pokemon", "Unknown Pokémon")
        gender = f" {data['gender']}" if data.get("gender") else ""
        form_info = f" ({data['form']})" if data.get("form") else ""
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
        if data.get("sprite_url"):
            embed.set_thumbnail(url=data["sprite_url"])
        embed.set_footer(text="Catch Detection System")
        return embed

    @commands.group(name="starboard", invoke_without_command=True)
    async def starboard_group(self, ctx):
        embed = discord.Embed(
            title="📋 Starboard Configuration Commands List",
            description=(
                "Link any category to any channel:\n"
                "```a!starboard set <category> <#channel>```\n\n"
                "**Available Categories:**\n"
                "• `shiny`, `rare`, `high_iv`, `low_iv`, `regional`, `gmax`\n\n"
                "**Check Current Mappings:**\n"
                "```a!starboard channel```"
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

        self.starboard_config.update_one(
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

    @starboard_group.command(name="channel", aliases=["channels"])
    async def show_channel_mappings(self, ctx):
        config = self.starboard_config.find_one({"guild_id": ctx.guild.id}) or {}
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

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != 716390085896962058:
            return

        if "Congratulations" not in message.content and "You caught a" not in message.content:
            return

        content = message.content
        config = self.starboard_config.find_one({"guild_id": message.guild.id}) or {}
        categories = config.get("categories", {})

        trainer_match = re.search(r"<@!?(\d+)>", content)
        trainer_mention = trainer_match.group(0) if trainer_match else "Trainer"

        sprite_url = None
        if message.embeds:
            embed_obj = message.embeds[0]
            if embed_obj.thumbnail:
                sprite_url = embed_obj.thumbnail.url
            elif embed_obj.image:
                sprite_url = embed_obj.image.url

        data = {
            "trainer_mention": trainer_mention,
            "pokemon": "Charizard",
            "gender": "♀",
            "form": "Shiny Form",
            "level": "12",
            "iv": "45.00",
            "chain": "506",
            "sprite_url": sprite_url
        }

        is_shiny = "✨" in content or "shiny" in content.lower()
        target_category = "shiny" if is_shiny else None

        if target_category and target_category in categories:
            target_channel_id = categories[target_category]
            target_channel = message.guild.get_channel(target_channel_id)

            if target_channel:
                embed = self.get_category_embed(target_category, data, message.jump_url)
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=message.jump_url))
                await target_channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Starboard(bot))
