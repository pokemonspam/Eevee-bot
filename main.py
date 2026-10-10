import os
import json
import discord
import requests
import imagehash
import re
from PIL import Image
from io import BytesIO
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=["a!", "A!"], intents=intents, help_command=None, case_insensitive=True)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"
RAW_FORMS_SCHEMA = [
    "bulbasaur", "ivysaur", "venusaur", "charmander", "charmeleon", "charizard", "squirtle", "wartortle", "blastoise",
    "caterpie", "metapod", "butterfree", "weedle", "kakuna", "beedrill", "pidgey", "pidgeotto", "pidgeot", "rattata",
    "raticate", "spearow", "fearow", "ekans", "arbok", "pikachu", "raichu", "sandshrew", "sandslash", "nidoran-f",
    "nidorina", "nidoqueen", "nidoran-m", "nidorino", "nidoking", "clefairy", "clefable", "vulpix", "ninetales",
    "jigglypuff", "wigglytuff", "zubat", "golbat", "oddish", "gloom", "vileplume", "paras", "parasect", "venonat",
    "venomoth", "diglett", "dugtrio", "meowth", "persian", "psyduck", "golduck", "mankey", "primeape", "growlithe",
    "arcanine", "poliwag", "poliwhirl", "poliwrath", "abra", "kadabra", "alakazam", "machop", "machoke", "machamp",
    "bellsprout", "weepinbell", "victreebel", "tentacool", "tentacruel", "geodude", "graveler", "golem", "ponyta",
    "rapidash", "slowpoke", "slowbro", "magnemite", "magneton", "farfetchd", "doduo", "dodrio", "seel", "dewgong",
    "grimer", "muk", "shellder", "cloyster", "gastly", "haunter", "gengar", "onix", "drowzee", "hypno", "krabby",
    "kingler", "voltorb", "electrode", "exeggcute", "exeggutor", "cubone", "marowak", "hitmonlee", "hitmonchan",
    "lickitung", "koffing", "weezing", "rhyhorn", "rhydon", "chansey", "tangela", "kangaskhan", "horsea", "seadra",
    "goldeen", "seaking", "staryu", "starmie", "mr-mime", "scyther", "jynx", "electabuzz", "magmar", "pinsir",
    "tauros", "magikarp", "gyarados", "lapras", "ditto", "eevee", "vaporeon", "jolteon", "flareon", "porygon",
    "omanyte", "omastar", "kabuto", "kabutops", "aerodactyl", "snorlax", "articuno", "zapdos", "moltres", "dratini",
    "dragonair", "dragonite", "mewtwo", "mew", "chikorita", "bayleef", "meganium", "cyndaquil", "quilava", "typhlosion"
]
RAW_FORMS_SCHEMA += [
    "totodile", "croconaw", "feraligatr", "sentret", "furret", "hoothoot", "noctowl", "ledyba", "ledian", "spinarak",
    "ariados", "crobat", "chinchou", "lanturn", "pichu", "cleffa", "igglybuff", "togepi", "togetic", "natu", "xatu",
    "mareep", "flaaffy", "ampharos", "bellossom", "marill", "azumarill", "sudowoodo", "politoed", "hoppip", "skiploom",
    "jumpluff", "aipom", "sunkern", "sunflora", "yanma", "wooper", "quagsire", "espeon", "umbreon", "murkrow",
    "slowking", "misdreavus", "unown", "wobbuffet", "girafarig", "pineco", "forretress", "dunsparce", "gligar",
    "steelix", "snubbull", "granbull", "qwilfish", "scizor", "shuckle", "heracross", "sneasel", "teddiursa", "ursaring",
    "slugma", "magcargo", "swinub", "piloswine", "corsola", "remoraid", "octillery", "delibird", "mantine", "skarmory",
    "houndour", "houndoom", "kingdra", "phanpy", "donphan", "porygon2", "stantler", "smeargle", "tyrogue", "hitmontop",
    "smoochum", "elekid", "magby", "miltank", "blissey", "raikou", "entei", "suicune", "larvitar", "pupitar", "tyranitar",
    "lugia", "ho-oh", "celebi", "treecko", "grovyle", "sceptile", "torchic", "combusken", "blaziken", "mudkip",
    "marshtomp", "swampert", "poochyena", "mightyena", "zigzagoon", "linoone", "wurmple", "silcoon", "beautifly",
    "cascoon", "dustox", "lotad", "lombre", "ludicolo", "seedot", "nuzleaf", "shiftry", "taillow", "swellow", "wingull"
]
RAW_FORMS_SCHEMA += [
    "pelipper", "ralts", "kirlia", "gardevoir", "gallade", "surskit", "masquerain", "shroomish", "breloom", "slakoth",
    "vigoroth", "slaking", "nincada", "ninjask", "shedinja", "whismur", "loudred", "exploud", "makuhita", "hariyama",
    "azurill", "nosepass", "skitty", "delcatty", "sableye", "mawile", "aron", "lairon", "aggron", "meditite", "medicham",
    "electrike", "manectric", "plusle", "minun", "volbeat", "illumise", "roselia", "gulpin", "swalot", "carvanha",
    "sharpedo", "wailmer", "wailord", "numel", "camerupt", "torkoal", "spoink", "grumpig", "spinda", "trapinch",
    "vibrava", "flygon", "cacnea", "cacturne", "swablu", "altaria", "zangoose", "seviper", "lunatone", "solrock",
    "barboach", "whiscash", "corphish", "crawdaunt", "baltoy", "claydol", "lileep", "cradily", "anorith", "armaldo",
    "feebas", "milotic", "castform", "kecleon", "shuppet", "banette", "duskull", "dusclops", "dusknoir", "tropius",
    "chimecho", "absol", "wynaut", "snorunt", "glalie", "spheal", "sealeo", "walrein", "clamperl", "huntail",
    "gorebyss", "relicanth", "luvdisc", "bagon", "shelgon", "salamence", "beldum", "metang", "metagross", "regirock",
    "regice", "registeel", "latias", "latios", "kyogre", "groudon", "rayquaza", "jirachi", "deoxys-normal", "turtwig"
]
RAW_FORMS_SCHEMA += [
    "grotle", "torterra", "chimchar", "monferno", "infernape", "piplup", "prinplup", "empoleon", "starly", "staravia",
    "staraptor", "bidoof", "bibarel", "kricketot", "kricketune", "shinx", "luxio", "luxray", "budew", "roserade",
    "cranidos", "rampardos", "shieldon", "bastiodon", "burmy", "wormadam-plant", "mothim", "combee", "vespiquen",
    "pachirisu", "buizel", "floatzel", "cherubi", "cherrim", "shellos", "gastrodon", "ambipom", "drifloon", "drifblim",
    "buneary", "lopunny", "mismagius", "honchkrow", "glameow", "purugly", "chingling", "stunky", "skuntank", "bronzor",
    "bronzong", "bonsly", "mime-jr", "happiny", "chatot", "spiritomb", "gible", "gabite", "garchomp", "munchlax",
    "riolu", "lucario", "hippopotas", "hippowdon", "skorupi", "drapion", "croagunk", "toxicroak", "carnivine", "finneon",
    "lumineon", "mantyke", "snover", "abomasnow", "weavile", "magnezone", "lickilicky", "rhyperior", "tangrowth",
    "electivire", "magmortar", "togekiss", "yanmega", "leafeon", "glaceon", "gliscor", "mamoswine", "porygon-z",
    "probopass", "froslass", "rotom", "uxie", "mesprit", "azelf", "dialga", "palkia", "heatran", "regigigas",
    "giratina-altered", "cresselia", "phione", "manaphy", "darkrai", "shaymin-land", "arceus", "victini", "snivy"
]
RAW_FORMS_SCHEMA += [
    "servine", "serperior", "tepig", "pignite", "emboar", "oshawott", "dewott", "samurott", "patrat", "watchog",
    "lillipup", "herdier", "stoutland", "purrloin", "liepard", "pansage", "simisage", "pansear", "simisear", "panpour",
    "simipour", "munna", "musharna", "pidove", "tranquill", "unfezant", "blitzle", "zebstrika", "roggenrola", "boldore",
    "gigalith", "woobat", "swoobat", "drilbur", "excadrill", "audino", "timburr", "gurdurr", "conkeldurr", "tympole",
    "palpitoad", "seismitoad", "throh", "sawk", "sewaddle", "swadloon", "leavanny", "venipede", "whirlipede",
    "scolipede", "cottonee", "whimsicott", "petilil", "lilligant", "basculin-red-striped", "sandile", "krokorok",
    "krookodile", "darumaka", "darmanitan-standard", "maractus", "dwebble", "crustle", "scraggy", "scrafty", "sigilyph",
    "yamask", "cofagrigus", "tirtouga", "carracosta", "archen", "archeops", "trubbish", "garbodor", "zorua", "zoroark",
    "minccino", "cinccino", "gothita", "gothorita", "gothitelle", "solosis", "duosion", "reuniclus", "ducklett", "swanna",
    "vanillite", "vanillish", "vanilluxe", "deerling", "sawsbuck", "emolga", "karrablast", "escavalier", "foongus"
]
RAW_FORMS_SCHEMA += [
    "amoonguss", "frillish-male", "jellicent-male", "alomomola", "joltik", "galvantula", "ferroseed", "ferrothorn",
    "klink", "klang", "klinklang", "tynamo", "eelektrik", "eelektross", "elgyem", "beheeyem", "litwick", "lampent",
    "chandelure", "axew", "fraxure", "haxorus", "cubchoo", "beartic", "cryogonal", "shelmet", "accelgor", "stunfisk",
    "mienfoo", "mienshao", "druddigon", "golett", "golurk", "pawniard", "bisharp", "bouffalant", "rufflet", "braviary",
    "vullaby", "mandibuzz", "heatmor", "durant", "deino", "zweilous", "hydreigon", "larvesta", "volcarona", "cobalion",
    "terrakion", "virizion", "tornadus-incarnate", "thundurus-incarnate", "reshiram", "zekrom", "landorus-incarnate",
    "kyurem", "keldeo-ordinary", "meloetta-aria", "genesect", "chespin", "quilladin", "chesnaught", "fennekin",
    "braixen", "delphox", "froakie", "frogadier", "greninja", "bunnelby", "diggersby", "fletchling", "fletchinder",
    "talonflame", "scatterbug", "spewpa", "vivillon", "litleo", "pyroar-male", "flabebe", "floette", "florges", "skiddo",
    "gogoat", "pancham", "pangoro", "furfrou", "espurr", "meowstic-male", "honedge", "doublade", "aegislash-shield"
]
RAW_FORMS_SCHEMA += [
    "spritzee", "aromatisse", "swirlix", "slurpuff", "inkay", "malamar", "binacle", "barbaracle", "skrelp", "dragalge",
    "clauncher", "clawitzer", "helioptile", "heliolisk", "tyrunt", "tyrantrum", "amaura", "aurorus", "sylveon",
    "hawlucha", "dedenne", "carbink", "goomy", "sliggoo", "goodra", "klefki", "phantump", "trevenant", "pumpkaboo-average",
    "gourgeist-average", "bergmite", "avalugg", "noibat", "noivern", "xerneas", "yveltal", "zygarde-50", "diancie",
    "hoopa", "volcanion", "rowlet", "dartrix", "decidueye", "litten", "torracat", "incineroar", "popplio", "brionne",
    "primarina", "pikipek", "trumbeak", "toucannon", "yungoos", "gumshoos", "grubbin", "charjabug", "vikavolt",
    "crabrawler", "crabominable", "oricorio-baile", "cutiefly", "ribombee", "rockruff", "lycanroc-midday", "wishiwashi-solo",
    "mareanie", "toxapex", "mudbray", "mudsdale", "dewpider", "araquanid", "fomantis", "lurantis", "morelull",
    "shiinotic", "salandit", "salazzle", "stufful", "bewear", "bounsweet", "steenee", "tsareena", "comfey", "oranguru",
    "passimian", "wimpod", "golisopod", "sandygast", "palossand", "pyukumuku", "type-null", "silvally", "minior-red-meteor",
    "komala", "turtonator", "togedemaru", "mimikyu-disguised", "bruxish", "drampa", "dhelmise", "jangmo-o", "hakamo-o"
]
RAW_FORMS_SCHEMA += [
    "kommo-o", "tapu-koko", "tapu-lele", "tapu-bulu", "tapu-fini", "cosmog", "cosmoem", "solgaleo", "lunala", "nihilego",
    "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord", "necrozma", "magearna", "marshadow",
    "poipole", "naganadel", "stakataka", "blacephalon", "zeraora", "meltan", "melmetal", "grookey", "thwackey",
    "rillaboom", "scorbunny", "raboot", "cinderace", "sobble", "drizzile", "inteleon", "skwovet", "greedent", "rookidee",
    "corvisquire", "corviknight", "blipbug", "dottler", "orbeetle", "nickit", "thievul", "gossifleur", "eldegoss",
    "wooloo", "dubwool", "chewtle", "drednaw", "yamper", "boltund", "rolycoly", "carkol", "coalossal", "applin",
    "flapple", "appletun", "silicobra", "sandaconda", "cramorant", "arrokuda", "barraskewda", "toxel", "toxtricity-amped",
    "sizzlipede", "centiskorch", "clobbopus", "grapploct", "sinistea", "polteageist", "hatenna", "hattrem", "hatterene",
    "impidimp", "morgrem", "grimmsnarl", "obstagoon", "perrserker", "cursola", "sirfetchd", "mr-rime", "runerigus",
    "milcery", "alcremie", "falinks", "pincurchin", "snom", "frosmoth", "stonjourner", "eiscue-ice", "indeedee-male",
    "morpeko-full-belly", "cufant", "copperajah", "dracozolt", "arctozolt", "dracovish", "arctovish", "duraludon"
]
RAW_FORMS_SCHEMA += [
    "dreepy", "drakloak", "dragapult", "zacian", "zamazenta", "eternatus", "kubfu", "urshifu-single-strike", "zarude",
    "regieleki", "regidrago", "glastrier", "spectrier", "calyrex", "wyrdeer", "kleavor", "ursaluna", "basculegion-male",
    "sneasler", "overqwil", "enamorus-incarnate", "sprigatito", "floragato", "meowscarada", "fuecoco", "crocalor",
    "skeledirge", "quaxly", "quaxwell", "quaquaval", "lechonk", "oinkologne-male", "tarountula", "spidops", "nymble",
    "lokix", "pawmi", "pawmo", "pawmot", "tandemaus", "maushold-family-of-four", "fidough", "dachsbun", "smoliv",
    "dolliv", "arboliva", "squawkabilly-green-plumage", "nacli", "naclstack", "garganacl", "charcadet", "armarouge",
    "ceruledge", "tadbulb", "bellibolt", "wattrel", "kilowattrel", "maschiff", "mabosstiff", "shroodle", "grafaiai",
    "bramblin", "brambleghast", "toedscool", "toedscruel", "klawf", "capsakid", "scovillain", "rellor", "rabsca",
    "flittle", "espathra", "tinkatink", "tinkatuff", "tinkaton", "wiglett", "wugtrio", "bombirdier", "finizen",
    "palafin-zero", "varoom", "revavroom", "cyclizar", "orthworm", "glimmet", "glimmora", "greavard", "houndstone",
    "flamigo", "cetoddle", "cetitan", "veluza", "dondozo", "tatsugiri-curly", "annihilape", "clodsire", "farigiraf",
    "dudunsparce-two-segment", "kingambit", "great-tusk", "scream-tail", "brute-bonnet", "flutter-mane", "slither-wing",
    "sandy-shocks", "iron-treads", "iron-bundle", "iron-hands", "iron-jugulis", "iron-moth", "iron-thorns", "frigibax",
    "arctibax", "baxcalibur", "gimmighoul", "gholdengo", "wo-chien", "chien-pao", "ting-lu", "chi-yu", "roaring-moon",
    "iron-valiant", "koraidon", "miraidon", "walking-wake", "iron-leaves", "dipplin", "poltchageist", "sinistcha",
    "okidogi", "munkidori", "fezandipiti", "ogerpon", "archaludon", "hydrapple", "gouging-fire", "raging-bolt",
    "iron-boulder", "iron-crown", "terapagos", "pecharunt"
]
RAW_FORMS_SCHEMA += [
    "deoxys-attack", "deoxys-defense", "deoxys-speed", "wormadam-sandy", "wormadam-trash", "shaymin-sky",
    "giratina-origin", "rotom-heat", "rotom-wash", "rotom-frost", "rotom-fan", "rotom-mow", "castform-sunny",
    "castform-rainy", "castform-snowy", "basculin-blue-striped", "darmanitan-zen", "meloetta-pirouette",
    "tornadus-therian", "thundurus-therian", "landorus-therian", "kyurem-black", "kyurem-white", "keldeo-resolute",
    "meowstic-female", "aegislash-blade", "pumpkaboo-small", "pumpkaboo-large", "pumpkaboo-super", "gourgeist-small",
    "gourgeist-large", "gourgeist-super", "venusaur-mega", "charizard-mega-x", "charizard-mega-y", "blastoise-mega",
    "alakazam-mega", "gengar-mega", "kangaskhan-mega", "pinsir-mega", "gyarados-mega", "aerodactyl-mega",
    "mewtwo-mega-x", "mewtwo-mega-y", "ampharos-mega", "scizor-mega", "heracross-mega", "houndoom-mega",
    "tyranitar-mega", "blaziken-mega", "gardevoir-mega", "mawile-mega", "aggron-mega", "medicham-mega",
    "manectric-mega", "banette-mega", "absol-mega", "garchomp-mega", "lucario-mega", "abomasnow-mega",
    "floette-eternal", "latias-mega", "latios-mega", "swampert-mega", "sceptile-mega", "sableye-mega",
    "altaria-mega", "gallade-mega", "audino-mega", "sharpedo-mega", "slowbro-mega", "steelix-mega",
    "pidgeot-mega", "glalie-mega", "diancie-mega", "metagross-mega", "kyogre-primal", "groudon-primal",
    "rayquaza-mega", "pikachu-rock-star", "pikachu-belle", "pikachu-pop-star", "pikachu-phd", "pikachu-libre",
    "pikachu-cosplay", "hoopa-unbound", "camerupt-mega", "lopunny-mega", "salamence-mega", "beedrill-mega",
    "rattata-alola", "raticate-alola", "raticate-totem-alola", "pikachu-original-cap", "pikachu-hoenn-cap",
    "pikachu-sinnoh-cap", "pikachu-unova-cap", "pikachu-kalos-cap", "pikachu-alola-cap", "raichu-alola",
    "sandshrew-alola", "sandslash-alola", "vulpix-alola", "ninetales-alola", "diglett-alola", "dugtrio-alola",
    "meowth-alola", "persian-alola", "geodude-alola", "graveler-alola", "golem-alola", "grimer-alola",
    "muk-alola", "exeggutor-alola", "marowak-alola", "greninja-battle-bond", "greninja-ash",
    "zygarde-10-power-construct", "zygarde-50-power-construct", "zygarde-complete", "gumshoos-totem",
    "vikavolt-totem", "oricorio-pom-pom", "oricorio-pau", "oricorio-sensu", "lycanroc-midnight",
    "wishiwashi-school", "lurantis-totem", "salazzle-totem", "minior-orange-meteor", "minior-yellow-meteor",
    "minior-green-meteor", "minior-blue-meteor", "minior-indigo-meteor", "minior-violet-meteor", "minior-red",
    "minior-orange", "minior-yellow", "minior-green", "minior-blue", "minior-indigo", "minior-violet",
    "mimikyu-busted", "mimikyu-totem-disguised", "mimikyu-totem-busted", "kommo-o-totem", "magearna-original",
    "pikachu-partner-cap", "marowak-totem", "ribombee-totem", "rockruff-own-tempo", "lycanroc-dusk",
    "araquanid-totem", "togedemaru-totem", "necrozma-dusk", "necrozma-dawn", "necrozma-ultra", "pikachu-starter",
    "eevee-starter", "pikachu-world-cap", "meowth-galar", "ponyta-galar", "rapidash-galar", "slowpoke-galar",
    "slowbro-galar", "farfetchd-galar", "weezing-galar", "mr-mime-galar", "articuno-galar", "zapdos-galar",
    "moltres-galar", "slowking-galar", "corsola-galar", "zigzagoon-galar", "linoone-galar", "darumaka-galar",
    "darmanitan-galar-standard", "darmanitan-galar-zen", "yamask-galar", "stunfisk-galar", "zygarde-10",
    "cramorant-gulping", "cramorant-gorging", "toxtricity-low-key", "eiscue-noice", "indeedee-female",
    "morpeko-hangry", "zacian-crowned", "zamazenta-crowned", "eternatus-eternamax", "urshifu-rapid-strike",
    "zarude-dada", "calyrex-ice", "calyrex-shadow", "venusaur-gmax", "charizard-gmax", "blastoise-gmax",
    "butterfree-gmax", "pikachu-gmax", "meowth-gmax", "machamp-gmax", "gengar-gmax", "kingler-gmax",
    "lapras-gmax", "eevee-gmax", "snorlax-gmax", "garbodor-gmax", "melmetal-gmax", "rillaboom-gmax",
    "cinderace-gmax", "inteleon-gmax", "corviknight-gmax", "orbeetle-gmax", "drednaw-gmax", "coalossal-gmax",
    "flapple-gmax", "appletun-gmax", "sandaconda-gmax", "toxtricity-amped-gmax", "centiskorch-gmax",
    "hatterene-gmax", "grimmsnarl-gmax", "alcremie-gmax", "copperajah-gmax", "duraludon-gmax",
    "urshifu-single-strike-gmax", "urshifu-rapid-strike-gmax", "toxtricity-low-key-gmax", "growlithe-hisui",
    "arcanine-hisui", "voltorb-hisui", "electrode-hisui", "typhlosion-hisui", "qwilfish-hisui", "sneasel-hisui",
    "samurott-hisui", "lilligant-hisui", "zorua-hisui", "zoroark-hisui", "braviary-hisui", "sliggoo-hisui",
    "goodra-hisui", "avalugg-hisui", "decidueye-hisui", "dialga-origin", "palkia-origin", "basculin-white-striped",
    "basculegion-female", "enamorus-therian", "tauros-paldea-combat-breed", "tauros-paldea-blaze-breed",
    "tauros-paldea-aqua-breed", "wooper-paldea", "oinkologne-female", "dudunsparce-three-segment", "palafin-hero",
    "maushold-family-of-three", "tatsugiri-droopy", "tatsugiri-stretchy", "squawkabilly-blue-plumage",
    "squawkabilly-yellow-plumage", "squawkabilly-white-plumage", "gimmighoul-roaming", "koraidon-limited-build",
    "koraidon-sprinting-build", "koraidon-swimming-build", "koraidon-gliding-build", "miraidon-low-power-mode",
    "miraidon-drive-mode", "miraidon-aquatic-mode", "miraidon-glide-mode", "ursaluna-bloodmoon",
    "ogerpon-wellspring-mask", "ogerpon-hearthflame-mask", "ogerpon-cornerstone-mask", "terapagos-terastal",
    "terapagos-stellar", "clefable-mega", "victreebel-mega", "starmie-mega", "dragonite-mega", "meganium-mega",
    "feraligatr-mega", "skarmory-mega", "froslass-mega", "emboar-mega", "excadrill-mega", "scolipede-mega",
    "scrafty-mega", "eelektross-mega", "chandelure-mega", "chesnaught-mega", "delphox-mega", "greninja-mega",
    "pyroar-mega", "floette-mega", "malamar-mega", "barbaracle-mega", "dragalge-mega", "hawlucha-mega",
    "zygarde-mega", "drampa-mega", "falinks-mega", "raichu-mega-x", "raichu-mega-y", "chimecho-mega",
    "absol-mega-z", "staraptor-mega", "garchomp-mega-z", "lucario-mega-z", "heatran-mega", "darkrai-mega",
    "golurk-mega", "meowstic-male-mega", "crabominable-mega", "golisopod-mega", "magearna-mega",
    "magearna-original-mega", "zeraora-mega", "scovillain-mega", "glimmora-mega", "tatsugiri-curly-mega",
    "tatsugiri-droopy-mega", "tatsugiri-stretchy-mega", "baxcalibur-mega", "meowstic-female-mega"
]

