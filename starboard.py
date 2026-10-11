import discord
import re

# In-memory runtime registry managed safely by the core engine process
starboard_channels = {
    "low_iv": None, "high_iv": None, "gmax": None,
    "shiny": None, "regional": None, "rare": None
}

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

def create_starboard_embed(title_text, emoji_icon, name, user_id, level, iv, chain, color_hex, sprite_url=None):
    embed = discord.Embed(title=f"{emoji_icon} {title_text}! {emoji_icon}", color=color_hex)
    
    desc = (
        f"**Trainer:** <@{user_id}>\n"
        f"**Pokémon:** {name}\n"
        f"**Level:** {level}\n"
        f"**IV:** {iv:.2f}%\n"
    )
    if chain is not None:
        desc += f"**Chain:** {chain}\n"
        
    embed.description = desc
    embed.set_footer(text="Catch Detection System")
    
    if sprite_url:
        embed.set_thumbnail(url=sprite_url)
        
    return embed

class JumpButtonView(discord.ui.View):
    def __init__(self, jump_url):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Jump to Catch 🔗", url=jump_url))

async def process_starboard_message(message):
    content = message.content if message.content else ""
    combined_text = content
    sprite_url = None

    if message.embeds:
        for emb in message.embeds:
            if emb.description: combined_text += "\n" + emb.description
            if emb.title: combined_text += "\n" + emb.title
            for field in emb.fields: combined_text += f"\n{field.name} {field.value}"
            
            # Scrape Pokémon sprite attachment from original message
            if emb.image and emb.image.url:
                sprite_url = emb.image.url
            elif emb.thumbnail and emb.thumbnail.url:
                sprite_url = emb.thumbnail.url

    clean_text = combined_text.lower().replace("é", "e")
    if "congratulations" in clean_text or "caught a" in clean_text:
        try:
            user_match = re.search(r'<@!?(\d+)>', combined_text)
            user_id = user_match.group(1) if user_match else "User"
            
            lvl_match = re.search(r'(?:level|lvl)\s*:?\s*(\d+)', combined_text, re.IGNORECASE)
            level = int(lvl_match.group(1)) if lvl_match else 1
            
            iv_match = re.search(r'iv\s*:?\s*([\d.]+)%', combined_text, re.IGNORECASE)
            iv_val = float(iv_match.group(1)) if iv_match else None
            
            chain_match = re.search(r'chain\s*:?\s*(\d+)', combined_text, re.IGNORECASE)
            chain_val = int(chain_match.group(1)) if chain_match else None
            
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

            await route_to_boards(message, name_text, user_id, level, iv_val, chain_val, is_shiny, is_gmax, is_regional, is_rare, sprite_url)
        except Exception as e:
            print(f"[STARBOARD SCAN ERROR] {e}")

async def route_to_boards(orig_msg, name, user_id, level, iv, chain, is_shiny, is_gmax, is_regional, is_rare, sprite_url):
    jump_url = orig_msg.jump_url
    guild = orig_msg.guild
    
    if iv < 10.0 and starboard_channels["low_iv"]:
        ch = guild.get_channel(starboard_channels["low_iv"])
        if ch: await ch.send(embed=create_starboard_embed("Low IV Catch Detected", "📉", name, user_id, level, iv, chain, discord.Color.from_rgb(100, 150, 255), sprite_url), view=JumpButtonView(jump_url))

    if iv >= 90.0 and starboard_channels["high_iv"]:
        ch = guild.get_channel(starboard_channels["high_iv"])
        if ch: await ch.send(embed=create_starboard_embed("High IV Catch Detected", "📈", name, user_id, level, iv, chain, discord.Color.from_rgb(100, 220, 100), sprite_url), view=JumpButtonView(jump_url))

    if is_gmax and starboard_channels["gmax"]:
        ch = guild.get_channel(starboard_channels["gmax"])
        if ch: await ch.send(embed=create_starboard_embed("Gmax Catch Detected", "⚔️", name, user_id, level, iv, chain, discord.Color.from_rgb(255, 100, 180), sprite_url), view=JumpButtonView(jump_url))

    if is_shiny and starboard_channels["shiny"]:
        ch = guild.get_channel(starboard_channels["shiny"])
        if ch: await ch.send(embed=create_starboard_embed("Shiny Catch Detected", "✨", name, user_id, level, iv, chain, discord.Color.from_rgb(255, 215, 0), sprite_url), view=JumpButtonView(jump_url))

    if is_regional and starboard_channels["regional"]:
        ch = guild.get_channel(starboard_channels["regional"])
        if ch: await ch.send(embed=create_starboard_embed("Regional Catch Detected", "🌍", name, user_id, level, iv, chain, discord.Color.from_rgb(50, 180, 180), sprite_url), view=JumpButtonView(jump_url))

    if is_rare and starboard_channels["rare"]:
        ch = guild.get_channel(starboard_channels["rare"])
        if ch: await ch.send(embed=create_starboard_embed("Rare Catch Detected", "⭐", name, user_id, level, iv, chain, discord.Color.from_rgb(255, 140, 0), sprite_url), view=JumpButtonView(jump_url))
