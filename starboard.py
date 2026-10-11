import discord

# Starboard channel ID mappings (loaded dynamically from MongoDB)
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
            
            # Import main inside function to avoid circular imports
            import main
            main.GlobalDatabase.save_starboard_config()

    @staticmethod
    async def process_starboard(message: discord.Message, category: str):
        """
        Formats and sends starboard embeds directly to Discord.
        """
        category = category.lower().strip()
        channel_id = starboard_channels.get(category)
        
        # Skip if no starboard channel is set for this category
        if not channel_id:
            return
            
        target_channel = message.guild.get_channel(channel_id)
        if not target_channel:
            return

        # Titles and Embed Colors per category
        category_metadata = {
            "shiny": ("✨ Shiny Starboard Alert", discord.Color.gold()),
            "rare": ("🌟 Rare Pokémon Catch", discord.Color.purple()),
            "gmax": ("💥 Gigantamax Starboard Alert", discord.Color.red()),
            "regional": ("🗺️ Regional Form Catch", discord.Color.teal()),
            "high_iv": ("⚡ High IV Catch (90%+)", discord.Color.green()),
            "low_iv": ("💀 0% IV Catch", discord.Color.dark_gray())
        }

        title, color = category_metadata.get(
            category, 
            (f"⭐ Starboard Alert: {category.upper()}", discord.Color.blue())
        )

        # Build notification embed
        embed = discord.Embed(
            title=title,
            description=f"{message.content}\n\n🔗 [Jump to Message]({message.jump_url})",
            color=color
        )
        embed.set_footer(text=f"Server: {message.guild.name} • Category: {category.upper()}")

        # Attach Pokémon image if Pokétwo provided attachments or embeds
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        elif message.embeds and message.embeds[0].image:
            embed.set_image(url=message.embeds[0].image.url)

        # Post directly to the configured starboard channel
        await target_channel.send(embed=embed)