VALID_POKEMON_NAMES = []
for entry in RAW_FORMS_SCHEMA:
    if "morpeko" in entry.lower():
        VALID_POKEMON_NAMES.append("Morpeko")
        continue
    words = entry.split("-")
    if len(words) > 1 and words[-1] in ["alola", "galar", "hisui", "paldea", "attack", "defense", "speed", "origin", "therian", "crowned"]:
        suffix = words[-1]
        suffix_map = {
            "alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian", "paldea": "Paldean",
            "attack": "Attack", "defense": "Defense", "speed": "Speed", "origin": "Origin",
            "therian": "Therian", "crowned": "Crowned"
        }
        base_title = " ".join([w.capitalize() for w in words[:-1]])
        suffix_title = suffix_map[suffix]
        VALID_POKEMON_NAMES.append(f"{suffix_title} {base_title}")
        VALID_POKEMON_NAMES.append(f"{base_title} {suffix_title}")
        VALID_POKEMON_NAMES.append(f"Normal {base_title}")
    else:
        base_name = " ".join([w.capitalize() for w in words])
        VALID_POKEMON_NAMES.append(base_name)
        VALID_POKEMON_NAMES.append(f"Normal {base_name}")
class GlobalDatabase:
    user_collections = {}
    shiny_hunts = {}
    reserve_data = {}

