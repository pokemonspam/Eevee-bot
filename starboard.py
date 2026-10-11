import discord

# Starboard channel ID mappings (stored dynamically in memory and MongoDB)
starboard_channels = {
    "shiny": None,
    "rare": None,
    "gmax": None,
    "regional": None,
    "high_iv": None,
    "low_iv": None
}

class StarboardManager:
    @staticmethod
    def set_channel(category: str, channel_id: int):
        """
        Updates the channel ID for a specific category and syncs with MongoDB.
        """
        category = category.lower().strip()
        if category in starboard_channels:
            starboard_channels[category] = channel_id
            
            # Import main inside the function to avoid circular import issues
            import main
            main.GlobalDatabase.save_starboard_config()

    @staticmethod
    async def process_starboard(message: discord.Message, category: str):
        """
        Processes and sends starboard notifications directly to Discord.
        """
        category = category.lower().strip()
        channel_id = starboard_channels.get(category)
        
        # If no channel is set for this category, do nothing
        if not channel_id:
            return
            
        target_channel = message.guild.get_channel(channel_id)
        if not target_channel:
            return

        # Category display title & color formatting
        category_titles = {
            "shiny": "✨ Shiny Starboard Alert",
            "rare": "🌟 Rare Pokémon Catch",
            "gmax": "💥 Gigantamax Catch",
            "regional": "🗺️ Regional Variant Catch",
            "high_iv": "⚡ High IV Catch (90%+)",
            "low_iv": "💀 Low IV Catch (0%)"
        }

        embed_title = category_titles.get(category, f"⭐ Starboard Alert: {category.upper()}")

        # Build notification embed
        embed = discord.Embed(
            title=embed_title,
            description=f"{message.content}\n\n🔗 [Jump to Message]({message.jump_url})",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Server: {message.guild.name} • Starboard Category: {category}")

        # Attach image if Pokétwo provided a sprite attachment
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        elif message.embeds and message.embeds[0].image:
            embed.set_image(url=message.embeds[0].image.url)

        # Send directly to the designated starboard channel
        await target_channel.send(embed=embed)
