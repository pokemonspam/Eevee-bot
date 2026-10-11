import os
import json
import discord
import re
from main import bot  # Hooks into your main active bot instance cleanly

CONFIG_FILE = "starboard_config.json"
starboard_channels = {
    "low_iv": None, "high_iv": None, "gmax": None,
    "shiny": None, "regional": None, "rare": None
}

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k in starboard_channels:
                starboard_channels[k] = data.get(k)
    except Exception as e:
        print(f"Config load error: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(starboard_channels, f, indent=4)
    except Exception as e:
        print(f"Config save error: {e}")
RARE_POKEMON_LIST = [
    "articuno", "zapdos", "moltres", "mewtwo", "mew", "raikou", "entei", "suicune", "lugia", "ho-oh", "celebi",
    "regirock", "regice", "registeel", "latias", "latios", "kyogre", "groudon", "rayquaza", "jirachi", "deoxys",
    "attack deoxys", "defense deoxys", "speed deoxys", "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran",
    "regigigas", "giratina", "cresselia", "phione", "manaphy", "darkrai", "shaymin", "victini", "cobalion",
    "terrakion", "virizion", "tornadus", "thundurus", "reshiram", "zekrom", "landorus", "kyurem", "keldeo",
    "meloetta", "pirouette meloetta", "genesect", "yveltal", "diancie", "hoopa", "volcanion", "type: null",
    "tapu koko", "tapu lele", "tapu bulu", "tapu fini", "cosmog", "cosmoem", "solgaleo", "lunala", "nihilego",
    "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord", "necrozma", "magearna",
    "marshadow", "poipole", "naganadel", "stakataka", "blacephalon", "zeraora", "meltan", "kubfu", "zarude",
    "dada zarude", "regieleki", "regidrago", "glastrier", "spectrier", "calyrex", "enamorus", "wo-chien",
    "chien-pao", "ting-lu", "chi-yu", "okidogi", "munkidori", "fezandipiti", "terapagos", "pecharunt",
    "zacian", "zamazenta", "eternatus", "urshifu", "rapid strike urshifu", "melmetal"
]

REGIONAL_POKEMON_LIST = [
    "alolan ninetales", "alolan vulpix", "alolan geodude", "alolan graveler", "alolan raticate", "alolan rattata",
    "alolan persian", "alolan meowth", "alolan exeggutor", "alolan dugtrio", "alolan diglett", "alolan grimer",
    "alolan golem", "alolan sandshrew", "alolan sandslash", "alolan marowak", "alolan raichu", "alolan muk",
    "galarian linoone", "galarian yamask", "galarian slowpoke", "galarian slowbro", "galarian slowking",
    "galarian farfetch'd", "galarian rapidash", "galarian ponyta", "galarian mr. mime", "galarian weezing",
    "galarian zigzagoon", "galarian corsola", "galarian meowth", "galarian darumaka", "galarian stunfisk",
    "galarian darmanitan", "galarian zen darmanitan", "obstagoon", "sirfetch'd", "cursola", "runerigus",
    "mr. rime", "perrserker", "hisuian growlithe", "hisuian arcanine", "hisuian electrode", "hisuian voltorb",
    "hisuian typhlosion", "hisuian lilligant", "hisuian samurott", "hisuian sneasel", "hisuian decidueye",
    "hisuian qwilfish", "hisuian braviary", "hisuian avalugg", "hisuian zoroark", "hisuian zorua", "hisuian sliggoo",
    "hisuian goodra", "basculegion", "sneasler", "overqwil", "paldean wooper", "combat breed tauros",
    "blaze breed tauros", "aqua breed tauros"
]

GMAX_POKEMON_LIST = [
    "venusaur", "eevee", "charizard", "blastoise", "butterfree", "pikachu", "meowth", "machamp", "gengar",
    "kingler", "lapras", "snorlax", "garbodor", "rillaboom", "cinderace", "inteleon", "corviknight", "orbeetle",
    "drednaw", "coalossal", "flapple", "appletun", "sandaconda", "amped toxtricity", "centiskorch", "hatterene",
    "grimmsnarl", "copperajah", "duraludon", "low key toxtricity", "alcremie", "vanilla cream berry sweet alcremie",
    "vanilla cream love sweet alcremie", "vanilla cream star sweet alcremie", "vanilla cream clover sweet alcremie",
    "vanilla cream flower sweet alcremie", "vanilla cream ribbon sweet alcremie", "eternatus", "urshifu",
    "rapid strike urshifu", "melmetal"
]
@bot.command(name="starboard")
@commands.has_permissions(manage_channels=True)
async def starboard_config_router(ctx, action: str = None, category: str = None, channel_arg: discord.TextChannel = None):
    try:
        valid_cats = ["low_iv", "high_iv", "gmax", "shiny", "regional", "rare"]
        
        # If user types just a!starboard or wrong parameters, output the help menu list
        if not action or action.lower() != "set" or not category or category.lower() not in valid_cats:
            embed = discord.Embed(title="📋 Starboard Configuration Commands List", color=discord.Color.red())
            embed.description = (
                "Link any category to any channel from anywhere using this syntax:\n"
                "`a!starboard set <category> <#channel_mention or channel_id>`\n\n"
                "**Available Categories:**\n"
                "• `shiny` - Shiny catches\n"
                "• `rare` - Legends, Mythicals, Paradox, Gmax Rares\n"
                "• `high_iv` - High IV catches (>= 90%)\n"
                "• `low_iv` - Low IV catches (< 10%)\n"
                "• `regional` - Regional variant catches\n"
                "• `gmax` - Standard Gigantamax catches\n\n"
                "**Examples:**\n"
                "`a!starboard set shiny #shiny-starboard`\n"
                "`a!starboard set rare 123456789012345678`"
            )
            return await ctx.send(embed=embed)
        
        target_channel = channel_arg if channel_arg else ctx.channel
        cat_clean = category.lower().strip()
        
        starboard_channels[cat_clean] = target_channel.id
        save_config()
        await ctx.send(f"✅ **Redirect Successful!** Catches for **{cat_clean}** will now automatically post into {target_channel.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Setup error: {e}")
async def process_starboard_message(message):
    content = message.content if message.content else ""
    combined_text = content
    if message.embeds:
        for emb in message.embeds:
            if emb.description: combined_text += "\n" + emb.description
            if emb.title: combined_text += "\n" + emb.title
            for field in emb.fields: combined_text += f"\n{field.name} {field.value}"

    clean_text = combined_text.lower().replace("é", "e")
    if "congratulations" in clean_text or "caught a" in clean_text:
        try:
            user_match = re.search(r'<@!?(\d+)>', combined_text)
            user_id = user_match.group(1) if user_match else "User"
            
            lvl_match = re.search(r'(?:level|lvl)\s*:?\s*(\d+)', combined_text, re.IGNORECASE)
            level = int(lvl_match.group(1)) if lvl_match else 1
            
            iv_match = re.search(r'iv\s*:?\s*([\d.]+)%', combined_text, re.IGNORECASE)
            iv_val = float(iv_match.group(1)) if iv_match else None
            
            name_text = ""
            name_match = re.search(r'caught a (?:shiny )?(?:gigantamax )?([a-zA-Z0-9\s:’.\-é♀♂]+?)(?:\!|\s|$)', combined_text, re.IGNORECASE)
            if name_match: name_text = name_match.group(1).strip()
            
            if not name_text or iv_val is None: return
            name_lower = name_text.lower().replace("é", "e")

            is_shiny = "✨" in combined_text or "shiny" in clean_text
            is_gmax = any(x in name_lower for x in GMAX_POKEMON_LIST) or "gigantamax" in clean_text or "gmax" in clean_text
            is_regional = any(x in name_lower for x in REGIONAL_POKEMON_LIST) or any(x in name_lower for x in ["alolan", "galarian", "hisuian", "paldean"])
            
            is_group_rare = any(grp in name_lower for grp in ["arceus", "silvally", "ogerpon", "koraidon", "miraidon", "xerneas", "zygarde"])
            is_rare = is_group_rare or any(x == name_lower or name_lower.endswith(f" {x}") for x in RARE_POKEMON_LIST)

            await route_to_boards(message, name_text, user_id, level, iv_val, is_shiny, is_gmax, is_regional, is_rare)
        except Exception as e:
            print(f"[STARBOARD SCAN ERROR] {e}")

def create_starboard_embed(title_text, emoji_icon, name, user_id, level, iv, color_hex):
    embed = discord.Embed(title=f"{emoji_icon} {title_text}", color=color_hex)
    embed.description = f"**Caught By:** <@{user_id}>\n**Pokémon:** {name}\n**Level:** {level}\n**IV:** {iv}%\n"
    return embed

class JumpButtonView(discord.ui.View):
    def __init__(self, jump_url):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=jump_url))