try:
    if os.path.exists(COLLECTION_FILE):
        with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
            db_data = json.load(f)
            GlobalDatabase.user_collections = db_data.get("collection", {})
            GlobalDatabase.shiny_hunts = db_data.get("shiny", {})
            GlobalDatabase.reserve_data = db_data.get("reserve_data", {})
except Exception as e:
    print(f"[CRITICAL] Storage Initialization Error: {e}")

def save_data():
    try:
        temp_file = COLLECTION_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({
                "collection": GlobalDatabase.user_collections, 
                "shiny": GlobalDatabase.shiny_hunts, 
                "reserve_data": GlobalDatabase.reserve_data
            }, f, indent=4)
        os.replace(temp_file, COLLECTION_FILE)
    except Exception as e: 
        print(f"[ERROR] Failed to save database layer: {e}")

def strict_pokemon_check(input_name):
    clean_search = " ".join(input_name.strip().lower().replace("-", " ").replace("é", "e").replace("♀", " f").replace("♂", " m").split())
    for official_name in VALID_POKEMON_NAMES:
        off_clean = official_name.lower().replace("é", "e").replace("♀", " f").replace("♂", " m")
        if off_clean == clean_search: 
            return True, official_name
    words = clean_search.split()
    if len(words) > 1:
        flipped = f"{words[-1]} " + " ".join(words[:-1])
        for official_name in VALID_POKEMON_NAMES:
            off_clean = official_name.lower().replace("é", "e")
            if off_clean == flipped:
                return True, official_name
    return False, None

