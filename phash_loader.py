import os
import requests

os.makedirs("pokemon_sprites", exist_ok=True)

print("🔄 Downloading Pokémon sprites (this may take a minute)...")

# Let's download up to the first 898 Pokémon (covers all main regions up to Gen 8)
for dex_id in range(1, 899):
    # Fetch data from PokéAPI to get the official name
    url = f"https://pokeapi.co/api/v2/pokemon/{dex_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        name = data["name"].capitalize()
        # Get official artwork or front default sprite URL
        sprite_url = data["sprites"]["other"]["official-artwork"]["front_default"]
        
        if not sprite_url:
            sprite_url = data["sprites"]["front_default"]
            
        if sprite_url:
            img_data = requests.get(sprite_url).content
            file_path = f"pokemon_sprites/{name}.png"
            with open(file_path, "wb") as handler:
                handler.write(img_data)
            print(f"[{dex_id}/898] Downloaded: {name}")

print("✅ All sprites downloaded successfully into 'pokemon_sprites/' folder!")