async def route_to_boards(orig_msg, name, user_id, level, iv, is_shiny, is_gmax, is_regional, is_rare):
    jump_url = orig_msg.jump_url
    guild = orig_msg.guild
    
    if iv < 10.0 and starboard_channels["low_iv"]:
        ch = guild.get_channel(starboard_channels["low_iv"])
        if ch: await ch.send(embed=create_starboard_embed("Low IV Catch Detected", "📉", name, user_id, level, iv, discord.Color.blue()), view=JumpButtonView(jump_url))

    if iv >= 90.0 and starboard_channels["high_iv"]:
        ch = guild.get_channel(starboard_channels["high_iv"])
        if ch: await ch.send(embed=create_starboard_embed("High IV Catch Detected", "📈", name, user_id, level, iv, discord.Color.green()), view=JumpButtonView(jump_url))

    if is_gmax and starboard_channels["gmax"]:
        ch = guild.get_channel(starboard_channels["gmax"])
        if ch: await ch.send(embed=create_starboard_embed("Gigantamax Catch Detected", "⚔️", name, user_id, level, iv, discord.Color.magenta()), view=JumpButtonView(jump_url))

    if is_shiny and starboard_channels["shiny"]:
        ch = guild.get_channel(starboard_channels["shiny"])
        if ch: await ch.send(embed=create_starboard_embed("Shiny Catch Detected", "✨", name, user_id, level, iv, discord.Color.gold()), view=JumpButtonView(jump_url))

    if is_regional and starboard_channels["regional"]:
        ch = guild.get_channel(starboard_channels["regional"])
        if ch: await ch.send(embed=create_starboard_embed("Regional Catch Detected", "🗺️", name, user_id, level, iv, discord.Color.teal()), view=JumpButtonView(jump_url))

    if is_rare and starboard_channels["rare"]:
        ch = guild.get_channel(starboard_channels["rare"])
        if ch: await ch.send(embed=create_starboard_embed("Rare Catch Detected", "🦅", name, user_id, level, iv, discord.Color.orange()), view=JumpButtonView(jump_url))