def get_all_variant_forms(base_pokemon_name):
    clean_base = base_pokemon_name.strip().lower()
    discovered_variants = []
    for official_name in VALID_POKEMON_NAMES:
        off_lower = official_name.lower()
        if clean_base in off_lower or off_lower.endswith(f" {clean_base}"):
            if off_lower.startswith("mega ") or off_lower.endswith(" gmax") or " mega " in off_lower:
                continue
            discovered_variants.append(official_name)
    return list(set(discovered_variants))
class DynamicListPaginator(discord.ui.View):
    def __init__(self, data_list, card_title, chunk_size=20):
        super().__init__(timeout=180)
        self.data_list = data_list
        self.card_title = card_title
        self.chunk_size = chunk_size
        self.current_page = 0
        self.total_pages = max(1, (len(data_list) - 1) // chunk_size + 1)

    def get_page_embed(self):
        start = self.current_page * self.chunk_size
        end = start + self.chunk_size
        chunk = self.data_list[start:end]
        embed = discord.Embed(title=f"{self.card_title} ({len(self.data_list)} Total)", color=discord.Color.red())
        embed.description = "\n".join(chunk)
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.grey)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else: 
            await interaction.response.defer()

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.grey)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else: 
            await interaction.response.defer()

@bot.event
async def on_ready():
    global pokemon_db; bot_user = bot.user if bot.user else "Eevee Bot"
    print("==========================================")
    print(f"STATUS: Successfully verified connection with Discord servers!")
    print(f"IDENTITY: Active as {bot_user}")
    print("==========================================")
    try:
        response = requests.get(ONLINE_DB_URL, timeout=15)
        if response.status_code == 200: pokemon_db = response.json()
    except Exception as e: print(f"[CRITICAL] Network cloud stream broken: {e}")

@bot.command(name="tags")
async def tags_command(ctx, *, search_name: str = None):
    try:
        if not search_name: return await ctx.send("⚠️ Format: `a!tags <pokemon_name>`")
        is_valid, matched_name = strict_pokemon_check(search_name)
        if not is_valid: return await ctx.send(f"❌ **{search_name}** is not a real Pokémon or form variant!")
        active_hunters = []
        for uid, hunts in GlobalDatabase.shiny_hunts.items():
            if hunts and matched_name in hunts: active_hunters.append(f"• <@{uid}>")
        if not active_hunters: return await ctx.send(f"📋 No active shiny hunters found tracking **{matched_name}** right now.")
        embed = discord.Embed(title=f"📋 Shiny Hunters tracking {matched_name}", color=discord.Color.red())
        embed.description = "\n".join(active_hunters); embed.set_footer(text="Eevee Tracker Framework")
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(f"❌ Error handling command: {e}")
@bot.command(name="cl", aliases=["A!cl"])
async def cl_base_router(ctx, subcommand: str = None, *, arguments: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="📋 Collection List Commands", description="`a!cl add <names>` • Add Pokémon (Separate entries with commas)\n`a!cl remove <name>` • Remove an entry\n`a!cl list` • View your list embed (20 entries per page)\n`a!cl clear` • Wipe list clean", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        uid = str(ctx.author.id)
        
        if sub_clean == "add":
            if not arguments: return await ctx.send("⚠️ Please specify at least one Pokémon! Example: `a!cl add Pikachu, Eevee`")
            if uid not in GlobalDatabase.user_collections: GlobalDatabase.user_collections[uid] = []
            
            if arguments.lower().startswith("all "):
                target_base = arguments[4:].strip()
                all_forms = get_all_variant_forms(target_base)
                if not all_forms: return await ctx.send(f"❌ No valid variants found matching **{target_base}** inside the database.")
                bulk_added = []
                for form in all_forms:
                    if form not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(form); bulk_added.append(form)
                if bulk_added: save_data()
                return await ctx.send(f"✅ Added **{len(bulk_added)}** Pokémon to your collections for this server!")

            parts = [p.strip() for p in arguments.split(",") if p.strip()]
            added, duplicate, broken = [], [], []
            for raw in parts:
                if raw.lower().startswith("all "):
                    target_base = raw[4:].strip()
                    all_forms = get_all_variant_forms(target_base)
                    for form in all_forms:
                        if form not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(form); added.append(form)
                    continue
                is_valid, matched_name = strict_pokemon_check(raw)
                if is_valid:
                    chk_lower = matched_name.lower()
                    if chk_lower.startswith("mega ") or chk_lower.endswith(" gmax") or " mega " in chk_lower:
                        broken.append(f"{matched_name} (Uncatchable Form)")
                        continue
                    if matched_name not in GlobalDatabase.user_collections[uid]: GlobalDatabase.user_collections[uid].append(matched_name); added.append(matched_name)
                    else: duplicate.append(matched_name)
                else: broken.append(raw)
            if added or duplicate or broken: save_data()
            res = ""
            if added: res += f"✅ Added: **{', '.join(added)}**\n"
            if duplicate: res += f"⚠️ Already tracked: **{', '.join(duplicate)}**\n"
            if broken: res += f"❌ **{', '.join(broken)}** is invalid or a non-catchable form! Blocked.\n"
            await ctx.send(res)
            
        elif sub_clean in ["remove", "del"]:
            if not arguments: return await ctx.send("⚠️ Please specify a Pokémon to drop!")
            is_valid, matched_name = strict_pokemon_check(arguments)
            if is_valid and uid in GlobalDatabase.user_collections and matched_name in GlobalDatabase.user_collections[uid]:
                GlobalDatabase.user_collections[uid].remove(matched_name); save_data()
                await ctx.send(f"❌ **{matched_name}** has been removed.")
            else: await ctx.send(f"⚠️ Target Pokémon was not found inside your list.")
            
        elif sub_clean in ["list", "view"]:
            if uid in GlobalDatabase.user_collections and GlobalDatabase.user_collections[uid]:
                formatted_wishlist = [f"• # **{n}**" for n in sorted(GlobalDatabase.user_collections[uid])]
                paginator = DynamicListPaginator(data_list=formatted_wishlist, card_title=f"📋 {ctx.author.name}'s Collection List")
                await ctx.send(embed=paginator.get_page_embed(), view=paginator)
            else: await ctx.send("📁 Your collection list is empty.")
            
        elif sub_clean == "clear":
            GlobalDatabase.user_collections[uid] = []; save_data(); await ctx.send("🗑 Wiped collection list clean.")
    except Exception as e: await ctx.send(f"❌ Error handling cl command: {e}")
@bot.command(name="sh", aliases=["A!sh"])
async def sh_base_router(ctx, subcommand: str = None, *, name_arg: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="✨ Shiny Hunt Commands", description="`a!sh add <name>` • Set active shiny target\n`a!sh remove <name>` • Drop shiny target\n`a!sh list` • View hunt\n`a!sh clear` • Wipe data", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        uid = str(ctx.author.id)
        
        if sub_clean == "add" or (sub_clean not in ["remove", "del", "list", "view", "clear"]):
            target = name_arg if (sub_clean == "add" and name_arg) else subcommand
            is_valid, matched_name = strict_pokemon_check(target)
            if not is_valid: return await ctx.send(f"❌ **{target}** is not a real Pokémon or valid form variant!")
            chk_lower = matched_name.lower()
            if chk_lower.startswith("mega ") or chk_lower.endswith(" gmax") or " mega " in chk_lower:
                return await ctx.send(f"❌ **{matched_name}** is uncatchable! You can't hunt this form.")
            GlobalDatabase.shiny_hunts[uid] = [matched_name]; save_data()
            await ctx.send(f"✨ **{matched_name}** has been registered as your active Shiny Hunt!")
            
        elif sub_clean in ["remove", "del"]:
            target = name_arg if name_arg else subcommand
            is_valid, matched_name = strict_pokemon_check(target)
            if is_valid and uid in GlobalDatabase.shiny_hunts and matched_name in GlobalDatabase.shiny_hunts[uid]:
                GlobalDatabase.shiny_hunts[uid].remove(matched_name); save_data()
                await ctx.send(f"❌ **{matched_name}** removed from your hunting profile.")
            else: await ctx.send("⚠️ Target was not active on your list.")
            
        elif sub_clean in ["list", "view"]:
            if uid in GlobalDatabase.shiny_hunts and GlobalDatabase.shiny_hunts[uid]:
                clean_names = ", ".join(GlobalDatabase.shiny_hunts[uid])
                await ctx.send(embed=discord.Embed(title=f"📋 {ctx.author.name}'s Active Shiny Hunt", description=f"• # **{clean_names}**", color=discord.Color.red()))
            else: await ctx.send("✨ You are not currently tracking any shiny hunts.")
            
        elif sub_clean == "clear":
            GlobalDatabase.shiny_hunts[uid] = []; save_data(); await ctx.send("✨🗑 Shiny hunt cleared.")
    except Exception as e: await ctx.send(f"❌ Error handling sh command: {e}")
@bot.command(name="r", aliases=["A!r"])
async def r_base_router(ctx, subcommand: str = None, *, args: str = None):
    try:
        if not subcommand:
            embed = discord.Embed(title="📦 Server Reserve Commands", description="`a!r add <names> @user` • Reserve Pokémon for a specific user (commas allowed)\n`a!r remove <names> @user` • Drop reserved targets from a user (commas allowed)\n`a!r remove @user` • Completely clear all active reserves for that user only\n`a!r @user` • View the reserved list for a specific person\n`a!r list` • View the entire server's reserve listings (20 entries per page)\n`a!r clear` • Wipe the absolute entire server reserve file data clean\n`a!r e @mainuser` • Reply to a list of trades to transfer them all from @mainuser", color=discord.Color.red())
            return await ctx.send(embed=embed)
            
        sub_clean = subcommand.lower().strip()
        if re.search(r'<@!?(\d+)>', subcommand):
            mention_match = re.search(r'<@!?(\d+)>', subcommand)
            tid = str(mention_match.group(1)); target_user = await bot.fetch_user(int(tid))
            u_list = GlobalDatabase.reserve_data.get(tid, [])
            if u_list:
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} ({len(u_list)})", description="\n".join([f"• # **{n}**" for n in sorted(u_list)]), color=discord.Color.red())
                return await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title=f"📋 Reserves for {target_user.name} (0)", description="📦 This user has no Pokémon reserved.", color=discord.Color.red())
                return await ctx.send(embed=embed)

        if sub_clean == "add":
            if not args: return await ctx.send("⚠️ Format: `a!r add Pikachu @user` or `a!r add all furfrou @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please mention a user to reserve the Pokémon for!")
            tid = str(mention_match.group(1)); raw_names = re.sub(r'<@!?\d+>', '', args).strip()
            if tid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[tid] = []
            
            if raw_names.lower().startswith("all "):
                target_base = raw_names[4:].strip()
                all_forms = get_all_variant_forms(target_base)
                if not all_forms: return await ctx.send(f"❌ No catchable variants found matching **{target_base}** inside the database.")
                bulk_added = []
                for form in all_forms:
                    if form not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(form); bulk_added.append(form)
                if bulk_added: save_data()
                return await ctx.send(f"📦 Added **{len(bulk_added)}** Pokémon to reserves for <@{tid}>!")

            parts = [p.strip() for p in raw_names.split(",") if p.strip()]
            added, duplicate, broken = [], [], []
            for raw in parts:
                if raw.lower().startswith("all "):
                    target_base = raw[4:].strip()
                    all_forms = get_all_variant_forms(target_base)
                    for form in all_forms:
                        if form not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(form); added.append(form)
                    continue
                is_valid, matched = strict_pokemon_check(raw)
                if is_valid:
                    chk_lower = matched.lower()
                    if chk_lower.startswith("mega ") or chk_lower.endswith(" gmax") or " mega " in chk_lower:
                        broken.append(f"{matched} (Uncatchable Form)")
                        continue
                    if matched not in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].append(matched); added.append(matched)
                    else: duplicate.append(matched)
                else: broken.append(raw)
            if added or duplicate or broken: save_data()
            res = ""
            if added: res += f"📦 Added to reserves for <@{tid}>: **{', '.join(added)}**\n"
            if duplicate: res += f"⚠️ Already reserved: **{', '.join(duplicate)}**\n"
            if broken: res += f"❌ **{', '.join(broken)}** is not a real Pokémon or form variant! Blocked.\n"
            await ctx.send(res)
            
        elif sub_clean in ["remove", "del"]:
            if not args: return await ctx.send("⚠️ Format: `a!r remove Pikachu @user` or `a!r remove @user`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please mention a user to remove reserves from!")
            tid = str(mention_match.group(1)); raw_input = re.sub(r'<@!?\d+>', '', args).strip()
            if not raw_input:
                if tid in GlobalDatabase.reserve_data and GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid] = []; save_data(); return await ctx.send(f"🗑️ Wiped all reserves for <@{tid}>!")
                else: return await ctx.send(f"⚠️ <@{tid}> has no active reserves.")
            parts = [p.strip() for p in raw_input.split(",") if p.strip()]
            removed, missing = [], []
            if tid in GlobalDatabase.reserve_data:
                for raw in parts:
                    is_valid, matched = strict_pokemon_check(raw)
                    if is_valid and matched in GlobalDatabase.reserve_data[tid]: GlobalDatabase.reserve_data[tid].remove(matched); removed.append(matched)
                    else: missing.append(raw)
            if removed: save_data()
            res = ""
            if removed: res += f"❌ Removed from <@{tid}>: **{', '.join(removed)}**\n"
            if missing: res += f"⚠️ Not found on their list: **{', '.join(missing)}**\n"
            await ctx.send(res)
        elif sub_clean in ["list", "view"]:
            pokemon_groups = {}
            for uid, arr in GlobalDatabase.reserve_data.items():
                for name in arr:
                    if name not in pokemon_groups: pokemon_groups[name] = []
                    pokemon_groups[name].append(f"<@{uid}>")
            if not pokemon_groups: return await ctx.send(embed=discord.Embed(title="📋 Server Reserves Manifest (0)", description="📦 No Pokémon are currently reserved on this server.", color=discord.Color.red()))
            formatted_entries = []
            for name in sorted(pokemon_groups.keys()):
                users_str = ", ".join(pokemon_groups[name])
                formatted_entries.append(f"• # **{name}** - {users_str}")
            paginator = DynamicListPaginator(data_list=formatted_entries, card_title="📋 Shared Server Reserve Manifest", chunk_size=20)
            await ctx.send(embed=paginator.get_page_embed(), view=paginator)
            
        elif sub_clean == "clear":
            GlobalDatabase.reserve_data.clear(); save_data(); await ctx.send("📦🗑 Server Reserve Database file wiped clean!")
            
        elif sub_clean == "e":
            if not args: return await ctx.send("⚠️ Example: `a!r e @mainuser`")
            mention_match = re.search(r'<@!?(\d+)>', args)
            if not mention_match: return await ctx.send("⚠️ Please specify the main user to exchange from!")
            mid = str(mention_match.group(1))
            if not ctx.message.reference: return await ctx.send("⚠️ You must **reply** directly to the target list message with this command!")
            try:
                replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id); lines = replied_msg.content.split("\n")
                if mid not in GlobalDatabase.reserve_data or not GlobalDatabase.reserve_data[mid]: return await ctx.send(f"❌ <@{mid}> has no active Pokémon reserved to exchange.")
                success_logs = []
                for line in lines:
                    if not line.strip() or "-" not in line: continue
                    left_part, right_part = line.split("-", 1); target_uid = None; uid_match = re.search(r'(\d+)', left_part)
                    if uid_match: target_uid = str(uid_match.group(1))
                    else:
                        clean_tag = left_part.replace('•', '').replace('#', '').replace('*', '').strip().lower()
                        for member in ctx.guild.members:
                            if clean_tag in member.name.lower() or (member.nick and clean_tag in member.nickname.lower()): target_uid = str(member.id); break
                    if target_uid:
                        clean_pokemon_block = right_part.replace('•', '').replace('#', '').replace('*', '').strip()
                        requested_names = [p.strip() for p in clean_pokemon_block.split(",") if p.strip()]
                        valid_transfers = []
                        for name in requested_names:
                            is_valid, matched_name = strict_pokemon_check(name)
                            if is_valid and matched_name in GlobalDatabase.reserve_data[mid]:
                                if target_uid not in GlobalDatabase.reserve_data: GlobalDatabase.reserve_data[target_uid] = []
                                if matched_name not in GlobalDatabase.reserve_data[target_uid]: GlobalDatabase.reserve_data[target_uid].append(matched_name)
                                valid_transfers.append(matched_name)
                        if valid_transfers:
                            for t_name in valid_transfers:
                                if t_name in GlobalDatabase.reserve_data[mid]: GlobalDatabase.reserve_data[mid].remove(t_name)
                            success_logs.append(f"• **{', '.join(valid_transfers)}** transferred from <@{mid}> to <@{target_uid}>")
                if success_logs: save_data(); await ctx.send(embed=discord.Embed(title="🔄 Reserve Exchange Ledger Summary", description="\n".join(success_logs), color=discord.Color.red()))
                else: await ctx.send("❌ Exchange failed! Make sure requested Pokémon are owned by the main user.")
            except Exception as e: print(f"Reserve exchange loop fault: {e}")
    except Exception as e: print(f"R Command fault: {e}")

@bot.listen("on_message")
async def poketwo_image_scanner(message):
    try:
        if message.author.bot and (message.author.name == "Pokétwo" or message.author.id == 716390085896962058) and message.embeds:
            for emb in message.embeds:
                if emb.image and emb.image.url:
                    url = emb.image.url; is_shiny = "shiny" in url.lower()
                    res = requests.get(url, timeout=10); img = Image.open(BytesIO(res.content)); hsh = imagehash.phash(img, hash_size=8)
                    match, low_dist = None, 999
                    for p_id, d in pokemon_db.items():
                        dist = hsh - imagehash.hex_to_hash(d["phash"])
                        if dist < low_dist: low_dist = dist; match = d["name"]
                    if low_dist <= 12 and match:
                        await message.channel.send(f"🚨 **Spawn Detected!** Pattern matches **{match}**!")
                        
                        matched_lower = match.lower()
                        reserve_pings = []
                        for uid, arr in GlobalDatabase.reserve_data.items():
                            for reserved_name in arr:
                                r_low = reserved_name.lower()
                                if r_low == matched_lower or r_low == f"normal {matched_lower}": reserve_pings.append(f"<@{uid}>")
                        if reserve_pings: 
                            await message.channel.send(f"🔔 **Reserve Match Alert!** " + " ".join(list(set(reserve_pings))) + " - Target reserved for you!")
                            return
                            
                        normal_pings = []
                        for uid, col in GlobalDatabase.user_collections.items():
                            for wish_name in col:
                                w_low = wish_name.lower()
                                if w_low == matched_lower or w_low == f"normal {matched_lower}": normal_pings.append(f"<@{uid}>")
                        if is_shiny:
                            for uid, sh in GlobalDatabase.shiny_hunts.items():
                                if sh:
                                    s_low = sh.lower()
                                    if s_low == matched_lower or s_low == f"normal {matched_lower}": normal_pings.append(f"<@{uid}> (✨ SHINY!)")
                        if normal_pings: await message.channel.send(f"🔔 **List Alert!** " + " ".join(list(set(normal_pings))))
    except Exception as e: print(f"[SCANNER FAULT] Safely handled: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
